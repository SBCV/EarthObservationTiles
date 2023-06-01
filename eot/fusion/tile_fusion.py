import math
from rtree import index as rtree_index
import copy
import os
import shutil

from eot.tiles.tile_manager import TileManager
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles.tile_reading import (
    read_image_tile_from_file,
    read_label_tile_from_file,
)
from eot.tiles.tile_writing import (
    write_image_tile_to_file,
    write_label_tile_to_file,
)
from eot.tiles.tiling_result import RasterTilingResults
from eot.utility.os_ext import makedirs_safely
from eot.fusion.tiling_analysis import get_aux_and_base_results
from eot.fusion.tile_fusion_debug import (
    debug_visualize_tile_merging,
)
from eot.fusion.pixel_substitution import (
    substitute_pixels,
)


def copy_tiling_result_file(idp, odp):
    idp_json_fp = TilePathManager.get_tiling_json_fp_from_dir(idp)
    odp_json_fp = TilePathManager.get_tiling_json_fp_from_dir(odp)
    shutil.copyfile(idp_json_fp, odp_json_fp)


def _compute_reliable_prediction_area(
    tile,
    disk_width,
    disk_height,
    source_x_stride,
    source_y_stride,
):
    # NB: it is essential to use the auxiliary tiles, since the base tiles
    #  are not suitable to determine the correct stride values
    tile.set_disk_size(disk_width, disk_height)
    disk_x_stride, disk_y_stride = tile.convert_source_to_disk(
        source_x_stride, source_y_stride
    )
    # Use ceil here to ensure that there are no pixel omitted during the
    #  substitution process. Rationale: pixels that are not substituted at the
    #  outer image areas might have a (strong) negative impact on the result.
    reliable_offset_x = math.ceil(disk_x_stride / 2)
    reliable_offset_y = math.ceil(disk_y_stride / 2)
    return reliable_offset_x, reliable_offset_y


def fuse_tile_predictions(
    raster_name_to_results_base,
    raster_name_to_results_aux,
    raster_tiling_results,
    logger,
    debug=False,
):
    predictions_base = []
    batch_indices_base = []
    tiles_base = []
    logger.info("Fuse predictions ...")
    for raster_name in raster_name_to_results_base.keys():
        (
            current_predictions_base,
            current_batch_indices_base,
            current_tiles_base,
        ) = raster_name_to_results_base[raster_name]
        (
            current_predictions_aux,
            _,
            current_tiles_aux,
        ) = raster_name_to_results_aux[raster_name]

        logger.info(f"Fuse predictions for {raster_name}")
        # Override base predictions with fused predictions
        raster_tiling_result = raster_tiling_results.get_raster_tiling_result(
            raster_name
        )
        tiling_info = raster_tiling_result.tiling_info
        source_x_stride = tiling_info.source_tile_stride_x_float.magnitude
        source_y_stride = tiling_info.source_tile_stride_y_float.magnitude
        current_predictions_base = fuse_tile_predictions_of_raster(
            current_predictions_base,
            current_tiles_base,
            current_predictions_aux,
            current_tiles_aux,
            source_x_stride,
            source_y_stride,
            debug_compare_with_reference=debug,
            debug_show_visualization=debug,
        )
        predictions_base.extend(current_predictions_base)
        batch_indices_base.extend(current_batch_indices_base)
        tiles_base.extend(current_tiles_base)
    return predictions_base, batch_indices_base, tiles_base


def fuse_tile_predictions_of_raster(
    predictions_base,
    tiles_base,
    predictions_aux,
    tiles_aux,
    source_x_stride,
    source_y_stride,
    debug_compare_with_reference=False,
    debug_show_visualization=False,
):
    for prediction, tile in zip(predictions_base, tiles_base):
        tile.label_data = prediction
    for prediction, tile in zip(predictions_aux, tiles_aux):
        tile.label_data = prediction

    reference_prediction = predictions_base[0]
    disk_height, disk_width = reference_prediction.shape[:2]
    (
        reliable_offset_x_int,
        reliable_offset_y_int,
    ) = _compute_reliable_prediction_area(
        tiles_base[0],
        disk_width,
        disk_height,
        source_x_stride,
        source_y_stride,
    )

    # https://rtree.readthedocs.io/en/latest/tutorial.html
    tile_aux_rtree = rtree_index.Index(interleaved=True)
    for index, tile_aux in enumerate(tiles_aux):
        tile_aux_rtree.insert(index, tile_aux.get_source_rectangle())

    fused_predictions = []
    # Complexity: O(nu_x nu_y)
    for tile_base in tiles_base:
        # Disk width and height is required for merging
        tile_base.set_disk_size(disk_width, disk_height)

        tiles_overlapping_aux_indices = tile_aux_rtree.intersection(
            tile_base.get_source_rectangle()
        )
        tiles_overlapping_aux = [
            tiles_aux[tiles_overlapping_aux_index]
            for tiles_overlapping_aux_index in tiles_overlapping_aux_indices
        ]

        if debug_compare_with_reference:
            tiles_overlapping_aux_ref = tile_base.get_overlapping_tiles(
                tiles_aux
            )
            assert len(tiles_overlapping_aux) == len(tiles_overlapping_aux_ref)
            for tile_overlapping, tile_overlapping_ref in zip(
                sorted(tiles_overlapping_aux),
                sorted(tiles_overlapping_aux_ref),
            ):
                assert tile_overlapping == tile_overlapping_ref

        fused_prediction = substitute_pixels(
            tile_base,
            tiles_overlapping_aux,
            reliable_offset_x_int,
            reliable_offset_y_int,
            data_call_back=lambda x: x.label_data,
        )
        fused_predictions.append(fused_prediction)

        if debug_show_visualization:
            debug_visualize_tile_merging(
                tile_base,
                tiles_overlapping_aux,
                reliable_offset_x_int,
                reliable_offset_y_int,
                source_x_stride,
                source_y_stride,
                fuse_areas=False,
            )

    return fused_predictions


def fuse_tiles(
    predict_tile_dp,
    idp_uses_palette,
    fuse_tile_dp,
    perform_prediction_base_tile_fusion,
    logger,
    consistent_for_varying_tile_strides=True,
    create_aux_files=False,
    debug=False,
):
    predict_spatial_info_json_fp = TilePathManager.get_tiling_json_fp_from_dir(
        predict_tile_dp
    )
    raster_tiling_results = RasterTilingResults.from_json_file(
        predict_spatial_info_json_fp
    )

    if consistent_for_varying_tile_strides:
        # NB: Optimal tiles are currently not supported for the consistent,
        #   since the tile offset would vary for different strides.
        ris_optimal_aligned = (
            raster_tiling_results.tiling_scheme.is_optimal_aligned()
        )
        msg = "Optimized alignment not supported for fusion of base tiles"
        assert not ris_optimal_aligned, msg

        uses_overhanging_tiles = (
            raster_tiling_results.tiling_scheme.uses_overhanging_tiles()
        )
        # NB: Disabling overhanging tiles would lead to a preference / handicap
        #  of specific stride values. By limiting the tiling to the image area
        #  it depends on the tile stride if there is a tile covering the
        #  boundary of the image. Using overlapping tiles ensures each tiling
        #  configuration is able to leverage the full image information.
        mgs = "Overhanging tiles are required to perform a fair comparison of different stride values"
        assert uses_overhanging_tiles, mgs

    if create_aux_files:
        raster_name_to_transform = {
            raster_tiling_result.raster_name: (
                raster_tiling_result.raster_transform,
                raster_tiling_result.raster_crs,
            )
            for raster_tiling_result in raster_tiling_results.raster_tiling_result_list
        }
    else:
        raster_name_to_transform = None

    makedirs_safely(fuse_tile_dp)
    predicted_tiles = list(
        TileManager.read_tiles_from_dir(idp=predict_tile_dp)
    )

    predictions = []
    batch_indices = []
    tiles = []
    for batch_index, predicted_tile in enumerate(predicted_tiles):
        prediction_ifp = predicted_tile.get_absolute_tile_fp()
        if idp_uses_palette:
            prediction_mat, palette = read_label_tile_from_file(prediction_ifp)
        else:
            prediction_mat = read_image_tile_from_file(prediction_ifp)
            palette = None

        predictions.append(prediction_mat)
        batch_indices.append(batch_index)
        tiles.append(predicted_tile)

    (
        raster_name_to_results_base,
        raster_name_to_results_aux,
    ) = get_aux_and_base_results(
        predictions,
        batch_indices,
        tiles,
        raster_tiling_results,
        logger=logger,
    )

    if perform_prediction_base_tile_fusion:
        predictions, batch_indices, tiles = fuse_tile_predictions(
            raster_name_to_results_base,
            raster_name_to_results_aux,
            raster_tiling_results,
            logger=logger,
            debug=debug,
        )
    else:
        predictions, batch_indices, tiles = _extract_base_results(
            raster_name_to_results_base
        )

    for prediction, image_tile in zip(predictions, tiles):

        prediction_tile = copy.deepcopy(image_tile)
        fuse_ofp = os.path.join(
            fuse_tile_dp, prediction_tile.get_relative_tile_fp()
        )
        prediction_tile.set_tile_fp(
            fuse_ofp, is_absolute=True, root_dp=fuse_tile_dp
        )
        if create_aux_files:
            raster_transform, crs = raster_name_to_transform[
                prediction_tile.get_raster_name()
            ]
            prediction_tile.compute_and_set_tile_transform_from_raster_transform(
                raster_transform, crs
            )
            prediction_tile.set_crs(crs)
        if idp_uses_palette:
            write_label_tile_to_file(
                odp=fuse_tile_dp,
                geo_tile=prediction_tile,
                label_data=prediction,
                palette_colors=palette.colors,
                create_aux_file=create_aux_files,
            )
        else:
            write_image_tile_to_file(
                odp=fuse_tile_dp,
                geo_tile=prediction_tile,
                image_data=prediction,
                ext=".png",
                create_aux_file=create_aux_files,
            )
    copy_tiling_result_file(predict_tile_dp, fuse_tile_dp)


def _extract_base_results(raster_name_to_results_base):
    predictions = []
    batch_indices = []
    tiles = []
    for raster_name in raster_name_to_results_base.keys():
        (
            current_predictions_base,
            current_batch_indices_base,
            current_tiles_base,
        ) = raster_name_to_results_base[raster_name]
        predictions.extend(current_predictions_base)
        batch_indices.extend(current_batch_indices_base)
        tiles.extend(current_tiles_base)
    return predictions, batch_indices, tiles
