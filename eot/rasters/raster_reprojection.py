from contextlib import contextmanager
import rasterio
from rasterio.io import MemoryFile
from rasterio.enums import Resampling
from rasterio import shutil as rio_shutil
from rasterio.vrt import WarpedVRT
from rasterio.warp import reproject
from eot.rasters.raster_geo_data import get_default_geo_transform
from eot.rasters.raster_source import get_src_raster
from eot.rasters.raster_driver import get_driver


def _create_reprojection_kwargs(
    src, dst_crs, dst_transform, dst_width, dst_height
):
    kwargs = src.meta.copy()
    kwargs.update(
        {
            "crs": dst_crs,
            "transform": dst_transform,
            "width": dst_width,
            "height": dst_height,
        }
    )
    return kwargs


def _reproject_bands(src, dst, resampling=Resampling.nearest):
    for i in range(1, src.count + 1):
        reproject(
            source=rasterio.band(src, i),
            destination=rasterio.band(dst, i),
            resampling=resampling,
        )


def reproject_raster(
    ifp_or_src,
    dst_crs,
    dst_transform,
    dst_width,
    dst_height,
    ofp,
    resampling=Resampling.nearest,
):
    with get_src_raster(ifp_or_src) as src:
        kwargs = _create_reprojection_kwargs(
            src, dst_crs, dst_transform, dst_width, dst_height
        )
        driver = get_driver(ofp)
        kwargs["driver"] = driver
        with rasterio.open(ofp, "w", **kwargs) as dst:
            _reproject_bands(src, dst, resampling)


def reproject_raster_2(
    ifp_or_src,
    dst_crs,
    transform,
    width,
    height,
    ofp,
    resampling=Resampling.nearest,
):
    # TODO Test this method
    # https://rasterio.readthedocs.io/en/latest/topics/virtual-warping.html#normalizing-data-to-a-consistent-grid
    with get_src_raster(ifp_or_src) as src:
        kwargs = {
            "resampling": resampling,
            "crs": dst_crs,
            "transform": transform,
            "height": height,
            "width": width,
        }
        with WarpedVRT(src, **kwargs) as vrt:
            rio_shutil.copy(vrt, ofp)


def get_default_transform_parameter(ifp_or_src, dst_crs=None):
    with get_src_raster(ifp_or_src) as src:
        if dst_crs is None:
            dst_crs = src.crs
        default_transform, width, height = get_default_geo_transform(
            src, dst_crs
        )
    return default_transform, dst_crs, width, height


def reproject_raster_with_default_transform(
    ifp_or_src, ofp, dst_crs=None, resampling=Resampling.nearest
):
    # https://rasterio.readthedocs.io/en/latest/topics/reproject.html#reprojecting-with-other-georeferencing-metadata
    (
        default_transform,
        default_crs,
        width,
        height,
    ) = get_default_transform_parameter(ifp_or_src, dst_crs)
    reproject_raster(
        ifp_or_src,
        default_crs,
        default_transform,
        width,
        height,
        ofp,
        resampling,
    )
    return default_transform, default_crs, width, height


@contextmanager
def get_reprojected_raster_generator(
    ifp_or_src,
    dst_crs,
    dst_transform,
    dst_width,
    dst_height,
    resampling=Resampling.nearest,
):
    # TODO: Have a look at the implementation of rasterio.open() here:
    #   https://github.com/rasterio/rasterio/blob/master/rasterio/__init__.py#L196
    #   https://github.com/rasterio/rasterio/blob/master/rasterio/__init__.py#L213
    # https://gis.stackexchange.com/questions/329434/creating-an-in-memory-rasterio-dataset-from-numpy-array
    with get_src_raster(ifp_or_src) as src:
        kwargs = _create_reprojection_kwargs(
            src, dst_crs, dst_transform, dst_width, dst_height
        )
        with MemoryFile() as memory_file:
            # Open as DatasetWriter
            with memory_file.open(**kwargs) as dst:
                _reproject_bands(src, dst, resampling)

            # Open as DatasetReader
            with memory_file.open() as dst:
                # yield (not return) is required for with statements
                yield dst


def get_reprojected_raster_with_default_transform_generator(
    ifp_or_src, dst_crs=None, resampling=Resampling.nearest
):
    default_transform, width, height = get_default_geo_transform(
        ifp_or_src, dst_crs
    )
    dst_dataset_generator = get_reprojected_raster_generator(
        ifp_or_src,
        dst_crs=dst_crs,
        dst_transform=default_transform,
        dst_width=width,
        dst_height=height,
        resampling=resampling,
    )
    return dst_dataset_generator
