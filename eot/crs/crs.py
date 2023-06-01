import mercantile

from rasterio.crs import CRS as _CRS
from rasterio.warp import transform as _transform
from rasterio.warp import transform_bounds as _transform_bounds
from rasterio.warp import transform_geom as _transform_geom
from rasterio.transform import IDENTITY as _IDENTITY


# https://epsg.io/3857
#   used in Google Maps, OpenStreetMap, Bing, ArcGIS, ESRI
EPSG_3857 = "EPSG:3857"

# https://epsg.io/4326
#   used in GPS, Geojson
EPSG_4326 = "EPSG:4326"


# Define some wrapper functions to obtain a lower coupling with rasterio
def epsg_4326_to_epsg_3857(lng, lat):
    return mercantile.xy(lng, lat)


# Define some wrapper functions to obtain a lower coupling with rasterio
transform_coords = _transform
transform_bounds = _transform_bounds
transform_geom = _transform_geom

CRS = _CRS
IDENTITY = _IDENTITY
