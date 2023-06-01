import numpy as np
import rasterio
from eot.crs.crs import EPSG_3857
from eot.utility.conversion import convert_rasterio_to_opencv_resampling
import cv2
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile


def _normalize_data(data):
    # print('data.shape', data.shape)
    if data.dtype == "uint16":  # GeoTiff could be 16 bits
        data = np.uint8(data / 256)
    elif data.dtype == "uint32":  # or 32 bits
        data = np.uint8(data / (256 * 256))
    elif data.dtype == "int16":  # or use ESA dirty hack (sic)
        data = np.uint8(data / 10000 * 256)
    return data


def _get_raster_data_of_mercator_tile(raster, tile, bands, resampling):
    pixel_to_epsg_3857_trans = tile.get_transform_pixel_to_epsg_3857()

    # https://rasterio.readthedocs.io/en/latest/api/rasterio.vrt.html

    # ##### Option 1 #####
    warped_vrt = rasterio.vrt.WarpedVRT(
        src_dataset=raster,
        crs=EPSG_3857,
        resampling=resampling,
        add_alpha=False,
        # By providing the transform, width and height parameters, the
        # warped_vrt raster covers only the geo-spatial area defined by
        # these parameters (in this case the area of the tile).
        # This reduces the required size of warped_vrt (in memory) and
        # seems to reduce warping artifacts.
        transform=pixel_to_epsg_3857_trans,
        width=tile.disk_width,
        height=tile.disk_height,
    )
    # Since warped_vrt contains only the data of the tile, we do not need
    # to define a window to access the correct data
    tile_disk_shape = (len(bands), tile.disk_height, tile.disk_width)
    try:
        tile_disk_data = warped_vrt.read(indexes=bands)
    except rasterio.errors.RasterioIOError:
        # This try-except-clause catches errors like:
        #  rasterio.errors.RasterioIOError: Read or write failed.
        #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
        #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
        #  TIFFReadEncodedStrip() failed.
        # Usually this error appears for tiles covering areas outside the
        #  raster image.
        # Tile data with zero values is considered as no valid tile data.
        tile_disk_data = np.zeros(tile_disk_shape, dtype=np.uint8)

    msg = f"{tile_disk_data.shape} vs. {tile_disk_shape}"
    assert tile_disk_data.shape == tile_disk_shape, msg

    # ##################

    # ##### Option 2 #####
    # warped_vrt = rasterio.vrt.WarpedVRT(
    #     src_dataset=raster,
    #     crs=EPSG_3857,
    #     resampling=resampling,
    #     add_alpha=False,
    # )
    # tile_disk_data_shape = (
    #     len(bands),
    #     tile.disk_width,
    #     tile.disk_height,
    # )
    # left, bottom, right, top = tile.get_bounds_epsg_3857()
    # tile_window = warped_vrt.window(left, bottom, right, top)
    # tile_disk_data = warped_vrt.read(
    #     out_shape=tile_disk_data_shape,
    #     indexes=bands,
    #     window=tile_window,
    # )
    # ##################

    tile_disk_data = _normalize_data(tile_disk_data)
    tile_disk_data = np.moveaxis(tile_disk_data, 0, 2)  # C,H,W -> H,W,C
    return tile_disk_data


def _get_raster_data_of_local_tile(
    raster, tile, bands, resampling, fill_value=None
):
    """
    :param tile:
    :param bands:
    :param resampling: something like Resampling in rasterio.enums
    :param fill_value: Can be a tuple like (0, 255, 0)
    :return:
    """
    cv2_resampling = convert_rasterio_to_opencv_resampling(resampling)
    source_x_offset, source_y_offset = tile.get_source_offset()
    source_width, source_height = tile.get_source_size()

    top_overhang = abs(min(0, source_y_offset))
    left_overhang = abs(min(0, source_x_offset))
    bottom_overhang = abs(
        min(0, raster.height - (source_y_offset + source_height))
    )
    right_overhang = abs(
        min(0, raster.width - (source_x_offset + source_width))
    )

    valid_source_height = source_height - top_overhang - bottom_overhang
    valid_source_width = source_width - left_overhang - right_overhang

    valid_source_y_offset = max(0, source_y_offset)
    valid_source_x_offset = max(0, source_x_offset)
    valid_source_window = (
        (
            valid_source_y_offset,
            valid_source_y_offset + valid_source_height,
        ),
        (
            valid_source_x_offset,
            valid_source_x_offset + valid_source_width,
        ),
    )

    # Tile data with zero values is considered as no valid tile data.
    tile_source_shape = (len(bands), source_height, source_width)
    tile_data_source = np.zeros(
        tile_source_shape, dtype=raster.get_data_type()
    )
    if fill_value:
        np.moveaxis(tile_data_source, 0, 2)[:, :] = fill_value
    try:
        tile_data_source[
            :,
            top_overhang : top_overhang + valid_source_height,
            left_overhang : left_overhang + valid_source_width,
        ] = raster.read(indexes=bands, window=valid_source_window)
    except rasterio.errors.RasterioIOError:
        # This try-except-clause catches errors like:
        #  rasterio.errors.RasterioIOError: Read or write failed.
        #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
        #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
        #  TIFFReadEncodedStrip() failed.
        # Usually this error appears for tiles covering areas outside the
        #  raster image.
        # Since tile_data_source is already initialized with 0 values,
        #  there is nothing left to do.
        pass

    msg = f"{tile_data_source.shape} vs. {tile_source_shape}"
    assert tile_data_source.shape == tile_source_shape, msg

    # Convert (channel, height, width) to (height, width, channel)
    tile_data_source = np.moveaxis(tile_data_source, 0, 2)
    tile_data_disk = cv2.resize(
        tile_data_source,
        tile.get_disk_size(),
        interpolation=cv2_resampling,
    )
    return tile_data_disk


def _get_raster_data_of_local_tile_legacy(raster, tile, bands, resampling):
    cv2_resampling = convert_rasterio_to_opencv_resampling(resampling)
    source_x_offset, source_y_offset = tile.get_source_offset()
    source_width, source_height = tile.get_source_size()
    window = (
        (source_y_offset, source_y_offset + source_height),
        (source_x_offset, source_x_offset + source_width),
    )
    tile_source_shape = (len(bands), source_height, source_width)
    try:
        tile_data_source = raster.read(indexes=bands, window=window)
    except rasterio.errors.RasterioIOError:
        # This try-except-clause catches errors like:
        #  rasterio.errors.RasterioIOError: Read or write failed.
        #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
        #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
        #  TIFFReadEncodedStrip() failed.
        # Usually this error appears for tiles covering areas outside the
        #  raster image.
        # Tile data with zero values is considered as no valid tile data.
        tile_data_source = np.zeros(
            tile_source_shape, dtype=raster.get_data_type()
        )

    if tile_data_source.shape != tile_source_shape:
        # For deployment:
        tile_data_source = np.resize(tile_data_source, tile_source_shape)

        # # For debugging:
        # #  Set invalid values / areas outside of raster to 1. Values
        # #  must not be 0, otherwise tiles are treated as "no-data".
        # tile_data_source_resized = np.ones(
        #     tile_source_shape, dtype=np.uint8
        # )
        # actual_bands, actual_height, actual_width = tile_data_source.shape
        # tile_data_source_resized[
        #     0:actual_bands, 0:actual_height, 0:actual_width
        # ] = tile_data_source
        # tile_data_source = tile_data_source_resized

    msg = f"{tile_data_source.shape} vs. {tile_source_shape}"
    assert tile_data_source.shape == tile_source_shape, msg

    # C,H,W -> H,W,C
    tile_data_source = np.moveaxis(tile_data_source, 0, 2)
    tile_data_disk = cv2.resize(
        tile_data_source,
        tile.get_disk_size(),
        interpolation=cv2_resampling,
    )
    return tile_data_disk


def get_raster_data_of_tile(raster, tile, bands, resampling, legacy=False):
    if isinstance(tile, MercatorTile):
        tile_data = _get_raster_data_of_mercator_tile(
            raster, tile, bands, resampling
        )
    elif isinstance(tile, ImagePixelTile):
        if legacy:
            tile_data = _get_raster_data_of_local_tile_legacy(
                raster, tile, bands, resampling
            )
        else:
            tile_data = _get_raster_data_of_local_tile(
                raster, tile, bands, resampling
            )
    else:
        assert False
    return tile_data
