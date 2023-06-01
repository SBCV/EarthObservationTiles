import os
from eot.tiles.tiling_scheme import MercatorTilingScheme
from eot.aggregation.tile_aggregation import (
    aggregate_dataset_tile_predictions_per_raster,
)
from eot.categories.dataset_category import DatasetCategory
from eot.categories.dataset_categories import DatasetCategories
from eot.tools.tools_api import run_tile_images


def main():

    working_dp = "/path/to/examples_potsdam_dataset_mini"
    raster_data_idp = os.path.join(working_dp, "raster")
    label_tile_dp = os.path.join(working_dp, "label_tiles")
    aggregation_odp = os.path.join(working_dp, "tiles_aggregated")
    raster_normalized_dp = os.path.join(working_dp, "raster_normalized")

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"
    label_search_regex = "**-labels*/*.tif"
    label_ignore_regex = ""

    grid_json_fn = "grid.json"

    # fmt:off
    categories = DatasetCategories(
        [
            DatasetCategory(name="background",          palette_index=0,    palette_color=(255, 0, 0),      label_values=[(255, 0, 0)],     is_active=True),                                # noqa
            DatasetCategory(name="building",            palette_index=1,    palette_color=(0, 0, 255),      label_values=[(0, 0, 255)],     is_active=True),                                # noqa
            DatasetCategory(name="tree",                palette_index=2,    palette_color=(0, 255, 0),      label_values=[(0, 255, 0)],     is_active=True),                                # noqa
            DatasetCategory(name="impervious_surfaces", palette_index=3,    palette_color=(255, 255, 255),  label_values=[(255, 255, 255)], is_active=True),                                # noqa
            DatasetCategory(name="low_vegetation",      palette_index=4,    palette_color=(0, 255, 255),    label_values=[(0, 255, 255)],   is_active=True),                                # noqa
            DatasetCategory(name="car",                 palette_index=5,    palette_color=(255, 255, 0),    label_values=[(255, 255, 0)],   is_active=True),                                # noqa
            DatasetCategory(name="ignore",              palette_index=255,  palette_color=(0, 0, 0),        label_values=[(0, 0, 0)],       is_active=False,    is_ignore_category=True)    # noqa
        ]
    )
    # fmt:on

    output_tile_size_pixel = [512, 512]

    tiling_scheme = MercatorTilingScheme()
    tiling_scheme.set_zoom_level(19)

    aggregate_as_json = True
    aggregate_as_images = True
    use_pixel_projection = False

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=label_search_regex,
        tif_ignore_regex=label_ignore_regex,
        tile_odp=label_tile_dp,
        output_tile_size_pixel=output_tile_size_pixel,
        tiling_scheme=tiling_scheme,
        write_labels=True,
        convert_images_to_labels=True,
        categories=categories,
    )

    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=aggregation_odp,
        test_data_dp=raster_data_idp,
        test_masks_dp=label_tile_dp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
        test_data_normalized_dp=raster_normalized_dp,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        use_pixel_projection=use_pixel_projection,
        categories=categories.get_non_ignore_categories(),
        grid_json_fn=grid_json_fn,
        lazy=False,
    )


if __name__ == "__main__":
    main()
