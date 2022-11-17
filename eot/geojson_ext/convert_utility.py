import numpy as np
from eot.geojson_ext.read_utility import read_and_parse_geojson_features
from eot.geometry.geometry import rasterize_features
from eot.rasters.write import write_dataset
from eot.rasters.raster import Raster


def convert_polygon_list_to_raster_data(
    polygon_list_transformed, raster, burn_color=255, background_color=0
):
    msg = f"{type(burn_color)}, {type(background_color)}"
    assert type(burn_color) == type(background_color), msg
    if isinstance(burn_color, int):
        burn_color = [burn_color]
    if isinstance(background_color, int):
        background_color = [background_color]
    assert len(burn_color) == len(background_color)

    raster_depth = len(background_color)
    raster_data = np.full(
        (raster.height, raster.width, raster_depth),
        background_color,
        dtype=np.uint8,
    )

    burned_shapes = rasterize_features(
        shapes=polygon_list_transformed,
        out_shape=(raster.height, raster.width),
        # Used as fill value for all areas not covered by input geometries
        fill=0,
        transform=raster.transform,
        # Used as value for all geometries, if not provided in `shapes`.
        default_value=1,
    )

    for idx, burn_color_value in enumerate(burn_color):
        burned_colors = burn_color_value * burned_shapes
        raster_data[:, :, idx][burned_shapes > 0] = burned_colors[
            burned_shapes > 0
        ]

    raster_data = np.transpose(raster_data, (2, 0, 1))
    return raster_data


def convert_geojson_to_raster(
    raster_ifp,
    label_geojson_ifp,
    label_raster_ofp,
    burn_color=255,
    background_color=0,
    use_color_map=False,
    burn_value_color_map=1,
    background_value_color_map=0,
    build_overviews=True,
    compression="DEFLATE",
    predictor="1",
):
    """Convert a geojson file to a raster image.

    burn_color and background_color may be also RGB(A) tuples.
    """
    # "DEFLATE" compression creates the VERY SMALL file sizes for label images
    # "LZW" compression creates reasonable file sizes for label images
    # "PACKBITS" compression creates VERY LARGE file sizes for label images
    assert compression in ["DEFLATE", "LZW"]

    # https://kokoalberti.com/articles/geotiff-compression-optimization-guide/
    #   The Deflate, LZW and ZSTD algorithms support the use of predictors,
    #   which is a method of storing only the difference from the previous
    #   value instead of the actual value. There are three predictor settings:
    #     No predictor (1, default)
    #     Horizontal differencing (2)
    #     Floating point predition (3)

    raster = Raster.get_from_file(raster_ifp)
    polygon_list_transformed, _ = read_and_parse_geojson_features(
        label_geojson_ifp, dst_crs=raster.crs
    )
    if use_color_map:
        geojson_burn_color = burn_value_color_map
        geojson_background_color = background_value_color_map
        color_map = {
            geojson_burn_color: burn_color,
            geojson_background_color: background_color,
        }
    else:
        geojson_burn_color = burn_color
        geojson_background_color = background_color
        color_map = None

    # Depending on the value of burn_color / background_color the method
    # returns a numpy array with 1, 3 or 4 channels / bands.
    raster_data = convert_polygon_list_to_raster_data(
        polygon_list_transformed,
        raster,
        geojson_burn_color,
        geojson_background_color,
    )
    write_dataset(
        raster,
        label_raster_ofp,
        overwrite_data=raster_data,
        image_axis_order=False,
        build_overviews=build_overviews,
        label_compatible_meta_data=True,
        compress=compression,
        predictor=predictor,
        color_map=color_map,
    )
