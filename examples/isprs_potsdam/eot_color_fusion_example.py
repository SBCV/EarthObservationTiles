import os
import shutil
from eot.tiles.tile_alignment import TileAlignment
from eot.tiles.tiling_scheme import LocalImageMeterSizeTilingScheme
from eot.aggregation.tile_aggregation import (
    aggregate_dataset_tile_predictions_per_raster,
)
from eot.categories.dataset_category import DatasetCategory
from eot.categories.dataset_categories import DatasetCategories
from eot.utility.log import Logs
from eot.tools.tools_api import run_tile_images
from eot.prediction_stub.prediction_simulation import (
    simulate_prediction_with_border,
)
from eot.fusion.tile_fusion import fuse_tiles
from eot.fusion.tile_comparison import compare_fusion_results_with_reference


def main():

    working_dp = "/path/to/examples_potsdam_dataset_mini"
    raster_data_idp = os.path.join(working_dp, "raster")
    image_tile_dp = os.path.join(working_dp, "image_tiles")
    predict_tile_dp = os.path.join(working_dp, "predicted_tiles")
    fused_tile_dp = os.path.join(working_dp, "fused_tiles")
    aggregation_odp = os.path.join(working_dp, "fused_tiles_aggregated")
    comparison_tile_odp = os.path.join(working_dp, "comparison_tiles")
    comparison_tiles_aggregated_odp = os.path.join(
        working_dp, "comparison_tiles_aggregated"
    )

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"

    grid_json_fn = "grid.json"

    # fmt:off
    segmentation_categories = DatasetCategories(
        [
            DatasetCategory(name="background",          palette_index=0,    palette_color=(255, 0, 0),      label_values=[(255, 0, 0)],     is_active=True),                                # noqa
            DatasetCategory(name="building",            palette_index=1,    palette_color=(0, 0, 255),      label_values=[(0, 0, 255)],     is_active=True),                                # noqa
            DatasetCategory(name="tree",                palette_index=2,    palette_color=(0, 255, 0),      label_values=[(0, 255, 0)],     is_active=True),                                # noqa
            DatasetCategory(name="impervious_surfaces", palette_index=3,    palette_color=(255, 255, 255),  label_values=[(255, 255, 255)], is_active=True),                                # noqa
            DatasetCategory(name="low_vegetation",      palette_index=4,    palette_color=(0, 255, 255),    label_values=[(0, 255, 255)],   is_active=True),                                # noqa
            DatasetCategory(name="car",                 palette_index=5,    palette_color=(255, 255, 0),    label_values=[(255, 255, 0)],   is_active=True),                                # noqa
            DatasetCategory(name="reliable_area",       palette_index=10,   palette_color=(255, 0, 255),    label_values=[(255, 0, 255)],   is_active=True),                                # noqa
            DatasetCategory(name="ignore",              palette_index=255,  palette_color=(0, 0, 0),        label_values=[(0, 0, 0)],       is_active=False,    is_ignore_category=True)    # noqa
        ]
    )
    # fmt:on
    comparison_category = DatasetCategory(
        name="fusion_difference",
        palette_index=11,
        palette_color=(255, 128, 255),
        label_values=None,
        is_active=True,
    )
    reliable_boundary_width = 1
    simulate_prediction = True

    output_tile_size_pixel = [512, 512]

    # NB: The overlap of the tiles is essential for the fusion process, i.e.
    #  the tile stride must be smaller than the tile size
    tiling_scheme = LocalImageMeterSizeTilingScheme()
    tiling_scheme.set_tile_size_in_meter([45, 45])
    # tiling_scheme.set_tile_stride_in_meter([45, 45])
    tiling_scheme.set_tile_stride_in_meter([22.5, 22.5])
    # tiling_scheme.set_tile_stride_in_meter([15, 15])
    # tiling_scheme.set_tile_stride_in_meter([11.25, 11.25])
    tiling_scheme.set_alignment(TileAlignment.centered_to_image.value)
    tiling_scheme.set_overhanging_tiles_flag(True)
    tiling_scheme.set_border_tiles_flag(True)

    # NB: This parameter controls if the tile fusion is performed or not. This
    #  allows to visualize the improvement of the tile fusion.
    perform_prediction_base_tile_fusion = True

    create_image_aux_files = False
    create_label_aux_files = False
    create_prediction_aux_files = False
    create_fusion_aux_files = False
    aggregate_as_json = False
    aggregate_as_images = True

    logger = Logs()

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=image_search_regex,
        tif_ignore_regex=image_ignore_regex,
        tile_odp=image_tile_dp,
        output_tile_size_pixel=output_tile_size_pixel,
        tiling_scheme=tiling_scheme,
        create_aux_files=create_image_aux_files,
    )

    # NB: This highlights a rectangle on the tiles denoting the reliable
    #  prediction area. After the tile aggregation, the aggregated parts
    #  of the resulting tiles become visible.
    reliable_category = segmentation_categories.get_category("reliable_area")
    if simulate_prediction:
        simulate_prediction_with_border(
            idp=image_tile_dp,
            idp_uses_palette=False,
            prediction_odp=predict_tile_dp,
            reliable_category=reliable_category,
            create_aux_files=create_prediction_aux_files,
            reliable_boundary_width=reliable_boundary_width,
        )
    else:
        shutil.copytree(image_tile_dp, predict_tile_dp)

    fuse_tiles(
        predict_tile_dp=predict_tile_dp,
        idp_uses_palette=False,
        fuse_tile_dp=fused_tile_dp,
        perform_prediction_base_tile_fusion=perform_prediction_base_tile_fusion,
        create_aux_files=create_fusion_aux_files,
        logger=logger,
    )
    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=aggregation_odp,
        test_data_dp=raster_data_idp,
        test_masks_dp=fused_tile_dp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
        test_data_normalized_dp=None,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        use_pixel_projection=True,
        categories=segmentation_categories.get_non_ignore_categories(),
        grid_json_fn=grid_json_fn,
        lazy=False,
    )

    compare_fusion_results_with_reference(
        original_tile_idp=image_tile_dp,
        fused_tile_idp=fused_tile_dp,
        idp_uses_palette=False,
        comparison_tile_odp=comparison_tile_odp,
        rgb_comparison_category=comparison_category,
        segmentation_categories=None,
    )

    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=comparison_tiles_aggregated_odp,
        test_data_dp=raster_data_idp,
        test_masks_dp=comparison_tile_odp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
        test_data_normalized_dp=None,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        # Only pixel projection allows aggregating color information
        use_pixel_projection=True,
        categories=DatasetCategories([comparison_category]),
        grid_json_fn=grid_json_fn,
        lazy=False,
    )


if __name__ == "__main__":
    main()
