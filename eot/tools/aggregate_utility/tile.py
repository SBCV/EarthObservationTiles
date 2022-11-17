import numpy as np
from PIL import Image


def get_tile_label_mat(label_ifp):
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


def get_tile_mask(tile_label_mat, category_index):
    tile_mask = (tile_label_mat == category_index).astype(np.uint8)
    return tile_mask


def get_tile_boundary(tile_label_mat):
    tile_boundary_mat = np.zeros(tile_label_mat.shape[:2], dtype=np.uint8)
    tile_boundary_mat[0, :] = 1
    tile_boundary_mat[-1, :] = 1
    tile_boundary_mat[:, 0] = 1
    tile_boundary_mat[:, -1] = 1
    return tile_boundary_mat
