import numpy as np


def _compute_pixel_distance(
    pixel_pos_1, pixel_pos_2, pixel_size_x=1.0, pixel_size_y=1.0
):
    row_1, col_1 = pixel_pos_1
    row_2, col_2 = pixel_pos_2
    row_distance_meter = (row_1 - row_2) * pixel_size_x
    col_distance_meter = (col_1 - col_2) * pixel_size_y
    distance = np.linalg.norm((row_distance_meter, col_distance_meter))
    return distance


def _compute_tile_width_height(
    lt_pixel, rt_pixel, rb_pixel, lb_pixel, pixel_size_x, pixel_size_y
):
    dist_lt_rt = _compute_pixel_distance(
        lt_pixel, rt_pixel, pixel_size_x, pixel_size_y
    )
    dist_lb_rb = _compute_pixel_distance(
        lb_pixel, rb_pixel, pixel_size_x, pixel_size_y
    )
    dist_lt_lb = _compute_pixel_distance(
        lt_pixel, lb_pixel, pixel_size_x, pixel_size_y
    )
    dist_rt_rb = _compute_pixel_distance(
        lt_pixel, lb_pixel, pixel_size_x, pixel_size_y
    )
    dist_l_r = np.asarray(dist_lt_rt + dist_lb_rb) / 2
    dist_t_b = np.asarray(dist_lt_lb + dist_rt_rb) / 2
    return dist_l_r, dist_t_b


def _compute_tile_extent(raster, tile, pixel_size_x, pixel_size_y):
    # While the unit of measurement in EPSG:3857 is indeed meters, distance
    # measurements become increasingly inaccurate away from the equator.
    # (https://gis.stackexchange.com/questions/242545/how-can-epsg3857-be-in-meters)
    # Thus, transform the EPSG_3857 coordinates to the crs of the raster image.
    # Use these transformed corners to determine the pixel locations.
    # Use the pixel size of the raster to determine this distance in pixel.
    (
        tile_lt_pixel,
        tile_rt_pixel,
        tile_rb_pixel,
        tile_lb_pixel,
    ) = raster.get_tile_bound_pixel_corners(tile)
    dist_l_r, dist_t_b = _compute_tile_width_height(
        tile_lt_pixel,
        tile_rt_pixel,
        tile_rb_pixel,
        tile_lb_pixel,
        pixel_size_x,
        pixel_size_y,
    )
    # Convert numpy.float64 to float
    return float(dist_l_r), float(dist_t_b)


def compute_tile_size_in_meter(raster, tile):
    pixel_size_x_meter, pixel_size_y_meter = raster.res
    tile_width_meter, tile_height_meter = _compute_tile_extent(
        raster, tile, pixel_size_x_meter, pixel_size_y_meter
    )
    return tile_width_meter, tile_height_meter


def compute_tile_size_in_source_pixel(raster, tile):
    tile_source_width, tile_source_height = _compute_tile_extent(
        raster, tile, 1.0, 1.0
    )
    return tile_source_width, tile_source_height
