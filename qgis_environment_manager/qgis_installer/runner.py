"""Running steps (blocking, no UI): every step through ``sh -c``; root steps through an elevator."""
import os
import shutil
import stat
import subprocess
import tempfile


def default_elevator(env=None, which=shutil.which):
    """pkexec when there is a graphical session (it shows a password dialog), sudo in a terminal."""
    env = os.environ if env is None else env
    graphical = bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))
    if which("pkexec") and graphical:
        return ["pkexec"]
    if which("sudo"):
        return ["sudo"]
    return ["pkexec"]


def run_steps(steps, on_line=None, elevate=("pkexec",), geteuid=None):
    """Run the steps in order, stop at the first failure.

    Returns ``(returncode, failed_step)``: ``(0, None)`` on success; ``(127, step)`` when the
    interpreter or the elevator could not be started. ``on_line(text)`` gets every output line
    (stdout and stderr merged)."""
    geteuid = geteuid or getattr(os, "geteuid", lambda: 1)   # off POSIX: never "already root"
    for s in steps:
        cmd = ["sh", "-c", s["sh"]]
        if s["root"] and geteuid() != 0:
            cmd = list(elevate) + cmd
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError:
            return 127, s
        with p:
            for line in p.stdout:
                if on_line:
                    on_line(line)
            rc = p.wait()
        if rc != 0:
            return rc, s
    return 0, None


def needs_elevation_fallback(rc, failed_step):
    """True when a root step could not even start (no pkexec / dismissed): offer a script instead."""
    return rc in (126, 127) and bool(failed_step) and failed_step["root"]


def write_root_script(steps, directory=None):
    """Write the root steps to a private script (mode 0700, fresh private folder) and return its path."""
    directory = directory or tempfile.mkdtemp(prefix="qgis-installer-")
    path = os.path.join(directory, "qgis-installer-root.sh")
    with open(path, "w") as f:
        f.write("\n".join(x["sh"] for x in steps if x["root"]))
    os.chmod(path, stat.S_IRWXU)
    return path
