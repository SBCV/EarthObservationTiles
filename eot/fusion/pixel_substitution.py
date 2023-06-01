import copy
import math


def substitute_pixels(
    tile_base,
    tiles_overlapping_aux,
    reliable_area_offset_x,
    reliable_area_offset_y,
    data_call_back,
):
    ###########################################################################
    # NB:
    #  - ALL following variables are INTEGER values and refer to pixels
    #    relative to the DISK extent
    #  - The position of the base and aux tiles are defined in source
    #    coordinates (e.g. source_x_offset). Because of quantization effects
    #    of the stride value it is not necessarily the case that subsequent
    #    tiles show the exact same relative offset. Example: a stride of
    #    s_x = 100.5 leads to offsets [0, 100, 201, 301, 402, ...].
    #    To obtain robustness w.r.t. quantization effects, it is important to
    #    use the absolute offsets instead of the stride values to determine the
    #    relative offset of adjacent (overlapping) tiles. Therefore, the
    #    following tile fusion implementation is independent of the
    #    quantization of the (float) stride values used in the tiling code.
    ###########################################################################

    convert_offset_to_int = math.floor

    # The following values (height, center_y, ...) are defined relative to the
    #  data on disk (and NOT w.r.t. the source data).
    tile_base_data = data_call_back(tile_base)
    height, width = tile_base_data.shape[0:2]
    merged_result = copy.deepcopy(tile_base_data)

    # The selection of the center (is more or less arbitrary), i.e. it does
    #  not matter if we floor or ceil.
    center_y = convert_offset_to_int(height / 2)
    center_x = convert_offset_to_int(width / 2)

    for tile_overlapping in tiles_overlapping_aux:
        (
            relative_offset_x,
            relative_offset_y,
        ) = tile_base.compute_relative_disk_offset(tile_overlapping)

        relative_center_y = center_y + relative_offset_y
        relative_center_x = center_x + relative_offset_x

        merged_lower_y = relative_center_y - reliable_area_offset_y
        merged_upper_y = relative_center_y + reliable_area_offset_y
        merged_lower_x = relative_center_x - reliable_area_offset_x
        merged_upper_x = relative_center_x + reliable_area_offset_x

        merged_lower_y_adjusted = max(0, merged_lower_y)
        merged_upper_y_adjusted = min(height, merged_upper_y)
        merged_lower_x_adjusted = max(0, merged_lower_x)
        merged_upper_x_adjusted = min(width, merged_upper_x)

        reliable_area_offset_y_lower_adjusted = (
            relative_center_y - merged_lower_y_adjusted
        )
        reliable_area_offset_y_upper_adjusted = (
            merged_upper_y_adjusted - relative_center_y
        )
        reliable_area_offset_x_lower_adjusted = (
            relative_center_x - merged_lower_x_adjusted
        )
        reliable_area_offset_x_upper_adjusted = (
            merged_upper_x_adjusted - relative_center_x
        )

        overlap_lower_y = center_y - reliable_area_offset_y_lower_adjusted
        overlap_upper_y = center_y + reliable_area_offset_y_upper_adjusted
        overlap_lower_x = center_x - reliable_area_offset_x_lower_adjusted
        overlap_upper_x = center_x + reliable_area_offset_x_upper_adjusted

        if overlap_lower_y > overlap_upper_y:
            continue
        if overlap_lower_x > overlap_upper_x:
            continue

        tile_overlapping_data = data_call_back(tile_overlapping)
        reliable_overlapping_result = tile_overlapping_data[
            overlap_lower_y:overlap_upper_y,
            overlap_lower_x:overlap_upper_x,
        ]
        merged_result[
            merged_lower_y_adjusted:merged_upper_y_adjusted,
            merged_lower_x_adjusted:merged_upper_x_adjusted,
        ] = reliable_overlapping_result

    return merged_result
