import copy
import os
import numpy as np
import itertools
from eot.rasters.raster import Raster
from eot.rasters.raster_writing import write_raster
from eot.tiles.tile_manager import TileManager
from eot.tiles.tile_reading import (
    read_image_tile_from_file,
    read_label_tile_from_file,
)
from eot.tiles.tile_writing import (
    write_image_tile_to_file,
    write_label_tile_to_file,
)
from eot.fusion.tile_fusion import copy_tiling_result_file
from eot.utility.os_ext import makedirs_safely
from eot.tiles.tiling_result import RasterTilingResults


def adjust_tile_fp(input_tile, new_odp):
    output_tile = copy.deepcopy(input_tile)
    new_ofp = os.path.join(new_odp, output_tile.get_relative_tile_fp())
    output_tile.set_tile_fp(new_ofp, is_absolute=True, root_dp=new_odp)
    return output_tile


def simulate_prediction_with_border(
    idp,
    idp_uses_palette,
    prediction_odp,
    reliable_category,
    reliable_boundary_width=5,
    create_aux_files=False,
    create_polygon_files=False,
):
    makedirs_safely(prediction_odp)

    raster_tiling_results = RasterTilingResults.get_from_dir(idp)

    raster_name_to_tiling_info = {
        raster_tiling_result.raster_name: raster_tiling_result.tiling_info
        for raster_tiling_result in raster_tiling_results.raster_tiling_result_list
    }
    if create_aux_files or create_polygon_files:
        raster_name_to_transform = {
            raster_tiling_result.raster_name: (
                raster_tiling_result.raster_transform,
                raster_tiling_result.raster_crs,
            )
            for raster_tiling_result in raster_tiling_results.raster_tiling_result_list
        }
    else:
        raster_name_to_transform = None

    for index, label_tile in enumerate(raster_tiling_results.tiles):

        label_ifp = label_tile.get_absolute_tile_fp()
        if idp_uses_palette:
            label_or_image_mat, palette = read_label_tile_from_file(label_ifp)
        else:
            label_or_image_mat = read_image_tile_from_file(label_ifp)
            palette = None
        label_tile.set_disk_size(
            label_or_image_mat.shape[1], label_or_image_mat.shape[0]
        )
        center_x, center_y = label_tile.get_disk_center(as_int=True)

        tiling_info = raster_name_to_tiling_info[label_tile.get_raster_name()]
        disk_x_stride, disk_y_stride = label_tile.convert_source_to_disk(
            tiling_info.source_tile_stride_x_float.m,
            tiling_info.source_tile_stride_y_float.m,
        )

        # NB: The reliable area is defined by: stride / 2
        reliable_area_width_half = int(disk_x_stride / 2)
        reliable_area_height_half = int(disk_y_stride / 2)

        prediction_mat = copy.deepcopy(label_or_image_mat)
        reliable_area_mat = np.zeros(prediction_mat.shape[:2])

        # Set the reliable area to 1
        outer_area_y_min = center_y - reliable_area_height_half
        outer_area_y_max = center_y + reliable_area_height_half
        outer_area_x_min = center_x - reliable_area_width_half
        outer_area_x_max = center_x + reliable_area_width_half
        reliable_area_mat[
            outer_area_y_min:outer_area_y_max,
            outer_area_x_min:outer_area_x_max,
        ] = 1

        # Set inner part of the reliable area to 0, such that the reliable area
        # is defined by the remaining boundary pixels with value 1
        inner_area_y_min = outer_area_y_min + reliable_boundary_width
        inner_area_y_max = outer_area_y_max - reliable_boundary_width
        inner_area_x_min = outer_area_x_min + reliable_boundary_width
        inner_area_x_max = outer_area_x_max - reliable_boundary_width
        reliable_area_mat[
            inner_area_y_min:inner_area_y_max,
            inner_area_x_min:inner_area_x_max,
        ] = 0

        if idp_uses_palette:
            target_value = reliable_category.palette_index
        else:
            target_value = reliable_category.palette_color
        prediction_mat[reliable_area_mat == 1] = target_value

        prediction_tile = adjust_tile_fp(label_tile, prediction_odp)
        if create_aux_files or create_polygon_files:
            raster_transform, crs = raster_name_to_transform[
                prediction_tile.get_raster_name()
            ]
            prediction_tile.compute_and_set_tile_transform_from_raster_transform(
                raster_transform, crs
            )
            prediction_tile.set_crs(crs)
        if idp_uses_palette:
            write_label_tile_to_file(
                prediction_odp,
                prediction_tile,
                prediction_mat,
                palette.colors,
                create_aux_file=create_aux_files,
                create_polygon_file=create_polygon_files,
            )
        else:
            write_image_tile_to_file(
                prediction_odp,
                prediction_tile,
                prediction_mat,
                ext=".png",
                create_aux_file=create_aux_files,
                create_polygon_file=create_polygon_files,
            )
    copy_tiling_result_file(idp, prediction_odp)


def simulate_prediction_with_pattern(label_idp, prediction_odp):
    makedirs_safely(prediction_odp)
    tiles = list(TileManager.read_tiles_from_dir(idp=label_idp))

    x_pattern = itertools.cycle(["horizontal", "vertical"])
    y_pattern = itertools.cycle(["diagonal_1", "diagonal_2"])
    next_x_pattern = None
    next_y_pattern = None

    tiles_sorted = sorted(tiles, key=lambda tile: tile.get_source_offset())
    x_offset = None
    y_offset = None
    for index, label_tile in enumerate(tiles_sorted):
        # read_image_tile_from_file(tile)
        label_ifp = label_tile.get_absolute_tile_fp()
        label_mat, palette = read_label_tile_from_file(label_ifp)

        current_x_offset, current_y_offset = label_tile.get_source_offset()

        if x_offset != current_x_offset:
            x_offset = current_x_offset
            next_x_pattern = next(x_pattern)
        if y_offset != current_y_offset:
            y_offset = current_y_offset
            next_y_pattern = next(y_pattern)

        pattern_x_mat = create_repetitive_pattern_label_mat(
            label_mat.shape, label_mat.dtype, next_x_pattern
        )
        pattern_y_mat = create_repetitive_pattern_label_mat(
            label_mat.shape, label_mat.dtype, next_y_pattern
        )

        pattern_mat = np.logical_xor(pattern_x_mat, pattern_y_mat)

        prediction_mat = copy.deepcopy(label_mat)
        prediction_mat[pattern_mat == 1] = 0

        prediction_tile = adjust_tile_fp(label_tile, prediction_odp)
        write_label_tile_to_file(
            prediction_odp, prediction_tile, prediction_mat, palette.colors
        )

    copy_tiling_result_file(label_idp, prediction_odp)


def create_repetitive_pattern_label_mat(shape, dtype, pattern_str):
    assert pattern_str in [
        "horizontal",
        "vertical",
        "diagonal_1",
        "diagonal_2",
        None,
    ]
    pattern_size = 50
    rounding_offset = 0.25

    horizontal_data = np.zeros(shape, np.uint16)
    vertical_data = np.zeros(shape, np.uint16)

    sign = 1
    if pattern_str == "diagonal_2":
        sign = -1

    if pattern_str in ["horizontal", "diagonal_1", "diagonal_2"]:
        for i in range(horizontal_data.shape[0]):
            horizontal_data[sign * i, :] = i % pattern_size

    if pattern_str in ["vertical", "diagonal_1", "diagonal_2"]:
        for i in range(vertical_data.shape[1]):
            vertical_data[:, i] = i % pattern_size

    combined_modulo_data = np.mod(
        horizontal_data + vertical_data, pattern_size
    ).astype(dtype)

    combined_rounded_modulo_data = np.around(
        combined_modulo_data / pattern_size - rounding_offset
    )

    return combined_rounded_modulo_data


def main():
    ifp = "/path/to/geo_data/test/data/open_cities_dar_0a4c40/dar_0a4c40/dar_0a4c40.tif"
    ofp = ifp + "_repetitive_pattern.tif"
    pattern_str = "diagonal"  # "diagonal", "vertical", "horizontal"

    print("Read data ...")
    raster = Raster.get_from_file(ifp)
    data = raster.get_raster_data_as_numpy()

    print("Compute pattern ...")
    pattern_data = create_repetitive_pattern_label_mat(
        data.shape, data.dtype, pattern_str
    )

    print("Write data ...")
    write_raster(
        raster,
        ofp,
        overwrite_data=pattern_data,
        image_axis_order=True,
        build_overviews=True,
    )


if __name__ == "__main__":
    main()
