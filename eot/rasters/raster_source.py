from contextlib import contextmanager
import rasterio


@contextmanager
def get_src_raster(ifp_or_src):
    if type(ifp_or_src) == str:
        with rasterio.open(ifp_or_src) as src:
            yield src
    else:
        yield ifp_or_src
