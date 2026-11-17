"""Textes de l'interface en 5 langues (FR, EN, ES, PT, DE), repli sur l'anglais."""
from qgis.core import QgsSettings

LANGS = ["fr", "en", "es", "pt", "de"]
LANG_FLAGS = {"fr": "🇫🇷", "en": "🇬🇧", "es": "🇪🇸", "pt": "🇵🇹", "de": "🇩🇪"}
LANG_LABELS = {"fr": "Français", "en": "English", "es": "Español", "pt": "Português", "de": "Deutsch"}

_lang = "fr"


def default_lang():
    try:
        loc = str(QgsSettings().value("locale/userLocale", "") or "")[:2].lower()
    except Exception:
        loc = ""
    return loc if loc in LANGS else "en"


def set_lang(code):
    global _lang
    _lang = code if code in LANGS else "en"


def lang():
    return _lang


def tr(key, **kw):
    entry = TR.get(key)
    if entry is None:
        return key
    text = entry.get(_lang) or entry["en"]
    return text.format(**kw) if kw else text


TR = {
    "window_title": {
        "fr": "CalePlan — Caler un PDF ou une image",
        "en": "CalePlan — Georeference a PDF or an image",
        "es": "CalePlan — Georreferenciar un PDF o una imagen",
        "pt": "CalePlan — Georreferenciar um PDF ou uma imagem",
        "de": "CalePlan — PDF oder Bild georeferenzieren"},
    "open_btn": {
        "fr": "Ouvrir un PDF ou une image…", "en": "Open a PDF or an image…",
        "es": "Abrir un PDF o una imagen…", "pt": "Abrir um PDF ou uma imagem…",
        "de": "PDF oder Bild öffnen…"},
    "open_short": {"fr": "Ouvrir…", "en": "Open…", "es": "Abrir…", "pt": "Abrir…", "de": "Öffnen…"},
    "open_title": {
        "fr": "Choisir un PDF ou une image", "en": "Choose a PDF or an image",
        "es": "Elegir un PDF o una imagen", "pt": "Escolher um PDF ou uma imagem",
        "de": "PDF oder Bild auswählen"},
    "file_filter": {
        "fr": "PDF et images (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif);;Tous les fichiers (*)",
        "en": "PDF and images (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif);;All files (*)",
        "es": "PDF e imágenes (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif);;Todos los archivos (*)",
        "pt": "PDF e imagens (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif);;Todos os ficheiros (*)",
        "de": "PDF und Bilder (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif);;Alle Dateien (*)"},
    "no_file": {
        "fr": "Aucun fichier ouvert — ou glissez-le ici", "en": "No file open — or drop it here",
        "es": "Ningún archivo abierto — o arrástrelo aquí", "pt": "Nenhum ficheiro aberto — ou arraste-o para aqui",
        "de": "Keine Datei geöffnet — oder hierher ziehen"},
    "file_info_pdf": {
        "fr": "{name}  —  {n} page(s)", "en": "{name}  —  {n} page(s)",
        "es": "{name}  —  {n} página(s)", "pt": "{name}  —  {n} página(s)",
        "de": "{name}  —  {n} Seite(n)"},
    "file_info_img": {
        "fr": "{name}  —  image", "en": "{name}  —  image", "es": "{name}  —  imagen",
        "pt": "{name}  —  imagem", "de": "{name}  —  Bild"},
    "dpi_label": {
        "fr": "Résolution du rendu :", "en": "Render resolution:", "es": "Resolución del render:",
        "pt": "Resolução da renderização:", "de": "Render-Auflösung:"},
    "pages_title": {
        "fr": "Pages", "en": "Pages", "es": "Páginas", "pt": "Páginas", "de": "Seiten"},
    "page_item": {
        "fr": "Page {n}", "en": "Page {n}", "es": "Página {n}", "pt": "Página {n}", "de": "Seite {n}"},
    "image_item": {
        "fr": "Image", "en": "Image", "es": "Imagen", "pt": "Imagem", "de": "Bild"},
    "view_hint": {
        "fr": "Clic = placer un repère · molette = zoom · bouton du milieu = déplacer",
        "en": "Click = place a point · wheel = zoom · middle button = pan",
        "es": "Clic = colocar un punto · rueda = zoom · botón central = desplazar",
        "pt": "Clique = colocar um ponto · roda = zoom · botão do meio = deslocar",
        "de": "Klick = Punkt setzen · Rad = Zoom · Mitteltaste = verschieben"},
    "btn_fit": {
        "fr": "Ajuster", "en": "Fit", "es": "Ajustar", "pt": "Ajustar", "de": "Einpassen"},
    "btn_undo": {
        "fr": "↶ Annuler le dernier point", "en": "↶ Undo last point", "es": "↶ Deshacer último punto",
        "pt": "↶ Anular último ponto", "de": "↶ Letzten Punkt entfernen"},
    "points_title": {
        "fr": "Points de contrôle", "en": "Control points", "es": "Puntos de control",
        "pt": "Pontos de controlo", "de": "Passpunkte"},
    "col_n": {"fr": "N°", "en": "No.", "es": "N.º", "pt": "N.º", "de": "Nr."},
    "col_img": {
        "fr": "Image (px)", "en": "Image (px)", "es": "Imagen (px)", "pt": "Imagem (px)", "de": "Bild (px)"},
    "col_x": {"fr": "X carte", "en": "Map X", "es": "X mapa", "pt": "X mapa", "de": "Karte X"},
    "col_y": {"fr": "Y carte", "en": "Map Y", "es": "Y mapa", "pt": "Y mapa", "de": "Karte Y"},
    "col_err": {"fr": "Écart", "en": "Error", "es": "Error", "pt": "Erro", "de": "Abw."},
    "hint_open": {
        "fr": "Ouvrez d'abord un PDF ou une image.", "en": "First open a PDF or an image.",
        "es": "Abra primero un PDF o una imagen.", "pt": "Abra primeiro um PDF ou uma imagem.",
        "de": "Öffnen Sie zuerst ein PDF oder ein Bild."},
    "hint_none": {
        "fr": "① Cliquez un repère net sur l'image (croisement, angle de parcelle…).",
        "en": "① Click a sharp landmark on the image (crossing, parcel corner…).",
        "es": "① Haga clic en una referencia nítida de la imagen (cruce, esquina de parcela…).",
        "pt": "① Clique num ponto de referência nítido da imagem (cruzamento, canto de parcela…).",
        "de": "① Klicken Sie einen klaren Punkt im Bild an (Kreuzung, Flurstücksecke…)."},
    "hint_pending": {
        "fr": "② Cliquez maintenant le MÊME repère sur la carte QGIS (point {n}). Échap = annuler.",
        "en": "② Now click the SAME landmark on the QGIS map (point {n}). Esc = cancel.",
        "es": "② Ahora haga clic en la MISMA referencia en el mapa de QGIS (punto {n}). Esc = cancelar.",
        "pt": "② Agora clique no MESMO ponto no mapa do QGIS (ponto {n}). Esc = cancelar.",
        "de": "② Klicken Sie jetzt denselben Punkt in der QGIS-Karte an (Punkt {n}). Esc = abbrechen."},
    "hint_one": {
        "fr": "Placez un 2e repère, le plus loin possible du premier.",
        "en": "Place a 2nd landmark, as far as possible from the first.",
        "es": "Coloque una 2.ª referencia, lo más lejos posible de la primera.",
        "pt": "Coloque um 2.º ponto, o mais afastado possível do primeiro.",
        "de": "Setzen Sie einen 2. Punkt, möglichst weit vom ersten entfernt."},
    "hint_ok": {
        "fr": "{n} points : calage possible. Ajoutez-en pour contrôler l'écart.",
        "en": "{n} points: ready to georeference. Add more to check the error.",
        "es": "{n} puntos: se puede georreferenciar. Añada más para controlar el error.",
        "pt": "{n} pontos: já é possível georreferenciar. Adicione mais para controlar o erro.",
        "de": "{n} Punkte: Georeferenzierung möglich. Weitere Punkte zeigen die Abweichung."},
    "btn_delete": {
        "fr": "Supprimer", "en": "Delete", "es": "Eliminar", "pt": "Eliminar", "de": "Löschen"},
    "btn_clear": {
        "fr": "Tout effacer", "en": "Clear all", "es": "Borrar todo", "pt": "Apagar tudo", "de": "Alle löschen"},
    "transfo_label": {
        "fr": "Transformation :", "en": "Transformation:", "es": "Transformación:",
        "pt": "Transformação:", "de": "Transformation:"},
    "transfo_auto": {
        "fr": "Automatique", "en": "Automatic", "es": "Automática", "pt": "Automática", "de": "Automatisch"},
    "transfo_sim": {
        "fr": "Similitude (sans déformation)", "en": "Similarity (no distortion)",
        "es": "Semejanza (sin deformación)", "pt": "Semelhança (sem deformação)",
        "de": "Ähnlichkeit (ohne Verzerrung)"},
    "transfo_aff": {
        "fr": "Affine (corrige la déformation)", "en": "Affine (corrects distortion)",
        "es": "Afín (corrige la deformación)", "pt": "Afim (corrige a deformação)",
        "de": "Affin (korrigiert Verzerrung)"},
    "fit_none": {
        "fr": "Calage : — (2 points minimum)", "en": "Fit: — (2 points minimum)",
        "es": "Ajuste: — (mínimo 2 puntos)", "pt": "Ajuste: — (mínimo 2 pontos)",
        "de": "Anpassung: — (mind. 2 Punkte)"},
    "fit_sim": {
        "fr": "Calage : similitude ({n} points)", "en": "Fit: similarity ({n} points)",
        "es": "Ajuste: semejanza ({n} puntos)", "pt": "Ajuste: semelhança ({n} pontos)",
        "de": "Anpassung: Ähnlichkeit ({n} Punkte)"},
    "fit_aff": {
        "fr": "Calage : affine ({n} points)", "en": "Fit: affine ({n} points)",
        "es": "Ajuste: afín ({n} puntos)", "pt": "Ajuste: afim ({n} pontos)",
        "de": "Anpassung: affin ({n} Punkte)"},
    "fit_exact": {
        "fr": "Affine sur 3 points : exacte, donc sans contrôle.",
        "en": "Affine on 3 points: exact, so no check.",
        "es": "Afín con 3 puntos: exacta, sin control.",
        "pt": "Afim com 3 pontos: exata, sem controlo.",
        "de": "Affin mit 3 Punkten: exakt, also ohne Kontrolle."},
    "fit_rms": {
        "fr": "Écart quadratique moyen : {v} m", "en": "Root mean square error: {v} m",
        "es": "Error cuadrático medio: {v} m", "pt": "Erro quadrático médio: {v} m",
        "de": "Mittlerer quadratischer Fehler: {v} m"},
    "fit_pixel": {
        "fr": "Pixel : {px} m · rotation : {rot}°", "en": "Pixel: {px} m · rotation: {rot}°",
        "es": "Píxel: {px} m · rotación: {rot}°", "pt": "Píxel: {px} m · rotação: {rot}°",
        "de": "Pixel: {px} m · Drehung: {rot}°"},
    "warn_close": {
        "fr": "Points très rapprochés : précision faible, éloignez-les.",
        "en": "Points very close together: low accuracy, spread them out.",
        "es": "Puntos muy cercanos: poca precisión, sepárelos.",
        "pt": "Pontos muito próximos: pouca precisão, afaste-os.",
        "de": "Punkte liegen sehr nah beieinander: geringe Genauigkeit."},
    "result_title": {
        "fr": "Résultat", "en": "Output", "es": "Resultado", "pt": "Resultado", "de": "Ergebnis"},
    "out_name": {
        "fr": "Nom du GeoTIFF", "en": "GeoTIFF name", "es": "Nombre del GeoTIFF",
        "pt": "Nome do GeoTIFF", "de": "GeoTIFF-Name"},
    "out_folder": {"fr": "Dossier", "en": "Folder", "es": "Carpeta", "pt": "Pasta", "de": "Ordner"},
    "out_folder_pick": {
        "fr": "Choisir le dossier de sortie", "en": "Choose the output folder",
        "es": "Elegir la carpeta de salida", "pt": "Escolher a pasta de saída", "de": "Ausgabeordner wählen"},
    "out_crs": {"fr": "SCR", "en": "CRS", "es": "SRC", "pt": "SRC", "de": "KBS"},
    "out_crs_value": {
        "fr": "{authid} (SCR du projet)", "en": "{authid} (project CRS)", "es": "{authid} (SRC del proyecto)",
        "pt": "{authid} (SRC do projeto)", "de": "{authid} (Projekt-KBS)"},
    "out_opacity": {
        "fr": "Opacité", "en": "Opacity", "es": "Opacidad", "pt": "Opacidade", "de": "Deckkraft"},
    "out_add": {
        "fr": "Ajouter au projet et zoomer dessus", "en": "Add to the project and zoom to it",
        "es": "Añadir al proyecto y hacer zoom", "pt": "Adicionar ao projeto e fazer zoom",
        "de": "Zum Projekt hinzufügen und hinzoomen"},
    "hide_window": {
        "fr": "Masquer cette fenêtre pendant le clic sur la carte",
        "en": "Hide this window while clicking on the map",
        "es": "Ocultar esta ventana mientras se hace clic en el mapa",
        "pt": "Ocultar esta janela durante o clique no mapa",
        "de": "Dieses Fenster beim Klick in die Karte ausblenden"},
    "btn_go": {
        "fr": "Caler", "en": "Georeference", "es": "Georreferenciar", "pt": "Georreferenciar",
        "de": "Georeferenzieren"},
    "btn_about": {"fr": "À propos", "en": "About", "es": "Acerca de", "pt": "Sobre", "de": "Über"},
    "btn_close": {"fr": "Fermer", "en": "Close", "es": "Cerrar", "pt": "Fechar", "de": "Schließen"},
    "status_ready": {
        "fr": "Prêt.", "en": "Ready.", "es": "Listo.", "pt": "Pronto.", "de": "Bereit."},
    "status_render": {
        "fr": "Rendu de la page {n}…", "en": "Rendering page {n}…", "es": "Renderizando la página {n}…",
        "pt": "A renderizar a página {n}…", "de": "Seite {n} wird gerendert…"},
    "status_loaded": {
        "fr": "Page {n} : {w} × {h} px{dpi}.", "en": "Page {n}: {w} × {h} px{dpi}.",
        "es": "Página {n}: {w} × {h} px{dpi}.", "pt": "Página {n}: {w} × {h} px{dpi}.",
        "de": "Seite {n}: {w} × {h} px{dpi}."},
    "status_dpi": {
        "fr": " à {dpi} dpi", "en": " at {dpi} dpi", "es": " a {dpi} dpi", "pt": " a {dpi} dpi",
        "de": " bei {dpi} dpi"},
    "status_capped": {
        "fr": " (réduit à {dpi} dpi : limite de {px} px)", "en": " (reduced to {dpi} dpi: {px} px limit)",
        "es": " (reducido a {dpi} dpi: límite de {px} px)", "pt": " (reduzido a {dpi} dpi: limite de {px} px)",
        "de": " (auf {dpi} dpi reduziert: Grenze {px} px)"},
    "status_waiting_map": {
        "fr": "⏳ En attente du clic sur la carte QGIS…", "en": "⏳ Waiting for the click on the QGIS map…",
        "es": "⏳ Esperando el clic en el mapa de QGIS…", "pt": "⏳ A aguardar o clique no mapa do QGIS…",
        "de": "⏳ Warte auf den Klick in der QGIS-Karte…"},
    "status_writing": {
        "fr": "Écriture du GeoTIFF…", "en": "Writing the GeoTIFF…", "es": "Escribiendo el GeoTIFF…",
        "pt": "A escrever o GeoTIFF…", "de": "GeoTIFF wird geschrieben…"},
    "map_msg": {
        "fr": "CalePlan : cliquez le point {n} sur la carte (Échap = annuler).",
        "en": "CalePlan: click point {n} on the map (Esc = cancel).",
        "es": "CalePlan: haga clic en el punto {n} del mapa (Esc = cancelar).",
        "pt": "CalePlan: clique no ponto {n} do mapa (Esc = cancelar).",
        "de": "CalePlan: Klicken Sie Punkt {n} in der Karte an (Esc = abbrechen)."},
    "done": {
        "fr": "✔ « {name} » créé{extra}.", "en": "✔ “{name}” created{extra}.",
        "es": "✔ «{name}» creado{extra}.", "pt": "✔ «{name}» criado{extra}.",
        "de": "✔ „{name}“ erstellt{extra}."},
    "done_added": {
        "fr": " et ajouté au projet", "en": " and added to the project", "es": " y añadido al proyecto",
        "pt": " e adicionado ao projeto", "de": " und zum Projekt hinzugefügt"},
    "done_replaced": {
        "fr": " et remplacé dans le projet (même place, même opacité)",
        "en": " and replaced in the project (same position, same opacity)",
        "es": " y reemplazado en el proyecto (misma posición, misma opacidad)",
        "pt": " e substituído no projeto (mesma posição, mesma opacidade)",
        "de": " und im Projekt ersetzt (gleiche Position, gleiche Deckkraft)"},
    "done_resampled": {
        "fr": " (plan tourné : rééchantillonné)", "en": " (rotated plan: resampled)",
        "es": " (plano girado: remuestreado)", "pt": " (planta rodada: reamostrada)",
        "de": " (gedrehter Plan: neu abgetastet)"},
    "confirm_overwrite": {
        "fr": "Le fichier « {name} » existe déjà. Le remplacer ?",
        "en": "The file “{name}” already exists. Replace it?",
        "es": "El archivo «{name}» ya existe. ¿Reemplazarlo?",
        "pt": "O ficheiro «{name}» já existe. Substituí-lo?",
        "de": "Die Datei „{name}“ existiert bereits. Ersetzen?"},
    "err_title": {"fr": "CalePlan", "en": "CalePlan", "es": "CalePlan", "pt": "CalePlan", "de": "CalePlan"},
    "err_no_backend": {
        "fr": "Aucun moteur de lecture PDF n'est disponible. Installez PyMuPDF (pip install pymupdf) "
              "dans le Python de QGIS, ou utilisez une image (JPG, PNG, TIFF).",
        "en": "No PDF reader is available. Install PyMuPDF (pip install pymupdf) in QGIS's Python, "
              "or use an image (JPG, PNG, TIFF).",
        "es": "No hay ningún lector de PDF disponible. Instale PyMuPDF (pip install pymupdf) en el Python "
              "de QGIS, o use una imagen (JPG, PNG, TIFF).",
        "pt": "Não há nenhum leitor de PDF disponível. Instale o PyMuPDF (pip install pymupdf) no Python "
              "do QGIS, ou use uma imagem (JPG, PNG, TIFF).",
        "de": "Kein PDF-Leser verfügbar. Installieren Sie PyMuPDF (pip install pymupdf) im QGIS-Python "
              "oder verwenden Sie ein Bild (JPG, PNG, TIFF)."},
    "err_open": {
        "fr": "Lecture impossible : {detail}", "en": "Cannot read the file: {detail}",
        "es": "No se puede leer el archivo: {detail}", "pt": "Não é possível ler o ficheiro: {detail}",
        "de": "Datei nicht lesbar: {detail}"},
    "err_encrypted": {
        "fr": "Ce PDF est protégé par un mot de passe : non pris en charge.",
        "en": "This PDF is password-protected: not supported.",
        "es": "Este PDF está protegido con contraseña: no compatible.",
        "pt": "Este PDF está protegido por palavra-passe: não suportado.",
        "de": "Dieses PDF ist passwortgeschützt: nicht unterstützt."},
    "err_bad_page": {
        "fr": "Page introuvable : {detail}", "en": "Page not found: {detail}",
        "es": "Página no encontrada: {detail}", "pt": "Página não encontrada: {detail}",
        "de": "Seite nicht gefunden: {detail}"},
    "err_collinear": {
        "fr": "Points alignés : placez-en un en dehors de la ligne.",
        "en": "Points are collinear: place one off the line.",
        "es": "Puntos alineados: coloque uno fuera de la línea.",
        "pt": "Pontos alinhados: coloque um fora da linha.",
        "de": "Punkte liegen auf einer Linie: setzen Sie einen daneben."},
    "err_coincident": {
        "fr": "Deux points sont identiques (sur l'image ou sur la carte).",
        "en": "Two points are identical (on the image or on the map).",
        "es": "Dos puntos son idénticos (en la imagen o en el mapa).",
        "pt": "Dois pontos são idênticos (na imagem ou no mapa).",
        "de": "Zwei Punkte sind identisch (im Bild oder in der Karte)."},
    "err_mirror": {
        "fr": "Le calage retournerait l'image (effet miroir) : vérifiez l'ordre des points.",
        "en": "The fit would mirror the image: check the order of the points.",
        "es": "El ajuste voltearía la imagen (espejo): compruebe el orden de los puntos.",
        "pt": "O ajuste inverteria a imagem (espelho): verifique a ordem dos pontos.",
        "de": "Die Anpassung würde das Bild spiegeln: prüfen Sie die Reihenfolge der Punkte."},
    "err_geographic": {
        "fr": "Le SCR du projet est géographique (degrés) : choisissez un SCR projeté (ex. EPSG:2154).",
        "en": "The project CRS is geographic (degrees): choose a projected CRS (e.g. EPSG:2154).",
        "es": "El SRC del proyecto es geográfico (grados): elija un SRC proyectado (p. ej. EPSG:2154).",
        "pt": "O SRC do projeto é geográfico (graus): escolha um SRC projetado (ex. EPSG:2154).",
        "de": "Das Projekt-KBS ist geographisch (Grad): wählen Sie ein projiziertes KBS (z. B. EPSG:2154)."},
    "err_write": {
        "fr": "Écriture impossible : {detail}", "en": "Cannot write the file: {detail}",
        "es": "No se puede escribir el archivo: {detail}", "pt": "Não é possível escrever o ficheiro: {detail}",
        "de": "Datei nicht schreibbar: {detail}"},
    "sec_source": {"fr": "Source", "en": "Source", "es": "Origen", "pt": "Origem", "de": "Quelle"},
    "sec_view": {
        "fr": "Repères sur l'image", "en": "Landmarks on the image", "es": "Puntos en la imagen",
        "pt": "Pontos na imagem", "de": "Passpunkte im Bild"},
    "chip_pages": {
        "fr": "{n} page(s)", "en": "{n} page(s)", "es": "{n} página(s)", "pt": "{n} página(s)", "de": "{n} Seite(n)"},
    "chip_points": {
        "fr": "{n} point(s)", "en": "{n} point(s)", "es": "{n} punto(s)", "pt": "{n} ponto(s)", "de": "{n} Punkt(e)"},
    "chip_on": {"fr": "ACTIVÉ", "en": "ON", "es": "ACTIVADO", "pt": "ATIVADO", "de": "AN"},
    "chip_off": {"fr": "DÉSACTIVÉ", "en": "OFF", "es": "DESACTIVADO", "pt": "DESATIVADO", "de": "AUS"},
    "card_add_title": {
        "fr": "Ajouter au projet", "en": "Add to the project", "es": "Añadir al proyecto",
        "pt": "Adicionar ao projeto", "de": "Zum Projekt hinzufügen"},
    "card_add_on": {
        "fr": "Le plan calé s'ouvre dans QGIS, en haut du panneau Couches, et la carte zoome dessus.",
        "en": "The georeferenced plan opens in QGIS, at the top of the Layers panel, and the map zooms to it.",
        "es": "El plano georreferenciado se abre en QGIS, arriba del panel Capas, y el mapa hace zoom.",
        "pt": "A planta georreferenciada abre no QGIS, no topo do painel Camadas, e o mapa faz zoom.",
        "de": "Der georeferenzierte Plan öffnet sich in QGIS oben im Ebenenfenster, die Karte zoomt darauf."},
    "card_add_off": {
        "fr": "Le GeoTIFF est seulement écrit sur le disque.", "en": "The GeoTIFF is only written to disk.",
        "es": "El GeoTIFF solo se escribe en el disco.", "pt": "O GeoTIFF é apenas escrito no disco.",
        "de": "Das GeoTIFF wird nur auf die Festplatte geschrieben."},
    "card_hide_title": {
        "fr": "Masquer au clic", "en": "Hide on click", "es": "Ocultar al clic", "pt": "Ocultar ao clicar",
        "de": "Beim Klick ausblenden"},
    "card_hide_on": {
        "fr": "La fenêtre disparaît le temps du clic sur la carte, puis revient.",
        "en": "The window disappears for the click, then comes back by itself.",
        "es": "La ventana desaparece durante el clic y vuelve sola.",
        "pt": "A janela desaparece durante o clique e volta sozinha.",
        "de": "Das Fenster verschwindet für den Klick und kommt von selbst zurück."},
    "card_hide_off": {
        "fr": "La fenêtre reste affichée : placez-la de façon à garder la carte visible.",
        "en": "The window stays visible: place it so the map stays visible.",
        "es": "La ventana sigue visible: colóquela para ver el mapa.",
        "pt": "A janela fica visível: coloque-a de modo a ver o mapa.",
        "de": "Das Fenster bleibt sichtbar: so platzieren, dass die Karte sichtbar bleibt."},
    "btn_log": {"fr": "Journal", "en": "Log", "es": "Registro", "pt": "Registo", "de": "Protokoll"},
    "recap_none": {
        "fr": "Ouvrez un PDF ou une image, puis placez au moins deux repères.",
        "en": "Open a PDF or an image, then place at least two landmarks.",
        "es": "Abra un PDF o una imagen y coloque al menos dos puntos.",
        "pt": "Abra um PDF ou uma imagem e coloque pelo menos dois pontos.",
        "de": "Öffnen Sie ein PDF oder ein Bild und setzen Sie mindestens zwei Punkte."},
    "recap_points": {
        "fr": "<b style=\"color:#1a6b3a\">{page}</b> · {n} point(s)",
        "en": "<b style=\"color:#1a6b3a\">{page}</b> · {n} point(s)",
        "es": "<b style=\"color:#1a6b3a\">{page}</b> · {n} punto(s)",
        "pt": "<b style=\"color:#1a6b3a\">{page}</b> · {n} ponto(s)",
        "de": "<b style=\"color:#1a6b3a\">{page}</b> · {n} Punkt(e)"},
    "recap_added": {
        "fr": "➕ ajouté au projet", "en": "➕ added to the project", "es": "➕ añadido al proyecto",
        "pt": "➕ adicionado ao projeto", "de": "➕ zum Projekt hinzugefügt"},
    "log_opened": {
        "fr": "ℹ Ouvert : {name} ({n} page(s))", "en": "ℹ Opened: {name} ({n} page(s))",
        "es": "ℹ Abierto: {name} ({n} página(s))", "pt": "ℹ Aberto: {name} ({n} página(s))",
        "de": "ℹ Geöffnet: {name} ({n} Seite(n))"},
    "log_point": {
        "fr": "▶ Point {n} : image ({px} ; {py}) → carte ({x} ; {y})",
        "en": "▶ Point {n}: image ({px} ; {py}) → map ({x} ; {y})",
        "es": "▶ Punto {n}: imagen ({px} ; {py}) → mapa ({x} ; {y})",
        "pt": "▶ Ponto {n}: imagem ({px} ; {py}) → mapa ({x} ; {y})",
        "de": "▶ Punkt {n}: Bild ({px} ; {py}) → Karte ({x} ; {y})"},
    "log_fit": {
        "fr": "ℹ {kind} sur {n} points, écart quadratique moyen {rms} m",
        "en": "ℹ {kind} on {n} points, RMS error {rms} m",
        "es": "ℹ {kind} con {n} puntos, error cuadrático medio {rms} m",
        "pt": "ℹ {kind} com {n} pontos, erro quadrático médio {rms} m",
        "de": "ℹ {kind} mit {n} Punkten, mittlerer quadratischer Fehler {rms} m"},
    "log_written": {
        "fr": "✔ OK → {path}", "en": "✔ OK → {path}", "es": "✔ OK → {path}", "pt": "✔ OK → {path}",
        "de": "✔ OK → {path}"},
    "log_error": {
        "fr": "✘ Erreur : {detail}", "en": "✘ Error: {detail}", "es": "✘ Error: {detail}",
        "pt": "✘ Erro: {detail}", "de": "✘ Fehler: {detail}"},
    "key_switch": {
        "fr": "Rendre transparent", "en": "Make transparent", "es": "Hacer transparente",
        "pt": "Tornar transparente", "de": "Transparent machen"},
    "key_switch_tip": {
        "fr": "Rend transparente une couleur de l'image (par exemple le fond blanc d'un scan) : le plan calé laisse voir la carte dessous.",
        "en": "Makes one colour of the image transparent (e.g. the white background of a scan) so the map shows through the georeferenced plan.",
        "es": "Hace transparente un color de la imagen (p. ej. el fondo blanco de un escaneado) para ver el mapa a través del plano.",
        "pt": "Torna transparente uma cor da imagem (p. ex. o fundo branco de uma digitalização) para ver o mapa através da planta.",
        "de": "Macht eine Farbe des Bildes transparent (z. B. den weißen Hintergrund eines Scans), sodass die Karte durchscheint."},
    "key_swatch_tip": {
        "fr": "Couleur rendue transparente — cliquez pour en choisir une autre",
        "en": "Colour made transparent — click to choose another",
        "es": "Color que se hace transparente — clic para elegir otro",
        "pt": "Cor tornada transparente — clique para escolher outra",
        "de": "Transparent gemachte Farbe — Klick zum Ändern"},
    "key_pick_tip": {
        "fr": "Pipette : cliquez ensuite la couleur sur l'image", "en": "Eyedropper: then click the colour on the image",
        "es": "Cuentagotas: luego haga clic en el color de la imagen", "pt": "Conta-gotas: depois clique na cor da imagem",
        "de": "Pipette: danach die Farbe im Bild anklicken"},
    "key_tol_tip": {
        "fr": "Tolérance : plus elle est grande, plus les teintes voisines deviennent transparentes",
        "en": "Tolerance: the higher it is, the more neighbouring shades become transparent",
        "es": "Tolerancia: cuanto mayor, más tonos cercanos se vuelven transparentes",
        "pt": "Tolerância: quanto maior, mais tons próximos ficam transparentes",
        "de": "Toleranz: je höher, desto mehr benachbarte Farbtöne werden transparent"},
    "key_dialog": {
        "fr": "Couleur à rendre transparente", "en": "Colour to make transparent",
        "es": "Color que se hace transparente", "pt": "Cor a tornar transparente", "de": "Transparent zu machende Farbe"},
    "hint_pick": {
        "fr": "💧 Cliquez sur l'image la couleur à rendre transparente. Échap = annuler.",
        "en": "💧 Click on the image the colour to make transparent. Esc = cancel.",
        "es": "💧 Haga clic en la imagen en el color que se hará transparente. Esc = cancelar.",
        "pt": "💧 Clique na imagem a cor a tornar transparente. Esc = cancelar.",
        "de": "💧 Klicken Sie im Bild die transparent zu machende Farbe an. Esc = abbrechen."},
    "recap_key": {
        "fr": "◻ transparent : {color} (±{tol})", "en": "◻ transparent: {color} (±{tol})",
        "es": "◻ transparente: {color} (±{tol})", "pt": "◻ transparente: {color} (±{tol})",
        "de": "◻ transparent: {color} (±{tol})"},
    "log_key": {
        "fr": "ℹ Couleur transparente {color}, tolérance {tol}", "en": "ℹ Transparent colour {color}, tolerance {tol}",
        "es": "ℹ Color transparente {color}, tolerancia {tol}", "pt": "ℹ Cor transparente {color}, tolerância {tol}",
        "de": "ℹ Transparente Farbe {color}, Toleranz {tol}"},
    "ab_version": {
        "fr": "Version {version} — journal des modifications", "en": "Version {version} — changelog",
        "es": "Versión {version} — registro de cambios", "pt": "Versão {version} — registo de alterações",
        "de": "Version {version} — Änderungsprotokoll"},
    "ab_description": {
        "fr": "CalePlan ouvre un PDF multipage (vignettes, choix de la page) ou une image, et la cale sur la "
              "carte QGIS avec deux clics par repère : un sur le plan, un sur la carte. Deux points suffisent "
              "(similitude, sans déformation) ; avec trois points l'écart est contrôlé, et dès quatre points une "
              "transformation affine corrige la déformation du scan. Le résultat est un GeoTIFF dans le SCR du "
              "projet, ajouté au projet.",
        "en": "CalePlan opens a multi-page PDF (thumbnails, page picker) or an image and georeferences it on the "
              "QGIS map with two clicks per landmark: one on the plan, one on the map. Two points are enough "
              "(similarity, no distortion); with three points the error is checked, and from four points an affine "
              "transformation corrects the scan distortion. The result is a GeoTIFF in the project CRS, added to "
              "the project.",
        "es": "CalePlan abre un PDF de varias páginas (miniaturas, elección de la página) o una imagen y la "
              "georreferencia en el mapa de QGIS con dos clics por punto: uno en el plano y otro en el mapa. Dos "
              "puntos bastan (semejanza, sin deformación); con tres puntos se controla el error y desde cuatro una "
              "transformación afín corrige la deformación del escaneado. El resultado es un GeoTIFF en el SRC del "
              "proyecto, añadido al proyecto.",
        "pt": "O CalePlan abre um PDF com várias páginas (miniaturas, escolha da página) ou uma imagem e "
              "georreferencia-a no mapa do QGIS com dois cliques por ponto: um na planta e outro no mapa. Dois "
              "pontos bastam (semelhança, sem deformação); com três pontos o erro é controlado e a partir de quatro "
              "uma transformação afim corrige a deformação da digitalização. O resultado é um GeoTIFF no SRC do "
              "projeto, adicionado ao projeto.",
        "de": "CalePlan öffnet ein mehrseitiges PDF (Vorschaubilder, Seitenwahl) oder ein Bild und georeferenziert "
              "es in der QGIS-Karte mit zwei Klicks pro Punkt: einer im Plan, einer in der Karte. Zwei Punkte "
              "genügen (Ähnlichkeit, ohne Verzerrung); mit drei Punkten wird der Fehler kontrolliert, ab vier "
              "Punkten korrigiert eine affine Transformation die Verzerrung des Scans. Ergebnis ist ein GeoTIFF im "
              "Projekt-KBS, das dem Projekt hinzugefügt wird."},
    "ab_note": {
        "fr": "<b>À savoir</b> — les PDF sont lus par PyMuPDF s'il est installé (le plus fiable), sinon par le pilote PDF de GDAL "
              "fourni avec QGIS. Les images (JPG, PNG, TIFF) n'ont besoin de rien.",
        "en": "<b>Good to know</b> — PDFs are read with PyMuPDF if installed (most reliable), otherwise with the GDAL PDF driver "
              "shipped with QGIS. Images (JPG, PNG, TIFF) need nothing extra.",
        "es": "<b>A tener en cuenta</b> — los PDF se leen con PyMuPDF si está instalado (lo más fiable), si no con el controlador PDF de "
              "GDAL incluido en QGIS. Las imágenes (JPG, PNG, TIFF) no necesitan nada más.",
        "pt": "<b>A saber</b> — os PDF são lidos com o PyMuPDF se instalado (o mais fiável), senão com o controlador PDF do GDAL "
              "incluído no QGIS. As imagens (JPG, PNG, TIFF) não precisam de nada mais.",
        "de": "<b>Gut zu wissen</b> — PDFs werden mit PyMuPDF gelesen, falls installiert (am zuverlässigsten), sonst mit dem in QGIS "
              "enthaltenen GDAL-PDF-Treiber. Bilder (JPG, PNG, TIFF) brauchen nichts zusätzlich."},
    "err_no_name": {
        "fr": "Indiquez un nom de fichier de sortie.", "en": "Enter an output file name.",
        "es": "Indique un nombre de archivo de salida.", "pt": "Indique um nome de ficheiro de saída.",
        "de": "Geben Sie einen Ausgabedateinamen an."},
}
