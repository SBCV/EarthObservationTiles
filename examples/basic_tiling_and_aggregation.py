import os
from eot.tools.tools_api import run_tile_images
from eot.tiles.tile import ImageCenteredMeterSizeTileType
from eot.geojson_ext.tiles_utility import (
    create_geojson_for_image_tiles,
    create_geojson_for_label_tiles,
)
from eot.aggregation.aggregate_tiles import (
    aggregate_dataset_tile_predictions_per_raster,
)


def main():

    working_dp = "/path/to/eot_test"
    raster_data_idp = os.path.join(working_dp, "raster")
    toml_config_fp = os.path.join(working_dp, "pipeline.toml")
    image_tile_dp = os.path.join(working_dp, "image_tiles")
    label_tile_dp = os.path.join(working_dp, "label_tiles")
    aggregation_odp = os.path.join(working_dp, "label_aggregated")

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"
    label_search_regex = "**-labels*/*.tif"
    label_ignore_regex = ""

    training_category_titles = [
        "background",
        "building",
        "tree",
        "impervious_surfaces",
        "low_vegetation",
        "car",
    ]

    dataset_type = "potsdam"
    tile_overview_txt_ofn = "tile_overview.txt"
    output_tile_size_pixel = [512, 512]
    tile_type = ImageCenteredMeterSizeTileType()
    input_tile_size_in_meter = [75, 75]
    input_tile_stride_in_meter = [75, 75]
    grid_json_fn = "grid.json"

    aggregate_as_json = True
    aggregate_as_images = True

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=image_search_regex,
        tif_ignore_regex=image_ignore_regex,
        tile_odp=image_tile_dp,
        tile_overview_txt_ofn=tile_overview_txt_ofn,
        dataset_type=dataset_type,
        output_tile_size_pixel=output_tile_size_pixel,
        tile_type=tile_type,
        input_tile_size_in_meter=input_tile_size_in_meter,
        input_tile_stride_in_meter=input_tile_stride_in_meter,
        # create_aux_files=create_tile_aux_files
    )

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=label_search_regex,
        tif_ignore_regex=label_ignore_regex,
        tile_odp=label_tile_dp,
        tile_overview_txt_ofn=tile_overview_txt_ofn,
        dataset_type=dataset_type,
        output_tile_size_pixel=output_tile_size_pixel,
        tile_type=tile_type,
        input_tile_size_in_meter=input_tile_size_in_meter,
        input_tile_stride_in_meter=input_tile_stride_in_meter,
        write_labels=True,
        config_ifp=toml_config_fp,
        convert_images_to_labels=True,
        requested_category_titles=training_category_titles,
        # create_aux_files=create_tile_aux_files
    )

    # Create a geojson grid defining the location of the image tiles
    create_geojson_for_image_tiles(
        raster_data_idp,
        image_search_regex,
        image_ignore_regex,
        image_tile_dp,
        grid_json_fn,
    )

    # Create a geojson grid defining the location of the label tiles as well as
    #  a geojson for each category defining the location of the corresponding
    #  pixels.
    create_geojson_for_label_tiles(
        raster_data_idp,
        label_search_regex,
        label_ignore_regex,
        image_tile_dp,
        label_tile_dp,
        toml_config_fp,
        training_category_titles,
        grid_json_fn,
    )

    aggregate_dataset_tile_predictions_per_raster(
        aggregation_odp=aggregation_odp,
        test_data_dp=raster_data_idp,
        test_masks_dp=label_tile_dp,
        search_regex=image_search_regex,
        ignore_regex=image_ignore_regex,
        toml_config_fp=toml_config_fp,
        tile_type=tile_type,
        test_data_normalized_dp=None,
        aggregate_save_normalized_raster=False,
        aggregate_as_json=aggregate_as_json,
        aggregate_as_images=aggregate_as_images,
        training_category_titles=training_category_titles,
        grid_json_fn=grid_json_fn,
        lazy=False,
    )


if __name__ == "__main__":
    main()
