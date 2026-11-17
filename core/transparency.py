"""Couleur rendue transparente (fond blanc d'un scan, cartouche, etc.).

Distance a la couleur choisie = ecart maximal sur les trois canaux (0..255) :
  - distance <= tolerance          -> totalement transparent ;
  - tolerance < distance < tol+fondu -> transparence partielle (adoucit les bords du texte et des traits) ;
  - au-dela                        -> opaque.
Le calcul se fait par blocs de lignes : pas de copie geante en memoire sur les grandes images.
"""
import numpy as np

CHUNK = 512        # lignes traitees a la fois


def feather(tolerance):
    """Largeur de la zone de fondu au-dela de la tolerance."""
    return max(4, int(tolerance) // 2)


def apply_color_key(arr, color, tolerance):
    """arr (h, w, 3|4) uint8 -> (h, w, 4) uint8 ; `color` = (r, g, b) a rendre transparent."""
    h, w = arr.shape[:2]
    r, g, b = (int(c) for c in color)
    tol = int(tolerance)
    fade = float(feather(tol))
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[:, :, :3] = arr[:, :, :3]
    has_alpha = arr.shape[2] == 4
    for y0 in range(0, h, CHUNK):
        y1 = min(h, y0 + CHUNK)
        blk = arr[y0:y1, :, :3].astype(np.int16)
        d = np.maximum(np.maximum(np.abs(blk[:, :, 0] - r), np.abs(blk[:, :, 1] - g)), np.abs(blk[:, :, 2] - b))
        alpha = np.clip((d - tol) / fade, 0.0, 1.0) * 255.0
        alpha = alpha.astype(np.uint8)
        if has_alpha:                                    # on ne rend jamais plus opaque qu'avant
            alpha = np.minimum(alpha, arr[y0:y1, :, 3])
        out[y0:y1, :, 3] = alpha
    return out


def sample_color(arr, fx, fy, radius=2):
    """Couleur moyenne autour du point (fx, fy) en fractions 0..1 : lisse le bruit des scans."""
    h, w = arr.shape[:2]
    x = min(max(int(fx * w), 0), w - 1)
    y = min(max(int(fy * h), 0), h - 1)
    blk = arr[max(0, y - radius):y + radius + 1, max(0, x - radius):x + radius + 1, :3]
    r, g, b = blk.reshape(-1, 3).mean(axis=0)
    return int(round(r)), int(round(g)), int(round(b))
