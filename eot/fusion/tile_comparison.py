import os
import numpy as np
from eot.fusion.tile_fusion import copy_tiling_result_file
from eot.tiles.tile_reading import (
    read_image_tile_from_file,
    read_label_tile_from_file,
)
from eot.tiles.tile_writing import (
    write_image_tile_to_file,
    write_label_tile_to_file,
)
from eot.utility.os_ext import makedirs_safely
from eot.tiles.tiling_result import RasterTilingResults
from eot.prediction_stub.prediction_simulation import adjust_tile_fp
from eot.comparison.segmentation_comparison import SegmentationComparison


def compute_rgb_difference_mat(original_mat, fused_mat, difference_category):
    assert len(fused_mat.shape) == 3
    # NB: the axis parameter defines along which axis a logical OR
    #  reduction is performed.
    difference_mat = np.zeros_like(fused_mat)
    difference_mask_3d = fused_mat != original_mat
    difference_mask_2d = np.any(difference_mask_3d, axis=-1)
    difference_mat[difference_mask_2d] = difference_category.palette_color
    return difference_mat


def compare_fusion_results_with_reference(
    original_tile_idp,
    fused_tile_idp,
    idp_uses_palette,
    comparison_tile_odp,
    label_comparison_categories=None,
    rgb_comparison_category=None,
    segmentation_categories=None,
    create_aux_file=False,
    create_polygon_file=False,
):
    assert bool(label_comparison_categories) != bool(rgb_comparison_category)
    makedirs_safely(comparison_tile_odp)

    raster_tiling_results_original = RasterTilingResults.get_from_dir(
        original_tile_idp
    )
    raster_tiling_results_fused = RasterTilingResults.get_from_dir(
        fused_tile_idp
    )
    original_tiles = list(raster_tiling_results_original.tiles)
    fused_tiles = list(raster_tiling_results_fused.tiles)
    num_original_tiles = len(original_tiles)
    num_fused_tiles = len(fused_tiles)
    mgs = f"{num_original_tiles} vs. {num_fused_tiles}"
    assert num_original_tiles >= num_fused_tiles, mgs

    fn_to_original_tile = {
        str(original_tile): original_tile for original_tile in original_tiles
    }

    if idp_uses_palette:
        active_category_names = segmentation_categories.get_category_names(
            only_active=True, include_ignore=False
        )
    else:
        active_category_names = None

    for index, fused_tile in enumerate(fused_tiles):
        original_tile = fn_to_original_tile[str(fused_tile)]

        fused_ifp = fused_tile.get_absolute_tile_fp()
        original_ifp = original_tile.get_absolute_tile_fp()

        if idp_uses_palette:
            fused_mat, fused_palette = read_label_tile_from_file(fused_ifp)
            original_mat, original_palette = read_label_tile_from_file(
                original_ifp
            )
            assert fused_palette.colors == original_palette.colors
            palette = fused_palette
        else:
            fused_mat = read_image_tile_from_file(fused_ifp)
            original_mat = read_image_tile_from_file(original_ifp)
            palette = None

        fused_tile.set_disk_size(fused_mat.shape[1], fused_mat.shape[0])

        if idp_uses_palette:
            assert label_comparison_categories.get_num_categories() > 2
            segmentation_comparison = SegmentationComparison(
                original_mat,
                fused_mat,
                segmentation_categories,
                label_comparison_categories,
            )
            for category_name in active_category_names:
                (
                    category_comparison
                ) = segmentation_comparison.get_category_comparison(
                    category_name
                )
                category_comparison_tile_odp = os.path.join(
                    comparison_tile_odp, category_name
                )
                category_comparison_tile = adjust_tile_fp(
                    fused_tile, category_comparison_tile_odp
                )
                write_label_tile_to_file(
                    category_comparison_tile_odp,
                    category_comparison_tile,
                    category_comparison.comparison_mat,
                    category_comparison.palette_colors,
                    create_aux_file=create_aux_file,
                    create_polygon_file=create_polygon_file,
                )
        else:
            difference_mat = compute_rgb_difference_mat(
                original_mat, fused_mat, rgb_comparison_category
            )
            comparison_tile = adjust_tile_fp(fused_tile, comparison_tile_odp)
            write_image_tile_to_file(
                comparison_tile_odp,
                comparison_tile,
                difference_mat,
                ext=".png",
                create_aux_file=create_aux_file,
                create_polygon_file=create_polygon_file,
            )

    if idp_uses_palette:
        for category_name in active_category_names:
            category_comparison_tile_odp = os.path.join(
                comparison_tile_odp, category_name
            )
            copy_tiling_result_file(
                original_tile_idp, category_comparison_tile_odp
            )
    else:
        copy_tiling_result_file(original_tile_idp, comparison_tile_odp)
