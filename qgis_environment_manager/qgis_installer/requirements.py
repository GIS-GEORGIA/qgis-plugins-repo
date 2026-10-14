"""What the GIS GEORGIA QGIS plugins need from the operating system, and how to install it (no UI).

Each requirement is a Python module or a command line tool, with the distribution package that provides it
per package manager (``None`` = no package, install it by hand). The names are verified against every
distribution's repositories by tests/pkgnames_check.py (run through tests/run-distros.sh).

Only meaningful for a QGIS that uses the system's Python and tools (installed from the official repository
or the distribution); a Flatpak or Snap QGIS has its own sandbox - see ``qgis_runtime``.
"""
import importlib.util
import os
import shutil
import sys

# id -> {kind, module|tools, label{en,ka}, pkgs{pm: [package names] | None}}
REQ = {
    "psycopg2": {
        "kind": "module", "module": "psycopg2",
        "label": {"en": "PostgreSQL driver for Python (psycopg2)", "ka": "PostgreSQL-ის დრაივერი Python-ისთვის (psycopg2)"},
        "pkgs": {"apt-get": ["python3-psycopg2"], "dnf": ["python3-psycopg2"], "pacman": ["python-psycopg2"],
                 "zypper": ["python{pyver}-psycopg2"], "apk": ["py3-psycopg2"]},
    },
    "pgclient": {
        "kind": "tool", "tools": ["pg_dump", "pg_restore", "psql"],
        "label": {"en": "PostgreSQL client tools (pg_dump, pg_restore, psql)",
                  "ka": "PostgreSQL-ის კლიენტის ხელსაწყოები (pg_dump, pg_restore, psql)"},
        "pkgs": {"apt-get": ["postgresql-client"], "dnf": ["postgresql"], "pacman": ["postgresql"],
                 "zypper": ["postgresql"], "apk": ["postgresql-client"]},
    },
    "exiftool": {
        "kind": "tool", "tools": ["exiftool"],
        "label": {"en": "ExifTool (RAW and HEIC photos)", "ka": "ExifTool (RAW და HEIC ფოტოები)"},
        "pkgs": {"apt-get": ["libimage-exiftool-perl"], "dnf": ["perl-Image-ExifTool"],
                 "pacman": ["perl-image-exiftool"], "zypper": ["exiftool"], "apk": ["exiftool"]},
    },
    "geopandas": {
        "kind": "module", "module": "geopandas",
        "label": {"en": "GeoPandas (vector import into PostGIS)", "ka": "GeoPandas (ვექტორის იმპორტი PostGIS-ში)"},
        "pkgs": {"apt-get": ["python3-geopandas"], "dnf": ["python3-geopandas"], "pacman": ["python-geopandas"],
                 "zypper": ["python{pyver}-geopandas"], "apk": None},
    },
    "saga": {
        "kind": "tool", "tools": ["saga_cmd"],
        "label": {"en": "SAGA GIS (solar radiation)", "ka": "SAGA GIS (მზის რადიაცია)"},
        "pkgs": {"apt-get": ["saga"], "dnf": None, "pacman": None, "zypper": None, "apk": None},
    },
    "grass": {
        "kind": "tool", "tools": ["grass"],
        "label": {"en": "GRASS GIS (r.sun)", "ka": "GRASS GIS (r.sun)"},
        "pkgs": {"apt-get": ["grass"], "dnf": ["grass"], "pacman": None, "zypper": ["grass"], "apk": None},
    },
    "windninja": {
        "kind": "tool", "tools": ["WindNinja_cli"],
        "label": {"en": "WindNinja (wind downscaling)", "ka": "WindNinja (ქარის დეტალიზაცია)"},
        "pkgs": {"apt-get": None, "dnf": None, "pacman": None, "zypper": None, "apk": None},
    },
}

# GIS GEORGIA plugin folder name -> [(requirement id, optional?)]
PLUGIN_REQUIREMENTS = {
    "postgis_manager": [("psycopg2", False), ("pgclient", False), ("geopandas", True)],
    "photo_geotagger": [("exiftool", True)],
    "geoeco": [("saga", False), ("grass", False), ("windninja", True)],
}

INSTALL_CMD = {
    "apt-get": "apt-get install -y",
    "dnf": "dnf install -y",
    "pacman": "pacman -S --noconfirm",
    "zypper": "zypper --non-interactive install",
    "apk": "apk add",
}


def is_present(req_id, which=shutil.which, find_spec=importlib.util.find_spec):
    """Is the module importable / are all the tools on PATH - in the interpreter that runs this."""
    r = REQ[req_id]
    if r["kind"] == "module":
        try:
            return find_spec(r["module"]) is not None
        except (ImportError, ValueError):
            return False
    return all(which(t) for t in r["tools"])


def status(plugin_id, **kw):
    """[{id, label, optional, present, packages}] for one plugin (packages per detected pm are not resolved here)."""
    return [{"id": rid, "label": REQ[rid]["label"], "optional": opt, "present": is_present(rid, **kw)}
            for rid, opt in PLUGIN_REQUIREMENTS.get(plugin_id, [])]


def python_tag():
    """'313' for Python 3.13 - openSUSE names its Python packages per interpreter (python313-psycopg2)."""
    return "{}{}".format(sys.version_info[0], sys.version_info[1])


def packages_for(req_ids, pm, pyver=None):
    """-> (package names to install, requirement ids that have no package for this package manager).

    ``pyver`` fills the ``{pyver}`` placeholder (default: the running interpreter's version)."""
    pyver = pyver or python_tag()
    pkgs, manual = [], []
    for rid in req_ids:
        names = REQ[rid]["pkgs"].get(pm)
        if names:
            names = [n.replace("{pyver}", pyver) for n in names]
            pkgs += [n for n in names if n not in pkgs]
        else:
            manual.append(rid)
    return pkgs, manual


def install_steps(req_ids, pm, pyver=None):
    """-> (steps, manual): one root step installing everything that has a package, and the ids that do not."""
    pkgs, manual = packages_for(req_ids, pm, pyver)
    cmd = INSTALL_CMD.get(pm)
    if not pkgs or not cmd:
        return [], list(req_ids) if not cmd else manual
    return [{"root": True, "sh": "set -eu\n" + cmd + " " + " ".join(pkgs) + "\n"}], manual


def qgis_runtime(env=None, exists=os.path.exists):
    """'flatpak', 'snap' or 'native' (system Python and tools visible to QGIS)."""
    env = os.environ if env is None else env
    if exists("/.flatpak-info") or env.get("FLATPAK_ID"):
        return "flatpak"
    if env.get("SNAP") or env.get("SNAP_NAME"):
        return "snap"
    return "native"
