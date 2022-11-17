import copy
import numpy as np
from eot.rasters.raster import Raster
from eot.tools.aggregate_utility.tile import (
    get_tile_mask,
    get_tile_boundary,
)
from eot.tools.aggregate_utility.geojson import (
    create_geojson_feature_collection,
)
from eot.tools.aggregate_utility.img.mask import compute_mask_values
from eot.geojson_ext.convert_utility import (
    convert_polygon_list_to_raster_data,
)
from eot.rasters.write import write_dataset
from eot.utility.np_utility import (
    get_non_black_pixel_indices,
    convert_to_image_axis_order,
)


def _compute_label_color_raster_data(original_raster, masks, category_indices):
    def get_mask_callback(tile_label_mat, palette, category_index):
        index_to_color = {
            index: color for color, index in palette.colors.items()
        }
        color = index_to_color[category_index]
        return get_tile_mask(tile_label_mat, category_index), color

    label_raster_data = _compute_label_raster_data(
        original_raster,
        masks,
        category_indices,
        get_mask_callback,
        label_raster_depth=4,
    )
    return label_raster_data


def _compute_label_mask_raster_data(
    original_raster, masks, category_indices, mask_values
):
    mask_values = compute_mask_values(mask_values, category_indices)

    def get_mask_callback(tile_label_mat, palette, category_index):
        index = category_indices.index(category_index)
        mask_value = mask_values[index]
        return get_tile_mask(tile_label_mat, category_index), mask_value

    label_raster_data = _compute_label_raster_data(
        original_raster,
        masks,
        category_indices,
        get_mask_callback,
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
    original_raster,
    masks,
    category_indices,
    get_mask_callback,
    label_raster_depth,
):
    label_raster_data = np.zeros(
        (label_raster_depth, original_raster.height, original_raster.width)
    )
    if label_raster_depth == 1:
        background_color = 0
    else:
        background_color = tuple([0] * label_raster_depth)
    for category_index in category_indices:

        def _get_mask_callback(tile_label_mat, palette):
            return get_mask_callback(tile_label_mat, palette, category_index)

        (
            feature_collection,
            index_or_label_color,
        ) = create_geojson_feature_collection(
            masks,
            get_mask_callback=_get_mask_callback,
        )
        geometry_list = [
            feature["geometry"] for feature in feature_collection.features
        ]
        geojson_raster_data = convert_polygon_list_to_raster_data(
            geometry_list,
            original_raster,
            _get_index_alpha_color(index_or_label_color),
            background_color,
        )
        non_zero_indices = geojson_raster_data > 0
        label_raster_data[non_zero_indices] = geojson_raster_data[
            non_zero_indices
        ]
    return label_raster_data


def _compute_grid_raster_data(original_raster, masks):
    background_color = (0, 0, 0, 0)
    label_raster_data = np.zeros(
        (4, original_raster.height, original_raster.width)
    )

    def get_mask_callback(tile_label_mat, palette):
        # palette not used in grid callback
        return get_tile_boundary(tile_label_mat), (0, 255, 0, 255)

    feature_collection, tile_color = create_geojson_feature_collection(
        masks, get_mask_callback=get_mask_callback
    )
    geometry_list = [
        feature["geometry"] for feature in feature_collection.features
    ]
    geojson_raster_data = convert_polygon_list_to_raster_data(
        geometry_list,
        original_raster,
        _get_index_alpha_color(tile_color),
        background_color,
    )
    non_zero_indices = geojson_raster_data > 0
    label_raster_data[non_zero_indices] = geojson_raster_data[non_zero_indices]
    return label_raster_data


def create_images_with_polgyon_projection(args, masks):

    original_raster = Raster.get_from_file(args.original_raster_ifp)

    label_index_raster_data = _compute_label_mask_raster_data(
        original_raster, masks, args.category_indices, args.mask_values
    )
    write_dataset(
        original_raster,
        args.gray_mask_png_ofp,
        overwrite_data=label_index_raster_data,
        image_axis_order=False,
        build_overviews=False,
        label_compatible_meta_data=True,
        compress="DEFLATE",
    )

    label_color_raster_data = _compute_label_color_raster_data(
        original_raster, masks, args.category_indices
    )
    write_dataset(
        original_raster,
        args.color_mask_png_ofp,
        overwrite_data=label_color_raster_data,
        image_axis_order=False,
        build_overviews=False,
        label_compatible_meta_data=True,
        compress="DEFLATE",
    )

    grid_raster_data = _compute_grid_raster_data(original_raster, masks)
    grid_raster_data_iao = convert_to_image_axis_order(grid_raster_data, True)
    image_data_iao = original_raster.get_raster_data_as_numpy(
        image_axis_order=True, add_alpha_channel=True
    )

    image_data_iao_g = copy.deepcopy(image_data_iao)
    indices = get_non_black_pixel_indices(grid_raster_data_iao)
    image_data_iao_g[indices] = grid_raster_data_iao[indices]
    write_dataset(
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
    write_dataset(
        original_raster,
        args.overlay_mask_png_ofp,
        overwrite_data=image_data_iao_mg,
        image_axis_order=True,
        build_overviews=False,
        label_compatible_meta_data=True,
    )
