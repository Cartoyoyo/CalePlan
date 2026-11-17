"""Chargement du GeoPackage d'un DXF cale dans le projet : un groupe, une couche par type
d'objet (textes, points, lignes, polygones), couleurs lues dans le champ « Color ».

Aucune expression « overlay_* » (autre couche) : un style ne lit que les champs de sa propre
couche ; l'etiquette d'un texte s'oriente avec son champ « Angle » et se dimensionne en unites
de carte avec « Height » (la hauteur du texte du DXF).
"""
from qgis.core import (QgsCoordinateTransform, QgsCsException, QgsFillSymbol, QgsLayerTreeGroup, QgsLineSymbol,
                       QgsMarkerSymbol, QgsPalLayerSettings, QgsProject, QgsProperty, QgsRectangle,
                       QgsSingleSymbolRenderer, QgsSymbolLayer, QgsTextFormat, QgsUnitTypes, QgsVectorLayer, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtGui import QColor

COLOR_EXPR = "coalesce(\"Color\", '#000000')"


def _enum(cls, scope, name):
    """Enumeration QGIS 3.28 (`Classe.Nom`) ou QGIS 3.30+ / 4 (`Classe.Portee.Nom`)."""
    sc = getattr(cls, scope, None)
    if sc is not None and hasattr(sc, name):
        return getattr(sc, name)
    return getattr(cls, name)


def _prop_color():
    return QgsProperty.fromExpression(COLOR_EXPR)


def _style_lines(layer):
    sym = QgsLineSymbol.createSimple({"line_width": "0.2", "line_color": "#000000", "capstyle": "round",
                                      "joinstyle": "round"})
    sl = sym.symbolLayer(0)
    sl.setDataDefinedProperty(_enum(QgsSymbolLayer, "Property", "StrokeColor"), _prop_color())
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def _style_polygons(layer):
    sym = QgsFillSymbol.createSimple({"color": "#808080", "outline_style": "no"})
    sl = sym.symbolLayer(0)
    sl.setDataDefinedProperty(_enum(QgsSymbolLayer, "Property", "FillColor"), _prop_color())
    sym.setOpacity(0.35)
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def _style_points(layer, has_texts=False):
    """Points du DXF ; un point qui porte un texte n'a pas de symbole, son texte est l'etiquette."""
    sym = QgsMarkerSymbol.createSimple({"name": "circle", "size": "1.6", "color": "#000000",
                                        "outline_style": "no"})
    sl = sym.symbolLayer(0)
    sl.setDataDefinedProperty(_enum(QgsSymbolLayer, "Property", "FillColor"), _prop_color())
    if has_texts:
        sl.setDataDefinedProperty(_enum(QgsSymbolLayer, "Property", "Size"),
                                  QgsProperty.fromExpression('CASE WHEN "Text" IS NULL THEN 1.6 ELSE 0 END'))
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    if not has_texts:
        return
    settings = QgsPalLayerSettings()
    settings.fieldName = "Text"
    fmt = QgsTextFormat()                       # on garde `fmt` : jamais de chaine .format().background()
    fmt.setSizeUnit(QgsUnitTypes.RenderUnit.RenderMapUnits if hasattr(QgsUnitTypes, "RenderUnit")
                    else QgsUnitTypes.RenderMapUnits)
    fmt.setSize(1.0)
    fmt.setColor(QColor("#000000"))
    settings.setFormat(fmt)
    dd = settings.dataDefinedProperties()
    dd.setProperty(_enum(QgsPalLayerSettings, "Property", "Size"), QgsProperty.fromField("Height"))
    dd.setProperty(_enum(QgsPalLayerSettings, "Property", "LabelRotation"),
                   QgsProperty.fromExpression('-coalesce("Angle", 0)'))
    dd.setProperty(_enum(QgsPalLayerSettings, "Property", "Color"), _prop_color())
    settings.setDataDefinedProperties(dd)
    settings.placement = _enum(QgsPalLayerSettings, "Placement", "OverPoint")
    settings.quadOffset = _enum(QgsPalLayerSettings, "QuadrantPosition", "QuadrantAboveRight")
    settings.displayAll = True
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


STYLES = {"lines": _style_lines, "polygons": _style_polygons}
SUFFIX = {"points": "(P)", "lines": "(L)", "polygons": "(F)"}      # comme l'import DXF de CanaPlan
MARK = "caleplan/gpkg"


def vector_layers_for(project, path, norm):
    """Couches vectorielles du projet qui lisent ce fichier (GeoPackage)."""
    wanted = norm(path)
    found = []
    for lay in project.mapLayers().values():
        if isinstance(lay, QgsVectorLayer):
            src = lay.source().split("|")[0]
            if src and norm(src) == wanted:
                found.append(lay)
    return found


def take_old(project, old_layers, gpkg, norm):
    """Retire un precedent calage de ce GeoPackage : le groupe du DXF (repere par sa propriete) et ses
    couches. Retourne (parent, index, visible) pour remettre le nouveau groupe a la meme place, ou None."""
    root = project.layerTreeRoot()
    place = None
    for g in root.findGroups(True):
        if g.customProperty(MARK) == norm(gpkg):
            parent = g.parent() or root
            place = (parent, parent.children().index(g), g.isVisible())
            parent.removeChildNode(g)
            break
    if place is None and old_layers:                 # couches deplacees par l'utilisateur : place de la 1re
        node = root.findLayer(old_layers[0].id())
        if node is not None:
            parent = node.parent() or root
            place = (parent, parent.children().index(node), node.isVisible())
    ids = [lay.id() for lay in old_layers]
    if ids:
        project.removeMapLayers(ids)
    return place


class Builder:
    """Ajoute le groupe `group_name` (nom du DXF) avec UN sous-groupe par calque du DXF, qui contient ses
    couches <calque>(P) points et textes, (L) lignes, (F) polygones. Une couche par appel de step() : l'appelant
    rend la main a l'interface entre deux (aucun processEvents), d'ou une barre de progression vivante.
    `tables` : liste renvoyee par dxfwrite.write_gpkg."""

    def __init__(self, project, gpkg, tables, group_name, crs, norm, place=None):
        self.project, self.gpkg, self.crs = project, gpkg, crs
        root = project.layerTreeRoot()
        self.group = QgsLayerTreeGroup(group_name)
        self.group.setCustomProperty(MARK, norm(gpkg))
        if place is not None:
            parent, index, visible = place
            parent.insertChildNode(min(index, len(parent.children())), self.group)
            self.group.setItemVisibilityChecked(visible)
        else:
            root.insertChildNode(0, self.group)
        self._root = root
        self._todo = list(tables)
        self._subs = {}
        self.total = len(self._todo)
        self.done = 0
        self.added = []

    def step(self):
        """Cree la couche suivante. True quand tout est fini."""
        if self.done < self.total:
            t = self._todo[self.done]
            self.done += 1
            calque = t["calque"]
            sub = self._subs.get(calque)
            if sub is None:
                sub = self._subs[calque] = self.group.addGroup(str(calque))
            layer = QgsVectorLayer("%s|layername=%s" % (self.gpkg, t["table"]),
                                   "%s%s" % (calque, SUFFIX[t["kind"]]), "ogr")
            if layer.isValid():
                layer.setCrs(self.crs)
                try:
                    if t["kind"] == "points":
                        _style_points(layer, t.get("texts", 0) > 0)
                    else:
                        STYLES[t["kind"]](layer)
                except (AttributeError, TypeError, ValueError):     # style rate : la couche reste lisible
                    pass
                self.project.addMapLayer(layer, False)
                sub.addLayer(layer)
                self.added.append(layer)
        if self.done < self.total:
            return False
        for sub in list(self._subs.values()):
            if not sub.children():
                self.group.removeChildNode(sub)
        if not self.added:
            (self.group.parent() or self._root).removeChildNode(self.group)
        return True


def add_layers(project, gpkg, tables, group_name, crs, norm, place=None):
    """Version d'une traite (essais, scripts) ; l'interface utilise Builder par etapes."""
    b = Builder(project, gpkg, tables, group_name, crs, norm, place)
    while not b.step():
        pass
    return b.added


def zoom_to(canvas, layers):
    """Cadre le canevas sur l'emprise de ces couches (dans le SCR du projet)."""
    ext = None
    canvas_crs = canvas.mapSettings().destinationCrs()
    for lay in layers:
        e = lay.extent()
        if e.isNull() or e.isEmpty():
            continue
        if lay.crs() != canvas_crs:
            try:
                e = QgsCoordinateTransform(lay.crs(), canvas_crs, QgsProject.instance()).transformBoundingBox(e)
            except QgsCsException:
                continue
        if ext is None:
            ext = QgsRectangle(e)
        else:
            ext.combineExtentWith(e)
    if ext is not None:
        ext.scale(1.1)
        canvas.setExtent(ext)
        canvas.refresh()
