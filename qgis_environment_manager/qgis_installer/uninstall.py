"""Finding every QGIS on the machine and building the removal steps. No UI."""
import os
import re
import shutil
import subprocess

from .system import CONTAINER_BOX


def _run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def _du(path):
    rc, out = _run(["du", "-sk", path])
    try:
        kb = int(out.split()[0])
    except (IndexError, ValueError):
        return "?"
    return f"{kb / 1024:.0f} MB" if kb >= 1024 else f"{kb} KB"


USER_DATA = ["~/.local/share/QGIS", "~/.config/QGIS", "~/.cache/QGIS", "~/.var/app/org.qgis.qgis"]


def find_installs(sysinfo):
    """Everything QGIS-related on this machine -> list of item dicts."""
    import glob
    items = []
    # apt / dpkg
    if shutil.which("dpkg-query"):
        rc, out = _run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}|${Package}|${Version}\\n",
                        "qgis*", "python3-qgis*", "libqgis*"])
        pk, ver = [], ""
        for line in out.splitlines():
            st, _, rest = line.partition("|")
            if st.strip() == "ii":
                name, _, v = rest.partition("|")
                pk.append(name)
                if name == "qgis":
                    ver = v
        if pk:
            origin = ""
            rc, pol = _run(["apt-cache", "policy", "qgis" if "qgis" in pk else sorted(pk)[0]])
            lines = pol.splitlines()
            for i, ln in enumerate(lines):
                if "***" in ln and i + 1 < len(lines):
                    origin = lines[i + 1].split()[1] if len(lines[i + 1].split()) > 1 else ""
                    break
            items.append({"kind": "apt", "pkgs": sorted(set(pk)), "v": ver or "?", "o": origin, "root": True})
    # repository + key files
    files = []
    for pat in ("/etc/apt/sources.list.d/*qgis*", "/etc/apt/keyrings/*qgis*", "/usr/share/keyrings/*qgis*",
                "/etc/apt/trusted.gpg.d/*qgis*"):
        files += glob.glob(pat)
    if files:
        chan = ""
        for f in files:
            if f.endswith((".sources", ".list")):
                with open(f, errors="replace") as fh:
                    m = re.search(r"qgis\.org/(\S+)", fh.read())
                if m:
                    chan = f" — {m.group(1)}"
                    break
        items.append({"kind": "repo", "files": sorted(files), "c": chan, "root": True})
    # flatpak
    if shutil.which("flatpak"):
        rc, out = _run(["flatpak", "list", "--app", "--columns=application,version,installation"])
        for line in out.splitlines():
            c = [x.strip() for x in line.split("\t")]
            if c and c[0] == "org.qgis.qgis":
                inst = c[2] if len(c) > 2 else "user"
                items.append({"kind": "flatpak", "i": inst, "v": c[1] if len(c) > 1 else "?",
                              "root": inst == "system"})
    # snap
    if shutil.which("snap"):
        rc, out = _run(["snap", "list", "qgis"])
        for line in out.splitlines()[1:]:
            c = line.split()
            if c and c[0] == "qgis":
                items.append({"kind": "snap", "v": c[1] if len(c) > 1 else "?", "root": True})
    # distro packages other than apt (the official ones and, on Arch, the AUR's qgis-ltr / qgis-git)
    pm = sysinfo["pm"]
    if pm == "pacman":
        found = [(n, _run(["pacman", "-Q", n])) for n in ("qgis", "qgis-ltr", "qgis-git")]
        have = [(n, out.split()[-1]) for n, (rc, out) in found if rc == 0 and out.split()]
        if have:
            items.append({"kind": "dist", "pm": pm, "pkgs": [n for n, _ in have], "v": have[0][1], "root": True})
    elif (pm in ("dnf", "zypper") or sysinfo.get("immutable") == "ostree") and shutil.which("rpm"):
        names = ["qgis", "qgis-ltr"] if pm == "zypper" else ["qgis"]
        for n in names:
            rc, out = _run(["rpm", "-q", "--qf", "%{VERSION}", n])
            if rc == 0:
                items.append({"kind": "dist", "pm": "rpm-ostree" if sysinfo.get("immutable") == "ostree" else pm,
                              "pkgs": [n], "v": out.strip(), "root": True})
    # containers made by this installer (Distrobox / Toolbx)
    for tool, cmd in (("distrobox", ["distrobox", "list"]), ("toolbox", ["toolbox", "list", "--containers"])):
        if shutil.which(tool):
            rc, out = _run(cmd)
            if rc == 0 and CONTAINER_BOX in out:
                items.append({"kind": "container", "tool": tool, "name": CONTAINER_BOX, "root": False})
    # user data (never ticked by default)
    for d in USER_DATA:
        full = os.path.expanduser(d)
        if os.path.isdir(full):
            items.append({"kind": "data", "path": full, "sz": _du(full), "root": False})
    return items


def build_remove_steps(items, purge, autoremove, sysinfo):
    """items = selected item dicts -> steps (one root step so the password is asked once)."""
    import shlex
    root, user = [], []
    home = os.path.expanduser("~")
    for it in items:
        k = it["kind"]
        if k == "apt":
            root.append(f"apt-get {'purge' if purge else 'remove'} -y {' '.join(shlex.quote(p) for p in it['pkgs'])}")
        elif k == "repo":
            root.append("rm -f " + " ".join(shlex.quote(f) for f in it["files"]))
        elif k == "flatpak":
            (root if it["root"] else user).append(f"flatpak uninstall --{it['i']} -y org.qgis.qgis")
        elif k == "snap":
            root.append("snap remove qgis")
        elif k == "dist":
            names = " ".join(shlex.quote(n) for n in it.get("pkgs") or ["qgis"])
            root.append({"dnf": f"dnf remove -y {names}", "zypper": f"zypper --non-interactive remove {names}",
                         "pacman": f"pacman -R --noconfirm {names}",
                         "rpm-ostree": f"rpm-ostree uninstall {names}"}[it["pm"]])
        elif k == "container":
            if it["tool"] in ("distrobox", "toolbox") and re.fullmatch(r"[A-Za-z0-9_.-]+", it["name"]):
                user.append(f"{it['tool']} rm --force {it['name']}")
        elif k == "data":
            path = it["path"]
            allowed = {os.path.expanduser(d) for d in USER_DATA}
            if path in allowed and path.startswith(home + os.sep):   # exact known folders only
                user.append(f"rm -rf -- {shlex.quote(path)}")
    if any(i["kind"] in ("apt", "repo") for i in items):
        if autoremove and any(i["kind"] == "apt" for i in items):
            root.append("apt-get autoremove -y")
        if any(i["kind"] == "repo" for i in items):
            root.append("apt-get update")
    steps = []
    if root:
        steps.append({"root": True, "sh": "set -u\n" + "\n".join(root) + "\n"})
    if user:
        steps.append({"root": False, "sh": "set -u\n" + "\n".join(user) + "\n"})
    return steps


def default_selection(items):
    """What the GUI ticks by default: everything except the user's own data."""
    return [it for it in items if it["kind"] != "data"]
