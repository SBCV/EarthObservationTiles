import os
import math
import mercantile

from eot.utility.log import Logs
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.tiling_info import RasterTilingInfo
from eot.tiles.tiling_result import RasterTilingResult
from eot.tiles.tiling_scheme import LocalImagePixelSizeTilingScheme
from eot.tiles.tile_alignment import TileAlignment


class Tiler:
    @staticmethod
    def compute_mercator_tiles(raster, tiling_scheme):
        zoom_level = tiling_scheme.get_zoom_level()
        w, s, e, n = raster.get_bounds_epsg_4326()
        tiles = [
            MercatorTile(x=x, y=y, z=z)
            for x, y, z in mercantile.tiles(w, s, e, n, zoom_level)
        ]
        raster_transform, raster_crs = raster.get_geo_transform_with_crs()
        raster_tiling_result = RasterTilingResult(
            tiles=tiles,
            tiling_info=RasterTilingInfo(tiling_scheme=tiling_scheme),
            raster_fp=raster.name,
            raster_crs=raster_crs,
            raster_transform=raster_transform,
            raster_width=raster.width,
            raster_height=raster.height,
        )
        return raster_tiling_result

    @classmethod
    def _compute_num_tiles_float(
        cls, raster_size_int, tile_size_int, tile_stride_float
    ):
        # In the following formula tile_stride - tile_size adapt the raster
        # extent that is considered for tiling, i.e. it is a correction value
        # that trims / pads the raster image.
        num_tiles_float = (
            raster_size_int + tile_stride_float - tile_size_int
        ) / tile_stride_float
        return num_tiles_float

    @classmethod
    def _compute_num_tiles_int(
        cls,
        area_size_int,
        tile_size_int,
        tile_stride_float,
        convert_num_tiles_to_int,
    ):
        num_tiles_float = cls._compute_num_tiles_float(
            area_size_int, tile_size_int, tile_stride_float
        )
        num_tiles_int = convert_num_tiles_to_int(num_tiles_float)
        # Ensure a positive return value
        num_tiles_int = max(num_tiles_int, 0)
        return num_tiles_int

    @classmethod
    def _compute_tiled_area_float(
        cls, num_tiles, tile_size_int, tile_stride_float
    ):
        tiled_area_float = (
            num_tiles * tile_stride_float + tile_size_int - tile_stride_float
        )
        return tiled_area_float

    @staticmethod
    def count_num_tiles(
        image_extent: int,
        tile_size: int,
        tile_stride: int,
    ):
        num_tiles = 0
        tile_min_pix = 0
        tile_max_pix = tile_size - 1
        image_max_pix = image_extent - 1
        while tile_max_pix <= image_max_pix:
            num_tiles += 1
            tile_min_pix += tile_stride
            tile_max_pix += tile_stride
        return num_tiles

    @classmethod
    def _check_num_tiles(
        cls,
        num_tiles,
        tile_size_int,
        tile_stride_float,
        raster_width_or_height,
    ):
        num_tiles_counted = cls.count_num_tiles(
            raster_width_or_height, tile_size_int, tile_stride_float
        )
        if num_tiles != num_tiles_counted:
            Logs.sinfo(
                f"num_tiles: {num_tiles} vs. num_tiles_counted: {num_tiles_counted}"
            )
            assert False

    @classmethod
    def _compute_tiling_origin_int(
        cls,
        raster_size_int,
        tile_size_int,
        tile_stride_float,
        tile_alignment,
        convert_num_tiles_to_int,
        convert_offset_to_int,
    ):
        num_tiles_int = cls._compute_num_tiles_int(
            raster_size_int,
            tile_size_int,
            tile_stride_float,
            convert_num_tiles_to_int,
        )
        assert num_tiles_int >= 1
        tiled_area_float = cls._compute_tiled_area_float(
            num_tiles_int, tile_size_int, tile_stride_float
        )
        if tile_alignment == TileAlignment.centered_to_image.value:
            tiling_scheme_origin_int = convert_offset_to_int(
                raster_size_int / 2
            )
        elif tile_alignment == TileAlignment.optimized.value:
            remaining_float = raster_size_int - tiled_area_float
            tiling_scheme_origin_int = convert_offset_to_int(
                remaining_float / 2
            )
        elif tile_alignment == TileAlignment.aligned_to_image_border:
            tiling_scheme_origin_int = 0
        else:
            assert False
        return tiling_scheme_origin_int

    @classmethod
    def _split_raster_wrt_origin(
        cls, raster_size_int, tiling_scheme_origin_int
    ):
        negative_area_int = tiling_scheme_origin_int
        positive_area_int = raster_size_int - tiling_scheme_origin_int
        return negative_area_int, positive_area_int

    @classmethod
    def _compute_num_negative_positive_tiles(
        cls,
        raster_size_int,
        tiling_scheme_origin_int,
        tile_size_int,
        tile_stride_float,
        convert_num_tiles_to_int,
    ):
        negative_area_int, positive_area_int = cls._split_raster_wrt_origin(
            raster_size_int, tiling_scheme_origin_int
        )
        num_positive_tiles_int = cls._compute_num_tiles_int(
            positive_area_int,
            tile_size_int,
            tile_stride_float,
            convert_num_tiles_to_int,
        )
        # NB: Counting the number of negative / positives tiles is
        #  asymmetrical, because the tile offset is always represented by the
        #  upper-left pixel position.
        #  Consider the following example, where the stride in x-direction s_x
        #  is equal to a third of the tile size in x-direction t_x
        #  (i.e. s_x = 1/3 t_x). In this case there is already another tile in
        #  the negative area, if there are 1/3 of the tile size t_x (in pixels)
        #  left of the tiling scheme origin. 2/3 of the tile are located in the
        #  positive tiling area.
        redundant_covered_area = min(
            tile_size_int - tile_stride_float, positive_area_int
        )
        enhanced_negative_area_int = negative_area_int + redundant_covered_area
        num_negative_tiles_int = cls._compute_num_tiles_int(
            enhanced_negative_area_int,
            tile_size_int,
            tile_stride_float,
            convert_num_tiles_to_int,
        )
        # NB: 0 negative tiles are allowed
        assert num_negative_tiles_int >= 0, f"{num_negative_tiles_int}"
        assert num_positive_tiles_int > 0, f"{num_positive_tiles_int}"
        return num_negative_tiles_int, num_positive_tiles_int

    @classmethod
    def _compute_negative_positive_area(
        cls,
        num_negative_tiles_int,
        num_positive_tiles_int,
        tile_size_int,
        tile_stride_float,
    ):
        negative_area_float = cls._compute_tiled_area_float(
            num_negative_tiles_int, tile_size_int, tile_stride_float
        )
        positive_area_float = cls._compute_tiled_area_float(
            num_positive_tiles_int, tile_size_int, tile_stride_float
        )
        return negative_area_float, positive_area_float

    @classmethod
    def compute_tiling_scheme_layout(
        cls,
        tile_size_float,
        raster_size_int,
        tile_stride_float,
        tile_alignment,
        align_to_base_tile_area,
        overhang,
        log_prefix,
    ):
        if overhang:
            convert_num_tiles_to_int = math.ceil
        else:
            convert_num_tiles_to_int = math.floor

        convert_offset_to_int = math.floor
        tile_size_int = int(tile_size_float)

        if align_to_base_tile_area:
            tile_stride_width_ratio = round(tile_size_int / tile_stride_float)
            base_tile_stride_float = (
                tile_stride_float * tile_stride_width_ratio
            )
            tiling_scheme_origin_int = cls._compute_tiling_origin_int(
                raster_size_int,
                tile_size_int,
                base_tile_stride_float,
                tile_alignment,
                convert_num_tiles_to_int=convert_num_tiles_to_int,
                convert_offset_to_int=convert_offset_to_int,
            )
        else:
            tiling_scheme_origin_int = cls._compute_tiling_origin_int(
                raster_size_int,
                tile_size_int,
                tile_stride_float,
                tile_alignment,
                convert_num_tiles_to_int=convert_num_tiles_to_int,
                convert_offset_to_int=convert_offset_to_int,
            )

        (
            num_negative_tiles_int,
            num_positive_tiles_int,
        ) = cls._compute_num_negative_positive_tiles(
            raster_size_int,
            tiling_scheme_origin_int,
            tile_size_int,
            tile_stride_float,
            convert_num_tiles_to_int=convert_num_tiles_to_int,
        )
        (
            negative_tiling_area_float,
            positive_tiling_area_float,
        ) = cls._compute_negative_positive_area(
            num_negative_tiles_int,
            num_positive_tiles_int,
            tile_size_int,
            tile_stride_float,
        )

        # Rounding relative_tile_offset_float could lead to tiles with
        #  different relative offsets. Thus, use floor or ceil
        assert convert_offset_to_int in [math.floor, math.ceil]

        # Compute negative tile offsets: subtract from origin, and shift index
        tile_offset_negative_int_list = []
        for idx in range(num_negative_tiles_int):
            relative_tile_offset_float = (idx + 1) * tile_stride_float
            relative_tile_offset_int = convert_offset_to_int(
                relative_tile_offset_float
            )
            offset_negative_int = (
                tiling_scheme_origin_int - relative_tile_offset_int
            )
            tile_offset_negative_int_list.append(offset_negative_int)

        # Compute positive tile offsets: add to origin
        tile_offset_positive_int_list = []
        for idx in range(num_positive_tiles_int):
            relative_tile_offset_float = idx * tile_stride_float
            relative_tile_offset_int = convert_offset_to_int(
                relative_tile_offset_float
            )
            offset_positive_int = (
                tiling_scheme_origin_int + relative_tile_offset_int
            )
            tile_offset_positive_int_list.append(offset_positive_int)

        # duplicate_offsets = set(tile_offset_negative_int_list).intersection(
        #     set(tile_offset_positive_int_list)
        # )
        # assert len(duplicate_offsets) == 0
        offset_int_list = (
            tile_offset_negative_int_list + tile_offset_positive_int_list
        )

        Logs.sinfo(f"{log_prefix}overhang: {overhang}")
        Logs.sinfo(f"{log_prefix}tile_size_int: {tile_size_int}")
        Logs.sinfo(f"{log_prefix}tile_stride: {tile_stride_float}")
        # fmt:off
        Logs.sinfo(f"{log_prefix}num_negative_tiles_int: {num_negative_tiles_int}")
        Logs.sinfo(f"{log_prefix}num_positive_tiles_int: {num_positive_tiles_int}")
        Logs.sinfo(f"{log_prefix}negative_tiling_area_float: {negative_tiling_area_float}")
        Logs.sinfo(f"{log_prefix}positive_tiling_area_float: {positive_tiling_area_float}")
        Logs.sinfo(f"{log_prefix}tiling_scheme_origin_int: {tiling_scheme_origin_int}")
        Logs.sinfo(f"{log_prefix}tile_offset_negative_int_list: {tile_offset_negative_int_list}")
        Logs.sinfo(f"{log_prefix}tile_offset_positive_int_list: {tile_offset_positive_int_list}")
        # fmt:on

        return tile_size_int, tiling_scheme_origin_int, offset_int_list

    @classmethod
    def compute_raster_local_tiles_with_pixel_size(
        cls,
        raster,
        tiling_scheme,
    ):
        (
            tile_size_x_float,
            tile_size_y_float,
        ) = tiling_scheme.get_tile_size_in_pixel(True)
        (
            tile_stride_x_float,
            tile_stride_y_float,
        ) = tiling_scheme.get_tile_stride_in_pixel(True)
        tile_alignment = tiling_scheme.get_alignment()
        align_to_base_tile_area = tiling_scheme.is_aligned_to_base_tile_area()
        tile_overhang = tiling_scheme.uses_overhanging_tiles()

        Logs.sinfo("---")
        Logs.sinfo("Tiling info:")
        Logs.sinfo(f"raster.width: {raster.width}")
        Logs.sinfo(f"raster.height: {raster.height}")
        Logs.sinfo(f"tile_alignment: {tile_alignment}")
        Logs.sinfo(f"align_to_base_tile_area: {align_to_base_tile_area}")
        (
            tile_size_x_int,
            tiling_scheme_origin_x_int,
            source_offset_x_int_list,
        ) = cls.compute_tiling_scheme_layout(
            tile_size_x_float,
            raster.width,
            tile_stride_x_float,
            tile_alignment,
            align_to_base_tile_area,
            tile_overhang,
            log_prefix="x_",
        )
        (
            tile_size_y_int,
            tiling_scheme_origin_y_int,
            source_offset_y_int_list,
        ) = cls.compute_tiling_scheme_layout(
            tile_size_y_float,
            raster.height,
            tile_stride_x_float,
            tile_alignment,
            align_to_base_tile_area,
            tile_overhang,
            log_prefix="y_",
        )
        Logs.sinfo("---")

        tiles = []
        transform, crs = raster.get_geo_transform_with_crs(
            check_validity=False
        )

        for source_offset_x_int in source_offset_x_int_list:
            for source_offset_y_int in source_offset_y_int_list:
                raster_name = os.path.splitext(os.path.basename(raster.name))[
                    0
                ]
                tile = ImagePixelTile(
                    raster_name=raster_name,
                    source_x_offset=source_offset_x_int,
                    source_y_offset=source_offset_y_int,
                    source_width=tile_size_x_int,
                    source_height=tile_size_y_int,
                    raster_transform=transform,
                    raster_crs=crs,
                )
                tiles.append(tile)

        # print("num_tiles_x", num_tiles_x)
        # print("num_tiles_y", num_tiles_y)
        # for tile in tiles:
        #     print("tile", tile)
        tiling_info = RasterTilingInfo(
            tiling_source_offset_int=(
                tiling_scheme_origin_x_int,
                tiling_scheme_origin_y_int,
            ),
            tiling_source_stride_float=(
                tile_stride_x_float,
                tile_stride_y_float,
            ),
            tiling_source_size_int=(tile_size_x_int, tile_size_y_int),
            tiling_scheme=tiling_scheme,
        )
        raster_transform, raster_crs = raster.get_geo_transform_with_crs()
        tiling_result = RasterTilingResult(
            raster_fp=raster.name,
            tiling_info=tiling_info,
            tiles=tiles,
            tiling_statistic=None,
            raster_crs=raster_crs,
            raster_transform=raster_transform,
            raster_width=raster.width,
            raster_height=raster.height,
        )
        return tiling_result

    @classmethod
    def compute_raster_local_tiles_with_meter_size(
        cls,
        raster,
        meter_tiling_scheme,
    ):
        (
            pixel_tiling_scheme
        ) = LocalImagePixelSizeTilingScheme.from_local_image_meter_size_tiling_scheme(
            meter_tiling_scheme, raster.get_meter_as_pixel
        )
        tiling_result = cls.compute_raster_local_tiles_with_pixel_size(
            raster,
            pixel_tiling_scheme,
        )
        # Overwrite the tiling_scheme
        tiling_result.tiling_info.tiling_scheme = meter_tiling_scheme
        return tiling_result

    @classmethod
    def compute_tiling(
        cls,
        raster,
        tiling_scheme,
    ):
        if tiling_scheme.represents_mercator_tiling():
            # Spherical mercator tiles (as in Google Maps, OSM, Mapbox, etc.)
            # https://mercantile.readthedocs.io/en/latest/quickstart.html
            tiling_result = cls.compute_mercator_tiles(raster, tiling_scheme)
        elif tiling_scheme.is_in_pixel():
            tiling_result = cls.compute_raster_local_tiles_with_pixel_size(
                raster, tiling_scheme
            )
        elif tiling_scheme.is_in_meter():
            tiling_result = cls.compute_raster_local_tiles_with_meter_size(
                raster, tiling_scheme
            )
        else:
            assert False, f"Unsupported tile type {tiling_scheme}"
        return tiling_result
