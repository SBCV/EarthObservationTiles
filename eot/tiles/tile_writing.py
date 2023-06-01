import os
from shutil import copyfile
import rasterio
import cv2
import numpy as np
from PIL import Image
from collections import defaultdict

from eot.rasters.raster import Raster
from eot.rasters.raster_writing import write_aux_xml
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.tile import Tile
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles.tile_reading import read_label_tile_from_file_as_indices


def write_image_tile_to_file(
    odp,
    geo_tile,
    image_data,
    ext,
    create_aux_file=False,
    create_polygon_file=False,
):
    """Write an image tile on disk."""

    assert ext in [".png", ".jpg", ".tif"]
    height, width, channel = image_data.shape
    if ext in [".png", ".jpg"]:
        assert channel in [1, 3, 4]
    elif ext == ".tif":
        pass

    odp = os.path.expanduser(odp)

    if isinstance(geo_tile, Tile):
        tile_fp = os.path.join(
            odp, TilePathManager.get_relative_tile_fp(geo_tile, ext)
        )
    else:
        tile_fp = os.path.join(odp, f"{geo_tile}{ext}")

    os.makedirs(os.path.dirname(tile_fp), exist_ok=True)

    if create_aux_file:
        write_aux_xml(
            image_data,
            tile_fp,
            geo_tile.get_tile_transform(),
            geo_tile.get_crs(),
            check_driver=False,
        )
    if create_polygon_file:
        geo_tile.write_bound_corners_as_geojson(
            tile_fp + ".geojson", as_polygon=True
        )

    # try:
    if ext in [".png", ".jpg"]:
        if channel == 1:
            Image.fromarray(image_data.reshape(height, width), mode="L").save(
                tile_fp
            )
        elif channel == 3:
            cv2.imwrite(tile_fp, cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR))
        elif channel == 4:
            cv2.imwrite(tile_fp, cv2.cvtColor(image_data, cv2.COLOR_RGBA2BGRA))
        else:
            assert False
    elif ext == ".tif":
        driver = rasterio.drivers.driver_from_extension(tile_fp)
        raster = Raster.get_from_file(
            tile_fp,
            "w",
            driver=driver,
            height=height,
            width=width,
            count=channel,
            dtype=image_data.dtype,
        )
        # height, width, channel -> channel, height, width
        raster.write(np.moveaxis(image_data, 2, 0))
    # except:
    #     assert False, "Unable to write {}".format(tile_fp)


def write_label_tile_to_file(
    odp,
    geo_tile,
    label_data,
    palette_colors,
    append=False,
    create_aux_file=False,
    copy_aux_file=False,
    create_polygon_file=False,
    default_palette_color=(0, 0, 0),
):
    """Write a label (or a mask) tile on disk using a color palette.

    That means, not only the color information, but also the corresponding
    palette indices are stored.
    """

    if len(label_data.shape) == 3:  # H,W,C -> H,W
        assert label_data.shape[2] == 1
        label_data = label_data.reshape(
            (label_data.shape[0], label_data.shape[1])
        )

    odp = os.path.expanduser(odp)
    if isinstance(geo_tile, Tile):
        ofp = os.path.join(
            odp, TilePathManager.get_relative_tile_fp(geo_tile, ".png")
        )
        tile_dp = os.path.dirname(ofp)
    else:
        tile_dp = odp

    if append and os.path.isfile(ofp):
        previous = read_label_tile_from_file_as_indices(ofp, silent=False)
        label_data = np.uint8(np.maximum(previous, label_data))
    else:
        os.makedirs(tile_dp, exist_ok=True)

    label_data = label_data.astype(np.uint8)
    if create_polygon_file:
        geo_tile.write_bound_corners_as_geojson(
            ofp + ".geojson", as_polygon=True
        )
    if create_aux_file:
        write_aux_xml(
            label_data,
            ofp,
            geo_tile.get_tile_transform(),
            geo_tile.get_crs(),
            check_driver=False,
        )
    if copy_aux_file:
        aux_xml_ifp = geo_tile.get_absolute_tile_fp() + ".aux.xml"
        if os.path.isfile(aux_xml_ifp):
            copyfile(aux_xml_ifp, ofp + ".aux.xml")
    label_image = Image.fromarray(label_data, mode="P")

    max_index = max(palette_colors.values())
    palette_color_indices = list(range(max_index + 1))
    palette_index_to_color_dict = defaultdict(lambda: default_palette_color)
    for color, index in palette_colors.items():
        palette_index_to_color_dict[index] = color
    palette_colors_list = [
        palette_index_to_color_dict[index] for index in palette_color_indices
    ]
    # Flatten ((R1, G1, B1), (R2, G2, B2), ...) to
    #  (R1, G1, B1, R2, G2, ...)
    palette_colors_tuple = list(sum(palette_colors_list, ()))
    label_image.putpalette(palette_colors_tuple)
    label_image.save(ofp, optimize=True)


def write_tile_bounds_to_file(odp, geo_tile, dst_crs, as_polygon=False):
    """Write the bounds of a tile to disk."""

    odp = os.path.expanduser(odp)
    ext = ".json"
    if isinstance(geo_tile, Tile):
        tile_fp = os.path.join(
            odp, TilePathManager.get_relative_tile_fp(geo_tile, ext)
        )
    else:
        tile_fp = os.path.join(odp, f"{geo_tile}{ext}")

    os.makedirs(os.path.dirname(tile_fp), exist_ok=True)

    try:
        if isinstance(geo_tile, MercatorTile):
            geo_tile.write_bound_corners_as_geojson(
                tile_fp, dst_crs, as_polygon
            )
    except:
        assert False, "Unable to write {}".format(tile_fp)
