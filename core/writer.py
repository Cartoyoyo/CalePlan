"""Ecriture du GeoTIFF cale.

- plan sans rotation : ecriture directe, sans reechantillonnage (aucune perte) ;
- plan tourne ou deforme : gdal.Warp vers une grille nord en haut, avec une bande alpha
  pour que les coins restent transparents.
"""
import os

import numpy as np
from osgeo import gdal, osr

from .render import _gdal_exceptions

CREATION = ["COMPRESS=DEFLATE", "PREDICTOR=2", "TILED=YES", "BIGTIFF=IF_SAFER"]


def is_rotated(gt):
    return max(abs(gt[2]), abs(gt[4])) > 1e-7 * max(abs(gt[1]), abs(gt[5]), 1e-12)


def _srs(crs_wkt):
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs_wkt)
    try:
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    except AttributeError:
        pass
    return srs


def _mem_dataset(arr, gt, crs_wkt):
    h, w, c = arr.shape
    mem = gdal.GetDriverByName("MEM").Create("", w, h, c, gdal.GDT_Byte)
    mem.SetGeoTransform(gt)
    mem.SetProjection(crs_wkt)
    colors = (gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand, gdal.GCI_AlphaBand)
    for i in range(c):
        band = mem.GetRasterBand(i + 1)
        band.WriteArray(np.ascontiguousarray(arr[:, :, i]))
        band.SetColorInterpretation(colors[i])
    return mem


def write_geotiff(arr, gt, crs_wkt, out_path, progress=None):
    """Ecrit `arr` (h, w, 3|4 uint8) en GeoTIFF cale par `gt` dans le SCR `crs_wkt`.

    Retourne True si le plan a ete reechantillonne (rotation), False sinon.
    """
    folder = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(folder, exist_ok=True)
    if os.path.exists(out_path):
        os.remove(out_path)
    callback = (lambda frac, msg, data: (progress(frac), 1)[1]) if progress else None
    with _gdal_exceptions():
        mem = _mem_dataset(arr, gt, crs_wkt)
        warped = is_rotated(gt)
        if warped:
            ds = gdal.Warp(out_path, mem, format="GTiff", dstSRS=_srs(crs_wkt).ExportToWkt(),
                           dstAlpha=(arr.shape[2] == 3), resampleAlg="bilinear",
                           multithread=True, creationOptions=CREATION, callback=callback)
        else:
            ds = gdal.GetDriverByName("GTiff").CreateCopy(out_path, mem, options=CREATION,
                                                          callback=callback)
        ds.FlushCache()
        ds = None
        mem = None
        out = gdal.Open(out_path, gdal.GA_Update)
        try:
            out.BuildOverviews("AVERAGE", [2, 4, 8, 16])
        finally:
            out = None
    return warped
