import glob
import os
import re
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.utility.os_extension import get_subdirs


class TilePathManager:

    WEB_MAP = "web_map"
    IMAGE_PIXEL_TILES = "image_pixel_tiles"

    @classmethod
    def _convert_tile_type_dn_to_tile_type(cls, tile_type_str):
        if tile_type_str == cls.WEB_MAP:
            return MercatorTile
        elif tile_type_str == cls.IMAGE_PIXEL_TILES:
            return ImagePixelTile
        else:
            assert False

    @classmethod
    def get_parent_dir_of_tile_class(cls, tile_class):
        if tile_class == MercatorTile:
            return cls.WEB_MAP
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
    def _get_dataset_tile_types_of_single_dataset(cls, dataset_idp):
        dp_list = []
        tile_dp_list = get_subdirs(dataset_idp)
        for tile_dp in tile_dp_list:
            dp_list.append(os.path.basename(tile_dp))
        return dp_list

    @classmethod
    def _get_dataset_tile_types_of_all_datasets(cls, root_idp):
        dp_list = []
        dataset_dp_list = get_subdirs(root_idp)
        for dataset_dp in dataset_dp_list:
            dp_list.extend(
                cls._get_dataset_tile_types_of_single_dataset(dataset_dp)
            )
        return dp_list

    @classmethod
    def _get_dataset_tile_types(cls, root_idp, is_dataset_dp):
        if is_dataset_dp:
            dataset_tile_types = cls._get_dataset_tile_types_of_single_dataset(
                root_idp
            )
        else:
            dataset_tile_types = cls._get_dataset_tile_types_of_all_datasets(
                root_idp
            )
        return dataset_tile_types

    @classmethod
    def get_tile_type_from_dir(cls, root_idp, is_dataset_dp):
        dataset_tile_type_str_list = cls._get_dataset_tile_types(
            root_idp, is_dataset_dp
        )
        dataset_tile_type_str_list = [
            tile_type
            for tile_type in dataset_tile_type_str_list
            if tile_type in [cls.WEB_MAP, cls.IMAGE_PIXEL_TILES]
        ]
        dataset_tile_type_list = [
            cls._convert_tile_type_dn_to_tile_type(tile_type_str)
            for tile_type_str in dataset_tile_type_str_list
        ]
        if len(dataset_tile_type_list) != 1:
            print(f"dataset_tile_types: {dataset_tile_type_list}")
            assert False
        return dataset_tile_type_list[0]

    @classmethod
    def read_relative_tile_fp_scheme_from_dir(cls, root_idp, is_dataset_dp):
        dataset_tile_types = cls._get_dataset_tile_types(
            root_idp, is_dataset_dp
        )

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
            msg += f' Expected "{cls.WEB_MAP}" or "{cls.IMAGE_PIXEL_TILES}", but found {dataset_tile_types} in {root_idp}!'
            assert False, msg

        if not is_dataset_dp:
            tile_fp_scheme = "*/" + tile_fp_scheme

        return tile_fp_scheme

    @classmethod
    def read_absolute_tile_fp_from_dir(cls, idp, tile):
        relative_fp = cls.get_relative_tile_fp(tile, tile_file_ext=".*")
        tile_fp_list = glob.glob(
            os.path.join(os.path.expanduser(idp), relative_fp)
        )
        if not tile_fp_list:
            return None

        assert len(tile_fp_list) == 1, "ambiguous tile path"
        absolute_fp = tile_fp_list[0]
        return absolute_fp

    @classmethod
    def convert_tile_fp_to_tile(cls, root_idp, tile_ifp, is_dataset_dp):
        dataset_tile_types = cls._get_dataset_tile_types(
            root_idp, is_dataset_dp
        )
        if is_dataset_dp:
            dataset_string = ""
        else:
            dataset_string = "(?P<dataset_name>.+)/"

        if (
            cls.get_parent_dir_of_tile_class(MercatorTile)
            in dataset_tile_types
        ):
            parent_dir = cls.get_parent_dir_of_tile_class(MercatorTile)
            prefix = dataset_string + parent_dir
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
            prefix = dataset_string + parent_dir
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
        if is_dataset_dp:
            # Example:
            #  /path/to/geo_data/train/images/potsdam/local_centered_size_m_50.0_50.0_stride_m_50.0_50.0/image_pixel_tiles
            #  --> root_dp = /path/to/geo_data/train/images/potsdam
            root_dp = os.path.dirname(os.path.dirname(root_idp))
        else:
            root_dp = root_idp
        tile.set_tile_fp(tile_ifp, is_absolute=True, root_dp=root_dp)
        return tile
