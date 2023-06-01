import os
from eot.tiles.tiling_scheme import MercatorTilingScheme
from eot.geojson_ext.geojson_creation import create_geojson_for_image_tiles
from eot.tools.tools_api import run_tile_images


def main():

    working_dp = "/path/to/examples_potsdam_dataset_mini"
    raster_data_idp = os.path.join(working_dp, "raster")
    image_tile_dp = os.path.join(working_dp, "image_tiles")

    image_search_regex = "**/*tif"
    image_ignore_regex = "**-labels*/*.tif"

    grid_json_fn = "grid.json"

    output_tile_size_pixel = [512, 512]

    tiling_scheme = MercatorTilingScheme(zoom_level=19)
    tiling_scheme.set_border_tiles_flag(False)

    run_tile_images(
        tif_idp=raster_data_idp,
        tif_search_regex=image_search_regex,
        tif_ignore_regex=image_ignore_regex,
        tile_odp=image_tile_dp,
        output_tile_size_pixel=output_tile_size_pixel,
        tiling_scheme=tiling_scheme,
        create_aux_files=True,
        create_polygon_files=True,
    )

    # Create a geojson grid defining the location of the image tiles
    create_geojson_for_image_tiles(
        raster_data_idp,
        image_search_regex,
        image_ignore_regex,
        image_tile_dp,
        grid_json_fn,
    )


if __name__ == "__main__":
    main()
