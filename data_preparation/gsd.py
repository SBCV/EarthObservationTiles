import numpy as np
from eot.rasters.raster import Raster


def convert_pixel_size_to_gsd(tif_ifp, tif_ofp):
    input_raster = Raster.get_from_file(tif_ifp)
    pixel_size_x, pixel_size_y = input_raster.get_gsd()

    if not np.isclose(pixel_size_x, pixel_size_y):
        print("Warning: Pixel size in x and y direction differs")
        print("pixel_size_x", pixel_size_x)
        print("pixel_size_y", pixel_size_y)

    gsd = (pixel_size_x + pixel_size_y) / 2
    meta_data_dict = {"GSD": str(gsd)}
    output_raster = Raster.get_from_file(tif_ofp, "r+")
    output_raster.add_meta_data(meta_data_dict)
