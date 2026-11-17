"""Fenetre « A propos » facon CanaPlan : bandeau, badges, texte justifie, GitHub / LinkedIn."""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import i18n
from .widgets import NOTICE_CSS

REPO = "https://github.com/Cartoyoyo/CalePlan"
LINKEDIN = "https://www.linkedin.com/in/ylaloux/"


def read_metadata(plugin_dir):
    """Lecture ligne a ligne (configparser echoue sur les cles multilignes)."""
    vals = {"name": "CalePlan", "version": "", "author": "", "homepage": REPO}
    path = os.path.join(plugin_dir, "metadata.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                for key in vals:
                    if line.startswith(key + "="):
                        vals[key] = line.split("=", 1)[1].strip()
    return vals


def _sep():
    s = QFrame()
    s.setFrameShape(QFrame.Shape.HLine)
    s.setFrameShadow(QFrame.Shadow.Sunken)
    return s


class AboutDialog(QDialog):

    def __init__(self, plugin_dir, parent=None):
        super().__init__(parent)
        meta = read_metadata(plugin_dir)
        self.setWindowTitle("%s CalePlan" % i18n.tr("btn_about"))
        self.setMinimumWidth(420)
        icon = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))
        about_dir = os.path.join(plugin_dir, "icons", "about")

        def img(name):
            return os.path.join(about_dir, name).replace("\\", "/")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        logo = os.path.join(about_dir, "logo-full.png")
        if os.path.exists(logo):
            from qgis.PyQt.QtGui import QPixmap
            lb = QLabel()
            lb.setPixmap(QPixmap(logo))
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lb)

        badges = QLabel(
            '<div style="line-height:220%%">'
            '<a href="https://qgis.org"><img src="%s"></a>&nbsp;&nbsp;'
            '<a href="https://www.gnu.org/licenses/gpl-3.0.html"><img src="%s"></a>&nbsp;&nbsp;'
            '<a href="%s#readme"><img src="%s"></a></div>'
            % (img("badge-qgis.png"), img("badge-formats.png"), meta["homepage"], img("badge-doc.png")))
        badges.setOpenExternalLinks(True)
        badges.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(badges)
        lay.addWidget(_sep())

        about = QLabel(i18n.tr("ab_description"))
        about.setWordWrap(True)
        about.setAlignment(Qt.AlignmentFlag.AlignJustify)
        lay.addWidget(about)

        note = QLabel(i18n.tr("ab_note"))
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignJustify)
        note.setStyleSheet(NOTICE_CSS)
        lay.addWidget(note)
        lay.addWidget(_sep())

        author = QLabel('<b>%s</b><br><a href="%s/blob/main/CHANGELOG.md">%s</a>'
                        % (meta["author"], meta["homepage"], i18n.tr("ab_version", version=meta["version"])))
        author.setOpenExternalLinks(True)
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(author)

        links = QLabel('<a href="%s"><img src="%s"></a>&nbsp;&nbsp;<a href="%s"><img src="%s"></a>'
                       % (meta["homepage"], img("badge-github.png"), LINKEDIN, img("badge-linkedin.png")))
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(links)
        lay.addWidget(_sep())

        close = QPushButton(i18n.tr("btn_close"))
        close.setDefault(True)
        close.setFixedWidth(100)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        row.addStretch()
        lay.addLayout(row)
