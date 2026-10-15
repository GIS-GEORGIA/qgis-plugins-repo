"""What QGIS and the GIS GEORGIA plugins need from the operating system, and how to install it (no UI).

The same table is the *components* list - the Linux counterpart of the OSGeo4W package chooser, kept small: command line
tools (GDAL, PROJ), GIS engines (GRASS, SAGA), Python libraries and database clients, each installed with the system's own
package manager. ``cat`` says where a component is listed; ``components()`` gives the rows, ``install_steps`` installs.
Nothing here removes packages: a library such as numpy can be a dependency of QGIS itself, and removing it would take QGIS along.

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
        "cat": "python", "kind": "module", "module": "psycopg2",
        "label": {"en": "PostgreSQL driver for Python (psycopg2)", "ka": "PostgreSQL-ის დრაივერი Python-ისთვის (psycopg2)"},
        "pkgs": {"apt-get": ["python3-psycopg2"], "dnf": ["python3-psycopg2"], "pacman": ["python-psycopg2"],
                 "zypper": ["python{pyver}-psycopg2"], "apk": ["py3-psycopg2"]},
    },
    "pgclient": {
        "cat": "db", "kind": "tool", "tools": ["pg_dump", "pg_restore", "psql"],
        "label": {"en": "PostgreSQL client tools (pg_dump, pg_restore, psql)",
                  "ka": "PostgreSQL-ის კლიენტის ხელსაწყოები (pg_dump, pg_restore, psql)"},
        "pkgs": {"apt-get": ["postgresql-client"], "dnf": ["postgresql"], "pacman": ["postgresql"],
                 "zypper": ["postgresql"], "apk": ["postgresql-client"]},
    },
    "exiftool": {
        "cat": "cli", "kind": "tool", "tools": ["exiftool"],
        "label": {"en": "ExifTool (RAW and HEIC photos)", "ka": "ExifTool (RAW და HEIC ფოტოები)"},
        "pkgs": {"apt-get": ["libimage-exiftool-perl"], "dnf": ["perl-Image-ExifTool"],
                 "pacman": ["perl-image-exiftool"], "zypper": ["exiftool"], "apk": ["exiftool"]},
    },
    "geopandas": {
        "cat": "python", "kind": "module", "module": "geopandas",
        "label": {"en": "GeoPandas (vector import into PostGIS)", "ka": "GeoPandas (ვექტორის იმპორტი PostGIS-ში)"},
        "pkgs": {"apt-get": ["python3-geopandas"], "dnf": ["python3-geopandas"], "pacman": ["python-geopandas"],
                 "zypper": ["python{pyver}-geopandas"], "apk": None},
    },
    "saga": {
        "cat": "engine", "kind": "tool", "tools": ["saga_cmd"],
        "label": {"en": "SAGA GIS (solar radiation)", "ka": "SAGA GIS (მზის რადიაცია)"},
        "pkgs": {"apt-get": ["saga"], "dnf": None, "pacman": None, "zypper": None, "apk": None},
    },
    "grass": {
        "cat": "engine", "kind": "tool", "tools": ["grass"],
        "label": {"en": "GRASS GIS (r.sun)", "ka": "GRASS GIS (r.sun)"},
        "pkgs": {"apt-get": ["grass"], "dnf": ["grass"], "pacman": None, "zypper": ["grass"], "apk": None},
    },
    "windninja": {
        "cat": "engine", "kind": "tool", "tools": ["WindNinja_cli"],
        "label": {"en": "WindNinja (wind downscaling)", "ka": "WindNinja (ქარის დეტალიზაცია)"},
        "pkgs": {"apt-get": None, "dnf": None, "pacman": None, "zypper": None, "apk": None},
    },
    "gdal": {
        "cat": "cli", "kind": "tool", "tools": ["gdalinfo", "ogr2ogr"],
        "label": {"en": "GDAL command line tools (gdalinfo, ogr2ogr, gdal_translate)",
                  "ka": "GDAL-ის ბრძანების სტრიქონის ხელსაწყოები (gdalinfo, ogr2ogr, gdal_translate)"},
        "pkgs": {"apt-get": ["gdal-bin"], "dnf": ["gdal"], "pacman": ["gdal"], "zypper": ["gdal"], "apk": ["gdal-tools"]},
    },
    "proj": {
        "cat": "cli", "kind": "tool", "tools": ["projinfo", "cs2cs"],
        "label": {"en": "PROJ tools (projinfo, cs2cs)", "ka": "PROJ-ის ხელსაწყოები (projinfo, cs2cs)"},
        "pkgs": {"apt-get": ["proj-bin"], "dnf": ["proj"], "pacman": ["proj"], "zypper": ["proj"], "apk": ["proj-util"]},
    },
    "gdal-python": {
        "cat": "python", "kind": "module", "module": "osgeo",
        "label": {"en": "GDAL/OGR for Python (osgeo)", "ka": "GDAL/OGR Python-ისთვის (osgeo)"},
        "pkgs": {"apt-get": ["python3-gdal"], "dnf": ["python3-gdal"], "pacman": ["gdal"],
                 "zypper": ["python{pyver}-GDAL"], "apk": ["py3-gdal"]},
    },
    "numpy": {
        "cat": "python", "kind": "module", "module": "numpy",
        "label": {"en": "NumPy", "ka": "NumPy"},
        "pkgs": {"apt-get": ["python3-numpy"], "dnf": ["python3-numpy"], "pacman": ["python-numpy"],
                 "zypper": ["python{pyver}-numpy"], "apk": ["py3-numpy"]},
    },
    "pandas": {
        "cat": "python", "kind": "module", "module": "pandas",
        "label": {"en": "pandas", "ka": "pandas"},
        "pkgs": {"apt-get": ["python3-pandas"], "dnf": ["python3-pandas"], "pacman": ["python-pandas"],
                 "zypper": ["python{pyver}-pandas"], "apk": ["py3-pandas"]},
    },
    "scipy": {
        "cat": "python", "kind": "module", "module": "scipy",
        "label": {"en": "SciPy", "ka": "SciPy"},
        "pkgs": {"apt-get": ["python3-scipy"], "dnf": ["python3-scipy"], "pacman": ["python-scipy"],
                 "zypper": ["python{pyver}-scipy"], "apk": ["py3-scipy"]},
    },
    "matplotlib": {
        "cat": "python", "kind": "module", "module": "matplotlib",
        "label": {"en": "Matplotlib (charts)", "ka": "Matplotlib (დიაგრამები)"},
        "pkgs": {"apt-get": ["python3-matplotlib"], "dnf": ["python3-matplotlib"], "pacman": ["python-matplotlib"],
                 "zypper": ["python{pyver}-matplotlib"], "apk": ["py3-matplotlib"]},
    },
    "shapely": {
        "cat": "python", "kind": "module", "module": "shapely",
        "label": {"en": "Shapely (geometry)", "ka": "Shapely (გეომეტრია)"},
        "pkgs": {"apt-get": ["python3-shapely"], "dnf": ["python3-shapely"], "pacman": ["python-shapely"],
                 "zypper": ["python{pyver}-Shapely"], "apk": ["py3-shapely"]},
    },
    "pyproj": {
        "cat": "python", "kind": "module", "module": "pyproj",
        "label": {"en": "pyproj (coordinate systems)", "ka": "pyproj (საკოორდინატო სისტემები)"},
        "pkgs": {"apt-get": ["python3-pyproj"], "dnf": ["python3-pyproj"], "pacman": ["python-pyproj"],
                 "zypper": ["python{pyver}-pyproj"], "apk": None},
    },
    "rasterio": {
        "cat": "python", "kind": "module", "module": "rasterio",
        "label": {"en": "rasterio (rasters)", "ka": "rasterio (რასტრები)"},
        "pkgs": {"apt-get": ["python3-rasterio"], "dnf": ["python3-rasterio"], "pacman": None,
                 "zypper": None, "apk": None},
    },
    "fiona": {
        "cat": "python", "kind": "module", "module": "fiona",
        "label": {"en": "Fiona (vector files)", "ka": "Fiona (ვექტორული ფაილები)"},
        "pkgs": {"apt-get": ["python3-fiona"], "dnf": ["python3-fiona"], "pacman": ["python-fiona"],
                 "zypper": ["python{pyver}-Fiona"], "apk": None},
    },
}

# where the components are listed, in this order
CATEGORIES = ("cli", "engine", "python", "db")

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


# Where packages put tools that a plain (non-login) PATH does not list: Arch installs ExifTool and other Perl tools in /usr/bin/vendor_perl,
# which only the login shell's profile adds. A tool there is installed, whatever this process's PATH says.
EXTRA_TOOL_DIRS = ("/usr/bin/vendor_perl", "/usr/bin/site_perl", "/usr/bin/core_perl", "/usr/local/bin", "/usr/sbin", "/sbin")


def _tool_present(tool, which, access=None):
    access = access or os.access
    if which(tool):
        return True
    if which is not shutil.which:                      # a test that injects its own `which` decides alone
        return False
    return any(access(os.path.join(d, tool), os.X_OK) and os.path.isfile(os.path.join(d, tool)) for d in EXTRA_TOOL_DIRS)


def is_present(req_id, which=shutil.which, find_spec=importlib.util.find_spec):
    """Is the module importable / are all the tools on PATH (or in the usual directories a login PATH adds) - in the interpreter that runs this."""
    r = REQ[req_id]
    if r["kind"] == "module":
        try:
            return find_spec(r["module"]) is not None
        except (ImportError, ValueError):
            return False
    return all(_tool_present(t, which) for t in r["tools"])


def status(plugin_id, **kw):
    """[{id, label, optional, present, packages}] for one plugin (packages per detected pm are not resolved here)."""
    return [{"id": rid, "label": REQ[rid]["label"], "optional": opt, "present": is_present(rid, **kw)}
            for rid, opt in PLUGIN_REQUIREMENTS.get(plugin_id, [])]


def components(pm, pyver=None, **kw):
    """Every component as a row, grouped by category in the order of CATEGORIES:
    ``{id, cat, label, present, packages, manual}`` (``manual``: no package for this package manager)."""
    rows = []
    for cat in CATEGORIES:
        for rid, spec in REQ.items():
            if spec.get("cat") != cat:
                continue
            pkgs, manual = packages_for([rid], pm, pyver)
            rows.append({"id": rid, "cat": cat, "label": spec["label"], "present": is_present(rid, **kw),
                         "packages": pkgs, "manual": bool(manual)})
    return rows


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
