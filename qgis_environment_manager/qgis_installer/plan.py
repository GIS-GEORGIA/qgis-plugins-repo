"""Turning a choice (method, channel, packages) into shell steps: [{"root": bool, "sh": str}]. No UI."""
import shutil

from . import system
from .system import SUFFIX


def sources_text(sysinfo, channel):
    uri = f"https://qgis.org/{sysinfo['family']}{SUFFIX[channel]}"
    return (f"Types: deb\nURIs: {uri}\nSuites: {sysinfo['code']}\nArchitectures: amd64\n"
            f"Components: main\nSigned-By: {system.KEYRING}\n")


def build_install(method, sysinfo, channel, pkgs):
    """-> list of steps {root: bool, sh: str}. POSIX sh only."""
    if method == "A":
        names = ["qgis"] + (["qgis-plugin-grass"] if pkgs["grass"] else []) + (["python3-qgis"] if pkgs["python"] else [])
        steps = [
            {"root": True, "sh": f"""set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wget gnupg ca-certificates
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
wget -qO "$TMP/key.gpg" {system.KEY_URL}
mkdir -m700 "$TMP/gnupg"
FPR=$(gpg --homedir "$TMP/gnupg" --no-default-keyring --keyring "$TMP/key.gpg" --list-keys --with-colons | awk -F: '$1=="fpr"{{print $10; exit}}')
if [ "$FPR" != "{system.KEY_FPR}" ]; then echo "KEY FINGERPRINT MISMATCH: $FPR" >&2; exit 1; fi
echo "Key fingerprint OK: $FPR"
install -m755 -d /etc/apt/keyrings
install -m644 "$TMP/key.gpg" {system.KEYRING}
cat > {system.SOURCES} <<'EOF'
{sources_text(sysinfo, channel)}EOF
apt-get update
apt-get install -y {' '.join(names)}
"""}]
        if pkgs["server"]:
            steps[0]["sh"] += "apt-get install -y --no-install-recommends --no-install-suggests qgis-server\n"
        return steps
    if method == "B":
        steps = []
        if not shutil.which("flatpak"):
            pm = sysinfo["pm"]
            inst = {"apt-get": "apt-get install -y flatpak", "dnf": "dnf install -y flatpak",
                    "pacman": "pacman -S --noconfirm flatpak", "zypper": "zypper --non-interactive install flatpak"}.get(pm)
            if inst:
                steps.append({"root": True, "sh": "set -eu\n" + inst + "\n"})
        steps.append({"root": False, "sh": """set -eu
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y flathub org.qgis.qgis
"""})
        return steps
    pm = sysinfo["pm"]
    cmd = {"apt-get": "apt-get install -y qgis qgis-plugin-grass", "dnf": "dnf install -y qgis",
           "pacman": "pacman -S --noconfirm qgis", "zypper": "zypper --non-interactive install qgis"}.get(pm)
    return [{"root": True, "sh": f"set -eu\n{cmd}\n"}] if cmd else []


def steps_script(steps):
    """All steps as one POSIX shell script (what ``--script`` prints)."""
    out = ["#!/bin/sh"]
    for s in steps:
        out.append("# " + ("run as root" if s["root"] else "run as your user"))
        out.append(s["sh"].rstrip())
        out.append("")
    return "\n".join(out)
