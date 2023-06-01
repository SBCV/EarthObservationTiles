import copy
import os
import json
import rasterio
from collections import OrderedDict
from varname import nameof
from eot.tiles.tiling_info import RasterTilingInfo
from eot.tiles.tiling_statistic import TilingInfoStatistic
from eot.tiles.tile_manager import TileManager
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles import tiling_scheme as tiling_scheme_module
from eot.tiles.structured_representation import StructuredRepresentation
from eot.utility.quantity import unit_reg


class RasterTilingResult(StructuredRepresentation):
    def __init__(
        self,
        raster_fp,
        tiling_info=None,
        tiles=None,
        disk_tile_size_int=None,
        tiling_statistic=None,
        raster_crs=None,
        raster_transform=None,
        raster_width=None,
        raster_height=None,
        **kwargs,
    ):
        if isinstance(tiling_info, dict):
            tiling_info = RasterTilingInfo.from_dict(tiling_info)
        if tiling_info is not None:
            assert isinstance(tiling_info, RasterTilingInfo)

        if isinstance(tiling_statistic, dict):
            tiling_statistic = TilingInfoStatistic.from_dict(tiling_statistic)
        if tiling_statistic is not None:
            assert isinstance(tiling_statistic, TilingInfoStatistic)

        self.raster_fp = raster_fp
        self.raster_crs = raster_crs
        # This check is necessary, since rasterio.Affine inherits from tuple
        if not isinstance(raster_transform, rasterio.Affine):
            if isinstance(raster_transform, list) or isinstance(
                raster_transform, tuple
            ):
                raster_transform = rasterio.Affine(*raster_transform)
            else:
                raise NotImplementedError
        self.raster_transform = raster_transform
        self.raster_width = raster_width
        self.raster_height = raster_height

        # Size is defined in (x,y) order
        self._disk_tile_size_int = None
        if disk_tile_size_int is not None:
            self.disk_tile_size_int = disk_tile_size_int
        if tiles is None:
            tiles = []
        self.tiles = tiles
        self.tiling_info = tiling_info
        self.tiling_statistic = tiling_statistic

    @property
    def raster_fn(self):
        return os.path.basename(self.raster_fp)

    @property
    def raster_name(self):
        return os.path.splitext(self.raster_fn)[0]

    @property
    def disk_tile_size_int(self):
        return self._disk_tile_size_int

    @disk_tile_size_int.setter
    def disk_tile_size_int(self, tile_size):
        self._disk_tile_size_int = unit_reg.Quantity(tile_size, unit_reg.pixel)

    @property
    def disk_tile_size_x_int(self):
        return self.disk_tile_size_int[0]

    @property
    def disk_tile_size_y_int(self):
        return self.disk_tile_size_int[1]

    def init_tiling_statistic_from(
        self, raster, tiles, disk_tile_size_x, disk_tile_size_y
    ):
        self.tiling_statistic = TilingInfoStatistic.init_from(
            raster, tiles, disk_tile_size_x, disk_tile_size_y
        )

    def to_object_dict(self, include_properties=False):
        object_dict = super().to_object_dict(include_properties)
        object_dict = copy.deepcopy(object_dict)
        # Add the raster file name and add it to front
        object_dict[nameof(self.raster_fn)] = self.raster_fn
        object_dict.move_to_end(nameof(self.raster_fn), last=False)
        # Remove tiles from the dictionary to maintain clarity
        del object_dict[nameof(self.tiles)]
        return object_dict


class RasterTilingResults(StructuredRepresentation):
    def __init__(
        self,
        raster_tiling_result_list=None,
        tiling_scheme=None,
        statistic_summary=None,
    ):
        if isinstance(tiling_scheme, dict):
            tiling_scheme_class_str = tiling_scheme["name"]
            tiling_scheme_class = getattr(
                tiling_scheme_module, tiling_scheme_class_str
            )
            tiling_scheme = tiling_scheme_class.from_dict(tiling_scheme)
        self.tiling_scheme = tiling_scheme

        if isinstance(raster_tiling_result_list, list):
            raster_tiling_result_list_converted = []
            for raster_tiling_result in raster_tiling_result_list:
                if isinstance(raster_tiling_result, dict):
                    raster_tiling_result = RasterTilingResult.from_dict(
                        raster_tiling_result
                    )
                    raster_tiling_result_list_converted.append(
                        raster_tiling_result
                    )
            raster_tiling_result_list = raster_tiling_result_list_converted
        self.raster_tiling_result_list = raster_tiling_result_list

        if isinstance(statistic_summary, dict):
            statistic_summary = TilingInfoStatistic.from_dict(
                statistic_summary
            )
        self.statistic_summary = statistic_summary

        if self.raster_tiling_result_list is None:
            self.raster_tiling_result_list = []

    @classmethod
    def get_from_dir(cls, idp, cover=None, target_raster_name=None):
        tiling_fp = TilePathManager.get_tiling_json_fp_from_dir(idp)
        raster_tiling_results = cls.from_json_file(tiling_fp)
        raster_tiling_results.tiles = TileManager.read_tiles_from_dir(
            idp, cover=cover, target_raster_name=target_raster_name
        )
        return raster_tiling_results

    @property
    def tiles(self):
        for raster_tiling_result in self.raster_tiling_result_list:
            for tile in raster_tiling_result.tiles:
                yield tile

    @tiles.setter
    def tiles(self, tiles):
        raster_name_to_raster_results = OrderedDict(
            (raster_tiling_result.raster_name, raster_tiling_result)
            for raster_tiling_result in self.raster_tiling_result_list
        )
        for tile in tiles:
            raster_name_to_raster_results[tile.get_raster_name()].tiles.append(
                tile
            )

    def add_raster_tiling_result(self, raster_tiling_result):
        assert isinstance(raster_tiling_result, RasterTilingResult)
        self.raster_tiling_result_list.append(raster_tiling_result)

    def get_raster_tiling_result(self, raster_name):
        found = False
        target_result = None
        for raster_tiling_result in self.raster_tiling_result_list:
            if raster_tiling_result.raster_name == raster_name:
                assert not found, "Name of raster tiling result is not unique!"
                target_result = raster_tiling_result
                found = True
        return target_result

    @property
    def raster_names(self):
        raster_names = [
            raster_tiling_result.raster_name
            for raster_tiling_result in self.raster_tiling_result_list
        ]
        return raster_names

    def compute_statistic_summary(self):
        tiling_statistic_list = [
            raster_tiling_result.tiling_statistic
            for raster_tiling_result in self.raster_tiling_result_list
            if raster_tiling_result.tiling_statistic is not None
        ]
        if tiling_statistic_list:
            self.statistic_summary = sum(tiling_statistic_list)
            self.statistic_summary.compute_avg_min_max(add_ratio_comment=True)
        else:
            self.statistic_summary = None

    def write_as_json(self, spatial_info_json_ofp, compute_summary=False):
        with open(spatial_info_json_ofp, "w") as ratio_json_file:
            if compute_summary:
                self.compute_statistic_summary()
            json_dict = self.to_plain_dict()
            json.dump(json_dict, ratio_json_file, indent=4)

    def write_as_txt(self, spatial_info_txt_ofp):
        with open(spatial_info_txt_ofp, "w") as ratio_file:
            lines = self.tiling_scheme.to_lines()
            ratio_file.writelines(lines)

            for raster_tiling_result in self.raster_tiling_result_list:
                ratio_file.write("\n")
                raster_tiling_result_lines = raster_tiling_result.to_lines()
                ratio_file.writelines(raster_tiling_result_lines)

            if self.statistic_summary:
                ratio_file.write("\n")
                lines = self.statistic_summary.to_lines()
                ratio_file.writelines(lines)
