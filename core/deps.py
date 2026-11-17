"""Installation a la demande d'ezdxf (lecture / ecriture des DXF).

Seul le calage d'un DXF en a besoin ; PDF et images fonctionnent sans. La bibliotheque n'est
donc pas embarquee dans le paquet publie : a la premiere ouverture d'un DXF, l'extension
propose de l'installer dans `<plugin>/libs` (pip, sans dependances : numpy vient de QGIS).
ezdxf, fontTools et pyparsing sont sous licence MIT. `libs/` est efface par QGIS a chaque
mise a jour de l'extension : l'installation est alors a refaire.
"""
import os
import sys

REQUIRED = (
    ("ezdxf", "ezdxf==1.4.4"),
    ("fontTools", "fontTools==4.63.0"),
    ("pyparsing", "pyparsing==3.3.2"),
    ("typing_extensions", "typing_extensions"),
)


def libs_dir():
    """`<plugin>/libs`, cree au besoin et place en tete du sys.path."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    libs = os.path.join(root, "libs")
    os.makedirs(libs, exist_ok=True)
    if libs not in sys.path:
        sys.path.insert(0, libs)
    return libs


def missing():
    """Specifications pip des bibliotheques absentes (ou dont l'import echoue)."""
    libs_dir()
    absent = []
    for module, spec in REQUIRED:
        try:
            __import__(module)
        except Exception:        # absente ou installation tronquee : seule la reinstallation y remedie
            absent.append(spec)
    return absent


def python_exe():
    """python.exe de l'installation (sys.executable est qgis-bin.exe sous Windows), ou None."""
    candidates = []
    exe = sys.executable or ""
    if os.path.basename(exe).lower().startswith("python"):
        candidates.append(exe)
    if os.name == "nt":
        candidates += [os.path.join(sys.prefix, "python.exe"), os.path.join(sys.prefix, "python3.exe"),
                       os.path.join(sys.prefix, "Scripts", "python.exe")]
    else:
        candidates += [os.path.join(sys.prefix, "bin", "python3"), os.path.join(sys.prefix, "bin", "python")]
    import shutil
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def pip_command(specs):
    python = python_exe()
    if not python:
        return None
    return [python, "-m", "pip", "install", "--target", libs_dir(), "--upgrade", "--no-deps",
            "--no-warn-script-location"] + list(specs)


def manual_command(specs):
    """La meme commande en texte, a coller dans l'OSGeo4W Shell si l'installation automatique echoue."""
    return '"%s" -m pip install --target "%s" --upgrade --no-deps %s' % (
        python_exe() or "python", libs_dir(), " ".join(specs))


def install(specs, timeout=600):
    """Lance pip. Retourne (succes, sortie). Ne leve pas : l'appelant affiche la sortie."""
    import subprocess  # nosec B404
    cmd = pip_command(specs)
    if cmd is None:
        return False, "Python introuvable (sys.prefix = %s)." % sys.prefix
    try:
        # Liste d'arguments sans shell : argv[0] est un python.exe localise sur le disque, le reste
        # est constitue de litteraux et des noms de paquets figes dans REQUIRED.
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)  # nosec B603
    except Exception as exc:        # reseau, droits, delai : le detail est montre a l'utilisateur
        return False, "%s: %s" % (type(exc).__name__, exc)
    out = ((res.stdout or "") + (res.stderr or "")).strip()
    if res.returncode != 0:
        return False, out or "pip : code %s" % res.returncode
    import importlib
    importlib.invalidate_caches()
    return True, out
