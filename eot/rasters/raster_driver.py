import rasterio


def get_driver(fp, check_driver=True):
    if fp is None:
        driver = "GTiff"
    else:
        # https://gdal.org/drivers/raster/index.html
        # https://github.com/mapbox/rasterio/blob/d7b2dd3ae64c55978e265fa9230732e88b1dc9ae/rasterio/drivers.py
        driver = rasterio.drivers.driver_from_extension(fp)
    if check_driver:
        assert driver in ["GTiff", "PNG"], driver
    return driver
