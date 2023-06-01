import os
from eot.geojson_ext.geo_segmentation import GeoSegmentation
from eot.tools.aggregation import get_tile_boundary, get_tile_mask


def create_grid_geojson(
    masks, geojson_ofp, raster_transform=None, raster_crs=None
):
    def get_mask_callback(tile_label_mat, palette):
        # palette not used in grid callback
        return get_tile_boundary(tile_label_mat), None

    geo_segmentation = GeoSegmentation.from_tiles(
        masks,
        get_mask_callback=get_mask_callback,
        raster_transform=raster_transform,
        raster_crs=raster_crs,
    )
    geo_segmentation.write_as_geojson_feature_collection(geojson_ofp)


def create_category_geojson(
    masks, categories, geojson_odp, raster_transform=None, raster_crs=None
):
    for category in categories:

        def get_mask_callback(tile_label_mat, palette):
            index_to_color = {
                index: color for color, index in palette.colors.items()
            }
            if category.palette_index in index_to_color:
                color = index_to_color[category.palette_index]
            else:
                color = None
            return get_tile_mask(tile_label_mat, category), color

        geo_segmentation = GeoSegmentation.from_tiles(
            masks,
            get_mask_callback=get_mask_callback,
            raster_transform=raster_transform,
            raster_crs=raster_crs,
        )
        category_str = category.name.lower()
        geojson_ofp = os.path.join(geojson_odp, category_str + ".json")
        geo_segmentation.write_as_geojson_feature_collection(geojson_ofp)
