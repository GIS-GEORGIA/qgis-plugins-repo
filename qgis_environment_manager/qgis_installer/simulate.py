"""What would the package manager do? Ask it in its own simulation mode, before anything is installed. No UI.

``explain(steps)`` looks at every install / upgrade / remove line of a plan, asks the system's package manager to simulate it
(``apt-get -s``, ``dnf --assumeno``, ``zypper --dry-run``, ``pacman -S --print``, ``apk --simulate``; for a Flatpak the size from
``flatpak remote-info``) and returns how many packages come, go or change, how much is downloaded and how much disk it needs, plus
warnings: something is *removed* by an install, or a removal would drag QGIS along.

It only reads. A line that cannot be simulated (a repository is added first, the package manager needs administrator rights even
to look, no network) simply yields no result: the plan is still shown, and nothing is claimed about it.
"""
import os
import re
import shlex
import subprocess

from . import i18n

QGIS_LIKE = ("qgis", "python3-qgis", "python-qgis", "libqgis", "qgis-")


def _run(cmd, timeout=180):
    try:
        env = dict(os.environ, LC_ALL="C", LANG="C")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout + p.stderr
    except Exception:
        return 1, ""


def human(n):
    """12345678 -> '11.8 MiB'."""
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return "{:.0f} {}".format(n, unit) if unit == "B" else "{:.1f} {}".format(n, unit)
        n /= 1024


def _version_key(v):
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", v) if p]


def _is_qgis(name):
    return name.startswith(QGIS_LIKE)


# ---------------------------------------------------------------- the lines of a plan that can be simulated
_APT = re.compile(r"^apt-get\s+(install|remove|purge)\s+(.+)$")
_DNF = re.compile(r"^dnf\s+(install|upgrade|remove)\s+(.+)$")
_ZYP = re.compile(r"^zypper\s+--non-interactive\s+(install|update|remove)\s+(.+)$")
_PAC = re.compile(r"^pacman\s+-(S|R)\s+(.+)$")
_APK = re.compile(r"^apk\s+(add|del)\s+(.+)$")
_FLAT = re.compile(r"^flatpak\s+install\s+(.+)$")


def _split(rest):
    """-> (options, names): words that start with '-' are options."""
    try:
        words = shlex.split(rest)
    except ValueError:
        return None, None
    return [w for w in words if w.startswith("-")], [w for w in words if not w.startswith("-")]


def parse_line(line):
    """One shell line -> {'tool', 'verb', 'names', 'opts'} when it is an install / upgrade / remove we can simulate, else None."""
    line = line.strip()
    for tool, rx in (("apt", _APT), ("dnf", _DNF), ("zypper", _ZYP), ("pacman", _PAC), ("apk", _APK)):
        m = rx.match(line)
        if m:
            opts, names = _split(m.group(2))
            if not names:
                return None
            verb = m.group(1)
            if tool == "pacman":
                verb = {"S": "install", "R": "remove"}[verb]
            verb = {"purge": "remove", "update": "upgrade", "add": "install", "del": "remove"}.get(verb, verb)
            return {"tool": tool, "verb": verb, "names": names, "opts": opts}
    m = _FLAT.match(line)
    if m:
        words = shlex.split(m.group(1))
        pos = [w for w in words if not w.startswith("-")]
        scope = "--system" if "--system" in words else "--user"
        if len(pos) >= 2:                                           # remote, ref
            return {"tool": "flatpak", "verb": "install", "names": pos[1:], "opts": [scope], "remote": pos[0]}
    return None


# ---------------------------------------------------------------- one simulation per tool
def _apt(p, run):
    verb = "remove" if p["verb"] == "remove" else "install"
    keep = [o for o in p["opts"] if o in ("--only-upgrade", "--no-install-recommends")]
    rc, out = run(["apt-get", "-s", verb, *keep, *p["names"]])
    if rc != 0 and "Inst" not in out and "Remv" not in out:
        return None
    inst = [ln for ln in out.splitlines() if ln.startswith("Inst ")]
    changed = [re.match(r"Inst\s+\S+\s+\[([^\]]+)\]\s+\((\S+)", ln) for ln in inst]     # "Inst name [old] (new ...)"; a new one is "Inst name (new ... [amd64])"
    changed = [m for m in changed if m]
    down = [m for m in changed if _version_key(m.group(2)) < _version_key(m.group(1))]
    res = {"installs": len(inst) - len(changed), "upgrades": len(changed) - len(down), "downgrades": len(down),
           "removes": [ln.split()[1] for ln in out.splitlines() if ln.startswith("Remv ")], "download": None, "disk": None}
    if verb == "install" and (res["installs"] or res["upgrades"]):
        rc2, uris = run(["apt-get", "-qq", "--print-uris", "install", *keep, "-y", *p["names"]])
        sizes = [ln.split() for ln in uris.splitlines() if ln.startswith("'")]
        total = sum(int(w[2]) for w in sizes if len(w) > 2 and w[2].isdigit())
        res["download"] = human(total) if sizes else None
    return res


def _dnf(p, run):
    rc, out = run(["dnf", p["verb"], "--assumeno", *p["names"]])
    res = {"installs": 0, "upgrades": 0, "removes": None, "remove_count": 0, "download": None, "disk": None}
    seen = False
    for ln in out.splitlines():
        s = ln.strip()
        m = re.match(r"^(Installing|Upgrading|Removing|Downgrading|Reinstalling):?\s+(\d+) packages?", s)     # dnf5
        if m:
            seen = True
            key = {"Installing": "installs", "Upgrading": "upgrades", "Removing": "remove_count"}.get(m.group(1))
            if key:
                res[key] += int(m.group(2))
            continue
        m = re.match(r"^(Install|Upgrade|Remove)\s+(\d+) Packages?", s)                                       # dnf4
        if m:
            seen = True
            res[{"Install": "installs", "Upgrade": "upgrades", "Remove": "remove_count"}[m.group(1)]] += int(m.group(2))
            continue
        m = re.search(r"Need to download ([\d.]+ \w+)\.", s) or re.match(r"^Total download size: (.+)$", s)
        if m:
            res["download"] = m.group(1)
        m = re.search(r"After this operation, ([\d.]+ \w+) (?:extra will be used|will be freed)", s) or re.match(r"^Installed size: (.+)$", s)
        if m:
            res["disk"] = m.group(1)
    return res if seen else None


def _unit_size(text):
    m = re.search(r"([\d.,]+)\s*([KMGT]i?B|B)\b", text)
    return "{} {}".format(m.group(1), m.group(2)) if m else None


def _zypper(p, run):
    verb = {"install": "install", "upgrade": "update", "remove": "remove"}[p["verb"]]
    rc, out = run(["zypper", "--non-interactive", verb, "--dry-run", *p["names"]])
    res = {"installs": 0, "upgrades": 0, "removes": None, "remove_count": 0, "download": None, "disk": None}
    seen = False
    for ln in out.splitlines():
        s = ln.strip()
        for rx, key in ((r"^(\d+) (?:new )?packages? to install", "installs"), (r"^(\d+) packages? to upgrade", "upgrades"),
                        (r"^(\d+) packages? to remove", "remove_count")):
            m = re.match(rx, s)
            if m:
                seen = True
                res[key] += int(m.group(1))
        m = re.match(r"^Package download size:\s+(.+)$", s) or re.match(r"^Overall download size:\s+([\d.,]+ \w+)", s)
        if m:
            res["download"] = _unit_size(m.group(1))
        m = re.search(r"([\d.,]+ \w+)\s+required by packages that will be installed", s)
        if m:
            res["disk"] = _unit_size(m.group(1))
    return res if seen else None


def _pacman(p, run):
    if p["verb"] == "remove":
        rc, out = run(["pacman", "-R", "--print", "--print-format", "%n", *p["names"]])
        names = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith(("error", "warning"))]
        return {"installs": 0, "upgrades": 0, "removes": names, "download": None, "disk": None} if rc == 0 else None
    rc, out = run(["pacman", "-S", "--print", "--print-format", "%n|%v|%s", *p["names"]])
    rows = [ln.split("|") for ln in out.splitlines() if ln.count("|") == 2]
    if rc != 0 or not rows:
        return None
    total = sum(int(r[2]) for r in rows if r[2].isdigit())
    return {"installs": len(rows), "upgrades": 0, "removes": [], "download": human(total), "disk": None}


def _apk(p, run):
    verb = "add" if p["verb"] == "install" else "del"
    rc, out = run(["apk", verb, "--simulate", *p["names"]])
    if rc != 0:
        return None
    return {"installs": len(re.findall(r"\bInstalling\b", out)), "upgrades": len(re.findall(r"\bUpgrading\b", out)),
            "removes": [m for m in re.findall(r"Purging (\S+)", out)], "download": None, "disk": None}


def _flat_size(text):
    """'592.6\xa0MB' (or '592.6?MB' when the locale cannot show the no-break space) -> '592.6 MB'."""
    m = re.match(r"\s*([\d.,]+)\W{0,3}\s*([KMGT]?i?B)\b", text)
    return "{} {}".format(m.group(1), m.group(2)) if m else text.strip()


def _flatpak(p, run):
    """The size of the app (and what it still needs) from the remote; only the first ref is asked."""
    ref = p["names"][0]
    rc, out = run(["flatpak", "remote-info", p["opts"][0], p["remote"], ref])
    if rc != 0:
        return None
    dl = re.search(r"^\s*Download:\s*(.+)$", out, re.M)
    inst = re.search(r"^\s*Installed:\s*(.+)$", out, re.M)
    if not (dl or inst):
        return None
    return {"installs": len(p["names"]), "upgrades": 0, "removes": [], "download": _flat_size(dl.group(1)) if dl else None,
            "disk": _flat_size(inst.group(1)) if inst else None}


_TOOLS = {"apt": _apt, "dnf": _dnf, "zypper": _zypper, "pacman": _pacman, "apk": _apk, "flatpak": _flatpak}


def simulate_line(line, run=None):
    """-> {'cmd', 'tool', 'verb', 'names', installs, upgrades, removes|remove_count, download, disk} or None."""
    p = parse_line(line)
    if p is None:
        return None
    res = _TOOLS[p["tool"]](p, run or _run)
    if res is None:
        return None
    res.update(cmd=line.strip(), tool=p["tool"], verb=p["verb"], names=p["names"])
    res.setdefault("remove_count", len(res["removes"] or []))
    if res.get("removes") is not None:
        res["remove_count"] = max(res["remove_count"], len(res["removes"]))
    return res


def warnings(results):
    """[(key, params)] for what deserves a second look: removals that an install causes, QGIS being dragged along."""
    out = []
    for r in results:
        removes = r.get("removes")
        extra = [n for n in (removes or []) if n not in r["names"]] if r["verb"] == "remove" else list(removes or [])
        if r["verb"] in ("install", "upgrade") and (r["remove_count"] or extra):
            out.append(("sim_removes_by_install", {"n": r["remove_count"], "names": ", ".join(extra[:8]) or "-"}))
        elif r["verb"] == "remove" and extra:
            out.append(("sim_removes_dependents", {"n": len(extra), "names": ", ".join(extra[:8])}))
        if any(_is_qgis(n) for n in extra) and not any(_is_qgis(n) for n in r["names"]):
            out.append(("sim_qgis_dragged", {"names": ", ".join(n for n in extra if _is_qgis(n))}))
    return out


def explain(steps, run=None):
    """{'items': [simulation results of every simulatable line], 'unsimulated': number of install lines that were not, 'warnings': [...]}."""
    items, missed = [], 0
    for st in steps:
        for line in st["sh"].splitlines():
            if parse_line(line) is None:
                continue
            res = simulate_line(line, run)
            if res is None:
                missed += 1
            else:
                items.append(res)
    return {"items": items, "unsimulated": missed, "warnings": warnings(items)}


def format_text(result, lang="en"):
    """The simulation as lines of text for a preview (empty string when there is nothing to say)."""
    t = lambda k, **kw: i18n.t(k, lang, **kw)  # noqa: E731
    lines = []
    for r in result["items"]:
        parts = []
        if r["installs"]:
            parts.append(t("sim_install", n=r["installs"]))
        if r["upgrades"]:
            parts.append(t("sim_upgrade", n=r["upgrades"]))
        if r.get("downgrades"):
            parts.append(t("sim_downgrade", n=r["downgrades"]))
        if r["remove_count"]:
            parts.append(t("sim_remove", n=r["remove_count"]))
        if r.get("download"):
            parts.append(t("sim_download", d=r["download"]))
        if r.get("disk"):
            parts.append(t("sim_disk", d=r["disk"]))
        lines.append("- {} {}: {}".format(r["tool"], r["verb"], ", ".join(parts) or t("sim_nothing")))
    for key, params in result["warnings"]:
        lines.append("! " + t(key, **params))
    if result["unsimulated"]:
        lines.append("* " + t("sim_unsimulated", n=result["unsimulated"]))
    if not lines:
        return ""
    return t("sim_head") + "\n" + "\n".join(lines)
