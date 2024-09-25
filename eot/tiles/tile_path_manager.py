import glob
import os
import re
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.utility.os_ext import get_subdirs


class TilePathManager:

    SPHERICAL_MERCATOR_TILES = "spherical_mercator_tiles"
    IMAGE_PIXEL_TILES = "image_pixel_tiles"

    @classmethod
    def _convert_tile_type_dn_to_tile_type(cls, tile_type_str):
        if tile_type_str == cls.SPHERICAL_MERCATOR_TILES:
            return MercatorTile
        elif tile_type_str == cls.IMAGE_PIXEL_TILES:
            return ImagePixelTile
        else:
            assert False

    @classmethod
    def get_parent_dir_of_tile_class(cls, tile_class):
        if tile_class == MercatorTile:
            return cls.SPHERICAL_MERCATOR_TILES
        elif tile_class == ImagePixelTile:
            return cls.IMAGE_PIXEL_TILES
        else:
            assert False

    @staticmethod
    def get_prefixes_of_tile_class(tile_class):
        if tile_class == MercatorTile:
            return ["x_", "y_", "z_"]
        elif tile_class == ImagePixelTile:
            return ["width_height_", "width_offset_", "height_offset_"]
        else:
            assert False

    @classmethod
    def get_relative_tile_fp(cls, tile, tile_file_ext=""):
        """Return the relative path to the corresponding tile file."""
        assert tile_file_ext == "" or tile_file_ext[0] == "."
        if isinstance(tile, MercatorTile):
            # Returns "<web_map>/<z>/<x>/<y>.jpg" if the tile is located in
            # "root/web_map/z/x/y.jpg"
            x, y, z = tile.get_x_y_z()
            x_prefix, y_prefix, z_prefix = cls.get_prefixes_of_tile_class(
                MercatorTile
            )
            relative_fp = os.path.join(
                cls.get_parent_dir_of_tile_class(MercatorTile),
                f"{z_prefix}{z}",
                f"{x_prefix}{x}",
                f"{y_prefix}{y}{tile_file_ext}",
            )
        elif isinstance(tile, ImagePixelTile):
            # Returns "<raster_name>/<size>/<x>/<y>.jpg" if the tile is located in
            # "root/raster_name/size/x/y.jpg"
            width_offset, height_offset = tile.get_source_offset()
            raster_name = tile.get_raster_name()
            width, height = tile.get_source_size()
            (
                width_height_prefix,
                width_offset_prefix,
                height_offset_prefix,
            ) = cls.get_prefixes_of_tile_class(ImagePixelTile)
            relative_fp = os.path.join(
                cls.get_parent_dir_of_tile_class(ImagePixelTile),
                f"{raster_name}",
                f"{width_height_prefix}{width}_{height}",
                f"{width_offset_prefix}{width_offset}",
                f"{height_offset_prefix}{height_offset}{tile_file_ext}",
            )
        else:
            assert False
        return relative_fp

    @classmethod
    def _get_dataset_tile_types_rec(cls, root_idp):
        tile_type_list = [cls.SPHERICAL_MERCATOR_TILES, cls.IMAGE_PIXEL_TILES]
        detected_tile_type_list = []
        remaining_sub_dp_list = []
        # Search for directory names representing the tile type using a
        #  breadth-first search.
        sub_dp_list = get_subdirs(root_idp)
        for sub_dp in sub_dp_list:
            potential_tile_type = os.path.basename(sub_dp)
            if potential_tile_type in tile_type_list:
                # In case we found a tile type, we'll not traverse the
                #  subdirectories of the corresponding directory
                detected_tile_type_list.append(potential_tile_type)
            else:
                # In case the folder name does not represent a tile type we
                #  traverse the corresponding subdirectories
                remaining_sub_dp_list.append(sub_dp)
        # Traverse the next level of subdirectories
        for sub_dp in remaining_sub_dp_list:
            detected_tile_type_list.extend(
                cls._get_dataset_tile_types_rec(sub_dp)
            )
        return detected_tile_type_list

    @classmethod
    def _get_dataset_tile_types(cls, root_idp):
        detected_tile_type_list = cls._get_dataset_tile_types_rec(root_idp)
        # In the case of mercator tiles there may be multiple directories
        #  with the same "tile_type" (inside the ".splits" directory).
        detected_tile_type_list = list(set(detected_tile_type_list))
        assert len(detected_tile_type_list) == 1, f"{detected_tile_type_list}"
        return detected_tile_type_list

    @classmethod
    def get_tile_type_from_dir(cls, root_idp):
        dataset_tile_type_str_list = cls._get_dataset_tile_types(root_idp)
        dataset_tile_type_list = [
            cls._convert_tile_type_dn_to_tile_type(tile_type_str)
            for tile_type_str in dataset_tile_type_str_list
        ]
        if len(dataset_tile_type_list) != 1:
            print(f"dataset_tile_types: {dataset_tile_type_list}")
            assert False
        return dataset_tile_type_list[0]

    @classmethod
    def get_tiling_dn_from_dir(cls, root_idp):
        tile_type = TilePathManager.get_tile_type_from_dir(root_idp)
        tiling_dn = TilePathManager.get_parent_dir_of_tile_class(tile_type)
        tiling_dp = os.path.join(root_idp, tiling_dn)
        assert os.path.isdir(tiling_dp), f"{tiling_dp}"
        return tiling_dp

    @classmethod
    def get_tiling_json_fp_from_dir(cls, root_idp):
        tiling_result_fp = cls.get_tiling_dn_from_dir(root_idp) + ".json"
        return tiling_result_fp

    @classmethod
    def get_tiling_txt_fp_from_dir(cls, root_idp):
        tiling_result_fp = cls.get_tiling_dn_from_dir(root_idp) + ".txt"
        return tiling_result_fp

    @classmethod
    def get_tiling_overview_txt_fp_from_dir(cls, root_idp):
        tiling_result_fp = (
            cls.get_tiling_dn_from_dir(root_idp) + "_overview.txt"
        )
        return tiling_result_fp

    @classmethod
    def get_tiling_panoptic_json_fp_from_dir(cls, root_idp):
        return os.path.join(root_idp, "panoptic.json")

    @classmethod
    def read_relative_tile_fp_scheme_from_dir(cls, root_idp):
        dataset_tile_types = cls._get_dataset_tile_types(root_idp)

        natural_num_scheme = "[0-9]*"
        if (
            cls.get_parent_dir_of_tile_class(MercatorTile)
            in dataset_tile_types
        ):
            parent_dir = cls.get_parent_dir_of_tile_class(MercatorTile)
            x_prefix, y_prefix, z_prefix = cls.get_prefixes_of_tile_class(
                MercatorTile
            )
            tile_fp_scheme = f"{parent_dir}/{z_prefix}{natural_num_scheme}/{x_prefix}{natural_num_scheme}/{y_prefix}{natural_num_scheme}.*"
        elif (
            cls.get_parent_dir_of_tile_class(ImagePixelTile)
            in dataset_tile_types
        ):
            parent_dir = cls.get_parent_dir_of_tile_class(ImagePixelTile)
            (
                width_height_prefix,
                width_offset_prefix,
                height_offset_prefix,
            ) = cls.get_prefixes_of_tile_class(ImagePixelTile)
            # Note: The first "-" is NOT treated as a special character.
            integer_num_scheme = "[-0-9]*"
            tile_fp_scheme = f"{parent_dir}/*/{width_height_prefix}{natural_num_scheme}_{natural_num_scheme}/{width_offset_prefix}{integer_num_scheme}/{height_offset_prefix}{integer_num_scheme}"
        else:
            msg = "Found no valid tile directory."
            msg += f' Expected "{cls.SPHERICAL_MERCATOR_TILES}" or "{cls.IMAGE_PIXEL_TILES}", but found {dataset_tile_types} in {root_idp}!'
            assert False, msg

        return tile_fp_scheme

    @classmethod
    def read_absolute_tile_fp_from_dir(cls, idp, tile):
        relative_fp = cls.get_relative_tile_fp(tile, tile_file_ext=".*")
        tile_fp_list = glob.glob(
            os.path.join(os.path.expanduser(idp), relative_fp)
        )
        if not tile_fp_list:
            return None

        tile_fp_list = [
            fp for fp in tile_fp_list
            if not fp.endswith(".aux.xml") and not fp.endswith(".geojson")
        ]

        assert len(tile_fp_list) == 1, f"ambiguous tile path {tile_fp_list}"
        absolute_fp = tile_fp_list[0]
        return absolute_fp

    @classmethod
    def convert_tile_fp_to_tile(cls, root_idp, tile_ifp):
        """
        There are two supported directory structures:
         Option 1: A "spherical_mercator_tile" directory, i.e.
          spherical_mercator_tile/<x>/<y>/<zoom>.png
        Option 2: A "image_pixel_tiles" directory, i.e.
          image_pixel_tiles/<raster_name>/width_height_<width>_<height>/width_offset_<width_offset>/height_offset_<height_offset>.png
        """
        dataset_tile_types = cls._get_dataset_tile_types(root_idp)
        if (
            cls.get_parent_dir_of_tile_class(MercatorTile)
            in dataset_tile_types
        ):
            parent_dir = cls.get_parent_dir_of_tile_class(MercatorTile)
            prefix = parent_dir
            x_prefix, y_prefix, z_prefix = cls.get_prefixes_of_tile_class(
                MercatorTile
            )
            regex_str = os.path.join(
                root_idp,
                f"{prefix}/{z_prefix}(?P<z>[0-9]+)/{x_prefix}(?P<x>[0-9]+)/{y_prefix}(?P<y>[0-9]+).+",
            )
            tile_as_dict = re.match(regex_str, tile_ifp)
            if tile_as_dict is None:
                return None
            x = int(tile_as_dict[MercatorTile.X_STR])
            y = int(tile_as_dict[MercatorTile.Y_STR])
            z = int(tile_as_dict[MercatorTile.Z_STR])
            tile = MercatorTile(x, y, z)
        elif (
            cls.get_parent_dir_of_tile_class(ImagePixelTile)
            in dataset_tile_types
        ):
            parent_dir = cls.get_parent_dir_of_tile_class(ImagePixelTile)
            prefix = parent_dir
            (
                width_height_prefix,
                width_offset_prefix,
                height_offset_prefix,
            ) = cls.get_prefixes_of_tile_class(ImagePixelTile)
            width_height_string = (
                f"{width_height_prefix}(?P<width_height>[0-9]+_[0-9]+)"
            )
            raster_string = f"(?P<raster_name>.+)"
            width_offset_string = (
                f"{width_offset_prefix}(?P<width_offset>[-]?[0-9]+)"
            )
            height_offset_string = (
                f"{height_offset_prefix}(?P<height_offset>[-]?[0-9]+)"
            )

            regex_str = os.path.join(
                root_idp,
                f"{prefix}/{raster_string}/{width_height_string}/{width_offset_string}/{height_offset_string}.+",
            )
            tile_as_dict = re.match(regex_str, tile_ifp)
            if tile_as_dict is None:
                return None
            width_height_str = tile_as_dict["width_height"]
            width_height_str_list = width_height_str.split("_")
            width = int(width_height_str_list[0])
            height = int(width_height_str_list[1])
            raster_name = tile_as_dict["raster_name"]
            width_offset = int(tile_as_dict["width_offset"])
            height_offset = int(tile_as_dict["height_offset"])
            tile = ImagePixelTile(
                raster_name, width_offset, height_offset, width, height
            )
        else:
            assert False
        tile.set_tile_fp(tile_ifp, is_absolute=True, root_dp=root_idp)
        return tile
