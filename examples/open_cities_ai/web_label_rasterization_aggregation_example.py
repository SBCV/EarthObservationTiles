import os
from eot.tiles.tiling_scheme import MercatorTilingScheme
from eot.categories.dataset_category import DatasetCategory
from eot.categories.dataset_categories import DatasetCategories
from eot.tools.tools_api import run_tile_images, run_cover, run_rasterize
from eot.aggregation.tile_aggregation import (
    aggregate_dataset_tile_predictions_per_raster,
)


def main():

    working_dp = "/path/to/examples_open_cities_ai_mini"
    raster_or_geojson_idp = os.path.join(working_dp, "raster")

    image_tile_dp = os.path.join(working_dp, "image_tiles")
    image_tile_cover_csv_fp = os.path.join(working_dp, "image_tile_cover.csv")
    label_rasterize_odp = os.path.join(working_dp, "label_tiles_rasterized")
    aggregation_odp = os.path.join(working_dp, "rasterized_tiles_aggregated")
    raster_normalized_dp = os.path.join(working_dp, "raster_normalized")

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"

    geojson_search_regex = "**/*geojson"
    geojson_ignore_regex = ""

    grid_json_fn = "grid.json"

    # fmt:off
    raster_categories = DatasetCategories(
        [
            DatasetCategory(name="background",  palette_index=0,    palette_color=(255, 0, 0),      label_values=[(0,)],     is_active=True),                                # noqa
            DatasetCategory(name="building",    palette_index=1,    palette_color=(0, 0, 255),      label_values=[(1,)],     is_active=True),                                # noqa
        ]
    )
    # fmt:on
    geojson_category = raster_categories.get_category("building")

    output_tile_size_pixel = [512, 512]

    tiling_scheme = MercatorTilingScheme()
    tiling_scheme.set_zoom_level(19)
    tiling_scheme.set_border_tiles_flag(True)

    aggregate_as_json = True
    aggregate_as_images = False
    use_pixel_projection = False

    run_tile_images(
        tif_idp=raster_or_geojson_idp,
        tif_search_regex=image_search_regex,
        tif_ignore_regex=image_ignore_regex,
        tile_odp=image_tile_dp,
        output_tile_size_pixel=output_tile_size_pixel,
        tiling_scheme=tiling_scheme,
        create_aux_files=True,
    )

    run_cover(tile_idp=image_tile_dp, ofp_list=[image_tile_cover_csv_fp])

    run_rasterize(
        geojson_idp=raster_or_geojson_idp,
        geojson_search_regex=geojson_search_regex,
        geojson_ignore_regex=geojson_ignore_regex,
        cover_csv_ifp=image_tile_cover_csv_fp,
        geojson_category=geojson_category,
        tile_data_categories=raster_categories,
        label_odp=label_rasterize_odp,
        output_tile_size_pixel=output_tile_size_pixel,
        lazy=False,
    )

    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=aggregation_odp,
        test_data_dp=raster_or_geojson_idp,
        test_masks_dp=label_rasterize_odp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        mercator_tiling_flag=tiling_scheme.represents_mercator_tiling(),
        test_data_normalized_dp=raster_normalized_dp,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        use_pixel_projection=use_pixel_projection,
        categories=raster_categories.get_non_ignore_categories(),
        grid_json_fn=grid_json_fn,
        lazy=False,
    )


if __name__ == "__main__":
    main()
