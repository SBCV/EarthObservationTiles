import numpy as np


def get_tile_boundary(tile_label_mat):
    tile_boundary_mat = np.zeros(tile_label_mat.shape[:2], dtype=np.uint8)
    tile_boundary_mat[0, :] = 1
    tile_boundary_mat[-1, :] = 1
    tile_boundary_mat[:, 0] = 1
    tile_boundary_mat[:, -1] = 1
    return tile_boundary_mat


def get_tile_mask(tile_label_mat, category, use_palette_index=True):
    if use_palette_index:
        target_value = category.palette_index
    else:
        target_value = category.palette_color
    tile_mask = (tile_label_mat == target_value).astype(np.uint8)
    return tile_mask
