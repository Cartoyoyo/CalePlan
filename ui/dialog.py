"""Fenetre principale de CalePlan (non modale) : pages | image | points + resultat."""
import math
import os
import re
import tempfile
import time

from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsCsException, QgsPointXY,
                       QgsProject, QgsRasterLayer, QgsSettings)
from qgis.gui import QgsProjectionSelectionWidget, QgsVertexMarker
from qgis.PyQt.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QColorDialog, QComboBox, QDialog,
                                 QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                                 QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSlider,
                                 QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from .. import i18n
from ..core import deps
from ..core import dxfread as DX
from ..core import dxfwrite as DW
from ..core import render as R
from ..core import transparency as K
from ..core import transform as T
from ..core import writer as W
from . import dxf_layers as DL
from .about import AboutDialog
from .map_tool import PickTool
from .viewer import ImageView, array_to_qimage
from .widgets import (ABOUT_BTN_CSS, COUNT_CSS, GO_CSS, GREEN, NOTICE_CSS, OptionCard, ToggleSwitch, section)

DPI_CHOICES = (100, 150, 200, 300)
PAPERS = (("A0", 841, 1189), ("A1", 594, 841), ("A2", 420, 594), ("A3", 297, 420),
          ("A4", 210, 297), ("A5", 148, 210))
_CRS_OPTION = getattr(QgsProjectionSelectionWidget, "CrsOption", None)
PROJECT_CRS_OPTION = getattr(_CRS_OPTION, "ProjectCrs", None) if _CRS_OPTION is not None else None
if PROJECT_CRS_OPTION is None:
    PROJECT_CRS_OPTION = getattr(QgsProjectionSelectionWidget, "ProjectCrs")
ICON_CROSS = getattr(QgsVertexMarker, "ICON_CROSS", None)
if ICON_CROSS is None:
    ICON_CROSS = QgsVertexMarker.IconType.ICON_CROSS


class WriteWorker(QThread):
    """Ecrit le GeoTIFF hors du fil de l'interface."""
    progressed = pyqtSignal(int)
    succeeded = pyqtSignal(bool)
    failed = pyqtSignal(str)

    def __init__(self, arr, gt, crs_wkt, out_path, key=None, parent=None):
        super().__init__(parent)
        self._args = (arr, gt, crs_wkt, out_path, key)

    def run(self):
        arr, gt, wkt, out, key = self._args
        try:
            if key is not None:                         # couleur transparente : bande alpha ajoutee
                arr = K.apply_color_key(arr, key[0], key[1])
            warped = W.write_geotiff(arr, gt, wkt, out, progress=lambda f: self.progressed.emit(int(f * 100)))
        except Exception as exc:        # GDAL / disque : le detail est affiche a l'utilisateur
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(bool(warped))


class LoadWorker(QThread):
    """Lit le DXF (ezdxf) hors du fil de l'interface ; l'apercu image est ensuite dessine par l'interface."""
    progressed = pyqtSignal(int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path
        self._last = -1

    def _tick(self, frac):
        pct = int(frac * 100)
        if pct != self._last:                  # un signal par pour cent, pas un par objet
            self._last = pct
            self.progressed.emit(pct)

    def run(self):
        try:
            data = DX.load(self._path, progress=self._tick)
        except DX.DxfError as exc:
            self.failed.emit(exc.code, exc.detail)
            return
        except Exception as exc:        # lecture ezdxf / memoire : le detail est montre a l'utilisateur
            self.failed.emit("open_failed", "%s: %s" % (type(exc).__name__, exc))
            return
        self.succeeded.emit(data)


class DxfWorker(QThread):
    """Ecrit le DXF cale (et son GeoPackage) hors du fil de l'interface : ezdxf et OGR, aucun objet QGIS."""
    progressed = pyqtSignal(str, int)         # etape ("dxf" | "gpkg"), pour cent de l'etape
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, src, matrix, tmp_dxf, tmp_gpkg, crs_wkt, parent=None):
        super().__init__(parent)
        self._args = (src, matrix, tmp_dxf, tmp_gpkg, crs_wkt)
        self._last = ("", -1)

    def _emit(self, stage, frac):
        pct = int(frac * 100)
        if (stage, pct) != self._last:
            self._last = (stage, pct)
            self.progressed.emit(stage, pct)

    def run(self):
        src, matrix, tmp_dxf, tmp_gpkg, wkt = self._args
        try:
            os.makedirs(os.path.dirname(os.path.abspath(tmp_dxf)), exist_ok=True)
            ok, dropped, enc = DW.write_dxf(src, tmp_dxf, matrix, lambda f: self._emit("dxf", f))
            counts = None
            if tmp_gpkg:
                counts = DW.write_gpkg(tmp_dxf, tmp_gpkg, wkt, enc, lambda f: self._emit("gpkg", f), ok + dropped)
        except Exception as exc:        # ezdxf / GDAL / disque : le detail est affiche a l'utilisateur
            self.failed.emit("%s: %s" % (type(exc).__name__, exc))
            return
        self.succeeded.emit({"ok": ok, "dropped": dropped, "counts": counts})


class InstallWorker(QThread):
    """Installe ezdxf (pip) hors du fil de l'interface."""
    done = pyqtSignal(bool, str)

    def run(self):
        ok, out = deps.install(deps.missing())
        self.done.emit(bool(ok), out)


def _sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def _paper(size_mm):
    if not size_mm:
        return ""
    short, long_ = sorted(size_mm)
    for name, s, l in PAPERS:
        if abs(short - s) <= 4 and abs(long_ - l) <= 6:
            return name
    return "%d×%d mm" % (round(long_), round(short))


class CalePlanDialog(QDialog):

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.plugin_dir = plugin_dir
        self.settings = QgsSettings()
        i18n.set_lang(self.settings.value("CalePlan/lang", i18n.default_lang()))

        self.path = None
        self.n_pages = 0
        self.page = 0
        self.arr = None
        self.eff_dpi = None
        self.points = {}              # page -> [ {fx, fy, X, Y} ]
        self.fit = None               # dernier calage valide
        self.fit_error = ""
        self._busy = False
        self._markers = []
        self._prev_tool = None
        self._hidden_for_pick = False
        self._name_edited = False
        self._thumb_todo = []
        self._worker = None
        self.dxf = None               # DxfData du DXF ouvert (None pour un PDF / une image)
        self._saving = True           # GeoTIFF enregistre dans le dossier choisi (sinon : dossier temporaire)
        self._installer = None
        self._loader = None           # lecture du DXF en cours (LoadWorker)
        self._builder = None          # creation des couches du DXF en cours (dxf_layers.Builder)
        self._plan = {}               # etape -> (debut, largeur) en pour cent de la barre
        self._written = set()         # fichiers ecrits par cette fenetre (remplacables sans question)
        self._outputs = {}            # (source, page) -> dernier GeoTIFF ecrit
        self._tmp = None
        self._picking = False         # pipette de couleur active
        self.out_crs = QgsCoordinateReferenceSystem(self.canvas.mapSettings().destinationCrs())   # SCR du calage
        self._crs_follows_project = True      # tant que l'utilisateur n'en choisit pas un autre
        saved_col = QColor(str(self.settings.value("CalePlan/key_color", "#ffffff")))
        self._key_color = saved_col if saved_col.isValid() else QColor("#ffffff")
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(120)
        self._preview_timer.timeout.connect(self._apply_preview)

        self.pick_tool = PickTool(self.canvas)
        self.pick_tool.picked.connect(self._on_map_picked)
        self.pick_tool.cancelled.connect(self._cancel_pending)

        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setAcceptDrops(True)
        icon = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))
        self.resize(1000, 640)
        self.setMinimumSize(940, 600)
        self._build_ui()
        self.retranslate()
        self._refresh()

    # ============================================================== interface
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 4)
        root.setSpacing(4)
        columns = QHBoxLayout()
        columns.setSpacing(8)
        root.addLayout(columns, 1)

        # ══ colonne gauche : ① Source ═════════════════════════════════════════
        self.lbl_src = QLabel()
        sec1, box1, head1 = section(self.lbl_src, 1)
        self.chip_pages = QLabel()
        self.chip_pages.setStyleSheet(COUNT_CSS)
        head1.addWidget(self.chip_pages)
        head1.addStretch()
        self.btn_open = QPushButton()
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(self._choose_file)
        box1.addWidget(self.btn_open)
        self.lbl_file = QLabel()
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setStyleSheet("font-size:11px;")
        box1.addWidget(self.lbl_file)
        self.lbl_dpi = QLabel()
        box1.addWidget(self.lbl_dpi)
        self.cmb_dpi = QComboBox()
        for d in DPI_CHOICES:
            self.cmb_dpi.addItem("%d dpi" % d, d)
        saved = int(self.settings.value("CalePlan/dpi", 150))
        self.cmb_dpi.setCurrentIndex(DPI_CHOICES.index(saved if saved in DPI_CHOICES else 150))
        self.cmb_dpi.currentIndexChanged.connect(self._dpi_changed)
        box1.addWidget(self.cmb_dpi)
        self.lst_pages = QListWidget()
        self.lst_pages.setIconSize(QSize(120, 86))
        self.lst_pages.setViewMode(QListWidget.ViewMode.IconMode)       # vignette au-dessus du texte
        self.lst_pages.setFlow(QListWidget.Flow.TopToBottom)
        self.lst_pages.setWrapping(False)
        self.lst_pages.setMovement(QListWidget.Movement.Static)
        self.lst_pages.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lst_pages.setGridSize(QSize(136, 116))
        self.lst_pages.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.lst_pages.currentRowChanged.connect(self._page_selected)
        box1.addWidget(self.lst_pages, 1)
        sec1.setFixedWidth(184)
        columns.addWidget(sec1)

        # ══ colonne centrale : ② Reperes sur l'image ═══════════════════════════
        self.lbl_view = QLabel()
        sec2, box2, head2 = section(self.lbl_view, 2)
        self.chip_points = QLabel()
        self.chip_points.setStyleSheet(COUNT_CSS)
        head2.addWidget(self.chip_points)
        head2.addStretch()
        tb = QHBoxLayout()
        self.btn_zout = QPushButton("−")
        self.btn_zin = QPushButton("+")
        for b in (self.btn_zout, self.btn_zin):
            b.setFixedWidth(30)
        self.btn_fit = QPushButton()
        self.btn_undo = QPushButton()
        self.btn_zout.clicked.connect(lambda: self.view.zoom(0.8))
        self.btn_zin.clicked.connect(lambda: self.view.zoom(1.25))
        self.btn_fit.clicked.connect(lambda: self.view.fit())
        self.btn_undo.clicked.connect(self._undo)
        tb.addWidget(self.btn_zout)
        tb.addWidget(self.btn_zin)
        tb.addWidget(self.btn_fit)
        tb.addStretch(1)
        tb.addWidget(self.btn_undo)
        box2.addLayout(tb)
        key = QHBoxLayout()
        key.setSpacing(6)
        self.sw_key = ToggleSwitch()
        self.lbl_key = QLabel()
        self.btn_swatch = QPushButton()
        self.btn_swatch.setFixedSize(30, 24)
        self.btn_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick = QPushButton("💧")
        self.btn_pick.setCheckable(True)
        self.btn_pick.setFixedSize(32, 24)
        self.lbl_tol = QLabel("±")
        self.sld_tol = QSlider(Qt.Orientation.Horizontal)
        self.sld_tol.setRange(0, 80)
        self.sld_tol.setValue(int(self.settings.value("CalePlan/key_tol", 12)))
        self.sld_tol.setFixedWidth(90)
        self.lbl_tol_val = QLabel(str(self.sld_tol.value()))
        self.lbl_tol_val.setMinimumWidth(20)
        for w_ in (self.sw_key, self.lbl_key, self.btn_swatch, self.btn_pick, self.lbl_tol, self.sld_tol,
                   self.lbl_tol_val):
            key.addWidget(w_)
        key.addStretch(1)
        box2.addLayout(key)
        self._paint_swatch()
        self.sw_key.toggled.connect(lambda _v: self._key_changed())
        self.btn_swatch.clicked.connect(self._choose_key_color)
        self.btn_pick.toggled.connect(self._toggle_pick)
        self.sld_tol.valueChanged.connect(self._tol_changed)
        self.view = ImageView()
        self.view.clicked.connect(self._on_image_clicked)
        box2.addWidget(self.view, 1)
        self.lbl_hint = QLabel()
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet(NOTICE_CSS.replace("padding:8px", "padding:5px"))
        self.lbl_hint.setMinimumHeight(40)
        box2.addWidget(self.lbl_hint)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(96)
        self.log_area.setVisible(False)
        box2.addWidget(self.log_area)
        columns.addWidget(sec2, 1)

        # ══ colonne droite ═══════════════════════════════════════════════════
        rw = QWidget()
        rw.setFixedWidth(340)
        right = QVBoxLayout(rw)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)
        columns.addWidget(rw)

        top = QHBoxLayout()
        top.addStretch()
        self.cmb_lang = QComboBox()
        for code in i18n.LANGS:
            self.cmb_lang.addItem("%s  %s" % (i18n.LANG_FLAGS[code], i18n.LANG_LABELS[code]), code)
        self.cmb_lang.setFixedHeight(26)
        self.cmb_lang.setMinimumWidth(130)
        self.cmb_lang.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cmb_lang.setCurrentIndex(i18n.LANGS.index(i18n.lang()))
        self.cmb_lang.currentIndexChanged.connect(self._lang_changed)
        top.addWidget(self.cmb_lang)
        self.btn_about = QPushButton()
        self.btn_about.setFixedSize(90, 26)
        self.btn_about.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_about.setStyleSheet(ABOUT_BTN_CSS)
        self.btn_about.clicked.connect(lambda: AboutDialog(self.plugin_dir, self).exec())
        top.addWidget(self.btn_about)
        right.addLayout(top)

        # ③ Points de controle
        self.lbl_pts_title = QLabel()
        sec3, box3, _h3 = section(self.lbl_pts_title, 3)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(19)
        hh = self.tbl.horizontalHeader()
        hh.setStretchLastSection(False)
        for c, w in ((0, 22), (1, 72), (2, 76), (3, 78), (4, 44)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.tbl.setColumnWidth(c, w)
        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tbl.setFixedHeight(108)
        self.tbl.itemChanged.connect(self._on_item_changed)
        box3.addWidget(self.tbl)
        rowb = QHBoxLayout()
        self.btn_del = QPushButton()
        self.btn_clear = QPushButton()
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_clear.clicked.connect(self._clear_points)
        rowb.addWidget(self.btn_del)
        rowb.addWidget(self.btn_clear)
        rowb.addStretch()
        box3.addLayout(rowb)
        trow = QHBoxLayout()
        self.lbl_transfo = QLabel()
        self.cmb_transfo = QComboBox()
        self.cmb_transfo.currentIndexChanged.connect(lambda _i: self._refresh())
        trow.addWidget(self.lbl_transfo)
        trow.addWidget(self.cmb_transfo, 1)
        box3.addLayout(trow)
        self.lbl_fit = QLabel()
        self.lbl_fit.setWordWrap(True)
        self.lbl_fit.setStyleSheet("font-weight:bold;color:%s;" % GREEN)
        box3.addWidget(self.lbl_fit)
        self.lbl_fit2 = QLabel()
        self.lbl_fit2.setWordWrap(True)
        self.lbl_fit2.setStyleSheet("color:#555;font-size:11px;")
        box3.addWidget(self.lbl_fit2)
        right.addWidget(sec3)

        # ④ Resultat
        self.lbl_res_title = QLabel()
        sec4, box4, _h4 = section(self.lbl_res_title, 4)
        _h4.addStretch()
        self.chk_save = QCheckBox()              # decoche : GeoTIFF dans le dossier temporaire, couche temporaire
        self.chk_save.setChecked(str(self.settings.value("CalePlan/save_tif", "false")).lower() == "true")
        self.chk_save.toggled.connect(self._save_toggled)
        _h4.addWidget(self.chk_save)
        g = QGridLayout()
        g.setColumnStretch(1, 1)
        g.setHorizontalSpacing(8)
        self.lbl_out_name = QLabel()
        self.edt_name = QLineEdit()
        self.edt_name.textEdited.connect(self._name_typed)
        self.lbl_out_folder = QLabel()
        self.edt_folder = QLineEdit(self._default_folder())
        self.btn_folder = QPushButton("📁")
        self.btn_folder.setFixedWidth(32)
        self.btn_folder.clicked.connect(self._choose_folder)
        self.lbl_out_crs = QLabel()
        self.crs_widget = QgsProjectionSelectionWidget()
        self.crs_widget.setOptionVisible(PROJECT_CRS_OPTION, True)
        self.crs_widget.setCrs(self.out_crs)
        self.crs_widget.crsChanged.connect(self._on_crs_widget)
        self.lbl_out_opacity = QLabel()
        self.sld_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sld_opacity.setRange(0, 100)
        self.sld_opacity.setValue(100)
        g.addWidget(self.lbl_out_name, 0, 0)
        g.addWidget(self.edt_name, 0, 1, 1, 2)
        g.addWidget(self.lbl_out_folder, 1, 0)
        g.addWidget(self.edt_folder, 1, 1)
        g.addWidget(self.btn_folder, 1, 2)
        g.addWidget(self.lbl_out_crs, 2, 0)
        g.addWidget(self.crs_widget, 2, 1, 1, 2)
        g.addWidget(self.lbl_out_opacity, 3, 0)
        g.addWidget(self.sld_opacity, 3, 1, 1, 2)
        # DXF : a la place de l'opacite, les deux sorties possibles
        self.lbl_out_what = QLabel()
        self.chk_out_dxf = QCheckBox()
        self.chk_out_gpkg = QCheckBox()
        self.chk_out_dxf.setChecked(str(self.settings.value("CalePlan/out_dxf", "true")).lower() == "true")
        self.chk_out_gpkg.setChecked(str(self.settings.value("CalePlan/out_gpkg", "true")).lower() == "true")
        for chk, key in ((self.chk_out_dxf, "CalePlan/out_dxf"), (self.chk_out_gpkg, "CalePlan/out_gpkg")):
            chk.toggled.connect(lambda v, k=key: (self.settings.setValue(k, bool(v)), self._refresh()))
        what = QHBoxLayout()
        what.setSpacing(12)
        what.addWidget(self.chk_out_dxf)
        what.addWidget(self.chk_out_gpkg)
        what.addStretch(1)
        g.addWidget(self.lbl_out_what, 3, 0)
        g.addLayout(what, 3, 1, 1, 2)
        self._img_only = [self.lbl_out_opacity, self.sld_opacity, self.sw_key, self.lbl_key, self.btn_swatch,
                          self.btn_pick, self.lbl_tol, self.sld_tol, self.lbl_tol_val]
        self._dxf_only = [self.lbl_out_what, self.chk_out_dxf, self.chk_out_gpkg]
        box4.addLayout(g)
        right.addWidget(sec4)

        # ⑤ ⑥ options a interrupteur
        self.card_add = OptionCard(5, "🗺")
        self.card_hide = OptionCard(6, "🖱")
        self.chk_add = self.card_add.switch
        self.chk_hide = self.card_hide.switch
        self.chk_add.setChecked(True)
        self.chk_hide.setChecked(str(self.settings.value("CalePlan/hide_window", "true")).lower() == "true")
        self.chk_add.toggled.connect(lambda _v: self._refresh())
        self.chk_hide.toggled.connect(lambda v: self.settings.setValue("CalePlan/hide_window", bool(v)))
        right.addWidget(self.card_add)
        right.addWidget(self.card_hide)
        right.addStretch(1)

        # ══ recapitulatif, etat, progression, boutons ═══════════════════════════
        self.lbl_recap = QLabel()
        self.lbl_recap.setWordWrap(True)
        self.lbl_recap.setObjectName("recap")
        self.lbl_recap.setStyleSheet("#recap{border:1px solid #c9c9c9;border-radius:3px;padding:5px 8px;}")
        root.addWidget(self.lbl_recap)
        self.lbl_status = QLabel()
        root.addWidget(self.lbl_status)
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        bottom.addWidget(self.progress, 1)
        self.btn_log = QPushButton()
        self.btn_log.setCheckable(True)
        self.btn_log.toggled.connect(self._show_log)
        bottom.addWidget(self.btn_log)
        self.btn_go = QPushButton()
        self.btn_go.setStyleSheet(GO_CSS)
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.clicked.connect(self._go)
        bottom.addWidget(self.btn_go)
        self.btn_close = QPushButton()
        self.btn_close.clicked.connect(self.close)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

    def _name_typed(self, _t):
        self._name_edited = True
        self._update_recap()

    def _show_log(self, on):
        self.log_area.setVisible(on)
        self.btn_log.setText(i18n.tr("btn_log") + (" ▾" if on else " ▸"))

    def log(self, text):
        self.log_area.append(text)

    # ============================================================ traductions
    def retranslate(self):
        t = i18n.tr
        self.setWindowTitle(t("window_title"))
        self.lbl_src.setText(t("sec_source"))
        self.lbl_view.setText(t("sec_view"))
        self.lbl_pts_title.setText(t("points_title"))
        self.lbl_res_title.setText(t("result_title"))
        self.btn_open.setText("📂  " + t("open_short"))
        self.btn_open.setToolTip(t("open_btn"))
        self.lbl_dpi.setText(t("dpi_label"))
        self.btn_about.setText(t("btn_about"))
        self.btn_fit.setText(t("btn_fit"))
        self.lbl_key.setText(t("key_switch"))
        self.lbl_key.setToolTip(t("key_switch_tip"))
        self.sw_key.setToolTip(t("key_switch_tip"))
        self.btn_swatch.setToolTip(t("key_swatch_tip"))
        self.btn_pick.setToolTip(t("key_pick_tip"))
        self.sld_tol.setToolTip(t("key_tol_tip"))
        self.lbl_tol.setToolTip(t("key_tol_tip"))
        self.btn_undo.setText(t("btn_undo"))
        self.view.setToolTip(t("view_hint"))
        self.tbl.setHorizontalHeaderLabels([t("col_n"), t("col_img"), t("col_x"), t("col_y"), t("col_err")])
        self.btn_del.setText(t("btn_delete"))
        self.btn_clear.setText(t("btn_clear"))
        self.lbl_transfo.setText(t("transfo_label"))
        cur = self.cmb_transfo.currentData() or "auto"
        self.cmb_transfo.blockSignals(True)
        self.cmb_transfo.clear()
        for code, key in (("auto", "transfo_auto"), ("similarity", "transfo_sim"), ("affine", "transfo_aff")):
            self.cmb_transfo.addItem(t(key), code)
        self.cmb_transfo.setCurrentIndex(max(0, self.cmb_transfo.findData(cur)))
        self.cmb_transfo.blockSignals(False)
        self.lbl_out_name.setText(t("out_name"))
        self.lbl_out_folder.setText(t("out_folder"))
        self.lbl_out_opacity.setText(t("out_opacity"))
        self.lbl_out_what.setText(t("out_what"))
        self.chk_out_dxf.setText(t("out_dxf_cb"))
        self.chk_out_gpkg.setText(t("out_gpkg_cb"))
        self.chk_save.setText(t("out_save"))
        self.chk_save.setToolTip(t("out_save_tip"))
        self.lbl_out_crs.setText(t("out_crs"))
        self.lbl_out_crs.setToolTip(t("crs_tip"))
        self.crs_widget.setToolTip(t("crs_tip"))
        self.card_add.set_texts(t("card_add_title"), t("card_add_on"), t("card_add_off"),
                                t("chip_on"), t("chip_off"))
        self.card_hide.set_texts(t("card_hide_title"), t("card_hide_on"), t("card_hide_off"),
                                 t("chip_on"), t("chip_off"))
        self.btn_go.setText(t("btn_go"))
        self.btn_close.setText(t("btn_close"))
        self.btn_log.setText(t("btn_log") + (" ▾" if self.btn_log.isChecked() else " ▸"))
        self.lbl_status.setText(t("status_ready"))
        self._apply_mode()
        self._update_file_label()
        self._fill_page_list(keep_thumbs=True)
        self._refresh()

    def _apply_mode(self):
        """Un DXF n'a ni resolution de rendu ni transparence ni opacite, et jamais de deformation :
        similitude seule ; ses deux sorties remplacent le curseur d'opacite."""
        is_dxf = self.dxf is not None
        for w in self._img_only:
            w.setVisible(not is_dxf)
        for w in self._dxf_only:
            w.setVisible(is_dxf)
        self.cmb_transfo.setEnabled(not is_dxf)
        self.chk_save.setVisible(not is_dxf)
        self._save_toggled()
        self.lbl_dpi.setText(i18n.tr("dxf_res_label" if is_dxf else "dpi_label"))
        self.lbl_out_name.setText(i18n.tr("out_name_dxf" if is_dxf else "out_name"))
        self.cmb_dpi.blockSignals(True)
        for i in range(self.cmb_dpi.count()):
            d = int(self.cmb_dpi.itemData(i))
            self.cmb_dpi.setItemText(i, i18n.tr("dxf_res_item", px=d * 20) if is_dxf else "%d dpi" % d)
        self.cmb_dpi.blockSignals(False)

    def _save_toggled(self, _v=None):
        """Sans enregistrement, le dossier de sortie ne sert plus : le GeoTIFF part dans le dossier temporaire."""
        keep = self.chk_save.isChecked() or self.dxf is not None
        self.edt_folder.setEnabled(keep)
        self.btn_folder.setEnabled(keep)
        self.lbl_out_folder.setEnabled(keep)
        self.settings.setValue("CalePlan/save_tif", bool(self.chk_save.isChecked()))
        if getattr(self, "lbl_recap", None) is not None:
            self._update_recap()

    @staticmethod
    def _temp_folder():
        return os.path.join(tempfile.gettempdir(), "CalePlan")

    def _lang_changed(self, _i):
        code = self.cmb_lang.currentData()
        i18n.set_lang(code)
        self.settings.setValue("CalePlan/lang", code)
        self.retranslate()

    def _update_file_label(self):
        if not self.path:
            self.lbl_file.setText(i18n.tr("no_file"))
            self.chip_pages.setText("")
            self.chip_pages.setVisible(False)
            return
        self.lbl_file.setText("<b>%s</b>" % os.path.basename(self.path))
        self.chip_pages.setText(i18n.tr("chip_dxf") if self.dxf is not None
                                else i18n.tr("chip_pages", n=self.n_pages) if R.is_pdf(self.path)
                                else i18n.tr("image_item"))
        self.chip_pages.setVisible(True)

    # ================================================================ fichier
    def _default_folder(self):
        saved = self.settings.value("CalePlan/out_dir", "")
        if saved and os.path.isdir(saved):
            return saved
        home = QgsProject.instance().homePath()
        if home and os.path.isdir(home):
            return home
        return os.path.join(os.path.expanduser("~"), "Documents", "CalePlan")

    def _choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, i18n.tr("out_folder_pick"), self.edt_folder.text())
        if d:
            self.edt_folder.setText(d)
            self.settings.setValue("CalePlan/out_dir", d)

    def _choose_file(self):
        start = self.settings.value("CalePlan/last_dir", "") or QgsProject.instance().homePath()
        path, _f = QFileDialog.getOpenFileName(self, i18n.tr("open_title"), start, i18n.tr("file_filter"))
        if path:
            self.open_file(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.open_file(urls[0].toLocalFile())

    def open_file(self, path):
        if self._busy:
            return
        self._cancel_pending()
        if R.is_dxf(path):
            self._open_dxf(path)
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            n = R.page_count(path)
        except R.RenderError as exc:
            QApplication.restoreOverrideCursor()
            self._error_box(exc)
            return
        QApplication.restoreOverrideCursor()
        self.dxf = None
        self._apply_mode()
        self.path = path
        self.n_pages = n
        self.page = 0
        self.points = {}
        self.arr = None
        self._name_edited = False
        self.settings.setValue("CalePlan/last_dir", os.path.dirname(path))
        self.view.clear_image()
        self._update_file_label()
        self._fill_page_list()
        self.log(i18n.tr("log_opened", name=os.path.basename(path), n=n))
        self._load_page()

    # ----------------------------------------------------------------- DXF
    def _offer_install(self, then):
        """Propose d'installer ezdxf (une fois), puis rappelle `then()` si l'installation reussit."""
        ans = QMessageBox.question(self, i18n.tr("err_title"), i18n.tr("dxf_need_text"))
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self.lbl_status.setText(i18n.tr("dxf_installing"))
        worker = InstallWorker(self)
        worker.done.connect(lambda ok, out: self._install_done(ok, out, then))
        worker.finished.connect(worker.deleteLater)
        self._installer = worker
        worker.start()

    def _install_done(self, ok, out, then):
        self._installer = None
        self._set_busy(False)
        self.log("ℹ " + (out[-400:] if out else ""))
        if ok and not deps.missing():
            self.lbl_status.setText(i18n.tr("dxf_install_ok"))
            then()
            return
        self.lbl_status.setText(i18n.tr("status_ready"))
        box = QMessageBox(QMessageBox.Icon.Critical, i18n.tr("err_title"),
                          i18n.tr("dxf_install_fail", cmd=deps.manual_command(deps.missing() or [s for _m, s in deps.REQUIRED])),
                          QMessageBox.StandardButton.Ok, self)
        box.setDetailedText(out)
        box.exec()

    def _open_dxf(self, path):
        if not DX.available():
            self._offer_install(lambda: self._open_dxf(path))
            return
        self._set_busy(True)
        self.lbl_status.setText(i18n.tr("status_dxf_read"))
        loader = LoadWorker(path, self)
        loader.progressed.connect(self.progress.setValue)
        loader.succeeded.connect(lambda data: self._dxf_loaded(path, data))
        loader.failed.connect(self._dxf_load_failed)
        loader.finished.connect(loader.deleteLater)
        self._loader = loader
        loader.start()

    def _dxf_load_failed(self, code, detail):
        self._loader = None
        self._set_busy(False)
        key = "err_dxf_empty" if code == "empty" else "err_dxf_open"
        QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr(key, detail=detail or code))
        self.lbl_status.setText(i18n.tr("status_ready"))

    def _dxf_loaded(self, path, data):
        self._loader = None
        self._set_busy(False)
        self.dxf = data
        self.path = path
        self.n_pages = 1
        self.page = 0
        self.points = {}
        self.arr = None
        self._name_edited = False
        self.settings.setValue("CalePlan/last_dir", os.path.dirname(path))
        self.view.clear_image()
        self._apply_mode()
        self._update_file_label()
        self._fill_page_list()
        x0, y0, x1, y1 = data.bounds
        extra = i18n.tr("log_dxf_outliers", k=data.outliers) if data.outliers else ""
        self.log(i18n.tr("log_dxf", n=data.n_entities, layers=data.layers, w="%.2f" % (x1 - x0),
                         h="%.2f" % (y1 - y0), extra=extra))
        if data.skipped:
            self.log(i18n.tr("log_dxf_skipped", k=data.skipped))
        self._load_page()                  # dessin de l'apercu (QPainter) : dans le fil de l'interface, moins d'une seconde

    def _fill_page_list(self, keep_thumbs=False):
        old = {}
        if keep_thumbs:
            for i in range(self.lst_pages.count()):
                old[i] = self.lst_pages.item(i).icon()
        self.lst_pages.blockSignals(True)
        row = self.page
        self.lst_pages.clear()
        for i in range(self.n_pages):
            it = QListWidgetItem(self._page_text(i))
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            if i in old:
                it.setIcon(old[i])
            self.lst_pages.addItem(it)
        if 0 <= row < self.n_pages:
            self.lst_pages.setCurrentRow(row)
        self.lst_pages.blockSignals(False)
        if not keep_thumbs:
            self._thumb_todo = [] if self.dxf is not None else list(range(self.n_pages))
            QTimer.singleShot(0, self._next_thumb)

    def _page_text(self, i):
        if self.dxf is not None:
            label = i18n.tr("dxf_item")
        elif self.path and R.is_pdf(self.path):
            label = i18n.tr("page_item", n=i + 1)
        else:
            label = i18n.tr("image_item")
        n = len([p for p in self.points.get(i, []) if p["X"] is not None])
        return label + (" · %d ●" % n if n else "")

    def _next_thumb(self):
        """Vignettes une par une (la fenetre reste reactive pendant le remplissage)."""
        if not self._thumb_todo or not self.path or self.dxf is not None:
            return
        if self._busy:                              # pas de rendu pendant l'ecriture
            QTimer.singleShot(300, self._next_thumb)
            return
        i = self._thumb_todo.pop(0)
        if i < self.lst_pages.count():
            try:
                arr = R.thumbnail(self.path, i, 200)
                pm = QPixmap.fromImage(array_to_qimage(arr)).scaled(
                    120, 86, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lst_pages.item(i).setIcon(QIcon(pm))
                size = R.page_size_mm(self.path, i)
                if size:
                    self.lst_pages.item(i).setToolTip(_paper(size))
            except (R.RenderError, OSError, RuntimeError, ValueError) as exc:    # vignette manquante : on le note au journal
                self.log(i18n.tr("log_error", detail="%s (%s)" % (exc, i18n.tr("page_item", n=i + 1))))
        QTimer.singleShot(0, self._next_thumb)

    def _page_selected(self, row):
        if row < 0 or row == self.page and self.arr is not None:
            return
        if self._busy:
            return
        self._cancel_pending()
        self.page = row
        self._load_page()

    def _dpi_changed(self, _i):
        self.settings.setValue("CalePlan/dpi", int(self.cmb_dpi.currentData()))
        if self.path:
            self._cancel_pending()
            self._load_page()

    def _load_page(self):
        if not self.path:
            return
        self.lbl_status.setText(i18n.tr("status_render", n=self.page + 1))
        self.lbl_status.repaint()                 # repeint direct, sans relancer la boucle d'evenements
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        dpi = int(self.cmb_dpi.currentData())
        if self.dxf is not None:
            # Les reperes sont gardes en COORDONNEES DU DESSIN le temps du re-rendu : changer la
            # definition de l'apercu ne les deplace pas.
            kept = []
            if self.arr is not None and self.dxf.geo is not None:
                h0, w0 = self.arr.shape[:2]
                for p in self._pts():
                    kept.append((p, DX.to_dxf(self.dxf.geo, p["fx"] * w0, p["fy"] * h0)))
            try:
                arr = DX.render(self.dxf, dpi * 20)
            except (RuntimeError, ValueError, MemoryError) as exc:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr("err_dxf_open", detail=str(exc)))
                return
            eff = None
            h1, w1 = arr.shape[:2]
            for p, (x, y) in kept:
                px, py = DX.to_pixel(self.dxf.geo, x, y)
                p["fx"], p["fy"] = px / w1, py / h1
        else:
            try:
                arr, eff = R.render(self.path, self.page, dpi)
            except R.RenderError as exc:
                QApplication.restoreOverrideCursor()
                self._error_box(exc)
                return
        QApplication.restoreOverrideCursor()
        self.arr, self.eff_dpi = arr, eff
        self.view.set_image(arr)
        if self.dxf is not None and self.lst_pages.count():
            pm = QPixmap.fromImage(array_to_qimage(arr)).scaled(
                120, 86, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lst_pages.item(0).setIcon(QIcon(pm))
        if self.sw_key.isChecked() and self.dxf is None:
            self._apply_preview()
        if not self._name_edited:
            base = _sanitize(os.path.splitext(os.path.basename(self.path))[0])
            if R.is_pdf(self.path) and self.n_pages > 1:
                base += "_p%d" % (self.page + 1)
            self.edt_name.setText(base + ("_cale.dxf" if self.dxf is not None else ".tif"))
        h, w = arr.shape[:2]
        extra = ""
        if eff is not None:
            extra = i18n.tr("status_dpi", dpi=round(eff))
            if eff < dpi - 0.5:
                extra += i18n.tr("status_capped", dpi=round(eff), px=R.MAX_SIDE)
        if self.dxf is not None:
            self.lbl_status.setText(i18n.tr("status_dxf_loaded", w=w, h=h, n=self.dxf.n_entities))
        else:
            self.lbl_status.setText(i18n.tr("status_loaded", n=self.page + 1, w=w, h=h, dpi=extra))
        self.log("ℹ " + self.lbl_status.text())
        self._refresh()

    # ================================================================= points
    def _pts(self):
        return self.points.setdefault(self.page, [])

    def _incomplete(self):
        return [p for p in self._pts() if p["X"] is None or p["Y"] is None]

    def _on_image_clicked(self, fx, fy):
        if self._busy or self.arr is None:
            return
        if self._picking:                           # pipette : on lit la couleur, on ne pose pas de repere
            r, g, b = K.sample_color(self.arr, fx, fy)
            self._key_color = QColor(r, g, b)
            self._paint_swatch()
            self.btn_pick.setChecked(False)
            self.sw_key.blockSignals(True)
            self.sw_key.setChecked(True)
            self.sw_key.blockSignals(False)
            self._key_changed()
            return
        if self._incomplete():
            self.lbl_status.setText(i18n.tr("status_waiting_map"))
            return
        snapped = False
        if self.dxf is not None and not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier):
            # accrochage au sommet du dessin le plus proche (10 pixels d'ecran) : precision du vecteur
            h, w = self.arr.shape[:2]
            hit = DX.snap(self.dxf, fx * w, fy * h, 10.0 / max(self.view.transform().m11(), 1e-6))
            if hit is not None:
                fx, fy, snapped = hit[0] / w, hit[1] / h, True
        self._pts().append({"fx": fx, "fy": fy, "X": None, "Y": None})
        if snapped:
            self.log(i18n.tr("log_snap"))
        self._start_pick()
        self._refresh()

    def _start_pick(self):
        cur = self.canvas.mapTool()
        if cur is not self.pick_tool:
            self._prev_tool = cur
        self.canvas.setMapTool(self.pick_tool)
        self.iface.messageBar().pushInfo("CalePlan", i18n.tr("map_msg", n=len(self._pts())))
        if self.chk_hide.isChecked():
            self._hidden_for_pick = True
            self.hide()

    def _end_pick(self):
        if self.canvas.mapTool() is self.pick_tool:
            if self._prev_tool is not None:
                self.canvas.setMapTool(self._prev_tool)
            else:
                self.canvas.unsetMapTool(self.pick_tool)
        self.iface.messageBar().clearWidgets()
        if self._hidden_for_pick:
            self._hidden_for_pick = False
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_map_picked(self, pt):
        inc = self._incomplete()
        if inc:
            pt = self._to_out(pt)                      # le clic est dans le SCR du projet
            inc[0]["X"], inc[0]["Y"] = float(pt.x()), float(pt.y())
            h, w = (self.arr.shape[:2] if self.arr is not None else (1, 1))
            self.log(i18n.tr("log_point", n=self._pts().index(inc[0]) + 1, px=round(inc[0]["fx"] * w),
                             py=round(inc[0]["fy"] * h), x="%.2f" % inc[0]["X"], y="%.2f" % inc[0]["Y"]))
        self._end_pick()
        self._refresh()
        if self.fit and len(self._complete_points()) >= 3:
            kind = i18n.tr("transfo_sim" if self.fit["kind"] == "similarity" else "transfo_aff").split(" (")[0]
            self.log(i18n.tr("log_fit", kind=kind, n=self.fit["n"], rms="%.2f" % self.fit["rms"]))

    def _cancel_pending(self):
        pts = self.points.get(self.page, [])
        changed = False
        for p in [p for p in pts if p["X"] is None or p["Y"] is None]:
            pts.remove(p)
            changed = True
        if self.canvas.mapTool() is self.pick_tool or self._hidden_for_pick:
            self._end_pick()
        if changed:
            self._refresh()

    def _undo(self):
        pts = self._pts()
        if pts:
            pts.pop()
            if self.canvas.mapTool() is self.pick_tool or self._hidden_for_pick:
                self._end_pick()
            self._refresh()

    def _delete_selected(self):
        r = self.tbl.currentRow()
        pts = self._pts()
        if 0 <= r < len(pts):
            pts.pop(r)
            if not self._incomplete() and self.canvas.mapTool() is self.pick_tool:
                self._end_pick()
            self._refresh()

    def _clear_points(self):
        self.points[self.page] = []
        if self.canvas.mapTool() is self.pick_tool or self._hidden_for_pick:
            self._end_pick()
        self._refresh()

    @staticmethod
    def _parse(text):
        try:
            return float(str(text).replace(" ", "").replace(" ", "").replace(",", "."))
        except ValueError:
            return None

    def _on_item_changed(self, item):
        if self._busy or getattr(self, "_filling", False):
            return
        r, c = item.row(), item.column()
        pts = self._pts()
        if not (0 <= r < len(pts)) or c not in (2, 3):
            return
        pts[r]["X" if c == 2 else "Y"] = self._parse(item.text())
        if not self._incomplete() and self.canvas.mapTool() is self.pick_tool:
            self._end_pick()
        self._refresh()

    # ============================================================ SCR du calage
    def _transform(self, source, target):
        return QgsCoordinateTransform(source, target, QgsProject.instance())

    def _to_out(self, pt):
        """Point du canevas (SCR du projet) -> SCR du calage."""
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if canvas_crs == self.out_crs:
            return pt
        return self._transform(canvas_crs, self.out_crs).transform(pt)

    def _to_canvas(self, x, y):
        """Point en SCR du calage -> SCR du projet (affichage des reperes sur la carte)."""
        pt = QgsPointXY(x, y)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if canvas_crs == self.out_crs:
            return pt
        try:
            return self._transform(self.out_crs, canvas_crs).transform(pt)
        except QgsCsException:
            return pt

    def _on_crs_widget(self, crs):
        """L'utilisateur choisit un SCR : tant qu'il est identique a celui du projet, on le suit."""
        self._crs_follows_project = (crs == self.canvas.mapSettings().destinationCrs())
        self._set_out_crs(crs)

    def _set_out_crs(self, new):
        """Change le SCR du calage : les points deja saisis sont CONVERTIS (ils gardent leur position reelle)."""
        new = QgsCoordinateReferenceSystem(new)
        if not new.isValid() or new == self.out_crs:
            return
        old = self.out_crs
        converted = []
        try:
            tr = self._transform(old, new)
            for pts in self.points.values():
                for p in pts:
                    if p["X"] is not None and p["Y"] is not None:
                        q = tr.transform(QgsPointXY(p["X"], p["Y"]))
                        converted.append((p, q.x(), q.y()))
        except QgsCsException as exc:
            self.log(i18n.tr("log_error", detail=i18n.tr("err_crs_transform", detail=str(exc))))
            self.crs_widget.blockSignals(True)
            self.crs_widget.setCrs(old)
            self.crs_widget.blockSignals(False)
            return
        for p, x, y in converted:
            p["X"], p["Y"] = x, y
        self.out_crs = new
        self.crs_widget.blockSignals(True)
        self.crs_widget.setCrs(new)
        self.crs_widget.blockSignals(False)
        if converted:
            self.log(i18n.tr("log_crs", authid=new.authid() or new.description()))
        self._refresh()

    # ====================================================== couleur transparente
    def _key_rgb(self):
        c = self._key_color
        return (c.red(), c.green(), c.blue())

    def _paint_swatch(self):
        c = self._key_color
        self.btn_swatch.setStyleSheet("QPushButton{background:%s;border:2px solid #7f8c8d;border-radius:3px;}"
                                      "QPushButton:hover{border-color:%s;}" % (c.name(), GREEN))

    def _choose_key_color(self):
        c = QColorDialog.getColor(self._key_color, self, i18n.tr("key_dialog"))
        if c.isValid():
            self._key_color = c
            self._paint_swatch()
            self.sw_key.blockSignals(True)
            self.sw_key.setChecked(True)
            self.sw_key.blockSignals(False)
            self._key_changed()

    def _toggle_pick(self, on):
        self._picking = bool(on)
        self.view.set_cursor_shape(Qt.CursorShape.PointingHandCursor if on else Qt.CursorShape.CrossCursor)
        self._update_hint()

    def _tol_changed(self, v):
        self.lbl_tol_val.setText(str(v))
        self.settings.setValue("CalePlan/key_tol", int(v))
        if self.sw_key.isChecked():
            self._preview_timer.start()
            self._update_recap()

    def _key_changed(self):
        self.settings.setValue("CalePlan/key_color", self._key_color.name())
        if self.sw_key.isChecked():
            self.log(i18n.tr("log_key", color=self._key_color.name().upper(), tol=self.sld_tol.value()))
        self._apply_preview()
        self._update_recap()

    def _apply_preview(self):
        """Apercu de la transparence sur un damier ; calcule sur une version reduite si l'image est grande."""
        if self.arr is None or not self.view.has_image():
            return
        src = self.arr
        step = -(-max(src.shape[:2]) // 3000)
        if step > 1:
            src = src[::step, ::step]
        if self.sw_key.isChecked():
            self.view.replace_image(K.apply_color_key(src, self._key_rgb(), self.sld_tol.value()), True)
        else:
            self.view.replace_image(src, False)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self._picking:
            self.btn_pick.setChecked(False)
            e.accept()
            return
        super().keyPressEvent(e)

    # ============================================================== rafraichir
    def _refresh(self):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if self._crs_follows_project and self.out_crs != canvas_crs:      # le projet a change de SCR
            self._set_out_crs(canvas_crs)
            return
        self._compute_fit()
        self._fill_table()
        pts = self._pts() if self.path else []
        self.view.set_points([(p["fx"], p["fy"], p["X"] is not None and p["Y"] is not None) for p in pts])
        self._redraw_markers()
        for col in (2, 3):
            head = self.tbl.horizontalHeaderItem(col)
            if head is not None:
                head.setToolTip(i18n.tr("col_xy_tip", authid=self.out_crs.authid() or self.out_crs.description()))
        self._update_hint()
        self._update_fit_labels()
        self.chip_points.setText(i18n.tr("chip_points", n=len(self._complete_points())))
        self._update_recap()
        ok = self.fit is not None and not self._incomplete() and not self._busy
        if self.dxf is not None and not (self.chk_out_dxf.isChecked() or self.chk_out_gpkg.isChecked()):
            ok = False
        self.btn_go.setEnabled(bool(ok))
        self.btn_undo.setEnabled(bool(pts))
        if self.lst_pages.count() and 0 <= self.page < self.lst_pages.count():
            self.lst_pages.item(self.page).setText(self._page_text(self.page))

    def _complete_points(self):
        return [p for p in (self._pts() if self.path else []) if p["X"] is not None and p["Y"] is not None]

    def _compute_fit(self):
        self.fit, self.fit_error, self.fit_warn = None, "", ""
        pts = self._complete_points()
        if len(pts) < 2 or self.arr is None:
            return
        h, w = self.arr.shape[:2]
        img = [(p["fx"] * w, p["fy"] * h) for p in pts]
        mp = [(p["X"], p["Y"]) for p in pts]
        try:
            # un dessin DXF n'a aucune deformation de scan : similitude seule (3 points et plus =
            # moindres carres, donc controle par l'ecart), l'affine ne ferait que cacher une erreur de pointe
            method = "similarity" if self.dxf is not None else (self.cmb_transfo.currentData() or "auto")
            res = T.fit(img, mp, method)
        except T.FitError as exc:
            self.fit_error = {"collinear": "err_collinear"}.get(exc.code, "err_coincident")
            return
        info = T.describe(res["gt"])
        if info["mirrored"]:
            self.fit_error = "err_mirror"
            return
        if not self.out_crs.isValid() or self.out_crs.isGeographic():
            self.fit_error = "err_geographic"
            return
        res["info"], res["n"] = info, len(pts)
        res["img"] = img
        dmin = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(img) for b in img[i + 1:])
        if dmin < 0.03 * max(w, h):
            self.fit_warn = "warn_close"
        self.fit = res

    def _fill_table(self):
        self._filling = True
        pts = self._pts() if self.path else []
        res = self.fit["residuals"] if self.fit else None
        self.tbl.setRowCount(len(pts))
        w = self.arr.shape[1] if self.arr is not None else 1
        h = self.arr.shape[0] if self.arr is not None else 1
        cx, cy = self._complete_index_map(pts)
        for i, p in enumerate(pts):
            vals = [str(i + 1), "%d ; %d" % (round(p["fx"] * w), round(p["fy"] * h)),
                    "" if p["X"] is None else "%.2f" % p["X"],
                    "" if p["Y"] is None else "%.2f" % p["Y"], ""]
            if res is not None and i in cx:
                vals[4] = "%.2f" % res[cx.index(i)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c not in (2, 3):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tbl.setItem(i, c, it)
        self._filling = False

    @staticmethod
    def _complete_index_map(pts):
        idx = [i for i, p in enumerate(pts) if p["X"] is not None and p["Y"] is not None]
        return idx, None

    def _redraw_markers(self):
        for m in self._markers:
            self.canvas.scene().removeItem(m)
        self._markers = []
        if not self.path or not self.isVisible() and not self._hidden_for_pick:
            return
        for p in self._complete_points():
            m = QgsVertexMarker(self.canvas)
            m.setCenter(self._to_canvas(p["X"], p["Y"]))
            m.setColor(QColor("#d62828"))
            m.setIconType(ICON_CROSS)
            m.setIconSize(14)
            m.setPenWidth(2)
            self._markers.append(m)

    def _update_hint(self):
        n = len(self._complete_points())
        if self._picking:
            self.lbl_hint.setText(i18n.tr("hint_pick"))
            return
        if not self._incomplete() and self.lbl_status.text() == i18n.tr("status_waiting_map"):
            self.lbl_status.setText(i18n.tr("status_ready"))
        if not self.path:
            txt = i18n.tr("hint_open")
        elif self._incomplete():
            txt = i18n.tr("hint_pending", n=len(self._pts()))
            self.lbl_status.setText(i18n.tr("status_waiting_map"))
        elif n == 0:
            txt = i18n.tr("hint_dxf" if self.dxf is not None else "hint_none")
        elif n == 1:
            txt = i18n.tr("hint_one")
        else:
            txt = i18n.tr("hint_ok", n=n)
        self.lbl_hint.setText(txt)

    def _update_fit_labels(self):
        n = len(self._complete_points())
        if self.fit_error:
            self.lbl_fit.setText("⚠ " + i18n.tr(self.fit_error))
            self.lbl_fit2.setText("")
            return
        if not self.fit:
            self.lbl_fit.setText(i18n.tr("fit_none"))
            self.lbl_fit2.setText("")
            return
        f = self.fit
        self.lbl_fit.setText(i18n.tr("fit_sim" if f["kind"] == "similarity" else "fit_aff", n=f["n"]))
        lines = []
        if f["n"] >= 3 and not (f["kind"] == "affine" and f["n"] == 3):
            lines.append(i18n.tr("fit_rms", v="%.2f" % f["rms"]))
        elif f["kind"] == "affine" and f["n"] == 3:
            lines.append(i18n.tr("fit_exact"))
        px = f["info"]["pixel_x"]
        if self.dxf is not None and self.dxf.geo is not None:
            lines.append(i18n.tr("fit_dxf", k="%.6g" % (px / self.dxf.geo[2]), rot="%.1f" % f["info"]["rotation"]))
        else:
            lines.append(i18n.tr("fit_pixel", px=("%.3f" % px).rstrip("0").rstrip("."),
                                 rot="%.1f" % f["info"]["rotation"]))
        if self.fit_warn:
            lines.append("⚠ " + i18n.tr(self.fit_warn))
        self.lbl_fit2.setText("\n".join(lines))

    def _update_recap(self):
        """Ligne de synthese sous les colonnes (meme principe qu'Export Layers)."""
        if not self.path:
            self.lbl_recap.setText(i18n.tr("recap_none"))
            return
        n = len(self._complete_points())
        page = (i18n.tr("page_item", n=self.page + 1) if R.is_pdf(self.path) and self.n_pages > 1
                else os.path.basename(self.path))
        parts = [i18n.tr("recap_points", page=page, n=n)]
        if self.fit:
            kind = i18n.tr("transfo_sim" if self.fit["kind"] == "similarity" else "transfo_aff").split(" (")[0]
            parts.append("<b style=\"color:%s\">%s</b>" % (GREEN, kind))
            if self.dxf is not None and self.dxf.geo is not None:
                parts.append(i18n.tr("fit_dxf", k="%.6g" % (self.fit["info"]["pixel_x"] / self.dxf.geo[2]),
                                     rot="%.1f" % self.fit["info"]["rotation"]))
            else:
                px = ("%.3f" % self.fit["info"]["pixel_x"]).rstrip("0").rstrip(".")
                parts.append(i18n.tr("fit_pixel", px=px, rot="%.1f" % self.fit["info"]["rotation"]))
        parts.append(self.out_crs.authid() or self.out_crs.description())
        if self.sw_key.isChecked() and self.dxf is None:
            parts.append(i18n.tr("recap_key", color=self._key_color.name().upper(), tol=self.sld_tol.value()))
        if self.chk_add.isChecked():
            parts.append("<b style=\"color:%s\">%s</b>" % (GREEN, i18n.tr("recap_added")))
        if self.dxf is None and not self.chk_save.isChecked():
            parts.append(i18n.tr("recap_temp"))
        name = self.edt_name.text().strip()
        text = " · ".join(parts)
        if name:
            text += " → <b>%s</b>" % name
        self.lbl_recap.setText(text)

    # ================================================================== calage
    def _go(self):
        if not self.fit or self._busy:
            return
        if self.dxf is not None:
            self._go_dxf()
            return
        name = _sanitize(self.edt_name.text())
        if not name:
            QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr("err_no_name"))
            return
        if not name.lower().endswith((".tif", ".tiff")):
            name += ".tif"
        self._saving = self.chk_save.isChecked()
        folder = (self.edt_folder.text().strip() or self._default_folder()) if self._saving else self._temp_folder()
        out = os.path.join(folder, name)
        known = (not self._saving) or self._norm(out) in self._written or bool(self._layers_for(out))
        if os.path.exists(out) and not known:       # fichier etranger : on demande ; le notre se remplace
            ans = QMessageBox.question(self, i18n.tr("err_title"), i18n.tr("confirm_overwrite", name=name))
            if ans != QMessageBox.StandardButton.Yes:
                return
        crs = QgsCoordinateReferenceSystem(self.out_crs)
        # Ecriture dans un fichier temporaire voisin : si elle echoue, l'ancien calage reste intact ;
        # le fichier definitif est remplace seulement apres avoir retire l'ancienne couche (verrou Windows).
        tmp = os.path.splitext(out)[0] + ".part.tif"
        self._tmp = tmp
        self._set_busy(True)
        self.lbl_status.setText(i18n.tr("status_writing"))
        # Ecriture dans un fil : l'interface reste libre, aucun processEvents() rappele depuis
        # le callback de GDAL (c'etait la cause d'un plantage natif dans QGIS).
        key = (self._key_rgb(), self.sld_tol.value()) if self.sw_key.isChecked() else None
        worker = WriteWorker(self.arr, self.fit["gt"], crs.toWkt(), tmp, key, self)
        worker.progressed.connect(self.progress.setValue)
        out_key = (self.path, self.page)
        worker.succeeded.connect(lambda warped: self._write_done(out, tmp, name, folder, crs, warped, out_key))
        worker.failed.connect(self._write_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    # ---------------------------------------------------------------- calage d'un DXF
    def _go_dxf(self):
        want_dxf, want_gpkg = self.chk_out_dxf.isChecked(), self.chk_out_gpkg.isChecked()
        if not (want_dxf or want_gpkg):
            QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr("err_no_output"))
            return
        stem = _sanitize(os.path.splitext(self.edt_name.text())[0])
        if not stem:
            QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr("err_no_name"))
            return
        folder = self.edt_folder.text().strip() or self._default_folder()
        out_dxf = os.path.join(folder, stem + ".dxf")
        out_gpkg = os.path.join(folder, stem + ".gpkg")
        if want_dxf and self._norm(out_dxf) == self._norm(self.path):      # jamais ecraser le DXF d'origine
            stem += "_cale"
            out_dxf = os.path.join(folder, stem + ".dxf")
            out_gpkg = os.path.join(folder, stem + ".gpkg")
        targets = ([out_dxf] if want_dxf else []) + ([out_gpkg] if want_gpkg else [])
        for t in targets:
            known = self._norm(t) in self._written or bool(DL.vector_layers_for(QgsProject.instance(), t, self._norm))
            if os.path.exists(t) and not known:
                ans = QMessageBox.question(self, i18n.tr("err_title"),
                                           i18n.tr("confirm_overwrite", name=os.path.basename(t)))
                if ans != QMessageBox.StandardButton.Yes:
                    return
        os.makedirs(folder, exist_ok=True)
        crs = QgsCoordinateReferenceSystem(self.out_crs)
        matrix = DX.pixel_gt_to_dxf_matrix(self.fit["gt"], self.dxf.geo)
        # Fichiers temporaires voisins : un echec laisse les anciens fichiers intacts.
        tmp_dxf = (os.path.join(folder, stem + ".part.dxf") if want_dxf
                   else os.path.join(tempfile.gettempdir(), "caleplan_%d.part.dxf" % os.getpid()))
        tmp_gpkg = os.path.join(folder, stem + ".part.gpkg") if want_gpkg else None
        self._ctx = {"out_dxf": out_dxf, "out_gpkg": out_gpkg, "tmp_dxf": tmp_dxf, "tmp_gpkg": tmp_gpkg,
                     "want_dxf": want_dxf, "want_gpkg": want_gpkg, "stem": stem, "folder": folder, "crs": crs}
        # Repartition de la barre : DXF recale, GeoPackage, puis creation des couches dans QGIS (la plus lente)
        adding = want_gpkg and self.chk_add.isChecked()
        if adding:
            self._plan = {"dxf": (0, 30), "gpkg": (30, 20), "layers": (50, 50)}
        elif want_gpkg:
            self._plan = {"dxf": (0, 60), "gpkg": (60, 40)}
        else:
            self._plan = {"dxf": (0, 100)}
        self._set_busy(True)
        self.lbl_status.setText(i18n.tr("status_writing_dxf"))
        worker = DxfWorker(self.path, matrix, tmp_dxf, tmp_gpkg, crs.toWkt(), self)
        worker.progressed.connect(self._dxf_progress)
        worker.succeeded.connect(self._dxf_done)
        worker.failed.connect(self._dxf_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _dxf_progress(self, stage, pct):
        start, width = self._plan.get(stage, (0, 100))
        self.progress.setValue(int(start + width * pct / 100.0))
        self.lbl_status.setText(i18n.tr("status_writing_gpkg" if stage == "gpkg" else "status_writing_dxf"))

    def _dxf_cleanup(self):
        ctx = getattr(self, "_ctx", None) or {}
        for key in ("tmp_dxf", "tmp_gpkg"):
            tmp = ctx.get(key)
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass                                  # fichier verrouille : il sera remplace au prochain essai

    def _dxf_failed(self, detail):
        self._worker = None
        self._dxf_cleanup()
        self._set_busy(False)
        self.log(i18n.tr("log_error", detail=detail))
        QMessageBox.critical(self, i18n.tr("err_title"), i18n.tr("err_write", detail=detail))

    def _dxf_done(self, res):
        self._worker = None
        ctx = self._ctx
        project = QgsProject.instance()
        place = None
        replaced = False
        if ctx["want_gpkg"]:
            old = DL.vector_layers_for(project, ctx["out_gpkg"], self._norm)
            replaced = bool(old)
            place = DL.take_old(project, old, ctx["out_gpkg"], self._norm)   # retirees AVANT d'ecraser le fichier (verrou Windows)
        for want, tmp, out in ((ctx["want_dxf"], ctx["tmp_dxf"], ctx["out_dxf"]),
                               (ctx["want_gpkg"], ctx["tmp_gpkg"], ctx["out_gpkg"])):
            if want and not self._swap(tmp, out):
                self._dxf_cleanup()
                self._set_busy(False)
                QMessageBox.critical(self, i18n.tr("err_title"), i18n.tr("err_write", detail=out))
                return
            if want:
                self._written.add(self._norm(out))
        self._dxf_cleanup()                               # il ne reste que le DXF temporaire inutile (GPKG seul)
        self.settings.setValue("CalePlan/out_dir", ctx["folder"])
        files = []
        if ctx["want_dxf"]:
            files.append(os.path.basename(ctx["out_dxf"]))
        if ctx["want_gpkg"]:
            files.append(os.path.basename(ctx["out_gpkg"]))
        ctx["files"] = files
        ctx["replaced"] = replaced
        tables = res.get("counts") or []
        if ctx["want_gpkg"]:
            n_calques = len({t["calque"] for t in tables})
            self.log(i18n.tr("log_gpkg", counts=i18n.tr("gpkg_summary", layers=n_calques,
                                                         objects=sum(t["count"] for t in tables))))
            if self.chk_add.isChecked() or place is not None:
                # Les couches se creent UNE PAR UNE, la main revenant a l'interface entre deux : la barre
                # avance et la fenetre reste vivante (aucun processEvents).
                group = _sanitize(os.path.splitext(os.path.basename(self.path))[0]) or ctx["stem"]
                if "layers" not in self._plan:
                    self._plan["layers"] = (self.progress.value(), 100 - self.progress.value())
                ctx["place"] = place
                self._builder = DL.Builder(project, ctx["out_gpkg"], tables, group, ctx["crs"], self._norm, place)
                self._build_step(res)
                return
        self._dxf_finish(res, None)

    def _build_step(self, res):
        b = self._builder
        if b is None:
            return
        try:
            finished = b.step()
        except RuntimeError as exc:           # couche refusee par QGIS : on passe, le reste du groupe reste utile
            self.log(i18n.tr("log_error", detail=str(exc)))
            finished = b.done >= b.total
        start, width = self._plan.get("layers", (0, 100))
        self.progress.setValue(int(start + width * b.done / max(1, b.total)))
        self.lbl_status.setText(i18n.tr("status_adding_layers", n=b.done, total=b.total))
        if not finished:
            QTimer.singleShot(0, lambda: self._build_step(res))     # rend la main a la boucle d'evenements
            return
        added = b.added
        self._builder = None
        if self._ctx.get("place") is None and added:
            DL.zoom_to(self.canvas, added)
        self._dxf_finish(res, added)

    def _dxf_finish(self, res, added):
        ctx = self._ctx
        extra = ""
        if added is not None:
            extra += i18n.tr("done_dxf_layers", n=len(added))
            if ctx.get("replaced"):
                extra += i18n.tr("done_dxf_replaced")
            self.canvas.refresh()
        if res.get("dropped"):
            extra += i18n.tr("done_dxf_dropped", n=res["dropped"])
        self._set_busy(False)
        msg = i18n.tr("done_dxf", files=" + ".join(ctx["files"]), extra=extra)
        self.lbl_status.setText(msg)
        for f in (ctx["out_dxf"] if ctx["want_dxf"] else None, ctx["out_gpkg"] if ctx["want_gpkg"] else None):
            if f:
                self.log(i18n.tr("log_written", path=f))
        self.iface.messageBar().pushSuccess("CalePlan", msg)

    @staticmethod
    def _norm(path):
        return os.path.normcase(os.path.abspath(path))

    def _layers_for(self, *paths):
        """Couches raster du projet qui lisent l'un de ces fichiers."""
        wanted = {self._norm(p) for p in paths if p}
        found = []
        for lay in QgsProject.instance().mapLayers().values():
            if isinstance(lay, QgsRasterLayer):
                src = lay.source().split("|")[0]
                if src and self._norm(src) in wanted:
                    found.append(lay)
        return found

    @staticmethod
    def _swap(tmp, out):
        """Remplace `out` par `tmp` (quelques essais : Windows garde le fichier verrouille un instant)."""
        for _ in range(30):
            try:
                if os.path.exists(out + ".aux.xml"):
                    os.remove(out + ".aux.xml")       # anciennes statistiques : fausses pour le nouveau calage
                os.replace(tmp, out)
                return True
            except PermissionError:
                time.sleep(0.1)
        return False

    def _write_failed(self, detail):
        self._worker = None
        self._drop_tmp()
        self._set_busy(False)
        self.log(i18n.tr("log_error", detail=detail))
        QMessageBox.critical(self, i18n.tr("err_title"), i18n.tr("err_write", detail=detail))

    def _drop_tmp(self):
        if self._tmp and os.path.exists(self._tmp):
            try:
                os.remove(self._tmp)
            except OSError:
                pass
        self._tmp = None

    def _write_done(self, out, tmp, name, folder, crs, warped, key):
        self._worker = None
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        # Recalage d'une image deja calee : l'ancienne couche est remplacee (meme place, meme nom,
        # meme opacite, meme visibilite) au lieu d'en ajouter une seconde.
        old = self._layers_for(out, self._outputs.get(key))
        info = None
        if old:
            node = root.findLayer(old[0].id())
            parent = node.parent() if node is not None else root
            info = {"name": old[0].name(), "opacity": old[0].opacity(),
                    "visible": node.isVisible() if node is not None else True,
                    "parent": parent,
                    "index": parent.children().index(node) if node is not None else 0}
            for lay in old:
                project.removeMapLayer(lay.id())
        if not self._swap(tmp, out):
            self._set_busy(False)
            QMessageBox.critical(self, i18n.tr("err_title"), i18n.tr("err_write", detail=out))
            return
        self._tmp = None
        if self._saving:
            self.settings.setValue("CalePlan/out_dir", folder)
        self._outputs[key] = out
        self._written.add(self._norm(out))
        extra = ""
        if info is not None or self.chk_add.isChecked() or not self._saving:    # sans fichier garde, la couche est la seule trace
            layer = QgsRasterLayer(out, info["name"] if info else os.path.splitext(name)[0])
            if layer.isValid():
                layer.setCrs(crs)
                if info is not None:
                    layer.setOpacity(info["opacity"])
                    project.addMapLayer(layer, False)
                    parent = info["parent"]
                    parent.insertLayer(min(info["index"], len(parent.children())), layer)
                    new_node = root.findLayer(layer.id())
                    if new_node is not None:
                        new_node.setItemVisibilityChecked(info["visible"])
                    extra = i18n.tr("done_replaced")
                else:
                    layer.setOpacity(self.sld_opacity.value() / 100.0)
                    project.addMapLayer(layer)
                    ext = layer.extent()
                    canvas_crs = self.canvas.mapSettings().destinationCrs()
                    if layer.crs() != canvas_crs:
                        try:
                            ext = self._transform(layer.crs(), canvas_crs).transformBoundingBox(ext)
                        except QgsCsException:
                            pass                        # on garde l'emprise telle quelle
                    self.canvas.setExtent(ext)
                    extra = i18n.tr("done_added")
                self.canvas.refresh()
        if warped:
            extra += i18n.tr("done_resampled")
        if not self._saving:
            extra += i18n.tr("done_temp")
        self._set_busy(False)
        msg = i18n.tr("done", name=name, extra=extra)
        self.lbl_status.setText(msg)
        self.log(i18n.tr("log_written", path=out))
        self.iface.messageBar().pushSuccess("CalePlan", msg)

    def _set_busy(self, busy):
        self._busy = busy
        self.progress.setValue(0)
        for w in (self.btn_open, self.cmb_dpi, self.lst_pages, self.btn_go, self.view):
            w.setEnabled(not busy)

    def _error_box(self, exc):
        key = {"no_pdf_backend": "err_no_backend", "encrypted": "err_encrypted",
               "bad_page": "err_bad_page"}.get(exc.code, "err_open")
        QMessageBox.warning(self, i18n.tr("err_title"), i18n.tr(key, detail=exc.detail or exc.code))

    # =================================================================== cycle
    def showEvent(self, e):
        super().showEvent(e)
        self._redraw_markers()

    def hideEvent(self, e):
        super().hideEvent(e)
        if not self._hidden_for_pick:           # fermeture reelle : on nettoie le canevas
            for m in self._markers:
                self.canvas.scene().removeItem(m)
            self._markers = []

    def closeEvent(self, e):
        self._cancel_pending()
        super().closeEvent(e)

    def shutdown(self):
        """Appele au dechargement du plugin."""
        self._thumb_todo = []
        self._preview_timer.stop()
        if self._worker is not None:
            self._worker.wait(30000)
        if self._installer is not None:
            self._installer.wait(60000)
        if self._loader is not None:
            self._loader.wait(60000)
        self._builder = None
        self._hidden_for_pick = False
        self._cancel_pending()
        for m in self._markers:
            self.canvas.scene().removeItem(m)
        self._markers = []
        self.close()
