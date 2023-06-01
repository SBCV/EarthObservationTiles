import copy
import numpy as np
from eot.rasters.raster import Raster
from eot.tools.aggregation import get_tile_boundary, get_tile_mask
from eot.geojson_ext.geo_segmentation import GeoSegmentation
from eot.rasters.raster_writing import write_raster
from eot.utility.np_ext import (
    get_non_black_pixel_indices,
    convert_to_image_axis_order,
)


def _compute_label_color_raster_data(original_raster, masks, categories):
    def get_category_mask_callback(tile_label_mat, palette, category):
        color = category.palette_color
        return get_tile_mask(tile_label_mat, category), color

    label_raster_data = _compute_label_raster_data(
        original_raster,
        masks,
        categories,
        get_category_mask_callback,
        label_raster_depth=4,
    )
    return label_raster_data


def _compute_label_mask_raster_data(original_raster, masks, categories):
    def get_category_mask_callback(tile_label_mat, palette, category):
        mask_value = category.palette_index
        return (get_tile_mask(tile_label_mat, category), mask_value)

    label_raster_data = _compute_label_raster_data(
        original_raster,
        masks,
        categories,
        get_category_mask_callback,
        label_raster_depth=1,
    )
    return label_raster_data


def _get_index_alpha_color(tile_color):
    if type(tile_color) in [int, float]:
        pass
    elif len(tile_color) == 3:
        tile_color = (*tile_color, 255)
    return tile_color


def _compute_label_raster_data(
    raster,
    masks,
    categories,
    get_category_mask_callback,
    label_raster_depth,
):
    label_raster_data = np.zeros(
        (label_raster_depth, raster.height, raster.width)
    )
    if label_raster_depth == 1:
        background_color = 0
    else:
        background_color = tuple([0] * label_raster_depth)
    for category in categories:

        def get_geojson_mask_callback(tile_label_mat, palette):
            return get_category_mask_callback(
                tile_label_mat, palette, category
            )

        raster_transform, raster_crs = raster.get_geo_transform_with_crs()
        geo_segmentation = GeoSegmentation.from_tiles(
            masks,
            get_mask_callback=get_geojson_mask_callback,
            raster_transform=raster_transform,
            raster_crs=raster_crs,
        )
        geojson_raster_data = geo_segmentation.to_raster_data(
            raster.width,
            raster.height,
            raster_transform,
            raster_crs,
            _get_index_alpha_color(geo_segmentation.mask_color),
            background_color,
        )
        non_zero_indices = geojson_raster_data > 0
        label_raster_data[non_zero_indices] = geojson_raster_data[
            non_zero_indices
        ]
    return label_raster_data


def _compute_grid_raster_data(raster, masks):
    background_color = (0, 0, 0, 0)
    label_raster_data = np.zeros((4, raster.height, raster.width))
    raster_transform, raster_crs = raster.get_geo_transform_with_crs()

    def get_geojson_mask_callback(tile_label_mat, palette):
        # palette not used in grid callback
        return get_tile_boundary(tile_label_mat), (0, 255, 0, 255)

    geo_segmentation = GeoSegmentation.from_tiles(
        masks,
        get_mask_callback=get_geojson_mask_callback,
        raster_transform=raster_transform,
        raster_crs=raster_crs,
    )
    geojson_raster_data = geo_segmentation.to_raster_data(
        raster.width,
        raster.height,
        raster_transform,
        raster_crs,
        _get_index_alpha_color(geo_segmentation.mask_color),
        background_color,
    )
    non_zero_indices = geojson_raster_data > 0
    label_raster_data[non_zero_indices] = geojson_raster_data[non_zero_indices]
    return label_raster_data


def create_images_with_polgyon_projection(args, masks, categories):
    original_raster = Raster.get_from_file(args.original_raster_ifp)
    label_index_raster_data = _compute_label_mask_raster_data(
        original_raster, masks, categories
    )
    color_map = {
        category.palette_index: category.palette_color
        for category in categories
    }
    write_raster(
        original_raster,
        args.gray_mask_png_ofp,
        overwrite_data=label_index_raster_data,
        image_axis_order=False,
        build_overviews=False,
        label_compatible_meta_data=True,
        compress="DEFLATE",
        color_map=color_map,
    )

    label_color_raster_data = _compute_label_color_raster_data(
        original_raster, masks, categories
    )
    write_raster(
        original_raster,
        args.color_mask_png_ofp,
        overwrite_data=label_color_raster_data,
        image_axis_order=False,
        build_overviews=False,
        label_compatible_meta_data=True,
        compress="DEFLATE",
    )

    # iao = image axis order
    grid_raster_data = _compute_grid_raster_data(original_raster, masks)
    grid_raster_data_iao = convert_to_image_axis_order(grid_raster_data, True)
    image_data_iao = original_raster.get_raster_data_as_numpy(
        image_axis_order=True, add_alpha_channel=True
    )

    image_data_iao_g = copy.deepcopy(image_data_iao)
    indices = get_non_black_pixel_indices(grid_raster_data_iao)
    image_data_iao_g[indices] = grid_raster_data_iao[indices]
    write_raster(
        original_raster,
        args.overlay_grid_png_ofp,
        overwrite_data=image_data_iao_g,
        image_axis_order=True,
        build_overviews=False,
        label_compatible_meta_data=True,
    )

    image_data_iao_mg = copy.deepcopy(image_data_iao)
    label_color_raster_data_iao = convert_to_image_axis_order(
        label_color_raster_data, True
    )
    indices = get_non_black_pixel_indices(label_color_raster_data_iao)
    image_data_iao_mg[indices] = label_color_raster_data_iao[indices]
    indices = get_non_black_pixel_indices(grid_raster_data_iao)
    image_data_iao_mg[indices] = grid_raster_data_iao[indices]
    write_raster(
        original_raster,
        args.overlay_mask_png_ofp,
        overwrite_data=image_data_iao_mg,
        image_axis_order=True,
        build_overviews=False,
        label_compatible_meta_data=True,
    )
