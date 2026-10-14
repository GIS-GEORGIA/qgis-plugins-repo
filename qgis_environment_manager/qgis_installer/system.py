"""System detection and the data about QGIS channels / supported distributions (no UI)."""
import platform
import shutil
import subprocess

# ---------------------------------------------------------------- data
LATEST, LTR = "4.2.x", "3.44.x"           # per the QGIS installation guide (2026-10)
KEY_URL = "https://download.qgis.org/downloads/qgis-archive-keyring.gpg"
KEY_FPR = "2D7E3441A707FDB3E7059441D155B8E6A419C5BE"   # expires 2027-08-08
KEYRING = "/etc/apt/keyrings/qgis-archive-keyring.gpg"
SOURCES = "/etc/apt/sources.list.d/qgis.sources"

# supported codenames -> LTR only?
SUPPORT = {
    "debian": {"bookworm": True, "trixie": False, "sid": False},
    "ubuntu": {"resolute": False, "questing": False, "plucky": False, "noble": True, "jammy": True},
}
# channel key -> repository suffix
SUFFIX = {"latest": "", "ltr": "-ltr", "nightly-release": "-nightly-release",
          "nightly-ltr": "-nightly-ltr", "nightly": "-nightly"}
CHANNELS = ["latest", "ltr", "nightly-release", "nightly-ltr", "nightly"]
LTR_ONLY_CHANNELS = ["ltr", "nightly-ltr"]


# ---------------------------------------------------------------- system detection
def read_os_release(path="/etc/os-release"):
    d = {}
    try:
        with open(path) as f:
            for line in f:
                if "=" in line:
                    k, v = line.rstrip("\n").split("=", 1)
                    d[k] = v.strip('"')
    except OSError:
        pass
    return d


def detect(os_release=None, pm=None, arch=None):
    """Describe this system. ``os_release`` / ``pm`` / ``arch`` override the real values
    (used by tests and by ``--os-release`` to preview what would happen on another system)."""
    o = read_os_release(os_release or "/etc/os-release")
    like = (o.get("ID", "") + " " + o.get("ID_LIKE", "")).lower()
    family, code = None, o.get("VERSION_CODENAME", "")
    if o.get("UBUNTU_CODENAME"):
        family, code = "ubuntu", o["UBUNTU_CODENAME"]
    elif o.get("DEBIAN_CODENAME"):
        family, code = "debian", o["DEBIAN_CODENAME"]
    elif "ubuntu" in like:
        family = "ubuntu"
    elif "debian" in like:
        family = "debian"
    if pm is None:
        pm = next((m for m in ("apt-get", "dnf", "pacman", "zypper") if shutil.which(m)), "")
    if arch is None:
        if shutil.which("dpkg"):
            arch = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True).stdout.strip()
        else:
            arch = platform.machine()
    supported, ltr_only = False, False
    if family and code in SUPPORT.get(family, {}):
        supported, ltr_only = True, SUPPORT[family][code]
    return {"name": o.get("PRETTY_NAME", "Linux"), "family": family, "code": code, "pm": pm,
            "arch": arch, "supported": supported, "ltr_only": ltr_only,
            "apt": family is not None and pm == "apt-get"}


def installed_qgis():
    if not shutil.which("dpkg-query"):
        return None
    r = subprocess.run(["dpkg-query", "-W", "-f=${Status} ${Version}", "qgis"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.startswith("install ok installed"):
        return r.stdout.split()[-1]
    return None


def method_available(method, sysinfo):
    """Is install method A (official apt repository), B (Flatpak) or C (distribution package) usable here?"""
    if method == "A":
        return bool(sysinfo["apt"] and sysinfo["supported"] and sysinfo["arch"] == "amd64")
    if method == "B":
        return True
    return bool(sysinfo["pm"])


def allowed_channels(sysinfo):
    """Channels the official repository offers for this system (LTR only on older bases)."""
    return LTR_ONLY_CHANNELS if sysinfo["ltr_only"] else CHANNELS


def default_channel(sysinfo):
    return "ltr" if sysinfo["ltr_only"] else "latest"
