"""Web Mercator tile maths and a small disk-cached OpenStreetMap tile fetcher (standard library only).

Follows the OSM tile usage policy: identifying User-Agent, local cache, at most two parallel connections.
The map must show "© OpenStreetMap contributors" (the standalone app draws it).
"""
import math
import os
import threading
import urllib.error
import urllib.request

TILE = 256
MAX_ZOOM = 19
URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "PhotoGeotagger-standalone/0.8 (+https://github.com/GIS-GEORGIA/qgis-plugins-repo)"


def world_size(zoom):
    return TILE * (2 ** zoom)


def to_pixel(lat, lon, zoom):
    """Global pixel coordinates (x right, y down) of a WGS 84 position."""
    lat = max(-85.05112878, min(85.05112878, lat))
    size = world_size(zoom)
    x = (lon + 180.0) / 360.0 * size
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * size
    return x, y


def from_pixel(x, y, zoom):
    size = world_size(zoom)
    lon = x / size * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / size
    lat = math.degrees(math.atan(0.5 * (math.exp(n) - math.exp(-n))))
    return lat, lon


def zoom_to_fit(points, width, height, margin=40):
    """Highest zoom at which all (lat, lon) points fit; (center_lat, center_lon, zoom)."""
    if not points:
        return 41.7, 44.8, 6
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    clat, clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
    for zoom in range(MAX_ZOOM, 0, -1):
        xs = [to_pixel(p[0], p[1], zoom)[0] for p in points]
        ys = [to_pixel(p[0], p[1], zoom)[1] for p in points]
        if max(xs) - min(xs) <= width - 2 * margin and max(ys) - min(ys) <= height - 2 * margin:
            return clat, clon, min(zoom, 17)
    return clat, clon, 1


class TileCache:
    """Disk cache plus background fetching; `on_ready(z, x, y)` is called (from a worker thread) after a download."""

    def __init__(self, directory, url=URL, opener=None, on_ready=None):
        self.directory = directory
        self.url = url
        self.opener = opener or urllib.request.urlopen
        self.on_ready = on_ready
        self.pending, self.failed = set(), set()
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(2)

    def _path(self, z, x, y):
        return os.path.join(self.directory, str(z), str(x), "%d.png" % y)

    def get(self, z, x, y):
        """PNG bytes when cached, else None (a download is started once)."""
        path = self._path(z, x, y)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        key = (z, x, y)
        with self._lock:
            if key in self.pending or key in self.failed:
                return None
            self.pending.add(key)
        threading.Thread(target=self._download, args=key, daemon=True).start()
        return None

    def _download(self, z, x, y):
        try:
            with self._slots:
                request = urllib.request.Request(self.url.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT})
                with self.opener(request, timeout=20) as response:
                    data = response.read()
            path = self._path(z, x, y)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            if self.on_ready:
                self.on_ready(z, x, y)
        except (urllib.error.URLError, OSError, ValueError):
            with self._lock:
                self.failed.add((z, x, y))
        finally:
            with self._lock:
                self.pending.discard((z, x, y))

    def retry_failed(self):
        with self._lock:
            self.failed.clear()
