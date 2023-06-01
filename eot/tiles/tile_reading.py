import io
import os

import cv2
import numpy as np
from PIL import Image

from eot.rasters.raster import Raster


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
        return np.array(Image.open(path)).astype(int)
    except:
        assert silent, "Unable to open existing label: {}".format(path)


def read_label_tile_from_file(label_ifp):
    img = Image.open(label_ifp).convert("P")
    tile_label_mat = np.array(img, dtype=np.uint8)
    # Note: img.getcolors() returns a list with the values PRESENT in the
    #   image. That means, the returned colors (i.e. the palette indices) are
    #  potentially only a subset of img.palette.colors!
    colors = img.palette.colors
    err_msg = (
        f"No valid color palette for {label_ifp}."
        "Does your Pillow version support color palettes?"
    )
    assert colors, err_msg
    return tile_label_mat, img.palette
