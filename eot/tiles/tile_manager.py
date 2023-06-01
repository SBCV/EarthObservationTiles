import sys
import glob
import os
import re
import csv

from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles.tile_conversion import convert_tiles_to_geojson


def _str_to_class(class_name):
    class_of_str = getattr(sys.modules[__name__], class_name)
    return class_of_str


class TileManager:
    @staticmethod
    def read_tile_from_dict(tile_dict):
        if tile_dict["class"] == MercatorTile.__name__:
            tile = MercatorTile(
                x=tile_dict[MercatorTile.X_STR],
                y=tile_dict[MercatorTile.Y_STR],
                z=tile_dict[MercatorTile.Z_STR],
            )
        elif tile_dict["class"] == ImagePixelTile.__name__:
            tile = ImagePixelTile(
                raster_name=tile_dict[ImagePixelTile.RASTER_NAME_STR],
                source_x_offset=tile_dict[ImagePixelTile.SOURCE_X_OFFSET_STR],
                source_y_offset=tile_dict[ImagePixelTile.SOURCE_Y_OFFSET_STR],
                source_width=tile_dict[ImagePixelTile.SOURCE_WIDTH_STR],
                source_height=tile_dict[ImagePixelTile.SOURCE_HEIGHT_STR],
            )
        else:
            assert False
        return tile

    @staticmethod
    def read_tiles_from_csv(ifp, extra_columns=False):
        """Retrieve tiles from a line-delimited csv file."""

        assert os.path.isfile(
            os.path.expanduser(ifp)
        ), "'{}' seems not a valid CSV file".format(ifp)
        with open(os.path.expanduser(ifp)) as fp:

            for row in fp:
                row = row.replace("\n", "")
                if not row:
                    continue

                row = re.split(
                    ",|\t", row
                )  # use either comma or tab as separator

                assert len(row) >= 1, "Invalid Cover"
                tile_class = _str_to_class(row[0])
                if tile_class == MercatorTile:
                    assert len(row) >= 4, "Invalid WebMercatorTile in Cover"
                    tile = MercatorTile(
                        x=int(row[1]), y=int(row[2]), z=int(row[3])
                    )
                    if not extra_columns or len(row) == 4:
                        yield tile
                    else:
                        yield [tile, *map(float, row[4:])]
                elif tile_class == ImagePixelTile:
                    assert len(row) >= 6, "Invalid PixelTile in Cover"
                    tile = ImagePixelTile(
                        raster_name=row[1],
                        source_x_offset=int(row[2]),
                        source_y_offset=int(row[3]),
                        source_width=int(row[4]),
                        source_height=int(row[5]),
                    )
                    yield tile
                else:
                    assert False

    @staticmethod
    def read_tiles_from_dir(idp, cover=None, target_raster_name=None):
        """Loads files from an on-disk dir.

        Searches for "spherical_mercator_tiles" and "image_pixel_tiles"
         directories, e.g.
          <path>/<to>/spherical_mercator_tiles/<tile_structure>
          <path>/>to>/image_pixel_tiles/<tile_structure>
        """
        idp = os.path.expanduser(idp)
        tile_relative_fp_scheme = (
            TilePathManager.read_relative_tile_fp_scheme_from_dir(idp)
        )
        tile_absolute_fp_scheme = os.path.join(idp, tile_relative_fp_scheme)
        tile_ifp_list = glob.glob(tile_absolute_fp_scheme)
        for tile_ifp in tile_ifp_list:
            if tile_ifp.endswith("aux.xml") or tile_ifp.endswith(".geojson"):
                continue
            tile = TilePathManager.convert_tile_fp_to_tile(
                root_idp=idp, tile_ifp=tile_ifp
            )

            if target_raster_name is not None:
                assert isinstance(tile, ImagePixelTile)
                if tile.get_raster_name() != target_raster_name:
                    continue

            if tile is None:
                print("CONTINUE")
                continue

            if cover is not None and tile not in cover:
                print("NOT IN COVER")
                continue

            tile.set_tile_fp(tile_ifp, is_absolute=True)
            yield tile

    @staticmethod
    def write_tiles_as_csv(ofp, tiles):
        with open(ofp, "w") as csv_file:
            for tile in tiles:
                row_as_tuple = (tile.__class__.__name__,) + tile.to_tuple()
                csv.writer(csv_file).writerow(row_as_tuple)

    @staticmethod
    def write_tiles_as_geojson(ofp, tiles, union):
        with open(ofp, "w") as geojson_file:
            geojson_file.write(convert_tiles_to_geojson(tiles, union=union))
