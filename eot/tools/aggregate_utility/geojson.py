import os
import geojson
from tqdm import tqdm
from eot.crs.crs import CRS

from eot.geojson_ext.parse_mask_utility import parse_mask
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.rasters.raster import Raster

from eot.tools.aggregate_utility.tile import (
    get_tile_label_mat,
    get_tile_mask,
    get_tile_boundary,
)


def _get_tile_transform(tile, tile_mat, raster_transform, raster_crs):
    # Get height and width from 2D and 3D masks
    width, height = tile_mat.shape[-2:]
    tile.disk_width = width
    tile.disk_height = height
    if isinstance(tile, MercatorTile):
        assert raster_transform is None
        assert raster_crs is None
        tile_transform = tile.get_transform_pixel_to_epsg_4326()
        tile_crs = CRS.from_epsg(4326)
    elif isinstance(tile, ImagePixelTile):
        tile.set_raster_transform(raster_transform)
        tile.set_crs(raster_crs)
        tile.compute_and_set_tile_transform()
        tile_transform = tile.get_tile_transform()
        tile_crs = tile.get_crs()
    else:
        assert False
    return tile_transform, tile_crs


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def create_geojson_feature_collection(
    masks, get_mask_callback, original_raster_ifp=None
):
    geojson_feature_list = []
    mask_color = None
    raster_transform = None
    raster_crs = None
    if original_raster_ifp:
        raster = Raster.get_from_file(original_raster_ifp)
        raster_transform = raster.transform
        raster_crs = raster.crs
    for tile in tqdm(masks, ascii=True, unit="mask"):
        tile_label_mat, palette = get_tile_label_mat(
            tile.get_absolute_tile_fp()
        )
        tile_mask, _mask_color = get_mask_callback(tile_label_mat, palette)
        tile_transform, tile_crs = _get_tile_transform(
            tile, tile_label_mat, raster_transform, raster_crs
        )
        # parse_mask() transforms the coordinates into EPSG_4326,
        # which is required by geojson
        tile_geojson_feature_list = parse_mask(
            tile_mask, tile_transform, src_crs=tile_crs
        )
        for tile_geojson_feature in tile_geojson_feature_list:
            if _mask_color is not None:
                # https://github.com/mapbox/simplestyle-spec/tree/master/1.1.0
                tile_geojson_feature["properties"]["fill"] = _rgb_to_hex(
                    _mask_color
                )
                tile_geojson_feature["properties"]["fill-opacity"] = 0.5
        geojson_feature_list.extend(tile_geojson_feature_list)
        if mask_color is None:
            mask_color = _mask_color
        else:
            assert mask_color == _mask_color
    geojson_feature_collection = geojson.FeatureCollection(
        geojson_feature_list
    )
    return geojson_feature_collection, mask_color


def create_grid_geojson(masks, geojson_ofp, original_raster_ifp=None):
    def get_mask_callback(tile_label_mat, palette):
        # palette not used in grid callback
        return get_tile_boundary(tile_label_mat), None

    feature_collection, _ = create_geojson_feature_collection(
        masks,
        get_mask_callback=get_mask_callback,
        original_raster_ifp=original_raster_ifp,
    )
    with open(geojson_ofp, "w", encoding="utf-8") as geojson_file:
        assert geojson_file, "Unable to write in output file"
        geojson_file.write(geojson.dumps(feature_collection))


def create_category_geojson(
    masks, categories, category_indices, original_raster_ifp, geojson_odp
):
    categories = [category for category in categories]
    for category_index in category_indices:

        def get_mask_callback(tile_label_mat, palette):
            index_to_color = {
                index: color for color, index in palette.colors.items()
            }
            if category_index in index_to_color:
                color = index_to_color[category_index]
            else:
                color = None
            return get_tile_mask(tile_label_mat, category_index), color

        feature_collection, label_color = create_geojson_feature_collection(
            masks,
            get_mask_callback=get_mask_callback,
            original_raster_ifp=original_raster_ifp,
        )
        category_str = categories[category_index].title.lower()
        geojson_ofp = os.path.join(geojson_odp, category_str + ".json")
        with open(geojson_ofp, "w", encoding="utf-8") as geojson_file:
            assert geojson_file, "Unable to write in output file"
            geojson_file.write(geojson.dumps(feature_collection))
