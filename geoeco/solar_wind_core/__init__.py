"""
GeoEco core — ღია ძრავებზე დაშენებული "ბოლო მილის" ლოგიკა.
Pure Python (numpy/gdal). ZERO qgis import — მუშაობს standalone-შიც და ტესტდება CI-ზე.

North star: ძრავებს (SAGA/GRASS/WindNinja) არ ვიმეორებთ — output → kWh → ₾ → რეპორტი.
"""

__version__ = "0.1.0"
__all__ = ["solar", "wind", "i18n", "raster_io"]
