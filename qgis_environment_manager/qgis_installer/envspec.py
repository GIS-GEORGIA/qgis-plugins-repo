"""An environment file: which QGIS and which components a machine should have, written from one machine and applied on others. No UI.

``export_spec`` reads this machine (the installations ``uninstall.find_installs`` found and the components ``requirements.components`` lists)
and returns a plain dict; ``validate`` checks a dict that came from a file; ``check`` says how far a machine is from it; ``plan`` builds the
steps that close the gap, with the same builders and the same confirmation as every other plan.

The file is **untrusted input** (it is passed around between machines): it holds names from closed lists, never commands. A recipe id must
be one of ``recipes.RECIPES``, options are checked against what that recipe accepts, a component id must be one of the components, and
anything else is refused, so nothing in the file can reach a shell. ``apply`` runs nothing by itself either: the plan is shown, simulated,
and confirmed like any other.

    {"schema": 1, "name": "GIS lab", "created": "2026-10-15",
     "qgis": {"goal": "stable", "recipe": "apt-official", "options": {"channel": "ltr"}, "version": "3.44.5"},
     "components": ["gdal", "numpy", "grass"]}

``qgis`` may be null (components only). ``goal`` is what to fall back on when the recipe does not exist on the machine it is applied to
(an Ubuntu recipe on Fedora); ``version`` is informational: a different installed version is reported, not forced.
"""
import datetime
import json
import re

from . import i18n, recipes, requirements, system

SCHEMA = 1
MAX_BYTES = 64 * 1024
GOAL_OF_CHANNEL = {"ltr": "stable", "nightly-ltr": "stable", "latest": "latest", "nightly-release": "latest", "nightly": "latest",
                   "testing": "latest"}
_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./:_@-]{0,199}$")
_NAME = re.compile(r"^[^\x00-\x1f]{0,80}$")
_VERSION = re.compile(r"^[A-Za-z0-9.+:~_-]{1,60}$")
BOOLS = ("grass", "python", "server", "geo_repo")


class SpecError(ValueError):
    """The file is not a valid environment file; the message says what is wrong."""


def component_ids():
    return [rid for rid, spec in requirements.REQ.items() if "cat" in spec]


# ---------------------------------------------------------------- writing
def _channel_of_repo(item):
    """'ubuntu-ltr' / 'debian' / 'ubuntu-nightly-ltr' (from the repository file's URL) -> the channel key."""
    m = re.search(r"(?:ubuntugis|debian|ubuntu)(-[\w-]+)?", item.get("c", ""))
    suffix = m.group(1) or "" if m else ""
    for key, suf in system.SUFFIX.items():
        if suf == suffix:
            return key
    return None


def export_spec(items, comp_rows, name="", today=None):
    """What this machine has, as a spec dict. ``items``: find_installs(); ``comp_rows``: requirements.components(pm)."""
    qgis = None
    apt = next((i for i in items if i["kind"] == "apt"), None)
    flatpak = next((i for i in items if i["kind"] == "flatpak"), None)
    dist = next((i for i in items if i["kind"] == "dist"), None)
    box = next((i for i in items if i["kind"] == "container"), None)
    repo = next((i for i in items if i["kind"] == "repo"), None)
    if apt:
        channel = _channel_of_repo(repo) if repo else None
        if channel:
            qgis = {"goal": GOAL_OF_CHANNEL.get(channel, "stable"), "recipe": "apt-official", "options": {"channel": channel}}
        else:
            qgis = {"goal": "stable", "recipe": "apt-distro", "options": {}}
        qgis["version"] = apt.get("v")
    elif dist:
        by_pm = {"dnf": "dnf-fedora", "zypper": "zypper-opensuse", "pacman": "pacman-arch", "rpm-ostree": "rpm-ostree-fedora"}
        qgis = {"goal": "stable", "recipe": by_pm.get(dist.get("pm")), "options": {}, "version": dist.get("v")}
        if qgis["recipe"] is None:
            qgis = None
    elif flatpak:
        branch = flatpak.get("br") or "stable"
        qgis = {"goal": "stable" if branch == "lts" else "latest", "recipe": "flatpak",
                "options": {"branch": branch, "scope": flatpak.get("i") or "user"}, "version": flatpak.get("v")}
    elif box:
        qgis = {"goal": "alongside", "recipe": "distrobox" if box["tool"] == "distrobox" else "toolbx", "options": {}}
    if qgis and not qgis.get("version"):
        qgis.pop("version", None)
    today = today or datetime.date.today()
    return {"schema": SCHEMA, "name": name, "created": today.isoformat(), "qgis": qgis,
            "components": [r["id"] for r in comp_rows if r["present"]]}


# ---------------------------------------------------------------- reading
def load(path):
    """Read and validate an environment file. SpecError (with a reason in the message) for anything that is not one; OSError if unreadable."""
    with open(path, "rb") as fh:
        raw = fh.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SpecError("the file is larger than 64 KB: that is not an environment file")
    try:
        return validate(json.loads(raw.decode("utf-8")))
    except (ValueError, UnicodeDecodeError) as exc:                       # malformed JSON is a ValueError too
        raise exc if isinstance(exc, SpecError) else SpecError("not JSON: {}".format(exc))


def validate(doc):
    """-> the spec in canonical form; SpecError for anything that is not exactly what an environment file may hold."""
    if not isinstance(doc, dict):
        raise SpecError("the file must hold one JSON object")
    unknown = set(doc) - {"schema", "name", "created", "qgis", "components"}
    if unknown:
        raise SpecError("unknown field(s): " + ", ".join(sorted(map(str, unknown))))
    if doc.get("schema") != SCHEMA:
        raise SpecError("schema must be {} (this file says {!r})".format(SCHEMA, doc.get("schema")))
    name = doc.get("name", "")
    if not isinstance(name, str) or not _NAME.match(name):
        raise SpecError("name must be text of up to 80 characters")
    created = doc.get("created", "")
    if not isinstance(created, str) or (created and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", created)):
        raise SpecError("created must be a date like 2026-10-15")
    comps = doc.get("components", [])
    if not isinstance(comps, list) or not all(isinstance(c, str) for c in comps):
        raise SpecError("components must be a list of component ids")
    known = component_ids()
    bad = [c for c in comps if c not in known]
    if bad:
        raise SpecError("unknown component(s): {} (known: {})".format(", ".join(bad[:5]), ", ".join(known)))
    out = {"schema": SCHEMA, "name": name, "created": created, "qgis": None,
           "components": [c for i, c in enumerate(comps) if c not in comps[:i]]}
    q = doc.get("qgis")
    if q is not None:
        out["qgis"] = _validate_qgis(q)
    return out


def _validate_qgis(q):
    if not isinstance(q, dict):
        raise SpecError("qgis must be an object or null")
    extra = set(q) - {"goal", "recipe", "options", "version"}
    if extra:
        raise SpecError("unknown field(s) in qgis: " + ", ".join(sorted(map(str, extra))))
    goal = q.get("goal", "stable")
    if not isinstance(goal, str) or goal not in recipes.GOALS:
        raise SpecError("goal must be one of {}".format(", ".join(recipes.GOALS)))
    rid = q.get("recipe")
    if rid is not None and not (isinstance(rid, str) and rid in recipes.RECIPES):
        raise SpecError("unknown recipe {!r}".format(rid if isinstance(rid, str) else type(rid).__name__))
    opts = q.get("options", {})
    if not isinstance(opts, dict):
        raise SpecError("options must be an object")
    allowed = set(recipes.RECIPES[rid]["options"]) if rid else set()
    clean = {}
    for key, val in opts.items():
        if not isinstance(key, str) or key not in allowed:
            raise SpecError("option {!r} is not an option of recipe {!r}".format(key, rid))
        if key == "channel":
            if not isinstance(val, str) or val not in list(system.CHANNELS) + ["testing"]:
                raise SpecError("channel is not a known channel")
        elif key == "branch":
            if not isinstance(val, str) or val not in recipes.FLATPAK_BRANCHES:
                raise SpecError("branch must be one of {}".format(", ".join(recipes.FLATPAK_BRANCHES)))
        elif key == "scope":
            if not isinstance(val, str) or val not in ("user", "system"):
                raise SpecError("scope must be user or system")
        elif key == "image":
            if not isinstance(val, str) or not _IMAGE.match(val):
                raise SpecError("image must be a plain container image name")
        elif key in BOOLS:
            if not isinstance(val, bool):
                raise SpecError("option {!r} must be true or false".format(key))
        clean[key] = val
    version = q.get("version")
    if version is not None and not (isinstance(version, str) and _VERSION.match(version)):
        raise SpecError("version must be a plain version string")
    out = {"goal": goal, "recipe": rid, "options": clean}
    if version:
        out["version"] = version
    return out


# ---------------------------------------------------------------- comparing and closing the gap
def check(spec, items, comp_rows):
    """How far this machine is from the spec: {'qgis': {...}, 'components_missing': [ids], 'components_ok': [ids], 'unavailable': [ids]}.

    ``qgis.state``: 'none' (the spec has none), 'ok', 'missing', 'version' (installed, but another version)."""
    q = spec.get("qgis")
    installed = [i for i in items if i["kind"] in ("apt", "flatpak", "snap", "dist", "container")]
    have = next((i for i in installed if i["kind"] != "container"), None) or (installed[0] if installed else None)
    if q is None:
        qgis = {"state": "none"}
    elif have is None:
        qgis = {"state": "missing"}
    elif q.get("version") and have.get("v") and q["version"] not in have["v"] and have["v"] not in q["version"]:
        qgis = {"state": "version", "installed": have["v"], "wanted": q["version"]}
    else:
        qgis = {"state": "ok", "installed": have.get("v", "")}
    rows = {r["id"]: r for r in comp_rows}
    missing = [c for c in spec["components"] if c in rows and not rows[c]["present"] and rows[c]["packages"]]
    unavailable = [c for c in spec["components"] if c in rows and not rows[c]["present"] and not rows[c]["packages"]]
    ok = [c for c in spec["components"] if c in rows and rows[c]["present"]]
    return {"qgis": qgis, "components_missing": missing, "components_ok": ok, "unavailable": unavailable}


def plan(spec, items, comp_rows, sysinfo):
    """{'steps', 'notes', 'manual', 'recipe', 'state'}: what closes the gap on THIS machine (nothing when it already matches)."""
    state = check(spec, items, comp_rows)
    steps, notes, manual, chosen = [], [], [], None
    q = spec.get("qgis")
    if state["qgis"]["state"] == "missing" and q:
        rid, opts = q.get("recipe"), dict(q.get("options", {}))
        if rid is None or not recipes.applicability(rid, sysinfo)[0]:        # a recipe of another system: what does this one recommend?
            rec = recipes.recommend(sysinfo, q.get("goal", "stable"))
            rid, opts = rec["recipe"], dict(rec["options"])
            notes.append("env_recipe_swapped")
        if rid is None:
            notes.append("env_no_recipe")
        else:
            res = recipes.make_plan(rid, sysinfo, opts)
            steps += res["steps"]
            notes += res["notes"]
            manual += res["manual"]
            chosen = rid
    if state["components_missing"] and sysinfo.get("pm"):
        cs, _ = requirements.install_steps(state["components_missing"], sysinfo["pm"])
        steps += cs
    if state["qgis"]["state"] == "version":
        notes.append("env_version_differs")
    if state["unavailable"]:
        notes.append("env_unavailable")
    return {"steps": steps, "notes": list(dict.fromkeys(notes)), "manual": manual, "recipe": chosen, "state": state}


def describe(spec, state, lang="en"):
    """The state of a machine against a spec as lines of text (what `env check` prints, and the Components tab shows)."""
    t = lambda k, **kw: i18n.t(k, lang, **kw)  # noqa: E731
    names = lambda ids: ", ".join(requirements.REQ[c]["label"][lang] for c in ids)  # noqa: E731
    q = state["qgis"]
    lines = [{"none": lambda: t("env_qgis_none"), "ok": lambda: t("env_qgis_ok", v=q.get("installed", "")), "missing": lambda: t("env_qgis_missing"),
              "version": lambda: t("env_qgis_version", installed=q.get("installed", ""), wanted=q.get("wanted", ""))}[q["state"]](),
             t("env_comp_line", ok=len(state["components_ok"]), n=len(spec["components"]))]
    if state["components_missing"]:
        lines.append(t("env_comp_missing", names=names(state["components_missing"])))
    if state["unavailable"]:
        lines.append(t("env_comp_unavailable", names=names(state["unavailable"])))
    return lines
