import os

from eot.aggregation.aggregation_path_manager import AggregationPathManager
from eot.tools.tools_api import run_aggregate
from eot.utility.os_ext import get_regex_fps_in_dp
from eot.utility.os_ext import mkdir_safely


def aggregate_dataset_tile_predictions_per_raster(
    aggregation_odp,
    test_data_dp,
    test_masks_dp,
    search_regex,
    ignore_regex,
    mercator_tiling_flag,
    test_data_normalized_dp,
    aggregate_save_normalized_raster,
    aggregate_as_json,
    aggregate_as_images,
    use_pixel_projection,
    categories,
    grid_json_fn,
    lazy,
):
    # Create for each raster image a json file reflecting the information
    # of the corresponding image-tiles
    original_ifps = get_regex_fps_in_dp(
        test_data_dp, search_regex, ignore_regex
    )
    normalized_fps = _get_normalized_fps(
        original_ifps, test_data_normalized_dp, mercator_tiling_flag
    )

    for original_ifp, normalized_fp in zip(original_ifps, normalized_fps):
        _create_normalization_odp(
            aggregate_save_normalized_raster,
            test_data_normalized_dp,
            normalized_fp,
        )

        aggregation_dn = os.path.splitext(os.path.basename(original_ifp))[0]
        apm = AggregationPathManager(aggregation_odp, aggregation_dn)

        if mercator_tiling_flag:
            masks_raster_name = None
        else:
            masks_raster_name = apm.aggregation_dn

        if aggregate_as_images:
            run_aggregate(
                masks_idp=test_masks_dp,
                categories=categories,
                masks_raster_name=masks_raster_name,
                geojson_grid_ofn=grid_json_fn,
                mask_gray_png_ofp=apm.mask_png_fp,
                mask_color_png_ofp=apm.mask_color_png_fp,
                mask_overlay_png_ofp=apm.mask_overlay_png_fp,
                overlay_grid_png_ofp=apm.grid_overlay_png_fp,
                use_pixel_projection=use_pixel_projection,
                original_raster_ifp=original_ifp,
                normalized_raster_fp=normalized_fp,
                save_normalized_raster=aggregate_save_normalized_raster,
                lazy=lazy,
            )
        if aggregate_as_json:
            run_aggregate(
                masks_idp=test_masks_dp,
                categories=categories,
                masks_raster_name=masks_raster_name,
                geojson_odp=apm.test_aggregated_masks_json_dp,
                geojson_grid_ofn=grid_json_fn,
                original_raster_ifp=original_ifp,
                lazy=lazy,
            )


def _create_normalization_odp(
    aggregate_save_normalized_raster, normalized_fp, test_data_normalized_dp
):
    if aggregate_save_normalized_raster and normalized_fp is not None:
        mkdir_safely(test_data_normalized_dp)
        mkdir_safely(os.path.dirname(normalized_fp))


def _get_normalized_fps(
    original_ifps, test_data_normalized_dp, mercator_tiling_flag
):
    # Normalized paths are only required for mercator tiles
    if mercator_tiling_flag:
        assert test_data_normalized_dp is not None
        normalized_fps = []
        for original_ifp in original_ifps:
            normalized_fp = os.path.join(
                test_data_normalized_dp,
                os.path.basename(os.path.dirname(original_ifp)),
                os.path.basename(original_ifp),
            )
            normalized_fps.append(normalized_fp)
    else:
        normalized_fps = [None] * len(original_ifps)
    return normalized_fps
