"""Classe principale : bouton de barre d'outils + entree du menu Raster."""
import os

from qgis.PyQt.QtGui import QIcon

try:                                    # Qt6 : QAction est dans QtGui
    from qgis.PyQt.QtGui import QAction
except ImportError:                     # Qt5 : QAction est dans QtWidgets
    from qgis.PyQt.QtWidgets import QAction

MENU = "&CalePlan"


class CalePlanPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(QIcon(os.path.join(self.plugin_dir, "icon.png")), "CalePlan",
                              self.iface.mainWindow())
        self.action.setToolTip("CalePlan — PDF / image → carte")
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)      # barre des extensions, comme mes autres plugins
        self.iface.addPluginToMenu(MENU, self.action)         # menu Extensions

    def unload(self):
        if self.dialog is not None:
            self.dialog.shutdown()
            self.dialog.deleteLater()
            self.dialog = None
        if self.action is not None:
            self.iface.removePluginMenu(MENU, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None

    def run(self):
        if self.dialog is None:
            from .ui.dialog import CalePlanDialog      # import tardif : chargement de QGIS plus rapide
            self.dialog = CalePlanDialog(self.iface, self.plugin_dir, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
