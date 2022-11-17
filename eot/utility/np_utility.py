import copy
import numpy as np


def get_unique_values(scalar_data):
    return np.unique(scalar_data)


def get_unique_colors(img_data):
    return np.unique(img_data.reshape(-1, img_data.shape[2]), axis=0)


def get_pixel_indices_of_color(image_data, color):
    assert image_data.shape[2] == 4, f"{image_data.shape[2]}"
    color_pixel_indices = np.all(image_data == color, axis=-1)
    return color_pixel_indices


def get_pixel_indices_of_color_complement(image_data, color):
    color_pixel_indices = get_pixel_indices_of_color(image_data, color)
    color_complement_pixel_indices = ~color_pixel_indices
    return color_complement_pixel_indices


def get_black_pixel_indices(image_data):
    return get_pixel_indices_of_color(image_data, (0, 0, 0, 0))


def get_non_black_pixel_indices(image_data):
    return ~get_black_pixel_indices(image_data)


def convert_to_image_axis_order(raster_data, create_copy=False):
    if create_copy:
        raster_data = copy.deepcopy(raster_data)
    # channel, height, width -> height, width, channel
    raster_data = np.moveaxis(raster_data, 0, 2)
    return raster_data


def convert_to_raster_axis_order(raster_data, create_copy=False):
    if create_copy:
        raster_data = copy.deepcopy(raster_data)
    # height, width, channel -> channel, height, width
    raster_data = np.moveaxis(raster_data, 2, 0)
    return raster_data
