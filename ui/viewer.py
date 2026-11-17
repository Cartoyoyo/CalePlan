"""Visionneuse de l'image / de la page : zoom molette, deplacement bouton du milieu
(ou glisser), clic gauche = poser un repere. Les reperes sont stockes en fraction (0..1)
de la largeur et de la hauteur, donc independants de la resolution du rendu."""
import numpy as np
from qgis.PyQt.QtCore import QPointF, QRectF, Qt, pyqtSignal
from qgis.PyQt.QtGui import QBrush, QColor, QFont, QImage, QPen, QPixmap, QPainter, QTransform
from qgis.PyQt.QtWidgets import (QGraphicsItem, QGraphicsItemGroup, QGraphicsPixmapItem,
                                 QGraphicsRectItem, QGraphicsScene, QGraphicsView)

DISPLAY_MAX = 6000          # cote maximum du pixmap affiche (l'image complete reste en memoire)
RED = QColor("#d62828")
ORANGE = QColor("#e08a00")


def array_to_qimage(arr):
    """Tableau (h, w, 3) RGB ou (h, w, 4) RGBA -> QImage (copie independante du tableau)."""
    h, w, c = arr.shape
    arr = np.ascontiguousarray(arr)
    fmt = QImage.Format.Format_RGBA8888 if c == 4 else QImage.Format.Format_RGB888
    return QImage(arr.data, w, h, c * w, fmt).copy()


def _checker_brush(cell_scale):
    """Damier gris/blanc pour montrer les zones transparentes."""
    pm = QPixmap(16, 16)
    pm.fill(QColor("#ffffff"))
    p = QPainter(pm)
    p.fillRect(0, 0, 8, 8, QColor("#cfd4d9"))
    p.fillRect(8, 8, 8, 8, QColor("#cfd4d9"))
    p.end()
    brush = QBrush(pm)
    brush.setTransform(QTransform().scale(cell_scale, cell_scale))
    return brush


def _event_pos(e):
    return e.position().toPoint() if hasattr(e, "position") else e.pos()


class ImageView(QGraphicsView):
    clicked = pyqtSignal(float, float)        # fraction x, fraction y

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setBackgroundBrush(QBrush(QColor("#dfe4e8")))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)     # le zoom recale lui-meme sur le curseur
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cursor_shape = Qt.CursorShape.CrossCursor
        self.viewport().setCursor(self._cursor_shape)
        self._item = None
        self._checker = None
        self._w = self._h = 0
        self._markers = []
        self._press = None
        self._moved = False
        self._last = None
        self._fitted = True
        self._fitting = False
        self._bars(False)

    # ------------------------------------------------------------------ image
    def clear_image(self):
        self._scene.clear()
        self._item = None
        self._checker = None
        self._markers = []
        self._w = self._h = 0

    def _pixmap_for(self, arr):
        """(pixmap, facteur) : l'affichage est limite a DISPLAY_MAX pixels, l'image complete reste en memoire."""
        h, w = arr.shape[:2]
        img = array_to_qimage(arr)
        k = 1.0
        if max(w, h) > DISPLAY_MAX:
            k = max(w, h) / float(DISPLAY_MAX)
            img = img.scaled(int(w / k), int(h / k), Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        return QPixmap.fromImage(img), k

    def set_image(self, arr):
        self.clear_image()
        h, w = arr.shape[:2]
        pm, k = self._pixmap_for(arr)
        # damier derriere l'image (visible seulement si l'image a de la transparence)
        self._checker = QGraphicsRectItem(0, 0, w, h)
        self._checker.setPen(QPen(Qt.PenStyle.NoPen))
        self._checker.setBrush(_checker_brush(max(w, h) / 500.0))
        self._checker.setZValue(-1)
        self._checker.setVisible(False)
        self._scene.addItem(self._checker)
        self._item = QGraphicsPixmapItem(pm)
        self._item.setScale(k)                  # coordonnees de scene = pixels de l'image complete
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._item)
        self._w, self._h = w, h
        m = max(w, h)          # grande marge : le zoom peut toujours recaler le point sous le curseur
        self._scene.setSceneRect(QRectF(-m, -m, w + 2 * m, h + 2 * m))
        self.fit()

    def replace_image(self, arr, transparent=False):
        """Change les pixels affiches sans toucher au zoom ni a la position. `arr` peut etre une
        version reduite de l'image (apercu rapide) : elle est mise a l'echelle de l'image complete."""
        if self._item is None:
            return
        pm, _k = self._pixmap_for(arr)
        self._item.setPixmap(pm)
        self._item.setScale(self._w / float(pm.width()))
        if self._checker is not None:
            self._checker.setVisible(bool(transparent))

    def set_cursor_shape(self, shape):
        self._cursor_shape = shape
        self.viewport().setCursor(shape)

    def has_image(self):
        return self._item is not None

    # ------------------------------------------------------------------- zoom
    def _bars(self, on):
        """Barres de defilement seulement hors mode « ajuste » : sinon fitInView les fait
        apparaitre, la zone utile change, resizeEvent rappelle fit() et la boucle ne s'arrete plus."""
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if on else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)

    def fit(self):
        if self._item is None:
            return
        self._fitted = True
        self._bars(False)
        self.resetTransform()
        self.fitInView(QRectF(0, 0, self._w, self._h), Qt.AspectRatioMode.KeepAspectRatio)

    def _fit_scale(self):
        vp = self.viewport()
        # meme calcul que fitInView (2 px de marge de chaque cote)
        return min((vp.width() - 4) / float(max(self._w, 1)), (vp.height() - 4) / float(max(self._h, 1)))

    def zoom_at(self, factor, pos=None):
        """Zoom de `factor` en gardant FIXE le point de l'image sous `pos` (coordonnees de la vue ;
        par defaut le centre). La molette l'appelle avec la position du curseur."""
        if self._item is None:
            return
        if pos is None:
            pos = self.viewport().rect().center()
        fit = self._fit_scale()
        target = self.transform().m11() * factor
        if target <= fit * 1.001:                  # plus loin que « ajuste » : on revient a l'ajustement
            self.fit()
            return
        target = min(target, 40.0)                 # 40 pixels d'ecran par pixel d'image au maximum
        factor = target / self.transform().m11()
        anchor = self.mapToScene(pos)              # point de l'image sous le curseur, avant le zoom
        self._fitted = False
        self._bars(True)
        self.scale(factor, factor)
        moved = self.mapFromScene(anchor)          # ou il se retrouve apres le zoom
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + moved.x() - pos.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + moved.y() - pos.y())

    def zoom(self, factor):
        """Zoom centre (boutons + et −)."""
        self.zoom_at(factor)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._fitted and not self._fitting:
            self._fitting = True
            try:
                self.fit()
            finally:
                self._fitting = False

    def wheelEvent(self, e):
        if self._item is None:
            return
        self.zoom_at(1.25 if e.angleDelta().y() > 0 else 0.8, _event_pos(e))
        e.accept()

    # ------------------------------------------------------------------ souris
    def mousePressEvent(self, e):
        if e.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._press = e.button()
            self._moved = False
            self._last = _event_pos(e)
            self._start = self._last
        e.accept()

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        pos = _event_pos(e)
        if not self._moved and (pos - self._start).manhattanLength() > 5:
            self._moved = True
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        if self._moved:
            d = pos - self._last
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            if self._fitted:
                self._fitted = False
                self._bars(True)
        self._last = pos

    def mouseReleaseEvent(self, e):
        if self._press is None:
            return
        button, moved = self._press, self._moved
        self._press = None
        self.viewport().setCursor(self._cursor_shape)
        if button == Qt.MouseButton.LeftButton and not moved and self._item is not None:
            p = self.mapToScene(_event_pos(e))
            fx, fy = p.x() / self._w, p.y() / self._h
            if 0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0:
                self.clicked.emit(fx, fy)

    # ----------------------------------------------------------------- reperes
    def set_points(self, points):
        """points : liste de (fx, fy, complet) ; le numero est la position + 1."""
        for g in self._markers:
            self._scene.removeItem(g)
        self._markers = []
        if self._item is None:
            return
        for n, (fx, fy, done) in enumerate(points, 1):
            col = RED if done else ORANGE
            pen = QPen(col, 2)
            pen.setCosmetic(True)
            g = QGraphicsItemGroup()
            g.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            g.addToGroup(self._scene.addEllipse(QRectF(-9, -9, 18, 18), pen))
            g.addToGroup(self._scene.addLine(-15, 0, 15, 0, pen))
            g.addToGroup(self._scene.addLine(0, -15, 0, 15, pen))
            tag = self._scene.addRect(QRectF(10, -24, 18, 15), QPen(Qt.PenStyle.NoPen), QBrush(col))
            g.addToGroup(tag)
            txt = self._scene.addText(str(n), QFont("Segoe UI", 8, QFont.Weight.Bold))
            txt.setDefaultTextColor(QColor("white"))
            txt.setPos(10 + (18 - txt.boundingRect().width()) / 2, -26)
            g.addToGroup(txt)
            g.setPos(QPointF(fx * self._w, fy * self._h))
            g.setZValue(10)
            self._scene.addItem(g)
            self._markers.append(g)
