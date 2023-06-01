import os
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
from eot.comparison.category_comparison import CategoryComparison


def main():

    working_dp = "/path/to/examples_potsdam_dataset_mini"
    raster_data_idp = os.path.join(working_dp, "raster")
    label_tile_dp = os.path.join(working_dp, "label_tiles")
    predict_tile_dp = os.path.join(working_dp, "predicted_tiles")
    fused_tile_dp = os.path.join(working_dp, "fused_tiles")
    fused_tiles_aggregated_odp = os.path.join(
        working_dp, "fused_tiles_aggregated"
    )
    comparison_tile_odp = os.path.join(working_dp, "comparison_tiles")
    comparison_tiles_aggregated_odp = os.path.join(
        working_dp, "comparison_tiles_aggregated"
    )

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"
    label_search_regex = "**-labels*/*.tif"
    label_ignore_regex = ""

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
    comparison_categories = DatasetCategories(
        [
            DatasetCategory(name="zero_values",     palette_index=0,    palette_color=(0, 0, 0)),
            DatasetCategory(name=CategoryComparison.true_positive_name,   palette_index=1,    palette_color=(0, 0, 127)),
            DatasetCategory(name=CategoryComparison.false_positive_name,  palette_index=2,    palette_color=(0, 127, 0)),
            DatasetCategory(name=CategoryComparison.true_negative_name,   palette_index=3,    palette_color=(127, 0, 0)),
            DatasetCategory(name=CategoryComparison.false_negative_name,  palette_index=4,    palette_color=(127, 127, 127)),
        ]
    )
    # fmt:on

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
    aggregate_as_json = True
    aggregate_as_images = True
    aggregate_as_images_using_pixel_projection = False

    logger = Logs()

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=label_search_regex,
        tif_ignore_regex=label_ignore_regex,
        tile_odp=label_tile_dp,
        output_tile_size_pixel=output_tile_size_pixel,
        tiling_scheme=tiling_scheme,
        write_labels=True,
        convert_images_to_labels=True,
        categories=segmentation_categories,
        create_aux_files=create_label_aux_files,
    )

    # NB: This highlights a rectangle on the tiles denoting the reliable
    #  prediction area. After the tile aggregation, the aggregated parts
    #  of the resulting tiles become visible.
    reliable_category = segmentation_categories.get_category("reliable_area")
    simulate_prediction_with_border(
        idp=label_tile_dp,
        idp_uses_palette=True,
        prediction_odp=predict_tile_dp,
        reliable_category=reliable_category,
        create_aux_files=create_prediction_aux_files,
    )

    fuse_tiles(
        predict_tile_dp=predict_tile_dp,
        idp_uses_palette=True,
        fuse_tile_dp=fused_tile_dp,
        perform_prediction_base_tile_fusion=perform_prediction_base_tile_fusion,
        create_aux_files=create_fusion_aux_files,
        logger=logger,
    )

    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=fused_tiles_aggregated_odp,
        test_data_dp=raster_data_idp,
        test_masks_dp=fused_tile_dp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
        test_data_normalized_dp=None,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        use_pixel_projection=aggregate_as_images_using_pixel_projection,
        categories=segmentation_categories.get_non_ignore_categories(),
        grid_json_fn=grid_json_fn,
        lazy=False,
    )

    compare_fusion_results_with_reference(
        original_tile_idp=label_tile_dp,
        fused_tile_idp=fused_tile_dp,
        idp_uses_palette=True,
        comparison_tile_odp=comparison_tile_odp,
        segmentation_categories=segmentation_categories.get_non_ignore_categories(),
        label_comparison_categories=comparison_categories,
    )

    for (
        segmentation_category
    ) in segmentation_categories.get_non_ignore_categories():
        category_tile_comparison_odp = os.path.join(
            comparison_tile_odp, segmentation_category.name
        )
        category_tile_comparison_aggregated_odp = os.path.join(
            comparison_tiles_aggregated_odp, segmentation_category.name
        )

        aggregate_dataset_tile_predictions_per_raster(
            aggregation_odp=category_tile_comparison_aggregated_odp,
            test_data_dp=raster_data_idp,
            test_masks_dp=category_tile_comparison_odp,
            search_regex=image_search_regex,
            ignore_regex=image_ignore_regex,
            mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
            test_data_normalized_dp=None,
            aggregate_save_normalized_raster=False,
            aggregate_as_json=aggregate_as_json,
            aggregate_as_images=aggregate_as_images,
            use_pixel_projection=aggregate_as_images_using_pixel_projection,
            categories=comparison_categories,
            grid_json_fn=grid_json_fn,
            lazy=False,
        )


if __name__ == "__main__":
    main()
