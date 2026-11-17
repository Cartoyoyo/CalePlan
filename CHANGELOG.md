# Changelog

## [1.0.1] - 2026-11-17

### Changed
- Publication automatique par tag : workflow GitHub (ZIP, Bandit, detect-secrets, envoi sur plugins.qgis.org, release GitHub) et dossier `tools/`.
- README : logo en tete, a la meme taille que CanaPlan.
- No change in the plugin's behaviour.

## [1.0.0] - 2026-11-17

### Added
- First release.
- Opens a PDF (page picker with thumbnails) or an image (JPG, PNG, TIFF, BMP, GIF).
- Click a landmark on the plan, then the same landmark on the QGIS map; coordinates can also be typed in the table.
- Similarity from 2 points, least-squares similarity with an error check from 3 points, affine from 4 points
  (or forced from the transformation list).
- GeoTIFF written in the project CRS (DEFLATE, overviews, transparent corners when the plan is rotated) and added to the project.
- Interface in 5 languages (FR, EN, ES, PT, DE); QGIS 3.28 to 4 (Qt 5 and Qt 6, QGIS 4 not tested yet).
- Transparent colour (eyedropper, tolerance, checkerboard preview, alpha band in the GeoTIFF).
- Re-georeferencing replaces the layer already in the project (same position, name, opacity).
- Toolbar button and Extensions menu entry; metadata and About page in the same style as my other plugins.
