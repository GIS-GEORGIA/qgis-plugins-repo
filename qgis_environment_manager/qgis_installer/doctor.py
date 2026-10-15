"""Health checks of the environment QGIS lives in. Reads only, no UI.

Every check looks at one concrete thing that is known to break QGIS and answers with findings ``(level, key, params)`` (level
``problem`` / ``warn`` / ``info``; the text of a finding is the i18n key ``doc_<key>``). A check that finds nothing says nothing: ``run_all``
also returns which checks ran, so "no problem found" means "these things were looked at", not "everything is fine".

* shadowing - a Python library in the user's own folder (``~/.local/lib/python3.x/site-packages``, from ``pip install --user``) is found
  before the system's copy that QGIS and its plugins were built against; this is the commonest way a working QGIS breaks.
* gdal - the GDAL command line tools and the GDAL Python bindings are different versions.
* proj - PROJ_LIB / PROJ_DATA point to a folder that is not there or has no proj.db (every coordinate transformation then fails).
* repo - the QGIS apt repository file is for another release than the one running (a distribution upgrade leaves it behind: 404 on update).
* dpkg - the package database is in a half-finished state (``dpkg --audit``).
* disk - little free space where QGIS writes (the profile, the package cache).
* sources - several QGIS installations of the same major version share one profile folder.
"""
import glob
import os
import re
import shutil
import subprocess

from . import i18n

# top-level module folder names whose user copy hides the system one
WATCHED = ("numpy", "osgeo", "pyproj", "shapely", "pandas", "scipy", "matplotlib", "rasterio", "fiona", "psycopg2", "geopandas", "PyQt5", "sip")
LOW_DISK = 1024 ** 3                         # 1 GiB


def _run(cmd, timeout=60):
    try:
        env = dict(os.environ, LC_ALL="C", LANG="C")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout + p.stderr
    except Exception:
        return 1, ""


# ---------------------------------------------------------------- python libraries that hide the system's
def user_site_dirs(home=None):
    home = home or os.path.expanduser("~")
    return sorted(glob.glob(os.path.join(home, ".local", "lib", "python3*", "site-packages")))


def system_site_dirs():
    import site
    dirs = list(getattr(site, "getsitepackages", lambda: [])())
    dirs += ["/usr/lib/python3/dist-packages", "/usr/lib64/python3/site-packages"]
    return [d for d in dict.fromkeys(dirs) if os.path.isdir(d)]


def check_shadowing(user_dirs, system_dirs, exists=os.path.isdir, names=WATCHED):
    out = []
    for name in names:
        user = next((d for d in user_dirs if exists(os.path.join(d, name))), None)
        system = next((d for d in system_dirs if exists(os.path.join(d, name))), None)
        if user and system:
            out.append(("warn", "shadowing", {"name": name, "user": os.path.join(user, name), "system": os.path.join(system, name)}))
    return out


# ---------------------------------------------------------------- GDAL
def _major_minor(text):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def check_gdal(cli_output, python_version):
    """``gdalinfo --version`` output and ``osgeo.gdal.__version__``; both given and different -> a finding."""
    cli, py = _major_minor(cli_output), _major_minor(python_version)
    if cli and py and cli != py:
        return [("warn", "gdal_mismatch", {"cli": "{}.{}".format(*cli), "py": "{}.{}".format(*py)})]
    return []


def python_gdal_version(python="python3", run=None):
    rc, out = (run or _run)([python, "-c", "from osgeo import gdal; print(gdal.__version__)"])
    return out.strip() if rc == 0 else None


# ---------------------------------------------------------------- PROJ
def check_proj(env, exists=os.path.exists):
    out = []
    for var in ("PROJ_LIB", "PROJ_DATA"):
        path = env.get(var)
        if not path:
            continue
        for part in [p for p in path.split(os.pathsep) if p]:
            if not exists(part):
                out.append(("problem", "proj_missing", {"var": var, "path": part}))
            elif not exists(os.path.join(part, "proj.db")):
                out.append(("problem", "proj_nodb", {"var": var, "path": part}))
    return out


# ---------------------------------------------------------------- repository and packages
def check_repo(sources_text, codename):
    """The QGIS apt repository file names the release it is for (``Suites: noble``); a different one than the system's is a left-over."""
    m = re.search(r"^Suites:\s*(\S+)", sources_text or "", re.M)
    if m and codename and m.group(1) != codename:
        return [("problem", "repo_old", {"suite": m.group(1), "codename": codename})]
    return []


def check_dpkg(audit_output):
    text = (audit_output or "").strip()
    if text:
        return [("problem", "dpkg_broken", {"first": text.splitlines()[0][:120]})]
    return []


def check_disk(paths, usage=shutil.disk_usage, exists=os.path.exists):
    out = []
    seen = set()
    for label, path in paths:
        if not exists(path):
            continue
        try:
            free = usage(path).free
        except OSError:
            continue
        if free < LOW_DISK and label not in seen:
            seen.add(label)
            out.append(("warn", "disk_low", {"where": path, "free": "{:.0f} MB".format(free / 1048576)}))
    return out


def check_sources(items):
    """Installations of the same major version that use one profile folder (system packages and containers; Flatpak and Snap keep their own)."""
    shared = [i for i in items if i["kind"] in ("apt", "dist", "container")]
    if len(shared) > 1:
        return [("info", "shared_profile", {"n": len(shared)})]
    return []


# ---------------------------------------------------------------- all of them
def run_all(items, sysinfo, env=None, run=None, home=None, read=None, exists=os.path.exists, usage=shutil.disk_usage,
            user_dirs=None, system_dirs=None, python_gdal=None):
    """{'findings': [(level, key, params)], 'ran': [check names], 'skipped': [check names]}; every argument is injectable for tests."""
    env = os.environ if env is None else env
    run = run or _run
    findings, ran, skipped = [], [], []

    findings += check_shadowing(user_site_dirs(home) if user_dirs is None else user_dirs,
                                system_site_dirs() if system_dirs is None else system_dirs)
    ran.append("shadowing")

    gdal_cli = shutil.which("gdalinfo") if run is _run else True
    if gdal_cli:
        rc, out = run(["gdalinfo", "--version"])
        py = python_gdal if python_gdal is not None else python_gdal_version(run=run)
        if rc == 0 and py:
            findings += check_gdal(out, py)
            ran.append("gdal")
        else:
            skipped.append("gdal")
    else:
        skipped.append("gdal")

    findings += check_proj(env, exists)
    ran.append("proj")

    if sysinfo.get("apt"):
        path = "/etc/apt/sources.list.d/qgis.sources"
        text = None
        if read is not None:
            text = read(path)
        elif exists(path):
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = None
        if text is not None:
            findings += check_repo(text, sysinfo.get("code"))
            ran.append("repo")
        else:
            skipped.append("repo")
        if shutil.which("dpkg") or run is not _run:
            rc, out = run(["dpkg", "--audit"])
            if rc == 0:
                findings += check_dpkg(out)
                ran.append("dpkg")
            else:
                skipped.append("dpkg")

    home = home or os.path.expanduser("~")
    findings += check_disk([("profile", home), ("packages", "/var")], usage, exists)
    ran.append("disk")
    findings += check_sources(items)
    ran.append("sources")
    order = {"problem": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: order[f[0]])
    return {"findings": findings, "ran": ran, "skipped": skipped}


def lines(result, lang="en"):
    """A result as lines of text: what was looked at, each finding with its level, what could not be looked at."""
    t = lambda k, **kw: i18n.t(k, lang, **kw)  # noqa: E731
    out = [t("doc_head", ran=", ".join(t("doc_chk_" + c) for c in result["ran"]))]
    for level, key, params in result["findings"]:
        out.append("[{}] {}".format(t("doc_level_" + level), t("doc_" + key, **params)))
    if not result["findings"]:
        out.append(t("doc_none"))
    if result["skipped"]:
        out.append(t("doc_skipped", skipped=", ".join(t("doc_chk_" + c) for c in result["skipped"])))
    return out


def has_problem(result):
    return any(level == "problem" for level, _k, _p in result["findings"])
