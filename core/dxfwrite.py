"""Ecriture d'un DXF cale et de son GeoPackage.

- DXF cale : le fichier d'origine est relu par ezdxf, chaque objet du MODELE est transforme par
  la similitude (translation + rotation + echelle uniforme, Z compris) ; calques, blocs, styles,
  textes et couleurs restent tels quels. Les definitions de blocs ne bougent pas : seules les
  insertions sont transformees. Un objet qui ne se transforme pas est retire (et compte) plutot
  que laisse a son ancienne place.
- GeoPackage : lu dans le DXF cale par le pilote DXF d'OGR (blocs mis a plat), puis range en
  couches points / lignes / polygones / textes dans le SCR choisi. Les textes gardent leur
  contenu, leur angle et leur hauteur ; la couleur du trait est conservee en champ.
"""
import math
import os
import re

from osgeo import gdal, ogr, osr

from .render import _gdal_exceptions

_STYLE_ANGLE = re.compile(r"[,(]a:(-?[0-9.]+)")
_STYLE_SIZE = re.compile(r"[,(]s:([0-9.]+)")
_STYLE_COLOR = re.compile(r"(?:\(|,)(?:c|fc):(#[0-9a-fA-F]{6})")


def scale_of(matrix):
    a, _b, _c, d, _e, _f = matrix
    return math.hypot(a, d)


def write_dxf(src, out, matrix, progress=None):
    """Ecrit `out` (DXF) : `src` transforme par `matrix` = (a, b, c, d, e, f)
    avec X = a*x + b*y + c ; Y = d*x + e*y + f. Retourne (n_transformes, n_retires, encodage)."""
    import ezdxf
    from ezdxf.math import Matrix44
    a, b, c, d, e, f = matrix
    k = scale_of(matrix)
    m = Matrix44((a, d, 0, 0,
                  b, e, 0, 0,
                  0, 0, k, 0,
                  c, f, 0, 1))
    def tick(f):
        if progress is not None:
            progress(min(1.0, max(0.0, f)))
    tick(0.0)
    doc = ezdxf.readfile(src)
    tick(0.35)
    msp = doc.modelspace()
    ok = dropped = 0
    entities = list(msp)
    total = max(1, len(entities))
    for i, ent in enumerate(entities):
        if i % 200 == 0:
            tick(0.35 + 0.35 * i / total)
        try:
            ent.transform(m)
            ok += 1
        except Exception:        # objet non transformable (type exotique) : retire, signale au journal
            try:
                msp.delete_entity(ent)
            except (ezdxf.DXFError, ValueError, KeyError, AttributeError):    # deja detache : rien d'autre a faire
                pass
            dropped += 1
    try:
        from ezdxf import zoom
        zoom.extents(msp)
    except (ezdxf.DXFError, ImportError, ValueError, TypeError, AttributeError):   # confort d'ouverture (vue initiale)
        pass
    tick(0.7)
    doc.saveas(out)
    tick(1.0)
    # encodage reel du fichier ecrit : le pilote DXF d'OGR se fie a $DWGCODEPAGE, faux pour un DXF
    # recent (UTF-8) et les accents des calques / textes deviennent « Ã »
    enc = getattr(doc, "output_encoding", None) or ("utf-8" if doc.dxfversion >= "AC1021" else doc.encoding)
    return ok, dropped, enc


def _flat(geom):
    """Decompose multi-geometries / collections en Point, LineString, Polygon simples (2D)."""
    if geom is None:
        return
    t = ogr.GT_Flatten(geom.GetGeometryType())
    if t in (ogr.wkbPoint, ogr.wkbLineString, ogr.wkbPolygon):
        g = geom.Clone()
        g.FlattenTo2D()
        yield t, g
    elif t == ogr.wkbLinearRing:
        g = ogr.Geometry(ogr.wkbLineString)
        for i in range(geom.GetPointCount()):
            g.AddPoint_2D(geom.GetX(i), geom.GetY(i))
        yield ogr.wkbLineString, g
    else:
        for i in range(geom.GetGeometryCount()):
            yield from _flat(geom.GetGeometryRef(i))


def _table_name(calque, used):
    """Nom de table GeoPackage sur : caracteres simples, unique meme si deux calques s'y ramenent."""
    base = re.sub(r"[^\w\- ]", "_", str(calque), flags=re.UNICODE).strip() or "0"
    name, n = base, 1
    while name.lower() in used:
        n += 1
        name = "%s_%d" % (base, n)
    used.add(name.lower())
    return name


KINDS = {ogr.wkbPoint: "points", ogr.wkbLineString: "lines", ogr.wkbPolygon: "polygons"}


def write_gpkg(dxf_path, gpkg_path, crs_wkt, encoding=None, progress=None, expected=0):
    """Cree `gpkg_path` depuis le DXF cale : UNE couche par calque du DXF et par type d'objet
    (<calque>__points / __lines / __polygons ; les textes sont des points qui portent
    Text, Angle, Height). Retourne la liste triee de {"table", "calque", "kind", "count", "texts"}
    avec kind = points | lines | polygons."""
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs_wkt)
    try:
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    except AttributeError:
        pass
    if os.path.exists(gpkg_path):
        os.remove(gpkg_path)
    entries = {}
    used = set()
    if encoding:
        gdal.SetConfigOption("DXF_ENCODING", str(encoding).upper())
    try:
        return _write_gpkg(dxf_path, gpkg_path, srs, entries, used, progress, expected)
    finally:
        if encoding:
            gdal.SetConfigOption("DXF_ENCODING", None)


def _write_gpkg(dxf_path, gpkg_path, srs, entries, used, progress=None, expected=0):
    with _gdal_exceptions():
        src = gdal.OpenEx(dxf_path, gdal.OF_VECTOR,
                          open_options=["INLINE_BLOCKS=TRUE", "MERGE_BLOCK_GEOMETRIES=FALSE",
                                        "TRANSLATE_ESCAPE_SEQUENCES=TRUE"])
        if src is None:
            raise RuntimeError("DXF illisible : %s" % dxf_path)
        ds = gdal.GetDriverByName("GPKG").Create(gpkg_path, 0, 0, 0, gdal.GDT_Unknown)
        if ds is None:
            raise RuntimeError("GeoPackage non cree : %s" % gpkg_path)
        tables = {}          # nom de calque -> nom de table de base

        def layer_for(calque, kind):
            key = (calque, kind)
            if key not in entries:
                if calque not in tables:
                    tables[calque] = _table_name(calque, used)
                gtype = {"points": ogr.wkbPoint, "lines": ogr.wkbLineString, "polygons": ogr.wkbPolygon}[kind]
                table = "%s__%s" % (tables[calque], kind)
                lyr = ds.CreateLayer(table, srs, gtype, ["SPATIAL_INDEX=YES"])
                fields = [("Layer", ogr.OFTString), ("Color", ogr.OFTString)]
                if kind == "points":
                    fields += [("Text", ogr.OFTString), ("Angle", ogr.OFTReal), ("Height", ogr.OFTReal)]
                for fname, ftype in fields:
                    lyr.CreateField(ogr.FieldDefn(fname, ftype))
                entries[key] = {"table": table, "calque": calque, "kind": kind, "count": 0, "texts": 0, "lyr": lyr}
            return entries[key]

        ds.StartTransaction()
        done = 0
        try:
            for i in range(src.GetLayerCount()):
                sl = src.GetLayer(i)
                defn = sl.GetLayerDefn()
                idx_layer = defn.GetFieldIndex("Layer")
                idx_text = defn.GetFieldIndex("Text")
                for feat in sl:
                    done += 1
                    if progress is not None and expected and done % 300 == 0:
                        progress(min(0.9, 0.9 * done / expected))
                    geom = feat.GetGeometryRef()
                    if geom is None:
                        continue
                    style = feat.GetStyleString() or ""
                    calque = (feat.GetField(idx_layer) if idx_layer >= 0 else None) or "0"
                    text = feat.GetField(idx_text) if idx_text >= 0 and style.startswith("LABEL") else None
                    mc = _STYLE_COLOR.search(style)
                    color = mc.group(1) if mc else None
                    for t, g in _flat(geom):
                        kind = KINDS[t]
                        ent = layer_for(calque, kind)
                        out = ogr.Feature(ent["lyr"].GetLayerDefn())
                        out.SetGeometry(g)
                        out.SetField("Layer", calque)
                        if color:
                            out.SetField("Color", color)
                        if kind == "points" and text:
                            ent["texts"] += 1
                            out.SetField("Text", text)
                            ma, ms = _STYLE_ANGLE.search(style), _STYLE_SIZE.search(style)
                            out.SetField("Angle", float(ma.group(1)) if ma else 0.0)
                            out.SetField("Height", float(ms.group(1)) if ms else 0.0)
                        ent["lyr"].CreateFeature(out)
                        ent["count"] += 1
        finally:
            ds.CommitTransaction()
        if progress is not None:
            progress(0.9)
        ds.FlushCache()
        if progress is not None:
            progress(1.0)
        ds = None
        src = None
    result = [{k: v for k, v in e.items() if k != "lyr"} for e in entries.values()]
    result.sort(key=lambda e: (str(e["calque"]).lower(), ("points", "lines", "polygons").index(e["kind"])))
    return result
