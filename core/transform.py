"""Calcul du calage : points image <-> points carte.

Convention : (px, py) = pixels de l'image, origine en haut a gauche, y vers le BAS.
(X, Y) = coordonnees carte, Y vers le HAUT. Le resultat est un geotransform GDAL
(a0, a1, a2, d0, d1, d2) tel que :

    X = a0 + a1 * px + a2 * py
    Y = d0 + d1 * px + d2 * py

- 2 points : similitude (translation + rotation + echelle uniforme), solution exacte,
  sans deformation ;
- 3 points : similitude aux moindres carres (on a alors un controle : ecart par point) ;
- 4 points et plus : affine aux moindres carres (absorbe la deformation du scan),
  avec ecart par point et ecart quadratique moyen.
Une affine sur 3 points est exacte (0 d'ecart) : elle n'offre aucune verification,
c'est pourquoi le mode automatique ne la choisit qu'a partir de 4 points.
"""
import math

import numpy as np


class FitError(ValueError):
    """Calage impossible ; `code` sert a choisir le message traduit."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def pixel_to_map(gt, px, py):
    return gt[0] + gt[1] * px + gt[2] * py, gt[3] + gt[4] * px + gt[5] * py


def fit(img_pts, map_pts, method="auto"):
    """Retourne un dict : kind ('similarity'|'affine'), gt, residuals (unites carte), rms.

    method : 'auto' (2-3 pts -> similitude, 4+ -> affine), 'similarity' ou 'affine'.
    """
    n = len(img_pts)
    if n != len(map_pts) or n < 2:
        raise FitError("min_points")
    if method == "auto":
        method = "similarity" if n < 4 else "affine"
    if method == "affine" and n < 3:
        method = "similarity"

    p = np.asarray(img_pts, dtype=float)
    m = np.asarray(map_pts, dtype=float)
    pm, mm = p.mean(axis=0), m.mean(axis=0)   # centrage : coordonnees L93 ~ 7e5 / 6.5e6
    dp, dm = p - pm, m - mm

    if method == "similarity":
        w = dp[:, 0] - 1j * dp[:, 1]          # y image vers le bas -> on le retourne
        z = dm[:, 0] + 1j * dm[:, 1]
        den = float((np.abs(w) ** 2).sum())
        if den < 1e-9:
            raise FitError("coincident")
        b = (z * np.conj(w)).sum() / den
        if abs(b) < 1e-15:
            raise FitError("coincident_map")
        a1, a2, d1, d2 = b.real, b.imag, b.imag, -b.real
    else:
        sv = np.linalg.svd(dp, compute_uv=False)
        if sv[0] < 1e-9 or sv[-1] < 1e-6 * sv[0]:
            raise FitError("collinear")
        sol = np.linalg.lstsq(dp, dm, rcond=None)[0]   # 2 x 2 : colonnes X puis Y
        a1, a2 = sol[0, 0], sol[1, 0]
        d1, d2 = sol[0, 1], sol[1, 1]

    a0 = mm[0] - a1 * pm[0] - a2 * pm[1]
    d0 = mm[1] - d1 * pm[0] - d2 * pm[1]
    gt = (float(a0), float(a1), float(a2), float(d0), float(d1), float(d2))

    res = []
    for (px, py), (x, y) in zip(img_pts, map_pts):
        qx, qy = pixel_to_map(gt, px, py)
        res.append(math.hypot(qx - x, qy - y))
    rms = math.sqrt(sum(r * r for r in res) / len(res))
    return {"kind": method, "gt": gt, "residuals": res, "rms": rms}


def describe(gt):
    """Taille du pixel, rotation (degres, antihoraire depuis l'est), miroir eventuel."""
    sx = math.hypot(gt[1], gt[4])
    sy = math.hypot(gt[2], gt[5])
    rot = math.degrees(math.atan2(gt[4], gt[1]))
    det = gt[1] * gt[5] - gt[2] * gt[4]
    return {"pixel_x": sx, "pixel_y": sy, "rotation": rot, "mirrored": det > 0}


def corners(gt, width, height):
    """Quatre coins de l'image en coordonnees carte (haut-gauche, haut-droit, bas-droit, bas-gauche)."""
    return [pixel_to_map(gt, x, y) for x, y in ((0, 0), (width, 0), (width, height), (0, height))]
