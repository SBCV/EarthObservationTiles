import io
import os
from shutil import copyfile

import cv2
import numpy as np
from PIL import Image

from eot.tiles.tile import Tile
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.tile_path_manager import TilePathManager
from eot.rasters.raster import Raster
from eot.rasters.write import write_aux_xml


def read_image_tile_from_url(requests_session, url, timeout=10):
    """Fetch a tile image using HTTP, and return it or None"""

    try:
        resp = requests_session.get(url, timeout=timeout)
        resp.raise_for_status()
        image = np.fromstring(io.BytesIO(resp.content).read(), np.uint8)
        return cv2.cvtColor(
            cv2.imdecode(image, cv2.IMREAD_ANYCOLOR), cv2.COLOR_BGR2RGB
        )

    except Exception:
        return None


def read_image_tile_from_file(ifp, bands=None, force_rgb=False):
    """Return a multiband image numpy array, from an image file path, or None."""

    ifp = os.path.expanduser(ifp)
    try:
        if ifp[-3:] == "png" and force_rgb:  # PIL PNG Color Palette handling
            return np.array(Image.open(ifp).convert("RGB"))
        elif ifp[-3:] == "png":
            return np.array(Image.open(ifp))
        else:
            raster = Raster.get_from_file(ifp)
    except:
        return None

    image = None
    for i in raster.indexes if bands is None else bands:
        data_band = raster.read(i)
        data_band = data_band.reshape(
            data_band.shape[0], data_band.shape[1], 1
        )  # H,W -> H,W,C
        image = (
            np.concatenate((image, data_band), axis=2)
            if image is not None
            else data_band
        )

    assert image is not None, "Unable to open {}".format(ifp)
    return image


def read_label_tile_from_file_as_indices(path, silent=True):
    """Return a numpy array, from a label file path, or None.

    Note that the label images are stored in "P" mode, i.e. containing a color
    palette.

    pil_image = Image.open(ifp)
    print(pil_image.mode)
    print(pil_image.getpalette())
    """

    try:
        return np.array(Image.open(os.path.expanduser(path))).astype(int)
    except:
        assert silent, "Unable to open existing label: {}".format(path)


def write_image_tile_to_file(
    odp, geo_tile, image_data, ext, create_aux_file=False
):
    """Write an image tile on disk."""

    assert ext in [".png", ".jpg", ".tif"]
    H, W, C = image_data.shape
    if ext in [".png", ".jpg"]:
        assert C in [1, 3]
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
        if isinstance(geo_tile, ImagePixelTile):
            write_aux_xml(
                image_data,
                tile_fp,
                geo_tile.get_tile_transform(),
                geo_tile.get_crs(),
                check_driver=False,
            )

    try:
        if C == 1:
            Image.fromarray(image_data.reshape(H, W), mode="L").save(tile_fp)
        elif C == 3:
            cv2.imwrite(tile_fp, cv2.cvtColor(image_data, cv2.COLOR_RGB2BGR))
        else:
            Raster.get_from_file(
                tile_fp,
                "w",
                driver="GTiff",
                height=H,
                width=W,
                count=C,
                dtype=image_data.dtype,
            ).write(
                np.moveaxis(image_data, 2, 0)  # H,W,C -> C,H,W
            )
    except:
        assert False, "Unable to write {}".format(tile_fp)


def write_label_tile_to_file(
    odp,
    geo_tile,
    label_data,
    config_categories_sorted,
    append=False,
    margin=0,
    create_aux_file=False,
    copy_aux_file=False,
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

    try:
        label_data = label_data.astype(np.uint8)
        if create_aux_file:
            if isinstance(geo_tile, ImagePixelTile):
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
        # print("palette_color_list", palette_color_list)
        palette_color_list = []
        for idx, category in enumerate(config_categories_sorted):
            assert category.palette_index == idx
            palette_color_list.append(tuple(category.palette_color))

        # Flatten ((R1, G1, B1), (R2, G2, B2), ...) to
        #  (R1, G1, B1, R2, G2, ...)
        palette_color_tuple = list(sum(palette_color_list, ()))
        label_image.putpalette(palette_color_tuple)
        label_image.save(ofp, optimize=True)
    except:
        assert False, f"Unable to write {ofp}"


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
