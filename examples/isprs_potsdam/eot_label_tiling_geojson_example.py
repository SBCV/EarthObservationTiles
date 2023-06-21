import os
from eot.tiles.tile_alignment import TileAlignment
from eot.tiles.tiling_scheme import LocalImageMeterSizeTilingScheme
from eot.geojson_ext.geojson_creation import create_geojson_for_label_tiles
from eot.tools.tools_api import run_tile_images
from eot.categories.dataset_category import DatasetCategory
from eot.categories.dataset_categories import DatasetCategories


def main():

    working_dp = "/path/to/examples_potsdam_dataset_mini"
    raster_data_idp = os.path.join(working_dp, "raster")
    label_tile_dp = os.path.join(working_dp, "label_tiles")

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

    tiling_scheme = LocalImageMeterSizeTilingScheme()
    tiling_scheme.set_tile_size_in_meter([45, 45])
    tiling_scheme.set_tile_stride_in_meter([45, 45])
    tiling_scheme.set_alignment(TileAlignment.centered_to_image.value)
    tiling_scheme.set_overhanging_tiles_flag(True)
    tiling_scheme.set_border_tiles_flag(True)

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
        create_aux_files=True,
    )

    # Create a geojson grid defining the location of the label tiles as well as
    #  a geojson for each category defining the location of the corresponding
    #  pixels.
    create_geojson_for_label_tiles(
        test_data_dp=raster_data_idp,
        search_regex=label_search_regex,
        ignore_regex=label_ignore_regex,
        test_images_dp=label_tile_dp,
        test_labels_dp=label_tile_dp,
        categories=categories.get_non_ignore_categories(),
        odp=label_tile_dp,
        grid_json_fn=grid_json_fn,
    )


if __name__ == "__main__":
    main()
