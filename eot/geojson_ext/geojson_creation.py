import os
from eot.utility.os_ext import makedirs_safely
from eot.utility.os_ext import get_regex_fps_in_dp

from eot.tiles.tile_manager import TileManager
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.mercator_tile import MercatorTile
from eot.rasters.raster import Raster
from eot.tools.tools_api import run_aggregate
from eot.tools.aggregation.geojson_aggregation import create_grid_geojson


def _create_geojson_tile_grid(idp, geojson_ofp, original_ifp=None):
    if original_ifp:
        image_raster_name = os.path.splitext(os.path.basename(original_ifp))[0]
        raster = Raster.get_from_file(original_ifp)
        raster_transform, raster_crs = raster.get_geo_transform_with_crs()
    else:
        image_raster_name = None
        raster_transform = None
        raster_crs = None

    image_tiles = list(
        TileManager.read_tiles_from_dir(
            idp=idp,
            target_raster_name=image_raster_name,
        )
    )
    makedirs_safely(os.path.dirname(geojson_ofp))
    create_grid_geojson(
        image_tiles,
        geojson_ofp,
        raster_transform=raster_transform,
        raster_crs=raster_crs,
    )


def create_geojson_for_image_tiles(
    data_dp, search_regex, ignore_regex, images_dp, grid_json_fn
):
    dataset_tile_type = TilePathManager.get_tile_type_from_dir(images_dp)
    if dataset_tile_type == ImagePixelTile:
        original_ifps = get_regex_fps_in_dp(
            data_dp, search_regex, ignore_regex
        )
        for original_ifp in original_ifps:
            image_raster_name = os.path.splitext(
                os.path.basename(original_ifp)
            )[0]
            geojson_odp = os.path.join(
                images_dp, "geojson_summary", image_raster_name
            )
            geojson_ofp = os.path.join(geojson_odp, grid_json_fn)
            _create_geojson_tile_grid(images_dp, geojson_ofp, original_ifp)
    elif dataset_tile_type == MercatorTile:
        geojson_odp = os.path.join(images_dp, "geojson_summary")
        geojson_ofp = os.path.join(geojson_odp, grid_json_fn)
        _create_geojson_tile_grid(images_dp, geojson_ofp)
    else:
        assert False


def create_geojson_for_label_tiles(
    test_data_dp,
    search_regex,
    ignore_regex,
    test_images_dp,
    test_labels_dp,
    categories,
    odp,
    grid_json_fn="grid.json",
    lazy=False,
):
    dataset_tile_type = TilePathManager.get_tile_type_from_dir(test_images_dp)
    if dataset_tile_type == ImagePixelTile:
        original_ifps = get_regex_fps_in_dp(
            test_data_dp, search_regex, ignore_regex
        )
        for original_ifp in original_ifps:
            masks_raster_name = os.path.splitext(
                os.path.basename(original_ifp)
            )[0]
            geojson_odp = os.path.join(
                odp, "geojson_summary", masks_raster_name
            )
            run_aggregate(
                masks_idp=test_labels_dp,
                categories=categories,
                masks_raster_name=masks_raster_name,
                geojson_odp=geojson_odp,
                geojson_grid_ofn=grid_json_fn,
                original_raster_ifp=original_ifp,
                lazy=lazy,
            )
    elif dataset_tile_type == MercatorTile:
        geojson_odp = os.path.join(odp, "geojson_summary")
        run_aggregate(
            masks_idp=test_labels_dp,
            categories=categories,
            geojson_odp=geojson_odp,
            geojson_grid_ofn=grid_json_fn,
            lazy=lazy,
        )
    else:
        assert False
