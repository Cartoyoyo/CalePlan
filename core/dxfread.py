"""Lecture d'un DXF (ezdxf) et rendu en image pour poser les reperes.

Le DXF est lu une fois : traits (par couleur), textes, points d'accroche. `render()` en fait une
image RGB (fond blanc) et renvoie la correspondance exacte pixel <-> unites du dessin :

    px = (x - x0) / s          py = (y1 - y) / s          (y image vers le bas)

Le calage se fait donc comme pour un plan en pixels ; `to_pixel()` / `to_dxf()` font le lien, et
`snap()` ramene un clic sur le sommet du dessin le plus proche (precision du vecteur, pas du pixel).
"""
import math

import numpy as np

from . import deps

MAX_VERTICES = 4_000_000        # au-dela, le reste du dessin est ignore (l'apercu reste utilisable)
MAX_TEXTS = 20000
DEFAULT_RGB = (0, 0, 0)


class DxfError(Exception):
    """Lecture impossible ; `code` sert a choisir le message traduit."""

    def __init__(self, code, detail=""):
        super().__init__(code if not detail else "%s : %s" % (code, detail))
        self.code = code
        self.detail = detail


def available():
    """True si ezdxf est importable (installation a la demande, voir deps.py)."""
    return not deps.missing()


def _rgb_of(entity, layer_rgb):
    """Couleur d'un objet : vraie couleur, sinon indice ACI, sinon couleur du calque."""
    from ezdxf.colors import aci2rgb
    try:
        dxf = entity.dxf
        if dxf.hasattr("true_color") and dxf.true_color:
            tc = int(dxf.true_color)
            return ((tc >> 16) & 255, (tc >> 8) & 255, tc & 255)
        if dxf.hasattr("color"):
            aci = int(dxf.color)
            if 1 <= aci <= 255:
                return tuple(aci2rgb(aci))
    except (AttributeError, ValueError, TypeError):
        pass
    return layer_rgb


def _on_paper(rgb):
    """Blanc / quasi blanc : invisible sur fond blanc, on le dessine en noir comme AutoCAD."""
    return (0, 0, 0) if min(rgb) > 235 else tuple(rgb)


class DxfData:
    def __init__(self):
        self.strokes = {}            # rgb -> [ndarray (n, 2)]
        self.texts = []              # (rgb, x, y, texte, hauteur, rotation en degres)
        self.dots = []               # (rgb, x, y)
        self.snap_pts = []           # [(x, y)] -> self.snap_arr
        self.snap_arr = np.zeros((0, 2))
        self.bounds = None           # (x0, y0, x1, y1) utilises pour l'image
        self.full_bounds = None
        self.outliers = 0
        self.n_entities = 0
        self.n_vertices = 0
        self.partial = False
        self.skipped = 0
        self.layers = 0
        self.geo = None              # (x0, y1, s) de la derniere image


def load(path, progress=None):
    """Lit le DXF (modele uniquement). Leve DxfError. `progress(fraction 0..1)` est appele regulierement
    (depuis le fil qui lit : aucun objet Qt n'est touche ici)."""
    def tick(f):
        if progress is not None:
            progress(min(1.0, max(0.0, f)))
    tick(0.0)
    if not available():
        raise DxfError("no_ezdxf")
    import ezdxf
    from ezdxf import path as ezpath
    try:
        doc = ezdxf.readfile(path)
    except (OSError, ezdxf.DXFError) as exc:
        raise DxfError("open_failed", str(exc))
    except Exception as exc:        # fichier tronque / encodage : ezdxf leve des types varies
        raise DxfError("open_failed", "%s: %s" % (type(exc).__name__, exc))

    tick(0.4)
    data = DxfData()
    from ezdxf.colors import aci2rgb
    layer_rgb = {}
    for lay in doc.layers:
        try:
            aci = abs(int(lay.color))
            layer_rgb[str(lay.dxf.name)] = tuple(aci2rgb(aci if 1 <= aci <= 255 else 7))
        except (AttributeError, ValueError, TypeError):
            layer_rgb[str(lay.dxf.name)] = (255, 255, 255)
    data.layers = len(layer_rgb)

    diag = 0.0
    try:
        from ezdxf import bbox
        bb = bbox.extents(doc.modelspace(), fast=True)
        if bb.has_data:
            diag = float((bb.extmax - bb.extmin).magnitude)
    except Exception:       # bbox sur objets exotiques : seule la finesse des courbes en depend
        diag = 0.0
    flat = (diag / 4000.0) if diag > 0 else 0.05

    snap = data.snap_pts

    def add_stroke(rgb, pts):
        if data.n_vertices > MAX_VERTICES:
            data.partial = True
            return
        a = np.asarray(pts, dtype=float).reshape(-1, 2)
        if len(a) >= 2:
            data.strokes.setdefault(_on_paper(rgb), []).append(a)
            data.n_vertices += len(a)

    def draw(e, rgb_layer, depth=0):
        rgb = _rgb_of(e, rgb_layer)
        t = e.dxftype()
        if t == "LINE":
            s, en = e.dxf.start, e.dxf.end
            add_stroke(rgb, [(s.x, s.y), (en.x, en.y)])
            snap.extend(((s.x, s.y), (en.x, en.y)))
        elif t == "LWPOLYLINE":
            pts5 = list(e.get_points("xyb"))
            xy = [(p[0], p[1]) for p in pts5]
            snap.extend(xy)
            if any(abs(p[2]) > 1e-12 for p in pts5):
                pth = ezpath.make_path(e)
                add_stroke(rgb, [(v.x, v.y) for v in pth.flattening(flat)])
            else:
                if e.closed and xy:
                    xy = xy + [xy[0]]
                add_stroke(rgb, xy)
        elif t == "POLYLINE":
            if getattr(e, "is_poly_face_mesh", False) or getattr(e, "is_polygon_mesh", False):
                return
            pth = ezpath.make_path(e)
            add_stroke(rgb, [(v.x, v.y) for v in pth.flattening(flat)])
            for v in e.vertices:
                loc = v.dxf.location
                snap.append((loc.x, loc.y))
        elif t in ("ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
            pth = ezpath.make_path(e)
            add_stroke(rgb, [(v.x, v.y) for v in pth.flattening(flat)])
            if t == "CIRCLE":
                snap.append((e.dxf.center.x, e.dxf.center.y))
            elif t == "ARC":
                snap.append((e.dxf.center.x, e.dxf.center.y))
                snap.append((pth.start.x, pth.start.y))
                snap.append((pth.end.x, pth.end.y))
        elif t == "HATCH":
            for pth in ezpath.make_path(e).sub_paths():
                add_stroke(rgb, [(v.x, v.y) for v in pth.flattening(flat)])
        elif t in ("SOLID", "TRACE", "3DFACE"):
            vs = [e.dxf.get("vtx%d" % i) for i in range(4)]
            vs = [(v.x, v.y) for v in vs if v is not None]
            if len(vs) == 4:                      # SOLID / TRACE : l'ordre des sommets est en Z
                vs = [vs[0], vs[1], vs[3], vs[2]]
            if vs:
                add_stroke(rgb, vs + [vs[0]])
        elif t == "POINT":
            loc = e.dxf.location
            data.dots.append((_on_paper(rgb), loc.x, loc.y))
            snap.append((loc.x, loc.y))
        elif t in ("TEXT", "ATTRIB", "ATTDEF", "MTEXT"):
            loc = e.dxf.insert
            if t == "MTEXT":
                txt = e.plain_text()
                height = float(e.dxf.get("char_height", 0) or 0)
                rot = float(e.dxf.get("rotation", 0) or 0)
                if not rot and e.dxf.hasattr("text_direction"):
                    d = e.dxf.text_direction
                    rot = math.degrees(math.atan2(d.y, d.x))
            else:
                txt = str(e.dxf.text)
                height = float(e.dxf.get("height", 0) or 0)
                rot = float(e.dxf.get("rotation", 0) or 0)
            if len(data.texts) < MAX_TEXTS:
                data.texts.append((_on_paper(rgb), loc.x, loc.y, txt.replace("\n", " "), height, rot))
            snap.append((loc.x, loc.y))
        elif t == "INSERT" and depth < 3:
            snap.append((e.dxf.insert.x, e.dxf.insert.y))
            try:
                subs = list(e.virtual_entities())
            except Exception:    # bloc vide / echelle nulle (ZeroDivisionError d'ezdxf) : on montre au moins son point
                data.dots.append((_on_paper(rgb), e.dxf.insert.x, e.dxf.insert.y))
                data.skipped += 1
                return
            for sub in subs:
                try:
                    draw(sub, rgb, depth + 1)         # couleur de l'INSERT pour les objets du bloc "par calque"
                except Exception:    # un objet de bloc illisible ne doit pas arreter la lecture
                    data.skipped += 1
        elif t == "DIMENSION" and depth < 3:
            try:
                for sub in e.virtual_entities():
                    draw(sub, rgb_layer, depth + 1)
            except Exception:
                data.skipped += 1

    entities = list(doc.modelspace())
    total = max(1, len(entities))
    for i, e in enumerate(entities):
        if i % 200 == 0:
            tick(0.4 + 0.55 * i / total)
        data.n_entities += 1
        try:
            lay = str(e.dxf.layer)
        except (AttributeError, ValueError):
            lay = "0"
        try:
            draw(e, layer_rgb.get(lay, (255, 255, 255)))
        except Exception:        # objet exotique : on le saute, on le signale dans le journal
            data.skipped += 1

    tick(0.97)
    data.snap_arr = np.asarray(snap, dtype=float).reshape(-1, 2)
    _set_bounds(data)
    tick(1.0)
    if data.bounds is None:
        raise DxfError("empty")
    return data


def _all_xy(data):
    parts = [a for lst in data.strokes.values() for a in lst]
    parts.append(np.asarray([(d[1], d[2]) for d in data.dots], dtype=float).reshape(-1, 2))
    parts.append(np.asarray([(t[1], t[2]) for t in data.texts], dtype=float).reshape(-1, 2))
    parts = [p for p in parts if len(p)]
    return np.vstack(parts) if parts else np.zeros((0, 2))


def _set_bounds(data):
    xy = _all_xy(data)
    xy = xy[np.isfinite(xy).all(axis=1)]
    if not len(xy):
        return
    full = (float(xy[:, 0].min()), float(xy[:, 1].min()), float(xy[:, 0].max()), float(xy[:, 1].max()))
    data.full_bounds = data.bounds = full
    if len(xy) < 50:
        return
    # objets egares tres loin du dessin (un point oublie a 0,0 par exemple) : ils ecrasent
    # tout le reste. Le coeur (1 % a 99 %) agrandi de 2 fois sa taille sert de cadre.
    lo = np.percentile(xy, 1, axis=0)
    hi = np.percentile(xy, 99, axis=0)
    size = np.maximum(hi - lo, 1e-9)
    inside = ((xy >= lo - 2 * size) & (xy <= hi + 2 * size)).all(axis=1)
    n_out = int((~inside).sum())
    if n_out and inside.sum() > 0:
        k = xy[inside]
        core = (float(k[:, 0].min()), float(k[:, 1].min()), float(k[:, 0].max()), float(k[:, 1].max()))
        if (core[2] - core[0]) * (core[3] - core[1]) < 0.25 * (full[2] - full[0]) * (full[3] - full[1]):
            data.bounds, data.outliers = core, n_out


# --------------------------------------------------------------------------- image
def render(data, long_side=3000, margin=0.02):
    """Retourne le tableau (h, w, 3) uint8 ; `data.geo = (x0, y1, s)` donne la correspondance."""
    from qgis.PyQt.QtCore import QPointF, Qt
    from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF

    x0, y0, x1, y1 = data.bounds
    w_u, h_u = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    pad = margin * max(w_u, h_u)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    w_u, h_u = x1 - x0, y1 - y0
    s = max(w_u, h_u) / float(long_side)
    w, h = max(1, int(math.ceil(w_u / s))), max(1, int(math.ceil(h_u / s)))
    data.geo = (x0, y1, s)

    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = max(1.0, long_side / 3000.0)          # trait proportionnel a la definition : lisible en vue d'ensemble
        for rgb, arrays in data.strokes.items():
            pen = QPen(QColor(*rgb), width)
            pen.setCosmetic(True)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for a in arrays:
                px = (a[:, 0] - x0) / s
                py = (y1 - a[:, 1]) / s
                if not (np.isfinite(px).all() and np.isfinite(py).all()):
                    continue
                p.drawPolyline(QPolygonF([QPointF(float(i), float(j)) for i, j in zip(px, py)]))
        for rgb, x, y in data.dots:
            pen = QPen(QColor(*rgb), 3.0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPoint(QPointF((x - x0) / s, (y1 - y) / s))
        for rgb, x, y, txt, height, rot in data.texts:
            hp = height / s
            pen = QPen(QColor(*rgb), 1.0)
            pen.setCosmetic(True)
            p.setPen(pen)
            if hp < 3 or not txt:
                p.drawPoint(QPointF((x - x0) / s, (y1 - y) / s))
                continue
            font = QFont("Arial")
            font.setPixelSize(max(3, int(round(hp))))
            p.setFont(font)
            p.save()
            p.translate((x - x0) / s, (y1 - y) / s)
            p.rotate(-rot)
            p.drawText(QPointF(0, 0), txt)
            p.restore()
    finally:
        p.end()
    return _qimage_to_array(img)


def _qimage_to_array(img):
    img = img.convertToFormat(img.Format.Format_RGB32) if hasattr(img, "Format") else img
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(h * bpl)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl // 4, 4)[:, :w, :]
    return np.ascontiguousarray(arr[:, :, 2::-1])        # BGRA (petit-boutiste) -> RGB


# ---------------------------------------------------------------- pixel <-> dessin
def to_pixel(geo, x, y):
    x0, y1, s = geo
    return (x - x0) / s, (y1 - y) / s


def to_dxf(geo, px, py):
    x0, y1, s = geo
    return x0 + px * s, y1 - py * s


def snap(data, px, py, radius_px):
    """Sommet du dessin le plus proche de (px, py) dans un rayon `radius_px` (pixels de l'image),
    en pixels de l'image, ou None."""
    if data.geo is None or not len(data.snap_arr):
        return None
    x0, y1, s = data.geo
    qx = (data.snap_arr[:, 0] - x0) / s
    qy = (y1 - data.snap_arr[:, 1]) / s
    d2 = (qx - px) ** 2 + (qy - py) ** 2
    i = int(np.argmin(d2))
    if d2[i] <= radius_px ** 2:
        return float(qx[i]), float(qy[i])
    return None


def pixel_gt_to_dxf_matrix(gt, geo):
    """Transformation DXF -> carte (a, b, c, d, e, f) avec X = a*x + b*y + c ; Y = d*x + e*y + f,
    composee du geotransform GDAL des pixels `gt` et de la correspondance pixel <-> dessin `geo`."""
    x0, y1, s = geo
    # px = (x - x0)/s ; py = (y1 - y)/s
    a = gt[1] / s
    b = -gt[2] / s
    c = gt[0] + gt[1] * (-x0 / s) + gt[2] * (y1 / s)
    d = gt[4] / s
    e = -gt[5] / s
    f = gt[3] + gt[4] * (-x0 / s) + gt[5] * (y1 / s)
    return a, b, c, d, e, f
