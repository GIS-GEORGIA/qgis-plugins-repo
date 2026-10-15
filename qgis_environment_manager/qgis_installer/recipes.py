"""Install recipes: every way the QGIS installation guide describes (Linux section), as data + a plan function.

A recipe knows when it applies to a system, what options it has, and turns a choice into shell steps (``run``
recipes) or verbatim instructions (``manual`` recipes). ``recommend`` picks the best one for a goal and says why.
No UI. Texts are in i18n.STR under ``rc_<id>`` (title), ``rcn_<reason>`` (why not applicable), ``rcw_<note>`` (notes
and warnings) and ``why_<reason>`` (why recommended).

``verified`` says how far the author checked a recipe (shown to the user, never hidden):
  container - package names resolved / a dry run succeeded inside a throw-away container (tests/qgis_recipes_container_test.py)
  real      - installed for real in a container (tests/qgis_container_test.py)
  flathub   - the Flathub refs and branches exist
  guide     - the steps are taken from the installation guide; not run by the author
  names     - the package names exist in the distribution's repositories; the install was not run
  manual    - instructions only, nothing is run
``side_by_side`` is True where the result lives apart from the system's QGIS (Flatpak, containers, Spack, Nix), so it can be
installed while QGIS is running and does not replace the QGIS you have; False means the system's own QGIS is changed in place.
Guide: https://qgis.org/resources/installation-guide/#linux
"""
import shlex

from . import plan, system

GUIDE_URL = "https://qgis.org/resources/installation-guide/#linux"
FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"
GEO_REPO = "https://download.opensuse.org/repositories/Application:/Geo/openSUSE_Tumbleweed/"
DISTROBOX_IMAGE = "registry.opensuse.org/opensuse/toolbox:latest"          # the guide's example
TOOLBX_IMAGE = "registry.fedoraproject.org/fedora-toolbox:rawhide"          # the guide's example
BOX = system.CONTAINER_BOX

FLATPAK_BRANCHES = ("stable", "lts")
AUR_CHANNELS = {"ltr": "qgis-ltr", "testing": "qgis-git"}
GOALS = ("stable", "latest", "alongside")


def _step(root, sh):
    return {"root": root, "sh": "set -eu\n" + sh.rstrip("\n") + "\n"}


def _pkgs(opts, names, grass=None, python=None, server=None):
    """['qgis', ...] honouring the grass / python / server checkboxes."""
    out = list(names)
    if opts.get("python", True) and python:          # the guide's order: qgis python3-qgis qgis-grass
        out.append(python)
    if opts.get("grass", True) and grass:
        out.append(grass)
    if opts.get("server", False) and server:
        out.append(server)
    return out


# ---------------------------------------------------------------- applicability
def _apt_official(s):
    if not s["apt"]:
        return False, "no_apt"
    if not s["supported"]:
        return False, "codename"
    if s["arch"] != "amd64":
        return False, "arch"
    return True, ""


def _apt_distro(s):
    return (True, "") if s["pm"] == "apt-get" else (False, "no_apt")


def _flatpak(s):
    if s["tools"].get("flatpak"):
        return True, ""
    if s["pm"] in ("apt-get", "dnf", "pacman", "zypper"):
        return True, ""                       # the recipe installs flatpak itself first
    return False, "no_flatpak"


def _dnf_fedora(s):
    if s["distro"] != "fedora":
        return False, "not_fedora"
    if s["immutable"] == "ostree":
        return False, "immutable"
    return (True, "") if s["pm"] == "dnf" else (False, "no_dnf")


def _rpm_ostree(s):
    ok = s["distro"] == "fedora" and s["immutable"] == "ostree" and s["tools"].get("rpm-ostree")
    return (True, "") if ok else (False, "not_atomic")


def _zypper(s):
    if s["distro"] != "opensuse":
        return False, "not_opensuse"
    if s["immutable"] == "transactional":
        return False, "immutable"
    return (True, "") if s["pm"] == "zypper" else (False, "no_zypper")


def _pacman(s):
    if s["distro"] != "arch":
        return False, "not_arch"
    return (True, "") if s["pm"] == "pacman" else (False, "no_pacman")


def _aur(s):
    if s["distro"] != "arch":
        return False, "not_arch"
    return (True, "") if (s["tools"].get("yay") or s["tools"].get("paru")) else (False, "no_aur_helper")


def _urpmi(s):
    if s["distro"] != "mageia":
        return False, "not_mageia"
    return (True, "") if s["tools"].get("urpmi") else (False, "no_urpmi")


def _tool(name):
    return lambda s: (True, "") if s["tools"].get(name) else (False, "no_" + name)


def _distro(name):
    return lambda s: (True, "") if s["distro"] == name else (False, "not_" + name)


# ---------------------------------------------------------------- plans
def _plan_apt_official(s, o):
    channel = o.get("channel") or system.default_channel(s)
    if channel not in system.allowed_channels(s):
        raise ValueError("channel '{}' is not offered for this system (allowed: {})".format(
            channel, ", ".join(system.allowed_channels(s))))
    pk = {"grass": o.get("grass", True), "python": o.get("python", True), "server": o.get("server", False)}
    steps = plan.build_install("A", s, channel, pk)
    return {"steps": steps, "notes": ["apt_other_sources", "apt_ubuntugis"]}


def _plan_apt_distro(s, o):
    names = _pkgs(o, ["qgis"], grass="qgis-plugin-grass", python="python3-qgis", server="qgis-server")
    return {"steps": [_step(True, "apt-get install -y " + " ".join(names))], "notes": ["distro_older"]}


def _plan_flatpak(s, o):
    branch = o.get("branch") or "stable"
    scope = o.get("scope") or "user"
    if branch not in FLATPAK_BRANCHES:
        raise ValueError("flatpak branch must be one of {}".format(FLATPAK_BRANCHES))
    if scope not in ("user", "system"):
        raise ValueError("flatpak scope must be user or system")
    steps = []
    if not s["tools"].get("flatpak"):
        inst = plan.FLATPAK_INSTALL.get(s["pm"])
        if inst:
            steps.append(_step(True, inst))
    root = scope == "system"
    steps.append(_step(root, "flatpak remote-add --{0} --if-not-exists flathub {1}\n"
                             "flatpak install --{0} -y flathub org.qgis.qgis//{2}".format(scope, FLATHUB_REPO, branch)))
    notes = ["flatpak_portal", "flatpak_pip"]
    if branch == "lts":
        notes.insert(0, "flatpak_lts_eol")
    return {"steps": steps, "notes": notes}


def _plan_dnf(s, o):
    names = _pkgs(o, ["qgis"], grass="qgis-grass", python="python3-qgis", server="qgis-server")
    return {"steps": [_step(True, "dnf install -y " + " ".join(names))], "notes": ["fedora_version"]}


def _plan_rpm_ostree(s, o):
    names = _pkgs(o, ["qgis"], grass="qgis-grass", python="python3-qgis", server="qgis-server")
    return {"steps": [_step(True, "rpm-ostree install --idempotent " + " ".join(names) +
                            "\necho 'Reboot to use the layered packages (systemctl reboot).'")],
            "notes": ["ostree_reboot", "ostree_flatpak"]}


def _plan_zypper(s, o):
    names = _pkgs(o, ["qgis"], grass="qgis-plugin-grass")          # Python support is part of the qgis package
    lines = []
    if o.get("geo_repo"):
        lines.append("zypper --non-interactive addrepo --refresh {} geo".format(GEO_REPO))
        lines.append("zypper --non-interactive --gpg-auto-import-keys refresh")
    lines.append("zypper --non-interactive install " + " ".join(names))
    return {"steps": [_step(True, "\n".join(lines))], "notes": ["suse_no_ltr"]}


def _plan_pacman(s, o):
    return {"steps": [_step(True, "pacman -S --noconfirm qgis")], "notes": ["arch_no_ltr"]}


def _plan_aur(s, o):
    channel = o.get("channel") or "ltr"
    if channel not in AUR_CHANNELS:
        raise ValueError("AUR channel must be one of {}".format(tuple(AUR_CHANNELS)))
    helper = "yay" if s["tools"].get("yay") else "paru"
    return {"steps": [_step(False, "{} -S --noconfirm {}".format(helper, AUR_CHANNELS[channel]))],
            "notes": ["aur_build"]}


def _plan_urpmi(s, o):
    names = _pkgs(o, ["qgis"], grass="qgis-grass")
    return {"steps": [_step(True, "urpmi --auto " + " ".join(names))], "notes": ["mageia_names"]}


def _plan_spack(s, o):
    return {"steps": [_step(False, "spack install qgis")], "notes": ["spack_long", "spack_load"]}


def _plan_distrobox(s, o):
    image = o.get("image") or DISTROBOX_IMAGE
    q = shlex.quote
    sh = ("distrobox list | grep -q {box} || distrobox create --yes --name {box} --image {img}\n"
          "distrobox enter {box} -- sudo zypper --non-interactive install qgis qgis-plugin-grass\n"
          "distrobox enter {box} -- distrobox-export --app qgis").format(box=BOX, img=q(image))
    return {"steps": [_step(False, sh)], "notes": ["box_alongside", "box_update_distrobox"]}


def _toolbx_image(s):
    """The guide shows rawhide; on a Fedora host the box is pinned to the host's release so it matches the system."""
    if s.get("distro") == "fedora" and s.get("version_id"):
        return "registry.fedoraproject.org/fedora-toolbox:" + s["version_id"]
    return TOOLBX_IMAGE


def _plan_toolbx(s, o):
    image = o.get("image") or _toolbx_image(s)
    q = shlex.quote
    sh = ("toolbox list --containers | grep -q {box} || toolbox create --assumeyes --image {img} {box}\n"
          "toolbox run --container {box} sudo dnf install -y qgis qgis-grass python3-qgis").format(box=BOX, img=q(image))
    return {"steps": [_step(False, sh)], "notes": ["box_alongside", "box_toolbx_launch"]}


def _plan_nix(s, o):
    ltr = o.get("channel") == "ltr"
    pkg = "qgis-ltr" if ltr else "qgis"
    return {"steps": [], "notes": ["nix_config"], "manual": [
        {"title": "nix_try", "text": "nix-shell -p {} --command qgis".format(pkg)},
        {"title": "nix_config", "text": "environment.systemPackages = [\n  pkgs.{}\n];".format(pkg)},
        {"title": "nix_python", "text": (
            "environment.systemPackages = with pkgs; [\n"
            "  (qgis.override {\n"
            "    extraPythonPackages = ps: with ps; [ numpy geopandas rasterio ];\n"
            "  })\n"
            "];")},
    ]}


def _plan_slackware(s, o):
    return {"steps": [], "notes": [], "manual": [
        {"title": "slackware_builds", "text": "https://slackbuilds.org/result/?search=qgis"}]}


# id -> recipe. Order = the order the user sees.
RECIPES = {
    "apt-official": {"side_by_side": False, "kind": "run", "verified": "real", "applies": _apt_official, "plan": _plan_apt_official,
                     "options": ["channel", "grass", "python", "server"]},
    "apt-distro": {"side_by_side": False, "kind": "run", "verified": "container", "applies": _apt_distro, "plan": _plan_apt_distro,
                   "options": ["grass", "python", "server"]},
    "flatpak": {"side_by_side": True, "kind": "run", "verified": "flathub", "applies": _flatpak, "plan": _plan_flatpak,
                "options": ["branch", "scope"]},
    "dnf-fedora": {"side_by_side": False, "kind": "run", "verified": "container", "applies": _dnf_fedora, "plan": _plan_dnf,
                   "options": ["grass", "python", "server"]},
    "rpm-ostree-fedora": {"side_by_side": False, "kind": "run", "verified": "guide", "applies": _rpm_ostree, "plan": _plan_rpm_ostree,
                          "options": ["grass", "python", "server"]},
    "zypper-opensuse": {"side_by_side": False, "kind": "run", "verified": "container", "applies": _zypper, "plan": _plan_zypper,
                        "options": ["grass", "geo_repo"]},
    "pacman-arch": {"side_by_side": False, "kind": "run", "verified": "container", "applies": _pacman, "plan": _plan_pacman, "options": []},
    "aur-helper": {"side_by_side": False, "kind": "run", "verified": "guide", "applies": _aur, "plan": _plan_aur, "options": ["channel"]},
    "urpmi-mageia": {"side_by_side": False, "kind": "run", "verified": "names", "applies": _urpmi, "plan": _plan_urpmi, "options": ["grass"]},
    "spack": {"side_by_side": True, "kind": "run", "verified": "guide", "applies": _tool("spack"), "plan": _plan_spack, "options": []},
    "distrobox": {"side_by_side": True, "kind": "run", "verified": "guide", "applies": _tool("distrobox"), "plan": _plan_distrobox,
                  "options": ["image"]},
    "toolbx": {"side_by_side": True, "kind": "run", "verified": "guide", "applies": _tool("toolbox"), "plan": _plan_toolbx,
               "options": ["image"]},
    "nix-manual": {"side_by_side": True, "kind": "manual", "verified": "manual", "applies": _distro("nixos"), "plan": _plan_nix,
                   "options": ["channel"]},
    "slackware-manual": {"side_by_side": False, "kind": "manual", "verified": "manual", "applies": _distro("slackware"),
                         "plan": _plan_slackware, "options": []},
}

# the old A / B / C of the GUI
METHOD_TO_RECIPE = {"A": "apt-official", "B": "flatpak"}


def recipe_for_method(method, sysinfo):
    if method in METHOD_TO_RECIPE:
        return METHOD_TO_RECIPE[method]
    pm = sysinfo["pm"]
    return {"apt-get": "apt-distro", "dnf": "dnf-fedora", "zypper": "zypper-opensuse", "pacman": "pacman-arch"}.get(pm)


def applicability(recipe_id, sysinfo):
    """(applies, reason_key) - the reason is an ``rcn_`` text key when it does not."""
    return RECIPES[recipe_id]["applies"](sysinfo)


def available(sysinfo):
    """[{id, kind, verified, applies, reason}] for every recipe, in display order."""
    out = []
    for rid, r in RECIPES.items():
        ok, why = r["applies"](sysinfo)
        out.append({"id": rid, "kind": r["kind"], "verified": r["verified"], "applies": ok, "reason": why,
                    "side_by_side": r["side_by_side"]})
    return out


def make_plan(recipe_id, sysinfo, opts=None):
    """{'steps': [...], 'notes': [keys], 'manual': [{'title': key, 'text': str}]}; raises ValueError if it cannot apply."""
    if recipe_id not in RECIPES:
        raise ValueError("unknown recipe: {}".format(recipe_id))
    ok, why = applicability(recipe_id, sysinfo)
    if not ok:
        raise ValueError("recipe {} does not apply here ({})".format(recipe_id, why))
    result = RECIPES[recipe_id]["plan"](sysinfo, dict(opts or {}))
    result.setdefault("manual", [])
    result["recipe"] = recipe_id
    return result


# ---------------------------------------------------------------- recommendation
def recommend(sysinfo, goal):
    """The best recipe for ``goal`` (stable / latest / alongside) on this system.

    -> {'recipe': id|None, 'options': {...}, 'why': key, 'alternatives': [ids that also apply]}"""
    if goal not in GOALS:
        raise ValueError("goal must be one of {}".format(GOALS))
    ltr = system.default_channel(sysinfo) == "ltr"
    if goal == "stable":
        wanted = [("apt-official", {"channel": "ltr"}, "apt_ltr"),
                  ("dnf-fedora", {}, "distro_tracks_release"),
                  ("urpmi-mageia", {}, "distro_tracks_release"),
                  ("flatpak", {"branch": "lts"}, "flatpak_lts")]
    elif goal == "latest":
        wanted = [("apt-official", {"channel": "latest"} if not ltr else None, "apt_latest"),
                  ("pacman-arch", {}, "rolling_latest"),
                  ("zypper-opensuse", {}, "rolling_latest"),
                  ("flatpak", {"branch": "stable"}, "flatpak_stable")]
    else:  # alongside: never touch the QGIS that is already there
        wanted = [("flatpak", {"branch": "stable"}, "alongside_flatpak"),
                  ("distrobox", {}, "alongside_box"),
                  ("toolbx", {}, "alongside_box")]
    chosen = None
    for rid, opts, why in wanted:
        if opts is None:
            continue
        if applicability(rid, sysinfo)[0]:
            chosen = (rid, opts, why)
            break
    alternatives = [a["id"] for a in available(sysinfo) if a["applies"] and (not chosen or a["id"] != chosen[0])]
    if chosen is None:
        return {"recipe": None, "options": {}, "why": "nothing_fits", "alternatives": alternatives}
    return {"recipe": chosen[0], "options": chosen[1], "why": chosen[2], "alternatives": alternatives}
