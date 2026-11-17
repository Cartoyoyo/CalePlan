"""Composants graphiques communs a mes plugins (meme famille qu'Export Layers) :
sections numerotees, pastilles, cartes a interrupteur, bandeau d'information."""
from qgis.PyQt.QtCore import QRectF, Qt
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

GREEN = "#1a6b3a"          # vert fonce : numeros, bouton principal
GREEN_ON = "#2e8b57"       # vert : interrupteur actif, pastilles
GREY = "#9aa5ad"           # gris : inactif
NOTICE_CSS = ("background:#FFF4E5; color:#6B4200; border:1px solid #E0A040;"
              "border-radius:4px; padding:8px;")
COUNT_CSS = ("background:#eef6fd;border:1px solid #9cc7ec;border-radius:8px;padding:0 6px;font-size:11px;")
CHIP_CSS = "font-size:10px;font-weight:bold;color:white;border-radius:8px;padding:1px 7px;background:%s;"
GO_CSS = ("QPushButton{background:%s;color:white;font-weight:bold;padding:4px 16px;border-radius:3px;}"
          "QPushButton:disabled{background:#9bb8a6;}" % GREEN)
ABOUT_BTN_CSS = ("QPushButton{background-color:#7f8c8d;color:white;border-radius:5px;font-weight:bold;"
                 "font-size:11px;}QPushButton:hover{background-color:#95a5a6;}")


def badge_label(text, color=GREEN):
    lbl = QLabel(text)
    lbl.setFixedSize(20, 20)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("background:%s;color:white;border-radius:10px;font-weight:bold;" % color)
    return lbl


def section(title_label, number):
    """Bloc encadre numerote -> (cadre, mise en page interne, ligne d'en-tete)."""
    frame = QFrame()
    frame.setObjectName("sec")
    frame.setStyleSheet("#sec{border:1px solid #c9c9c9;border-radius:4px;}")
    box = QVBoxLayout(frame)
    box.setContentsMargins(8, 6, 8, 8)
    box.setSpacing(5)
    head = QHBoxLayout()
    head.setSpacing(6)
    head.addWidget(badge_label(str(number)))
    title_label.setStyleSheet("font-weight:bold;")
    head.addWidget(title_label)
    box.addLayout(head)
    return frame, box, head


class ToggleSwitch(QCheckBox):
    """Case a cocher dessinee en interrupteur (Qt5 / Qt6)."""

    ON, OFF = QColor(GREEN_ON), QColor("#b9c2c9")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _event):
        on = self.isChecked()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        track = QColor(self.ON if on else self.OFF)
        if not self.isEnabled():
            track.setAlpha(120)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 2, 40, 18), 9, 9)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(20 if on else 2, 3, 16, 16))
        p.end()


class OptionCard(QFrame):
    """Bloc a interrupteur : [interrupteur] [icone]  (n) Titre  [ACTIVE]  + explication.
    Un clic n'importe ou dans le bloc bascule l'interrupteur."""

    def __init__(self, number, icon, parent=None):
        super().__init__(parent)
        self.setObjectName("optCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.switch = ToggleSwitch()
        self._texts = ("", "", "", "", "")       # titre, msg actif, msg inactif, chip actif, chip inactif
        box = QHBoxLayout(self)
        box.setContentsMargins(10, 4, 10, 4)
        box.setSpacing(10)
        box.addWidget(self.switch)
        ic = QLabel(icon)
        ic.setStyleSheet("font-size:18px;")
        box.addWidget(ic)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.badge = badge_label(str(number))
        head.addWidget(self.badge)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight:bold;font-size:13px;")
        head.addWidget(self.title)
        self.chip = QLabel()
        head.addWidget(self.chip)
        head.addStretch()
        texts.addLayout(head)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet("font-size:11px;")
        texts.addWidget(self.msg)
        box.addLayout(texts, 1)
        self.switch.toggled.connect(lambda _v: self.paint_state())

    def mousePressEvent(self, event):
        if self.switch.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.switch.toggle()
        super().mousePressEvent(event)

    def set_texts(self, title, msg_on, msg_off, chip_on, chip_off):
        self._texts = (title, msg_on, msg_off, chip_on, chip_off)
        self.paint_state()

    def paint_state(self):
        on = self.switch.isChecked()
        title, msg_on, msg_off, chip_on, chip_off = self._texts
        self.title.setText(title)
        self.msg.setText(msg_on if on else msg_off)
        self.chip.setText(chip_on if on else chip_off)
        self.setStyleSheet(
            "#optCard{border:2px solid #2e8b57;border-radius:6px;background:rgba(46,139,87,0.10);}" if on else
            "#optCard{border:2px solid #c9c9c9;border-radius:6px;}")
        self.badge.setStyleSheet("color:white;border-radius:10px;font-weight:bold;background:%s;"
                                 % (GREEN if on else GREY))
        self.chip.setStyleSheet(CHIP_CSS % (GREEN_ON if on else GREY))
