"""QGIS without internet on the target machine: a folder (or a USB stick) made once on a machine that is online, and an install from it.

Only the Flatpak build can do this in one piece: it carries its runtime, so ``flatpak create-usb`` copies the
application and everything it needs into ``DEST/.ostree/repo`` and ``flatpak install --sideload-repo`` reads it back with no
network. Flathub has no collection ID in its repo file, and ``create-usb`` refuses a remote without one, so the plan sets
the public one (``org.flathub.Stable``) first - verified for real: export, then install in a container with no network.

``export_plan`` and ``install_plan`` return ``{'steps': [...], 'notes': [keys], 'manual': []}`` like ``recipes.make_plan``.
Texts are in i18n.STR under ``rcw_off_*`` (notes). The destination is quoted for the shell and may not hold a newline.
"""
import os
import posixpath
import shlex

REF = "org.qgis.qgis"
COLLECTION = "org.flathub.Stable"
REPO_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
REPO_FILE = "flathub.flatpakrepo"
BRANCHES = ("stable", "lts")


class OfflineError(ValueError):
    """The request cannot be turned into commands (a bad path or branch). ``args[0]`` is an i18n key."""


def _step(root, sh):
    return {"root": root, "sh": "set -eu\n" + sh.rstrip("\n") + "\n"}


def _path(p):
    if not p or "\n" in p or "\r" in p or "\0" in p:
        raise OfflineError("off_bad_path")
    p = os.path.expanduser(p)
    p = posixpath.normpath(p) if p.startswith("/") else os.path.abspath(p)
    if p == "/":
        raise OfflineError("off_bad_path")
    return p


def _scope(scope):
    if scope not in ("user", "system"):
        raise OfflineError("off_bad_scope")
    return scope


def _ref(branch):
    if branch not in BRANCHES:
        raise OfflineError("off_bad_branch")
    return "{}//{}".format(REF, branch)


def export_plan(dest, branch="lts", scope="system", have_flatpak=True):
    """Make DEST ready for another machine: QGIS plus its runtime (about 1.2 GB for the LTS build), and the Flathub repo file."""
    dest, scope, ref = _path(dest), _scope(scope), _ref(branch)
    if not have_flatpak:
        return {"steps": [], "notes": ["off_no_flatpak"], "manual": []}
    d, flag, root = shlex.quote(dest), "--" + scope, scope == "system"
    sh = "\n".join([
        "mkdir -p " + d,
        "flatpak remote-add {f} --if-not-exists flathub {url}".format(f=flag, url=REPO_URL),
        "flatpak remote-modify {f} --collection-id={c} flathub".format(f=flag, c=COLLECTION),
        "flatpak info {f} {ref} >/dev/null 2>&1 || flatpak install {f} -y flathub {ref}".format(f=flag, ref=ref),
        "flatpak create-usb {f} {d} {ref}".format(f=flag, d=d, ref=ref),
        "if command -v curl >/dev/null 2>&1; then curl -fsSL -o {d}/{name} {url}; else wget -q -O {d}/{name} {url}; fi".format(
            d=d, name=REPO_FILE, url=REPO_URL),
    ])
    return {"steps": [_step(root, sh)], "notes": ["off_export_size"], "manual": []}


def install_plan(src, branch="lts", scope="system", have_flatpak=True):
    """Install the QGIS that DEST holds, with no network. The machine needs Flatpak itself."""
    src, scope, ref = _path(src), _scope(scope), _ref(branch)
    if not have_flatpak:
        return {"steps": [], "notes": ["off_no_flatpak"], "manual": []}
    s, flag = shlex.quote(src), "--" + scope
    sh = "\n".join([
        "test -d {s}/.ostree/repo".format(s=s),
        "flatpak remote-add {f} --if-not-exists flathub {s}/{name}".format(f=flag, s=s, name=REPO_FILE),
        "flatpak remote-modify {f} --collection-id={c} flathub".format(f=flag, c=COLLECTION),
        "flatpak install {f} -y --sideload-repo={s}/.ostree/repo flathub {ref}".format(f=flag, s=s, ref=ref),
    ])
    return {"steps": [_step(scope == "system", sh)], "notes": ["off_install_offline"], "manual": []}
