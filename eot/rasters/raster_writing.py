import os
import numpy as np
import rasterio
from contextlib import contextmanager
from rasterio.io import MemoryFile
from eot.rasters.raster_driver import get_driver


def _parse_transfrom_crs_gcps(transform, crs, gcps, check_result=False):

    if transform is not None and not transform.is_identity and crs is not None:
        _transform = transform
        _crs = crs
        _gcps = None
    elif gcps is not None and len(gcps[0]) >= 1 and gcps[1] is not None:
        _transform = None
        _crs = None
        _gcps = gcps
    else:
        _transform = None
        _crs = None
        _gcps = None
        if check_result:
            assert False
    return _transform, _crs, _gcps


def _prepare_data(data, image_axis_order):
    if data is not None:
        data = np.copy(data)
        if data.ndim == 2:
            if image_axis_order:
                # Append dimension: (height, width, channel)
                # Equivalent to np.atleast_3d
                data = np.expand_dims(data, axis=-1)
            else:
                # Prepend dimension: (channel, height, width)
                data = np.expand_dims(data, axis=0)
        if image_axis_order:
            # (height, width, channel) -> (channel, height, width)
            data = np.moveaxis(data, 2, 0)
    return data


def copy_raster(ifp, ofp):
    """Copies the raster (and possibly changes the file format)"""
    with rasterio.open(ifp) as src:
        transform, crs, gcps = _parse_transfrom_crs_gcps(
            src.transform, src.crs, src.gcps, check_result=True
        )
        write_raster(src, ofp, transform=transform, crs=crs, gcps=gcps)


def write_numpy_as_raster(
    src,
    ofp,
    transform,
    crs,
    image_axis_order=True,
    check_driver=True,
    **kwargs
):
    src_copy = _prepare_data(src, image_axis_order)
    driver = get_driver(ofp, check_driver)
    with rasterio.open(
        ofp,
        "w",
        driver=driver,
        height=src_copy.shape[1],
        width=src_copy.shape[2],
        count=src_copy.shape[0],
        dtype=str(src_copy.dtype),
        crs=crs,
        transform=transform,
        **kwargs
    ) as new_dataset:
        new_dataset.write(src_copy)


def write_aux_xml(
    src,
    ofp,
    transform,
    crs,
    image_axis_order=True,
    check_driver=True,
    check_transform_crs=True,
    **kwargs
):
    if check_transform_crs:
        assert transform is not None
        assert crs is not None
    src_copy = _prepare_data(src, image_axis_order)
    driver = get_driver(ofp, check_driver)
    with rasterio.open(
        ofp,
        "w",
        driver=driver,
        height=src_copy.shape[1],
        width=src_copy.shape[2],
        count=src_copy.shape[0],
        dtype=str(src_copy.dtype),
        crs=crs,
        transform=transform,
        **kwargs
    ) as _:
        pass
    os.remove(ofp)


def _initialize_profile(profile, kwargs, ofp, overwrite_data):
    # https://gdal.org/drivers/raster/gtiff.html#creation-options
    for key, value in kwargs.items():
        profile[key] = value
    profile["driver"] = get_driver(ofp)
    if overwrite_data is not None:
        profile["count"] = overwrite_data.shape[0]


def _ensure_label_compatible_meta_data(profile):
    # If present delete the photometric key, which is only valid for JPEG
    # compressions.
    profile.pop("photometric", None)
    return profile


def _ensure_consistent_crs_transform_values(profile):
    # Avoid the following case, since it results in empty images (in QGIS):
    #   crs is None
    #   transform is not None
    if profile["crs"] is None:
        profile["transform"] = None
    return profile


def _write_data(src, dst, overwrite_data, dst_dtype, transform, crs, gcps):
    if overwrite_data is not None:
        result = overwrite_data
    else:
        data = src.read()
        result = data.astype(dst_dtype, casting="unsafe", copy=False)
    dst.write(result)
    _transform, _crs, _gcps = _parse_transfrom_crs_gcps(transform, crs, gcps)
    if _transform is not None:
        dst.transform = _transform
    if _crs is not None:
        dst.crs = _crs
    if _gcps is not None:
        dst.gcps = gcps


def _write_color_map(dst, color_map):
    # Note: Tiff files do not support alpha values in color maps
    #  See: https://github.com/rasterio/rasterio/issues/394

    msg = "Color maps are only allowed for single channel images"
    assert dst.count == 1, msg
    assert isinstance(color_map, dict)
    dst.write_colormap(1, color_map)


def _build_overviews(src, dst):
    # https://rasterio.readthedocs.io/en/latest/topics/overviews.html
    reference_band = 1
    src_overviews = src.overviews(reference_band)
    # src_overviews is something like [2,4,8,...]
    dst.build_overviews(src_overviews)


def write_raster(
    src,
    ofp,
    transform=None,
    crs=None,
    gcps=None,
    overwrite_data=None,
    image_axis_order=False,
    build_overviews=True,
    label_compatible_meta_data=False,
    color_map=None,
    **kwargs
):
    """
    For labeled data one might use the following kwargs to reduce file size:
        compress="DEFLATE"
        predictor="1"

    For the definition of color_map see
     https://rasterio.readthedocs.io/en/latest/topics/color.html#writing-colormaps
    """

    profile = src.profile
    overwrite_data = _prepare_data(overwrite_data, image_axis_order)
    _initialize_profile(profile, kwargs, ofp, overwrite_data)

    if label_compatible_meta_data:
        profile = _ensure_label_compatible_meta_data(profile)

    profile = _ensure_consistent_crs_transform_values(profile)

    with rasterio.open(ofp, "w", **profile) as dst:
        dst_dtype = profile["dtype"]
        _write_data(src, dst, overwrite_data, dst_dtype, transform, crs, gcps)
        if color_map is not None:
            _write_color_map(dst, color_map)
        if build_overviews:
            _build_overviews(src, dst)


@contextmanager
def get_written_raster_generator(
    src,
    transform=None,
    crs=None,
    gcps=None,
    overwrite_data=None,
    image_axis_order=False,
    build_overviews=True,
    label_compatible_meta_data=False,
    **kwargs
):
    profile = src.profile
    overwrite_data = _prepare_data(overwrite_data, image_axis_order)
    _initialize_profile(profile, kwargs, None, overwrite_data)

    if label_compatible_meta_data:
        profile = _ensure_label_compatible_meta_data(profile)

    profile = _ensure_consistent_crs_transform_values(profile)

    with MemoryFile() as memory_file:
        # Open as DatasetWriter
        with memory_file.open(**profile) as dst:
            dst_dtype = profile["dtype"]
            _write_data(
                src, dst, overwrite_data, dst_dtype, transform, crs, gcps
            )
            if build_overviews:
                _build_overviews(src, dst)

        # Open as DatasetReader
        with memory_file.open() as dst:
            # yield (not return) is required for with statements
            yield dst
