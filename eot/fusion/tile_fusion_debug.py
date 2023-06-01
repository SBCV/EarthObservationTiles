import copy
import numpy as np
import skimage
import cv2
import matplotlib
import matplotlib.pyplot as plt
import imageio
from eot.utility.log import Logs
from eot.fusion.pixel_substitution import substitute_pixels


def _visualize_merged_images(
    fig, gridspec, tile, tile_merged_orginal, tile_merged_modified, vmin, vmax
):
    # RGB image corresponding to tile
    ax = fig.add_subplot(gridspec[0, 0])
    ax.title.set_text(f"Reference Color Tile\n{tile.get_source_offset()}")
    image_fp = tile.get_absolute_tile_fp()
    ax.imshow(imageio.imread(image_fp))

    # Merged RGB image corresponding to tile
    ax = fig.add_subplot(gridspec[0, 1])
    ax.title.set_text(
        f"Merged Color Tile\n{tile_merged_modified.get_source_offset()}"
    )
    ax.imshow(tile_merged_modified.color_data)

    # Merged RGB image corresponding to tile
    ax = fig.add_subplot(gridspec[0, 2])
    ax.title.set_text(
        f"Difference Color Tile\n{tile_merged_orginal.get_source_offset()}"
    )
    diff_data = np.abs(tile_merged_orginal.color_data - tile.color_data)
    ax.imshow(diff_data)

    # Prediction corresponding to tile
    ax = fig.add_subplot(gridspec[1, 0])
    ax.title.set_text(f"Reference Prediction Tile\n{tile.get_source_offset()}")
    ax.imshow(tile.label_data)

    # Merged predictions corresponding to tile
    ax = fig.add_subplot(gridspec[1, 1])
    ax.title.set_text(
        f"Merged Prediction Tile\n{tile_merged_modified.get_source_offset()}"
    )
    ax.imshow(tile_merged_modified.label_data, vmin=vmin, vmax=vmax)

    # Merged label image corresponding to tile
    ax = fig.add_subplot(gridspec[1, 2])
    ax.title.set_text(
        f"Difference Label Tile\n{tile_merged_orginal.get_source_offset()}"
    )
    diff_data = np.abs(tile_merged_orginal.label_data - tile.label_data)
    ax.imshow(diff_data)


def _get_horizontal_vertical_neighbor_image(
    tile_merged,
    overlapping_tiles,
    source_x_stride,
    source_y_stride,
    data_call_back,
):
    orthogonal_neighbors = []
    for overlapping_tile in overlapping_tiles:
        x_offset_c, y_offset_c = tile_merged.get_source_offset()
        x_offset_n, y_offset_n = overlapping_tile.get_source_offset()
        if x_offset_c == x_offset_n or y_offset_c == y_offset_n:
            orthogonal_neighbors.append(overlapping_tile)

    source_width, source_height = tile_merged.get_source_size()
    x_offsets = [
        overlapping_tile.get_source_x_offset()
        for overlapping_tile in overlapping_tiles
    ]
    y_offsets = [
        overlapping_tile.get_source_y_offset()
        for overlapping_tile in overlapping_tiles
    ]
    x_offset_ref = min(x_offsets)
    y_offset_ref = min(y_offsets)
    max_x_offset_relative = max(x_offsets) - x_offset_ref
    max_y_offset_relative = max(y_offsets) - y_offset_ref
    x_display_scaling = int(source_width / source_x_stride)
    y_display_scaling = int(source_height / source_y_stride)
    x_extend = int(
        1.1 * x_display_scaling * max_x_offset_relative + source_width
    )
    y_extend = int(
        1.1 * y_display_scaling * max_y_offset_relative + source_height
    )

    tile_merged_data = data_call_back(tile_merged)
    combined_shape = (y_extend, x_extend)
    if len(tile_merged_data.shape) == 3:
        combined_shape = combined_shape + (3,)
    combined_result = np.zeros(shape=combined_shape)
    for tile in orthogonal_neighbors:
        x_offset_relative = int(
            1.1 * (tile.get_source_x_offset() - x_offset_ref)
        )
        y_offset_relative = int(
            1.1 * (tile.get_source_y_offset() - y_offset_ref)
        )

        combined_lower_y = y_display_scaling * y_offset_relative
        combined_upper_y = (
            y_display_scaling * y_offset_relative + source_height
        )
        combined_lower_x = x_display_scaling * x_offset_relative
        combined_upper_x = x_display_scaling * x_offset_relative + source_width

        tile_data = data_call_back(tile)
        tile_data_shape_2d = (source_height, source_width)

        if len(tile_data.shape) == 2:
            # Worked only for label data
            tile_data = tile_data.astype("uint8")
            tile_data_resized = cv2.resize(tile_data, tile_data_shape_2d)
        elif len(tile_data.shape) == 3:
            # # Worked only for color data
            tile_data_resized = skimage.transform.resize(
                tile_data, tile_data_shape_2d
            )
        else:
            assert False
        combined_result[
            combined_lower_y:combined_upper_y,
            combined_lower_x:combined_upper_x,
        ] = tile_data_resized
    return combined_result


def _visualize_neighbor_images(
    fig,
    gridspec,
    tile_merged,
    overlapping_tiles,
    source_x_stride,
    source_y_stride,
    vmin,
    vmax,
):
    color_neighbor_image = _get_horizontal_vertical_neighbor_image(
        tile_merged,
        overlapping_tiles,
        source_x_stride,
        source_y_stride,
        data_call_back=lambda x: x.color_data,
    )
    ax = fig.add_subplot(gridspec[0, 0])
    ax.imshow(color_neighbor_image)

    label_neighbor_image = _get_horizontal_vertical_neighbor_image(
        tile_merged,
        overlapping_tiles,
        source_x_stride,
        source_y_stride,
        data_call_back=lambda x: x.label_data,
    )
    ax = fig.add_subplot(gridspec[1, 0])
    ax.imshow(label_neighbor_image, vmin=vmin, vmax=vmax)


def visualize_tile_merging(
    tile,
    tile_merged_orginal,
    tile_merged_modified,
    overlapping_tiles,
    source_x_stride,
    source_y_stride,
    fig_size=(20, 12),
    visualize_tile_neighbors=False,
):
    fig = plt.figure()
    fig.set_size_inches(*fig_size)
    vmin = 0
    vmax = len(overlapping_tiles)

    if visualize_tile_neighbors:
        num_columns = 2
    else:
        num_columns = 1

    gs_root = matplotlib.gridspec.GridSpec(1, num_columns, figure=fig)
    gs_upper = gs_root[0].subgridspec(2, 3)
    # Note: Because of the resizing of the tile content (different source and
    #  disk extents) it is possible that the original raster image data has
    #  been interpolated! Thus, the difference image of the reference color
    #  image and the merged color image might be not 0.
    _visualize_merged_images(
        fig,
        gs_upper,
        tile,
        tile_merged_orginal,
        tile_merged_modified,
        vmin,
        vmax,
    )

    if visualize_tile_neighbors:
        # Warning: This is quite slow! - but helpful ;)
        gs_lower = gs_root[1].subgridspec(2, 1)
        _visualize_neighbor_images(
            fig,
            gs_lower,
            tile_merged_modified,
            overlapping_tiles,
            source_x_stride,
            source_y_stride,
            vmin,
            vmax,
        )
    plt.show()


def _set_array_to_index(
    tile_data, index, reliable_offset_x, reliable_offset_y
):
    height, width = tile_data.shape[0:2]
    center_y = int(height / 2)
    center_x = int(width / 2)
    tile_data[:] = index
    lower_y = center_y - reliable_offset_y
    upper_y = center_y + reliable_offset_y
    lower_x = center_x - reliable_offset_x
    upper_x = center_x + reliable_offset_x
    tile_data[lower_y:upper_y, lower_x:upper_x] = 10 + index


def _mod_tile_for_visualization(
    tile, index, reliable_offset_x, reliable_offset_y, merge_areas
):
    if merge_areas:
        _set_array_to_index(
            tile.label_data,
            index,
            reliable_offset_x,
            reliable_offset_y,
        )
        _set_array_to_index(
            tile.color_data,
            index,
            reliable_offset_x,
            reliable_offset_y,
        )
    else:
        tile.label_data[tile.label_data > 0] = 10 + index
    return tile


def debug_visualize_tile_merging(
    tile_base,
    tiles_overlapping_aux,
    reliable_offset_x,
    reliable_offset_y,
    source_x_stride,
    source_y_stride,
    fuse_areas=False,
):
    num_overlapping_tiles_aux = len(tiles_overlapping_aux)
    Logs.svinfo("tile_base", tile_base)
    Logs.svinfo("image_tile_aux", tile_base.get_source_offset())
    Logs.svinfo("num_overlapping_tiles_aux", num_overlapping_tiles_aux)
    for image_tile_aux in tiles_overlapping_aux:
        Logs.svinfo("image_tile_aux", image_tile_aux.get_source_offset())
    Logs.sinfo("-----------------------------------------------------")

    tile_base.color_data = imageio.imread(tile_base.get_absolute_tile_fp())
    for image_tile_aux in tiles_overlapping_aux:
        image_tile_aux.color_data = imageio.imread(
            image_tile_aux.get_absolute_tile_fp()
        )

    tiles_overlapping_aux_mod = []
    for index, tile_overlapping in enumerate(tiles_overlapping_aux):
        tile_overlapping_mod = copy.deepcopy(tile_overlapping)
        tile_overlapping_mod = _mod_tile_for_visualization(
            tile_overlapping_mod,
            index,
            reliable_offset_x,
            reliable_offset_y,
            fuse_areas,
        )
        tiles_overlapping_aux_mod.append(tile_overlapping_mod)

    tile_merged_original = copy.deepcopy(tile_base)
    tile_merged_original.color_data = substitute_pixels(
        tile_base,
        tiles_overlapping_aux,
        reliable_offset_x,
        reliable_offset_y,
        data_call_back=lambda x: x.color_data,
    )
    tile_merged_original.label_data = substitute_pixels(
        tile_base,
        tiles_overlapping_aux,
        reliable_offset_x,
        reliable_offset_y,
        data_call_back=lambda x: x.label_data,
    )

    tile_merged_modified = copy.deepcopy(tile_base)
    tile_merged_modified.color_data = substitute_pixels(
        tile_base,
        tiles_overlapping_aux_mod,
        reliable_offset_x,
        reliable_offset_y,
        data_call_back=lambda x: x.color_data,
    )
    tile_merged_modified.label_data = substitute_pixels(
        tile_base,
        tiles_overlapping_aux_mod,
        reliable_offset_x,
        reliable_offset_y,
        data_call_back=lambda x: x.label_data,
    )
    visualize_tile_merging(
        tile=tile_base,
        tile_merged_orginal=tile_merged_original,
        tile_merged_modified=tile_merged_modified,
        overlapping_tiles=tiles_overlapping_aux_mod,
        source_x_stride=source_x_stride,
        source_y_stride=source_y_stride,
        visualize_tile_neighbors=False,
    )
