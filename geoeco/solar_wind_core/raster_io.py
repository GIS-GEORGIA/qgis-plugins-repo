"""
GDAL-ის მსუბუქი wrapper — რასტრის წაკითხვა/ჩაწერა numpy მასივად.

QGIS-ს GDAL უკვე მოყვება. import lazy-ია, რომ pure-math ტესტებმა
(pv_yield/economics/weibull) GDAL-ის გარეშეც გაირბინოს.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RasterData:
    """რასტრი + გეო-რეფერენსი. array shape = (rows, cols)."""
    array: Any            # numpy.ndarray
    geotransform: tuple   # GDAL GeoTransform (6 float)
    projection: str       # WKT
    nodata: float | None = None

    @property
    def pixel_area_m2(self) -> float:
        """ერთი პიქსელის ფართი მ²-ში (პროექცია მეტრებში უნდა იყოს)."""
        px = abs(self.geotransform[1])
        py = abs(self.geotransform[5])
        return px * py


def read_raster(path: str, band: int = 1) -> RasterData:
    from osgeo import gdal  # lazy import
    ds = gdal.Open(path)
    if ds is None:
        raise FileNotFoundError(f"რასტრი ვერ გაიხსნა / cannot open raster: {path}")
    b = ds.GetRasterBand(band)
    arr = b.ReadAsArray()
    return RasterData(
        array=arr,
        geotransform=ds.GetGeoTransform(),
        projection=ds.GetProjection(),
        nodata=b.GetNoDataValue(),
    )


def write_raster(path: str, data: RasterData, dtype: str = "float32") -> str:
    from osgeo import gdal, gdal_array  # lazy import
    rows, cols = data.array.shape
    gdal_dtype = gdal_array.NumericTypeCodeToGDALTypeCode(data.array.dtype)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, 1, gdal_dtype,
                       options=["COMPRESS=DEFLATE", "TILED=YES"])
    ds.SetGeoTransform(data.geotransform)
    ds.SetProjection(data.projection)
    band = ds.GetRasterBand(1)
    if data.nodata is not None:
        band.SetNoDataValue(float(data.nodata))
    band.WriteArray(data.array)
    band.FlushCache()
    ds = None
    return path


def latlon_center(data: RasterData) -> tuple[float, float]:
    """რასტრის ცენტრის lat/lon — მზის პოზიციისთვის საჭირო."""
    from osgeo import osr  # lazy import
    gt = data.geotransform
    rows, cols = data.array.shape
    cx = gt[0] + gt[1] * cols / 2 + gt[2] * rows / 2
    cy = gt[3] + gt[4] * cols / 2 + gt[5] * rows / 2

    src = osr.SpatialReference()
    src.ImportFromWkt(data.projection)
    tgt = osr.SpatialReference()
    tgt.ImportFromEPSG(4326)
    try:
        src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        tgt.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    except AttributeError:
        pass
    ct = osr.CoordinateTransformation(src, tgt)
    lon, lat, _ = ct.TransformPoint(cx, cy)
    return lat, lon
