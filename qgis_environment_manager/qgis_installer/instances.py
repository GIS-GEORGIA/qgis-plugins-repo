"""Every QGIS on this machine as something you can start, and whether a newer build is waiting. No UI.

``list_instances(items)`` takes the items of ``uninstall.find_installs`` and returns rows
``{id, kind, version, label_item, launch, launchable, shared_profile}``: ``launch`` is the argument list that starts that QGIS
(``None`` when no way is known), e.g. ``['flatpak', 'run', '--branch=lts', 'org.qgis.qgis']``.
``check_updates(items)`` asks each installation's own package manager whether a newer build is available. It only reads: nothing
is installed, and a package manager that needs the network and cannot reach it answers "unknown" (None), never "up to date".

Two QGIS programs of the same major version share the user's profile folder; starting both at once can corrupt it, which is why
``launch`` is only ever called after the user has seen the command and the warning (see the ``inst_profile`` text).
"""
import shutil
import subprocess

from .system import CONTAINER_BOX


def _run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def _instance_id(it):
    kind = it["kind"]
    if kind == "flatpak":
        return "flatpak-{}-{}".format(it.get("i", "user"), it.get("br") or "default")
    if kind == "dist":
        return "dist-{}-{}".format(it.get("pm", ""), (it.get("pkgs") or ["qgis"])[0])
    if kind == "container":
        return "container-" + it["tool"]
    return kind                                       # apt, snap


def _launch_argv(it, which):
    kind = it["kind"]
    if kind in ("apt", "dist"):
        names = ["qgis"]
        if kind == "dist":                            # an AUR package may install its own binary name
            names = [n for n in (it.get("pkgs") or []) if n.startswith("qgis")] + ["qgis"]
        for n in names:
            if which(n):
                return [n]
        return None
    if kind == "flatpak":
        if not which("flatpak"):
            return None
        branch = ["--branch=" + it["br"]] if it.get("br") else []
        return ["flatpak", "run", *branch, "org.qgis.qgis"]
    if kind == "snap":
        return ["snap", "run", "qgis"] if which("snap") else None
    if kind == "container":
        box = it.get("name") or CONTAINER_BOX
        if it["tool"] == "distrobox" and which("distrobox"):
            return ["distrobox", "enter", box, "--", "qgis"]
        if it["tool"] == "toolbox" and which("toolbox"):
            return ["toolbox", "run", "--container", box, "qgis"]
    return None


def list_instances(items, which=None):
    """The installations that can be started, in the order found."""
    which = which or shutil.which
    out = []
    for it in items:
        if it["kind"] not in ("apt", "flatpak", "snap", "dist", "container"):
            continue
        argv = _launch_argv(it, which)
        out.append({"id": _instance_id(it), "kind": it["kind"], "version": it.get("v", ""), "label_item": it,
                    "launch": argv, "launchable": argv is not None,
                    "shared_profile": it["kind"] in ("apt", "dist", "container")})   # Flatpak and Snap keep their own profile
    return out


def find(instances, instance_id):
    for r in instances:
        if r["id"] == instance_id:
            return r
    return None


def launch(row, popen=None):
    """Start that QGIS detached from this process (it keeps running when the caller exits). Returns the process id."""
    if not row.get("launch"):
        raise ValueError("no way to start this QGIS is known")
    popen = popen or subprocess.Popen
    p = popen(row["launch"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
              start_new_session=True)
    return p.pid


# ---------------------------------------------------------------- updates
def _apt_policy(pkg, run):
    rc, out = run(["apt-cache", "policy", pkg])
    inst = cand = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Installed:"):
            inst = line.split(":", 1)[1].strip()
        elif line.startswith("Candidate:"):
            cand = line.split(":", 1)[1].strip()
    return rc, inst, cand


def check_updates(items, run=None):
    """[{id, version, update: True|False|None, candidate, source}] for every installation that can be asked.

    ``source`` is 'cached' (what the package manager's last refresh knows) or 'network'. ``update`` None = could not tell."""
    run = run or _run
    rows = []
    for it in items:
        kind = it["kind"]
        if kind not in ("apt", "flatpak", "snap", "dist"):
            continue
        row = {"id": _instance_id(it), "version": it.get("v", ""), "update": None, "candidate": None, "source": "cached"}
        if kind == "apt":
            pkg = "qgis" if "qgis" in it["pkgs"] else sorted(it["pkgs"])[0]
            rc, inst, cand = _apt_policy(pkg, run)
            if rc == 0 and inst and cand and cand != "(none)":
                row["update"], row["candidate"] = (inst != cand), cand
        elif kind == "flatpak":
            row["source"] = "network"
            rc, out = run(["flatpak", "remote-ls", "--updates", "--" + it.get("i", "user"), "--columns=application,branch"])
            if rc == 0:
                want = it.get("br")
                row["update"] = any(ln.split("\t")[0].strip() == "org.qgis.qgis"
                                    and (not want or (len(ln.split("\t")) > 1 and ln.split("\t")[1].strip() == want))
                                    for ln in out.splitlines())
        elif kind == "snap":
            row["source"] = "network"
            rc, out = run(["snap", "refresh", "--list"])
            if rc == 0:
                row["update"] = any(ln.split()[:1] == ["qgis"] for ln in out.splitlines())
        elif kind == "dist":
            pm, pkgs = it.get("pm"), it.get("pkgs") or ["qgis"]
            if pm == "dnf":
                row["source"] = "network"
                rc, _ = run(["dnf", "-q", "check-update", *pkgs])
                row["update"] = {100: True, 0: False}.get(rc)           # dnf: 100 = updates available, 0 = none, other = error
            elif pm == "zypper":
                rc, out = run(["zypper", "--non-interactive", "list-updates"])
                if rc == 0:
                    row["update"] = any(any(c.strip() in pkgs for c in ln.split("|")) for ln in out.splitlines())
            elif pm == "pacman":
                rc, out = run(["pacman", "-Qu", *pkgs])
                row["update"] = {0: bool(out.strip()), 1: False}.get(rc)   # 1 = nothing upgradable (per the last database sync)
        rows.append(row)
    return rows
