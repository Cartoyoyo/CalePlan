"""Outil de carte : un clic gauche renvoie le point en coordonnees du projet ; Echap annule.
La molette et le bouton du milieu (zoom / deplacement) restent geres par le canevas."""
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.gui import QgsMapTool


class PickTool(QgsMapTool):
    picked = pyqtSignal(object)        # QgsPointXY dans le SCR du canevas
    cancelled = pyqtSignal()

    def __init__(self, canvas):
        super().__init__(canvas)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.toMapCoordinates(e.pos()))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            e.accept()
