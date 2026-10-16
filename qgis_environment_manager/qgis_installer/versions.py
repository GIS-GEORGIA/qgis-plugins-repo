"""Which versions of an installed QGIS can be had, going to one of them (also back to an older one), and keeping a version. No UI.

Works on the items of ``uninstall.find_installs`` like the other modules; ``run`` is the command runner (default: real commands,
injectable for tests). Everything here is reading or *building* steps: nothing is changed until the user has seen the commands
(and, with ``simulate.explain``, what they would do) and confirmed.

* apt: ``apt-cache madison`` lists the versions every configured repository offers (Ubuntu keeps older ones in its release and
  security pockets; Debian's mirrors keep only the current one). Going to a version installs ``package=version`` for every installed
  QGIS package that has it, with ``--allow-downgrades``.
* dnf / zypper: the repositories' lists (``dnf list --showduplicates``, ``zypper search -s``); ``dnf downgrade`` or
  ``zypper install --oldpackage``.
* Flatpak has no QGIS version numbers on the remote, only builds (commits) with a date and a subject: those are listed as they are
  and ``flatpak update --commit=`` goes to one.
* Arch keeps only the newest build in its repositories: nothing to choose (the Arch Linux Archive is a manual matter).
* Keeping a version: ``apt-mark hold``, ``zypper addlock``, ``dnf versionlock``, ``flatpak mask``; Arch has no command, only a
  line in pacman.conf, which is shown as an instruction.
"""
import re
import shlex
import subprocess


def _run(cmd, timeout=120):
    try:
        import os
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=dict(os.environ, LC_ALL="C", LANG="C"))
        return p.returncode, p.stdout + p.stderr
    except Exception:
        return 1, ""


def _step(root, sh):
    return {"root": root, "sh": "set -eu\n" + sh.rstrip("\n") + "\n"}


def _natural(v):
    """Sort key for version strings like 1:3.44.5+24noble or 3.44.1-2.fc44."""
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", v) if p]


def primary_package(item):
    pkgs = item.get("pkgs") or ["qgis"]
    return "qgis" if "qgis" in pkgs else sorted(pkgs)[0]


# ---------------------------------------------------------------- listing
def available(item, run=None):
    """{'versions': [{'version', 'origin', 'installed', 'commit'?}] (newest first), 'note': text key or None}."""
    run = run or _run
    kind = item["kind"]
    if kind == "apt":
        return {"versions": _apt_versions(primary_package(item), item.get("v"), run), "note": "ver_downgrade"}
    if kind == "flatpak":
        return {"versions": _flatpak_builds(item, run), "note": "ver_flatpak"}
    if kind == "dist":
        pm = item.get("pm")
        pkg = primary_package(item)
        if pm == "dnf":
            return {"versions": _dnf_versions(pkg, run), "note": "ver_downgrade"}
        if pm == "zypper":
            return {"versions": _zypper_versions(pkg, run), "note": "ver_downgrade"}
        if pm == "pacman":
            return {"versions": [], "note": "ver_arch"}
    return {"versions": [], "note": "ver_unsupported"}


def _apt_versions(pkg, installed, run):
    rc, out = run(["apt-cache", "madison", pkg])
    seen, rows = set(), []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or parts[0] != pkg or parts[1] in seen:
            continue
        seen.add(parts[1])
        rows.append({"version": parts[1], "origin": parts[2], "installed": parts[1] == installed})
    return rows


def _dnf_versions(pkg, run):
    rc, out = run(["dnf", "-q", "list", "--showduplicates", pkg])
    rows, mode = [], None
    for line in out.splitlines():
        s = line.strip()
        if re.match(r"^Installed [Pp]ackages", s):
            mode = "installed"
        elif re.match(r"^Available [Pp]ackages", s):
            mode = "available"
        elif mode and s and len(s.split()) >= 3 and s.split()[0].startswith(pkg + "."):
            version, origin = s.split()[1], s.split()[2]
            rows.append({"version": version, "origin": origin if mode == "available" else "@System", "installed": mode == "installed"})
    merged = {}
    for r in rows:                                                       # the installed one is also listed as available
        if r["version"] in merged:
            merged[r["version"]]["installed"] = merged[r["version"]]["installed"] or r["installed"]
        else:
            merged[r["version"]] = r
    return sorted(merged.values(), key=lambda r: _natural(r["version"]), reverse=True)


def _zypper_versions(pkg, run):
    rc, out = run(["zypper", "--non-interactive", "search", "-s", "--match-exact", pkg])
    rows = {}
    for line in out.splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 6 and cols[1] == pkg and cols[2] == "package":
            r = rows.setdefault(cols[3], {"version": cols[3], "origin": cols[5], "installed": False})
            r["installed"] = r["installed"] or cols[0].startswith("i")
    return sorted(rows.values(), key=lambda r: _natural(r["version"]), reverse=True)


def _flatpak_builds(item, run):
    scope = "--" + ("system" if item.get("i") == "system" else "user")
    ref = "org.qgis.qgis" + ("//" + item["br"] if item.get("br") else "")
    rc, out = run(["flatpak", "remote-info", "--log", scope, "flathub", ref])
    rows = []
    for block in re.split(r"\n\s*\n", out):
        c = re.search(r"^\s*Commit:\s*([0-9a-f]{64})\s*$", block, re.M)
        if not c:
            continue
        if any(r["commit"] == c.group(1) for r in rows):      # the header block repeats the newest log entry
            continue
        subject = re.search(r"^\s*Subject:\s*(.*)$", block, re.M)
        date = re.search(r"^\s*Date:\s*(\S+)", block, re.M)
        rows.append({"version": "{} {}".format(date.group(1) if date else "?", (subject.group(1) if subject else "").strip()).strip(),
                     "origin": "flathub", "installed": False, "commit": c.group(1)})
    return rows


# ---------------------------------------------------------------- going to a version
def steps_for(item, row, run=None):
    """{'steps', 'notes'} to bring the installation to ``row`` (one of ``available(item)['versions']``); ValueError if it cannot."""
    run = run or _run
    kind, ver = item["kind"], row["version"]
    q = shlex.quote
    if kind == "apt":
        have = []
        for pkg in item["pkgs"]:
            if any(r["version"] == ver for r in _apt_versions(pkg, None, run)):
                have.append(pkg)
        if primary_package(item) not in have:
            raise ValueError("{} has no version {}".format(primary_package(item), ver))
        specs = " ".join(q("{}={}".format(p, ver)) for p in have)
        return {"steps": [_step(True, "apt-get install -y --allow-downgrades " + specs)], "notes": ["ver_downgrade"]}
    if kind == "dist" and item.get("pm") == "dnf":
        pkg = primary_package(item)
        older = row.get("installed") is False and item.get("v") and _natural(ver) < _natural(item["v"])
        verb = "downgrade" if older else "install"
        return {"steps": [_step(True, "dnf {} -y {}".format(verb, q("{}-{}".format(pkg, ver))))], "notes": ["ver_downgrade"]}
    if kind == "dist" and item.get("pm") == "zypper":
        return {"steps": [_step(True, "zypper --non-interactive install --oldpackage {}".format(q("{}={}".format(primary_package(item), ver))))],
                "notes": ["ver_downgrade"]}
    if kind == "flatpak" and row.get("commit") and re.fullmatch(r"[0-9a-f]{64}", row["commit"]):
        scope = "system" if item.get("i") == "system" else "user"
        ref = "org.qgis.qgis" + ("//" + item["br"] if re.fullmatch(r"[A-Za-z0-9_.-]+", item.get("br") or "") else "")
        return {"steps": [_step(scope == "system", "flatpak update --{} -y --commit={} {}".format(scope, row["commit"], ref))],
                "notes": ["ver_flatpak"]}
    raise ValueError("no way to choose a version for this installation")


# ---------------------------------------------------------------- keeping a version
def lock_state(item, run=None):
    """True (kept), False (not kept) or None (cannot tell / no mechanism)."""
    run = run or _run
    kind = item["kind"]
    if kind == "apt":
        rc, out = run(["apt-mark", "showhold"])
        held = out.split()
        return (primary_package(item) in held) if rc == 0 else None
    if kind == "flatpak":
        scope = "--" + ("system" if item.get("i") == "system" else "user")
        rc, out = run(["flatpak", "mask", scope])
        return any(ln.strip().startswith("org.qgis.qgis") for ln in out.splitlines()) if rc == 0 else None
    if kind == "dist" and item.get("pm") == "zypper":
        rc, out = run(["zypper", "--non-interactive", "locks"])
        return any(primary_package(item) in [c.strip() for c in ln.split("|")] for ln in out.splitlines()) if rc == 0 else None
    if kind == "dist" and item.get("pm") == "dnf":
        rc, out = run(["dnf", "versionlock", "list"])
        pkg = primary_package(item)
        # dnf 5 prints "Package name: bash" + "evr = ..."; dnf 4 prints one "bash-0:5.1.8-6.fc.*" per line
        return any(ln.strip() == "Package name: " + pkg or ln.strip().startswith(pkg + "-") for ln in out.splitlines()) if rc == 0 else None
    return None


def lock_steps(item, lock):
    """{'steps', 'notes', 'manual'} to keep (lock=True) or release (lock=False) the installed version."""
    kind = item["kind"]
    q = shlex.quote
    if kind == "apt":
        pkgs = " ".join(q(p) for p in item["pkgs"])
        return {"steps": [_step(True, "apt-mark {} {}".format("hold" if lock else "unhold", pkgs))], "notes": [], "manual": []}
    if kind == "flatpak":
        scope = "system" if item.get("i") == "system" else "user"
        ref = "org.qgis.qgis" + ("//" + item["br"] if re.fullmatch(r"[A-Za-z0-9_.-]+", item.get("br") or "") else "")
        return {"steps": [_step(scope == "system", "flatpak mask --{}{} {}".format(scope, "" if lock else " --remove", ref))],
                "notes": [], "manual": []}
    if kind == "dist" and item.get("pm") == "zypper":
        pkgs = " ".join(q(p) for p in item.get("pkgs") or ["qgis"])
        return {"steps": [_step(True, "zypper --non-interactive {} {}".format("addlock" if lock else "removelock", pkgs))], "notes": [], "manual": []}
    if kind == "dist" and item.get("pm") == "dnf":
        pkgs = " ".join(q(p) for p in item.get("pkgs") or ["qgis"])
        return {"steps": [_step(True, "dnf versionlock {} {}".format("add" if lock else "delete", pkgs))], "notes": ["lock_dnf_plugin"], "manual": []}
    if kind == "dist" and item.get("pm") == "pacman":
        text = "IgnorePkg = {}      # in /etc/pacman.conf, section [options]".format(" ".join(item.get("pkgs") or ["qgis"]))
        return {"steps": [], "notes": ["lock_arch"], "manual": [{"title": "lock_arch", "text": text}]}
    return {"steps": [], "notes": ["lock_unsupported"], "manual": []}
