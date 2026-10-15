"""Updating the QGIS that is already installed: what to run for each installation that was found. No UI.

``plan(items, sysinfo)`` takes the items of ``uninstall.find_installs`` and returns
``{'steps': [...], 'notes': [keys], 'manual': [{'title': key, 'text': str}]}`` like ``recipes.make_plan``.
Texts are in i18n.STR under ``rcw_upd_*`` (notes) and ``rcm_upd_*`` (manual block titles).

Updating means "the newest build of the same line": it does not change the channel (latest -> LTR needs a removal and a
new install, because apt will not downgrade) and it never touches user data. A running QGIS must be closed first.
"""
import shlex


def _step(root, sh):
    return {"root": root, "sh": "set -eu\n" + sh.rstrip("\n") + "\n"}


def plan(items, sysinfo):
    steps, notes, manual = [], [], []
    for it in items:
        kind = it["kind"]
        if kind == "apt":
            names = " ".join(shlex.quote(p) for p in it["pkgs"])
            steps.append(_step(True, "apt-get update\napt-get install -y --only-upgrade " + names))
        elif kind == "flatpak":
            scope = "system" if it.get("i") == "system" else "user"
            steps.append(_step(scope == "system", "flatpak update --{} -y org.qgis.qgis".format(scope)))
        elif kind == "snap":
            steps.append(_step(True, "snap refresh qgis"))
        elif kind == "dist":
            _dist(it, steps, notes, manual)
        elif kind == "container":
            notes.append("upd_container")
    actionable = bool(steps or manual)
    if actionable:
        notes.insert(0, "upd_close_qgis")
    elif not notes:
        notes.append("upd_none")
    seen = set()
    notes = [n for n in notes if not (n in seen or seen.add(n))]
    return {"steps": steps, "notes": notes, "manual": manual}


def _dist(it, steps, notes, manual):
    pm = it.get("pm")
    names = " ".join(shlex.quote(p) for p in it.get("pkgs") or ["qgis"])
    aur = [p for p in it.get("pkgs") or [] if p in ("qgis-ltr", "qgis-git")]
    if pm == "dnf":
        steps.append(_step(True, "dnf upgrade -y " + names))
    elif pm == "zypper":
        steps.append(_step(True, "zypper --non-interactive update " + names))
    elif pm == "rpm-ostree":
        steps.append(_step(True, "rpm-ostree upgrade"))
        notes.append("upd_ostree")
    elif pm == "pacman":
        # Arch does not support updating one package: a partial upgrade can break the system
        manual.append({"title": "upd_arch", "text": "sudo pacman -Syu"})
        notes.append("upd_arch_full")
        if aur:
            manual.append({"title": "upd_aur", "text": "yay -S --needed {}   # or paru".format(" ".join(aur))})
    else:
        notes.append("upd_unknown")
