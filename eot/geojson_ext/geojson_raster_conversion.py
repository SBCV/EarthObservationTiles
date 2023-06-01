from eot.geojson_ext.geo_segmentation import GeoSegmentation
from eot.rasters.raster import Raster


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
    raster = Raster.get_from_file(raster_ifp)
    geo_segmentation = GeoSegmentation.from_geojson_file(label_geojson_ifp)
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

    geo_segmentation.write_to_raster(
        label_raster_ofp,
        raster,
        geojson_burn_color,
        geojson_background_color,
        build_overviews,
        compression,
        predictor,
        color_map,
    )
