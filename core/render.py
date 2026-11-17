"""Lecture des PDF (page par page) et des images, en tableaux numpy RGB.

Moteurs PDF, dans l'ordre :
  1. PyMuPDF (module `pymupdf` ou `fitz`), s'il est installe : rapide et fiable ;
  2. pilote GDAL « PDF » (poppler / pdfium) fourni avec QGIS ;
  3. sinon, message d'erreur clair (RenderError 'no_pdf_backend').

Le tout est protege par gdal.ExceptionMgr : on ne touche jamais au mode d'exceptions
global de GDAL, qui est partage avec les autres extensions.
"""
import contextlib
import os

import numpy as np
from osgeo import gdal

PDF_EXT = (".pdf",)
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif")
MAX_SIDE = 12000          # cote maximum (pixels) du rendu : au-dela, la resolution est reduite
_force_backend = None     # "gdal" pour tester le moteur de secours


class RenderError(Exception):
    """Lecture impossible ; `code` sert a choisir le message traduit."""

    def __init__(self, code, detail=""):
        super().__init__(code if not detail else "%s : %s" % (code, detail))
        self.code = code
        self.detail = detail


@contextlib.contextmanager
def _gdal_exceptions():
    """Exceptions GDAL actives le temps du bloc, sans toucher a l'etat global."""
    mgr = getattr(gdal, "ExceptionMgr", None)
    if mgr is not None:
        with mgr(useExceptions=True):
            yield
        return
    previous = gdal.GetUseExceptions()
    gdal.UseExceptions()
    try:
        yield
    finally:
        if not previous:
            gdal.DontUseExceptions()


def _import_pymupdf():
    if _force_backend == "gdal":
        return None
    try:
        import pymupdf
        return pymupdf
    except (ImportError, OSError):          # absent, ou binaire incompatible avec ce Python
        pass
    try:
        import fitz
        if hasattr(fitz, "open"):
            return fitz
    except (ImportError, OSError):
        pass
    return None


def pdf_backend():
    """'pymupdf', 'gdal' ou None."""
    if _import_pymupdf() is not None:
        return "pymupdf"
    if gdal.GetDriverByName("PDF") is not None:
        return "gdal"
    return None


def is_pdf(path):
    return os.path.splitext(path)[1].lower() in PDF_EXT


def is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXT


# --------------------------------------------------------------------------- PDF
def _open_mupdf(path):
    mu = _import_pymupdf()
    try:
        doc = mu.open(path)
    except Exception as exc:
        raise RenderError("open_failed", str(exc))
    if getattr(doc, "needs_pass", False):
        doc.close()
        raise RenderError("encrypted")
    return doc


def _gdal_open_page(path, page, dpi):
    """Le pilote PDF de GDAL choisit la page par un nom de sous-jeu « PDF:n:fichier »
    (l'option PAGE n'existe pas : elle est ignoree et rend toujours la page 1)."""
    return gdal.OpenEx("PDF:%d:%s" % (page + 1, path), gdal.OF_RASTER,
                       open_options=["DPI=%s" % dpi])


def page_count(path):
    if not is_pdf(path):
        return 1
    backend = pdf_backend()
    if backend == "pymupdf":
        doc = _open_mupdf(path)
        try:
            return doc.page_count
        finally:
            doc.close()
    if backend == "gdal":
        with _gdal_exceptions():
            try:
                ds = gdal.OpenEx(path, gdal.OF_RASTER, open_options=["DPI=20"])
            except RuntimeError as exc:
                raise RenderError("open_failed", str(exc))
            subs = ds.GetMetadata("SUBDATASETS") or {}
            ds = None
        n = sum(1 for k in subs if k.endswith("_NAME"))
        return max(1, n)       # PDF d'une page : pas de sous-jeux
    raise RenderError("no_pdf_backend")


def page_size_mm(path, page=0):
    """(largeur, hauteur) de la page en millimetres, ou None si inconnu."""
    if not is_pdf(path):
        return None
    try:
        backend = pdf_backend()
        if backend == "pymupdf":
            doc = _open_mupdf(path)
            try:
                r = doc[page].rect
                return r.width / 72.0 * 25.4, r.height / 72.0 * 25.4
            finally:
                doc.close()
        if backend == "gdal":
            with _gdal_exceptions():
                ds = _gdal_open_page(path, page, 72)
                return ds.RasterXSize / 72.0 * 25.4, ds.RasterYSize / 72.0 * 25.4
    except Exception:
        return None
    return None


def _render_pdf(path, page, dpi, max_side):
    backend = pdf_backend()
    if backend == "pymupdf":
        mu = _import_pymupdf()
        doc = _open_mupdf(path)
        try:
            if not 0 <= page < doc.page_count:
                raise RenderError("bad_page", str(page + 1))
            pg = doc[page]
            r = pg.rect
            scale = dpi / 72.0
            longest = max(r.width, r.height) * scale
            if longest > max_side:
                scale *= max_side / longest
            pix = pg.get_pixmap(matrix=mu.Matrix(scale, scale), colorspace=mu.csRGB, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
            return arr, scale * 72.0
        finally:
            doc.close()
    if backend == "gdal":
        with _gdal_exceptions():
            try:
                probe = _gdal_open_page(path, page, 72)
            except RuntimeError as exc:
                raise RenderError("open_failed", str(exc))
            longest = max(probe.RasterXSize, probe.RasterYSize) * dpi / 72.0
            probe = None
            use_dpi = dpi if longest <= max_side else dpi * max_side / longest
            ds = _gdal_open_page(path, page, round(use_dpi, 2))
            return _dataset_to_array(ds), float(use_dpi)
    raise RenderError("no_pdf_backend")


# ------------------------------------------------------------------------ images
def _dataset_to_array(ds, buf=None):
    """Convertit un dataset GDAL en tableau (h, w, 3) uint8 (palette, gris, RGBA geres)."""
    w, h = (buf if buf else (ds.RasterXSize, ds.RasterYSize))
    count = ds.RasterCount
    bands = []
    for i in range(1, min(count, 4) + 1):
        a = ds.GetRasterBand(i).ReadAsArray(buf_xsize=w, buf_ysize=h)
        bands.append(a)
    first = ds.GetRasterBand(1)
    if count == 1 and first.GetColorTable() is not None:
        ct = first.GetColorTable()
        lut = np.array([ct.GetColorEntry(i)[:3] for i in range(ct.GetCount())], dtype=np.uint8)
        idx = np.clip(bands[0], 0, len(lut) - 1)
        return lut[idx]
    if count == 1:
        bands = [bands[0]] * 3
    elif count == 2:
        bands = [bands[0]] * 3
    arr = np.dstack(bands[:3])
    if arr.dtype != np.uint8:
        lo, hi = float(arr.min()), float(arr.max())
        arr = ((arr.astype(np.float64) - lo) / max(hi - lo, 1e-9) * 255).astype(np.uint8)
    return arr


def _render_image(path, max_side):
    with _gdal_exceptions():
        try:
            ds = gdal.Open(path)
        except RuntimeError as exc:
            raise RenderError("open_failed", str(exc))
        w, h = ds.RasterXSize, ds.RasterYSize
        k = min(1.0, max_side / float(max(w, h)))
        buf = (max(1, int(w * k)), max(1, int(h * k)))
        return _dataset_to_array(ds, buf)


# ------------------------------------------------------------------- point d'entree
def render(path, page=0, dpi=150, max_side=MAX_SIDE):
    """Retourne (tableau RGB uint8, dpi reellement utilise ou None pour une image)."""
    if not os.path.isfile(path):
        raise RenderError("not_found", path)
    if is_pdf(path):
        return _render_pdf(path, page, float(dpi), max_side)
    return _render_image(path, max_side), None


def thumbnail(path, page=0, long_side=200):
    """Vignette basse resolution (tableau RGB)."""
    if is_pdf(path):
        size = page_size_mm(path, page)
        longest_in = (max(size) / 25.4) if size else 12.0
        dpi = max(8.0, long_side / longest_in)
        return render(path, page, dpi, max_side=long_side * 2)[0]
    return _render_image(path, long_side * 2)
