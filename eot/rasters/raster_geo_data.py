import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform
from eot.rasters.raster_writing import write_raster, _parse_transfrom_crs_gcps
from eot.utility.conversion import convert_affine_to_numpy


def has_valid_matrix_geo_transform(raster):
    has_transformation = not raster.transform.is_identity
    has_crs = raster.crs is not None
    return has_transformation and has_crs


def has_valid_gcps_geo_transform(raster):
    has_gcps = len(raster.gcps[0]) > 0
    has_gcps_crs = raster.gcps[1]
    return has_gcps and has_gcps_crs


def get_default_geo_transform(raster, dst_crs):
    if has_valid_matrix_geo_transform(raster):
        default_transform, width, height = calculate_default_transform(
            raster.crs, dst_crs, raster.width, raster.height, *raster.bounds
        )
    elif has_valid_gcps_geo_transform(raster):
        default_transform, width, height = calculate_default_transform(
            raster.gcps[1],
            dst_crs,
            raster.width,
            raster.height,
            gcps=raster.gcps[0],
        )
    else:
        assert False
    return default_transform, width, height


def has_default_geo_transform(raster):
    has_default_transform = True
    _, crs = get_geo_transform_pixel_to_crs(raster, check_validity=True)
    default_transform, width, height = get_default_geo_transform(raster, crs)
    default_transform_np = convert_affine_to_numpy(default_transform)
    raster_transform_np = convert_affine_to_numpy(raster.transform)

    # NOTE: Use in the following np.allclose() instead of np.array_equal, since
    # the result of "get_default_transformation()" is (because of numerical
    # errors) not unique. Consider the following code snippet:
    #
    # default_trans_1, width_1, height_1 = get_default_transformation(raster)
    # kwargs.update(
    #     {
    #         "crs": dst_crs,
    #         "transform": default_trans_1,
    #         "width": width_1,
    #         "height": height_1,
    #     }
    # )
    # with rasterio.open(ofp, "w", **kwargs) as dst:
    #   default_trans_2, width_2, height_2 = get_default_transformation(dst)
    #   assert width_1 == width_2                       # Should pass
    #   assert height_1 == height_2                     # Should pass
    #   assert default_trans_1 == default_trans_2       # May fail

    if not np.allclose(default_transform_np, raster_transform_np):
        has_default_transform = False
    if width != raster.width or height != raster.height:
        has_default_transform = False
    return has_default_transform


def get_geo_transform_pixel_to_crs(raster, check_validity=True):
    valid_transformation_matrix = has_valid_matrix_geo_transform(raster)
    valid_gcps = has_valid_gcps_geo_transform(raster)

    if check_validity:
        assert valid_transformation_matrix != valid_gcps

    if valid_transformation_matrix:
        transform = raster.transform
        crs = raster.crs
    elif valid_gcps:
        transform = rasterio.transform.from_gcps(raster.gcps[0])
        crs = raster.gcps[1]
    else:
        transform = None
        crs = None

    return transform, crs


def get_geo_transform_pixel_to_crs_from_file(ifp, check_validity=True):
    """Uses the transformation matrix and GPCS to determine a transformation"""

    with rasterio.open(ifp, "r") as raster:
        return get_geo_transform_pixel_to_crs(raster, check_validity)


def get_geo_transform_crs_to_pixel_from_file(ifp, check_validity=True):
    """Uses the transformation matrix and GPCS to determine a transformation"""

    with rasterio.open(ifp, "r") as raster:
        transform, crs = get_geo_transform_pixel_to_crs(raster, check_validity)
        return ~transform, crs


def write_geo_data(ifp, ofp, transform=None, crs=None, gcps=None):
    """Write the raster"""

    # Note: newer rasterio versions provide also rasterio.shutil.copy
    # See also:
    # https://github.com/mapbox/rasterio/blob/master/rasterio/rio/convert.py

    with rasterio.open(ifp, "r") as src:
        write_raster(src, ofp, transform=transform, crs=crs, gcps=gcps)


def overwrite_geo_transform(ifp, ofp, transform, crs):
    write_geo_data(ifp, ofp, transform=transform, crs=crs)


def overwrite_geo_transform_or_crs(ifp, ofp, transform=None, crs=None):
    """Overwrite the transform and/or crs of an raster image."""

    assert crs is not None or transform is not None

    _transform, _crs = get_geo_transform_pixel_to_crs_from_file(
        ifp, check_validity=False
    )
    if transform is None:
        transform = _transform
    if crs is None:
        crs = _crs
    write_geo_data(ifp, ofp, transform=transform, crs=crs)


def ensure_geo_transform(ifp, ofp, check_validity=True):
    """Derives a geo transform from GCPS, if necessary."""

    transform, crs = get_geo_transform_pixel_to_crs_from_file(
        ifp, check_validity
    )
    write_geo_data(ifp, ofp, transform=transform, crs=crs)


def copy_geo_meta_data(ifp_with_geo, ifp_with_image_data, ofp):
    with rasterio.open(ifp_with_geo) as src_with_geo:
        transform, crs, gcps = _parse_transfrom_crs_gcps(
            src_with_geo.transform,
            src_with_geo.crs,
            src_with_geo.gcps,
            check_result=True
        )
        with rasterio.open(ifp_with_image_data) as src_with_image_data:
            write_raster(
                src_with_image_data,
                ofp,
                transform=transform,
                crs=crs,
                gcps=gcps
            )
