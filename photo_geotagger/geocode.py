"""Reverse geocoding (coordinates -> country / region / city / street) with OpenStreetMap Nominatim.

Standard library only. Follows the Nominatim usage policy: an identifying User-Agent, at most one
request per second, and results are cached so photos taken at one spot cost a single request.
Not meant for bulk jobs on the public server: point `url` at your own Nominatim instance for those.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

PUBLIC_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "PhotoGeotagger-QGIS-plugin/0.6 (+https://github.com/GIS-GEORGIA/qgis-plugins-repo)"
MIN_INTERVAL = 1.1  # seconds between requests to the public server

CITY_KEYS = ("city", "town", "village", "municipality", "hamlet", "county")
STREET_KEYS = ("road", "pedestrian", "footway", "path", "residential")
AREA_KEYS = ("suburb", "neighbourhood", "city_district", "quarter")


class GeocodeError(Exception):
    pass


def parse_address(data):
    """Map a Nominatim `reverse` JSON answer to {country, region, city, location} (empty values dropped)."""
    addr = data.get("address") or {}

    def first(keys):
        for key in keys:
            if addr.get(key):
                return addr[key]
        return ""

    street = first(STREET_KEYS)
    if street and addr.get("house_number"):
        street = "%s %s" % (street, addr["house_number"])
    location = ", ".join(part for part in (street, first(AREA_KEYS)) if part)
    place = {"country": addr.get("country", ""), "region": addr.get("state") or addr.get("region") or "",
             "city": first(CITY_KEYS), "location": location}
    return {k: v for k, v in place.items() if v}


class Geocoder:
    """Cached, rate-limited reverse geocoder. Use one instance per job and call it from one thread."""

    def __init__(self, lang="en", url=PUBLIC_URL, min_interval=None, opener=None, sleep=time.sleep,
                 clock=time.monotonic):
        self.lang, self.url = lang, url or PUBLIC_URL
        self.min_interval = MIN_INTERVAL if min_interval is None else min_interval
        self.opener = opener or urllib.request.urlopen
        self.sleep, self.clock = sleep, clock
        self.cache = {}
        self.requests = 0
        self._last = None

    def lookup(self, lat, lon):
        """Place dict for the coordinates; {} when OSM knows nothing there. Raises GeocodeError on failure."""
        key = (round(lat, 4), round(lon, 4))  # about 10 m: street level stays correct
        if key in self.cache:
            return dict(self.cache[key])
        if self._last is not None:
            wait = self.min_interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        query = urllib.parse.urlencode({"format": "jsonv2", "lat": "%.6f" % lat, "lon": "%.6f" % lon,
                                        "zoom": 18, "addressdetails": 1, "accept-language": self.lang})
        request = urllib.request.Request("%s?%s" % (self.url, query), headers={"User-Agent": USER_AGENT})
        try:
            with self.opener(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise GeocodeError(str(exc))
        finally:
            self._last = self.clock()
            self.requests += 1
        place = {} if data.get("error") else parse_address(data)
        self.cache[key] = place
        return dict(place)
