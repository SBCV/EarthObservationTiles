import numpy as np

from eot.tiles.tile_reading import read_image_tile_from_file


def _read_image_tile_if_available(tile, tile_to_tile_fp, bands):
    """Retrieves neighbour tile image if exists."""
    if tile in tile_to_tile_fp:
        tile_fp = tile_to_tile_fp[tile]
        return read_image_tile_from_file(tile_fp, bands)
    else:
        return None


def create_image_metatile(tile, tile_list, bands):
    """Buffers a tile image adding borders on all sides based on adjacent tiles

                ------------------
                | ul |  uc  | ur |
    metatile =  | cl | tile | cr |
                | bl |  bc  | br |
                ------------------

    Zeros are padded if necessary.
    """

    ul, uc, ur, cl, cr, bl, bc, br = tile.get_neighbors()

    tile_to_tile_fp = {tile: tile.get_absolute_tile_fp() for tile in tile_list}
    # 3x3 matrix (upper, center, bottom) x (left, center, right)
    ul = _read_image_tile_if_available(ul, tile_to_tile_fp, bands)
    uc = _read_image_tile_if_available(uc, tile_to_tile_fp, bands)
    ur = _read_image_tile_if_available(ur, tile_to_tile_fp, bands)
    cl = _read_image_tile_if_available(cl, tile_to_tile_fp, bands)
    cc = _read_image_tile_if_available(tile, tile_to_tile_fp, bands)
    cr = _read_image_tile_if_available(cr, tile_to_tile_fp, bands)
    bl = _read_image_tile_if_available(bl, tile_to_tile_fp, bands)
    bc = _read_image_tile_if_available(bc, tile_to_tile_fp, bands)
    br = _read_image_tile_if_available(br, tile_to_tile_fp, bands)

    b = len(bands)
    ts = cc.shape[1]
    o = int(ts / 4)
    oo = o * 2

    img = np.zeros((ts + oo, ts + oo, len(bands))).astype(np.uint8)

    # fmt:off
    img[0:o,        0:o,        :] = ul[-o:ts, -o:ts, :] if ul is not None else np.zeros((o,   o, b)).astype(np.uint8)
    img[0:o,        o:ts+o,     :] = uc[-o:ts,  0:ts, :] if uc is not None else np.zeros((o,  ts, b)).astype(np.uint8)
    img[0:o,        ts+o:ts+oo, :] = ur[-o:ts,   0:o, :] if ur is not None else np.zeros((o,   o, b)).astype(np.uint8)
    img[o:ts+o,     0:o,        :] = cl[0:ts,  -o:ts, :] if cl is not None else np.zeros((ts,  o, b)).astype(np.uint8)
    img[o:ts+o,     o:ts+o,     :] = cc                  if cc is not None else np.zeros((ts, ts, b)).astype(np.uint8)
    img[o:ts+o,     ts+o:ts+oo, :] = cr[0:ts,    0:o, :] if cr is not None else np.zeros((ts,  o, b)).astype(np.uint8)
    img[ts+o:ts+oo, 0:o,        :] = bl[0:o,   -o:ts, :] if bl is not None else np.zeros((o,   o, b)).astype(np.uint8)
    img[ts+o:ts+oo, o:ts+o,     :] = bc[0:o,    0:ts, :] if bc is not None else np.zeros((o,  ts, b)).astype(np.uint8)
    img[ts+o:ts+oo, ts+o:ts+oo, :] = br[0:o,     0:o, :] if br is not None else np.zeros((o,   o, b)).astype(np.uint8)
    # fmt:on

    return img
