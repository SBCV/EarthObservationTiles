import os
import math
import mercantile

from eot.core.log import Logs
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile


class TilingInfo:
    def __init__(
        self,
        tiling_offset_x_int=None,
        tiling_offset_y_int=None,
        tile_stride_x_float=None,
        tile_stride_y_float=None,
    ):
        self.tiling_offset_x_int = tiling_offset_x_int
        self.tiling_offset_y_int = tiling_offset_y_int
        self.tile_stride_x_float = tile_stride_x_float
        self.tile_stride_y_float = tile_stride_y_float


class Tiler:
    @staticmethod
    def compute_mercator_tiles(raster, zoom):
        w, s, e, n = raster.get_bounds_epsg_4326()
        tiles = [
            MercatorTile(x=x, y=y, z=z)
            for x, y, z in mercantile.tiles(w, s, e, n, zoom)
        ]
        return tiles

    @classmethod
    def _compute_num_tiles(
        cls, raster_extent, tile_stride_float, tile_extent_int
    ):
        # In the following formula tile_stride - tile_extent adapt the raster
        # extent that is considered for tiling, i.e. it is a correction value
        # that trims / pads the raster image.
        num_tiles_exact = (
            raster_extent + tile_stride_float - tile_extent_int
        ) / tile_stride_float
        return num_tiles_exact

    @classmethod
    def _compute_tiled_area(cls, num_tiles, tile_stride_float, tile_size_int):
        tiled_area = (
            num_tiles * tile_stride_float + tile_size_int - tile_stride_float
        )
        return tiled_area

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
    def _compute_num_tiles_and_area(
        cls,
        raster_width_or_height,
        tile_stride_float,
        tile_size_int,
        centered,
        convert_num_tiles_to_int,
        convert_offset_to_int,
    ):
        num_tiles_float = cls._compute_num_tiles(
            raster_width_or_height, tile_stride_float, tile_size_int
        )
        num_tiles_int = convert_num_tiles_to_int(num_tiles_float)
        assert num_tiles_int >= 1
        tiled_area_float = cls._compute_tiled_area(
            num_tiles_int, tile_stride_float, tile_size_int
        )
        if centered:
            remaining_float = raster_width_or_height - tiled_area_float
            tiled_area_offset_int = convert_offset_to_int(remaining_float / 2)
        else:
            tiled_area_offset_int = 0
        return num_tiles_int, tiled_area_float, tiled_area_offset_int

    @classmethod
    def _check_non_overhanging_tiled_area(
        cls,
        base_tiled_area_offset_int,
        base_tiled_area_float,
        all_tiled_area_float,
        tile_stride_float,
        raster_extent,
    ):
        # Motivation: The area covered by overlapping tiles must be at least
        #  as large as the area covered by the base tiles. At the same time the
        #  overlapping tiles must not exceed the raster boundaries.
        #  Other results are caused by numerical precision artifacts of
        #  `cls._compute_num_tiles_and_area()`.

        remaining_area_int = raster_extent - base_tiled_area_offset_int
        if not all_tiled_area_float <= remaining_area_int:
            msg = f"remaining_area_int vs all_tiled_area_float: {remaining_area_int} vs {all_tiled_area_float}"
            Logs.sinfo(msg)
            assert False

        diff = all_tiled_area_float - base_tiled_area_float
        # https://stackoverflow.com/questions/12754680/modulo-operator-in-python
        remainder = math.fmod(diff, tile_stride_float)
        if not math.isclose(remainder, 0):
            msg = f"base_tiled_area_float vs all_tiled_area_float: {base_tiled_area_float} vs {all_tiled_area_float}"
            Logs.sinfo(msg)
            assert False

    @classmethod
    def compute_tiling_scheme_layout(
        cls,
        tile_size_float,
        raster_extent,
        tile_stride_float,
        centered,
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

        if not align_to_base_tile_area:
            (
                num_tiles_int,
                tiled_area_float,
                tiled_area_offset_int,
            ) = cls._compute_num_tiles_and_area(
                raster_extent,
                tile_stride_float,
                tile_size_int,
                centered,
                convert_num_tiles_to_int=convert_num_tiles_to_int,
                convert_offset_to_int=convert_offset_to_int,
            )

        else:
            # 1. Compute the base tile layout
            tile_stride_width_ratio = round(tile_size_int / tile_stride_float)
            base_tile_stride_float = (
                tile_stride_float * tile_stride_width_ratio
            )
            (
                base_num_tiles_int,
                base_tiled_area_float,
                base_tiled_area_offset_int,
            ) = cls._compute_num_tiles_and_area(
                raster_extent,
                base_tile_stride_float,
                tile_size_int,
                centered,
                convert_num_tiles_to_int=convert_num_tiles_to_int,
                convert_offset_to_int=convert_offset_to_int,
            )
            # 2. Use the information of the base tile layout to align / define
            #  the current (potentially overlapping) tiles
            if overhang:
                # In this case it is sufficient to restrict the tiling to the
                #  base tiling area, since the base tiling already contains the
                #  full image data.
                tiling_extent = base_tiled_area_float
            else:
                # In this case there is (potentially) additional image data
                #  outside the base tiling, which we can use during tiling.
                #
                # If the tiling scheme is centered w.r.t. the image, there is
                #  an area outside the tiling scheme (left and right or top and
                #  bottom) with `outside_area < tile_size_int / 2`. Thus,
                #  additional tiles this area exist only if
                #  `tile_stride_float < tile_size_int / 2`. This, is true for
                #  `tile_stride_float := tile_size_int / x` with `x >= 3` and
                #  x describing the `tile_stride_width_ratio`.
                #
                # If there are tiles left of or above of the base tiling scheme
                #  the definition of a new aligned tiling scheme becomes tricky
                #  because of floating number inaccuracies.
                # Consider the following:
                #  Option 1:
                #   Definition of a tiling offset left / top of the base
                #   tiling offset shifted by a multiple of the stride size.
                #   Because of floating inaccuracies the subsequent tiles are
                #   potentially no longer aligned with the base tile scheme.
                #  Option 2:
                #   Use the base tiling scheme offset as origin in a coordinate
                #   system. Then, tiles left / top must be treated differently
                #   than tiles to the right / bottom. This introduces
                #   additional complexity.
                #
                # Since such cases (tile_stride_width_ratio >= 3) is not
                #  crucial while substituting semantic segmentations, the
                #  current implementation supports only tile strides with
                #  tile_stride_width_ratio < 3.
                assert tile_stride_width_ratio <= 2
                # In the case of `tile_stride_width_ratio <= 2` there are no
                #  tiles left or top of the offset. So it is sufficient to
                #  determine the tiles \wrt the right / bottom area (i.e.
                #  `raster_extent - base_tiled_area_offset_int`)
                tiling_extent = raster_extent - base_tiled_area_offset_int
            (
                all_num_tiles_int,
                all_tiled_area_float,
                _,
            ) = cls._compute_num_tiles_and_area(
                tiling_extent,
                tile_stride_float,
                tile_size_int,
                centered=False,
                convert_num_tiles_to_int=convert_num_tiles_to_int,
                convert_offset_to_int=convert_offset_to_int,
            )
            if not overhang:
                cls._check_non_overhanging_tiled_area(
                    base_tiled_area_offset_int,
                    base_tiled_area_float,
                    all_tiled_area_float,
                    tile_stride_float,
                    raster_extent,
                )

            num_tiles_int = all_num_tiles_int
            tiled_area_float = all_tiled_area_float
            tiled_area_offset_int = base_tiled_area_offset_int

        Logs.sinfo(f"{log_prefix}overhang: {overhang}")
        Logs.sinfo(f"{log_prefix}tile_size_int: {tile_size_int}")
        Logs.sinfo(f"{log_prefix}tile_stride: {tile_stride_float}")
        Logs.sinfo(f"{log_prefix}num_tiles: {num_tiles_int}")
        Logs.sinfo(f"{log_prefix}tiled_area_float: {tiled_area_float}")
        Logs.sinfo(f"{log_prefix}tiled_area_offset: {tiled_area_offset_int}")

        return tile_size_int, tiled_area_offset_int, num_tiles_int

    @classmethod
    def compute_raster_local_tiles_with_pixel_size(
        cls,
        raster,
        tile_size_x_float,
        tile_size_y_float,
        tile_stride_x_float,
        tile_stride_y_float,
        centered,
        align_to_base_tile_area=True,
        tile_overhang=False,
    ):
        Logs.sinfo("---")
        Logs.sinfo("Tiling info:")
        Logs.sinfo(f"raster.width: {raster.width}")
        Logs.sinfo(f"raster.height: {raster.height}")
        Logs.sinfo(f"centered: {centered}")
        Logs.sinfo(f"align_to_base_tile_area: {align_to_base_tile_area}")
        (
            tile_size_x_int,
            tiled_area_offset_x_int,
            num_tiles_x,
        ) = cls.compute_tiling_scheme_layout(
            tile_size_x_float,
            raster.width,
            tile_stride_x_float,
            centered,
            align_to_base_tile_area,
            tile_overhang,
            log_prefix="x_",
        )
        (
            tile_size_y_int,
            tiled_area_offset_y_int,
            num_tiles_y,
        ) = cls.compute_tiling_scheme_layout(
            tile_size_y_float,
            raster.height,
            tile_stride_x_float,
            centered,
            align_to_base_tile_area,
            tile_overhang,
            log_prefix="y_",
        )
        Logs.sinfo("---")

        tiles = []
        transform, crs = raster.get_transform_with_crs(check_validity=False)
        for idx_x in range(num_tiles_x):
            for idx_y in range(num_tiles_y):
                raster_name = os.path.splitext(os.path.basename(raster.name))[
                    0
                ]

                source_offset_x_int = tiled_area_offset_x_int + math.floor(
                    idx_x * tile_stride_x_float
                )
                source_offset_y_int = tiled_area_offset_y_int + math.floor(
                    idx_y * tile_stride_y_float
                )

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
        tiling_info = TilingInfo(
            tiling_offset_x_int=tiled_area_offset_x_int,
            tiling_offset_y_int=tiled_area_offset_y_int,
            tile_stride_x_float=tile_stride_x_float,
            tile_stride_y_float=tile_stride_y_float,
        )
        return tiles, tiling_info

    @classmethod
    def compute_raster_local_tiles_with_meter_size(
        cls,
        raster,
        input_tile_size_x_in_meter,
        input_tile_size_y_in_meter,
        input_tile_stride_x_in_meter,
        input_tile_stride_y_in_meter,
        centered,
        align_to_base_tile_area,
        tile_overhang,
    ):
        input_tile_size_x_in_pixel_float = raster.get_meter_as_pixel(
            input_tile_size_x_in_meter
        )
        input_tile_size_y_in_pixel_float = raster.get_meter_as_pixel(
            input_tile_size_y_in_meter
        )
        input_tile_stride_x_in_pixel_float = raster.get_meter_as_pixel(
            input_tile_stride_x_in_meter
        )
        input_tile_stride_y_in_pixel_float = raster.get_meter_as_pixel(
            input_tile_stride_y_in_meter
        )

        return cls.compute_raster_local_tiles_with_pixel_size(
            raster,
            input_tile_size_x_in_pixel_float,
            input_tile_size_y_in_pixel_float,
            input_tile_stride_x_in_pixel_float,
            input_tile_stride_y_in_pixel_float,
            centered=centered,
            align_to_base_tile_area=align_to_base_tile_area,
            tile_overhang=tile_overhang,
        )

    @classmethod
    def get_tiles(
        cls,
        raster,
        tile_type,
        input_tile_zoom_level=None,
        input_tile_size_in_meter=None,
        input_tile_size_in_pixel=None,
        input_tile_stride_in_meter=None,
        input_tile_stride_in_pixel=None,
        align_to_base_tile_area=None,
        tile_overhang=None,
        return_tiling_info=False,
    ):
        assert align_to_base_tile_area is not None
        if tile_type.is_mercator_tile():
            assert input_tile_zoom_level is not None
            # Spherical mercator tiles (as in Google Maps, OSM, Mapbox, etc.)
            # https://mercantile.readthedocs.io/en/latest/quickstart.html
            tiles = cls.compute_mercator_tiles(raster, input_tile_zoom_level)
            tiling_info = TilingInfo()
        elif tile_type.is_in_pixel():
            assert input_tile_size_in_pixel is not None
            (
                input_tile_size_x_in_pixel,
                input_tile_size_y_in_pixel,
            ) = input_tile_size_in_pixel
            if input_tile_stride_in_pixel is None:
                input_tile_stride_in_pixel = input_tile_size_in_pixel
            (
                input_tile_stride_x_in_pixel,
                input_tile_stride_y_in_pixel,
            ) = input_tile_stride_in_pixel
            (
                tiles,
                tiling_info,
            ) = cls.compute_raster_local_tiles_with_pixel_size(
                raster,
                input_tile_size_x_in_pixel,
                input_tile_size_y_in_pixel,
                input_tile_stride_x_in_pixel,
                input_tile_stride_y_in_pixel,
                centered=tile_type.is_centered_to_image(),
                align_to_base_tile_area=align_to_base_tile_area,
                tile_overhang=tile_overhang,
            )
        elif tile_type.is_in_meter():
            assert input_tile_size_in_meter is not None
            (
                input_tile_size_x_in_meter,
                input_tile_size_y_in_meter,
            ) = input_tile_size_in_meter
            if input_tile_stride_in_meter is None:
                input_tile_stride_in_meter = input_tile_size_in_meter
            (
                input_tile_stride_x_in_meter,
                input_tile_stride_y_in_meter,
            ) = input_tile_stride_in_meter
            (
                tiles,
                tiling_info,
            ) = cls.compute_raster_local_tiles_with_meter_size(
                raster,
                input_tile_size_x_in_meter,
                input_tile_size_y_in_meter,
                input_tile_stride_x_in_meter,
                input_tile_stride_y_in_meter,
                centered=tile_type.is_centered_to_image(),
                align_to_base_tile_area=align_to_base_tile_area,
                tile_overhang=tile_overhang,
            )
        else:
            assert False, f"Unsupported tile type {tile_type}"
        if return_tiling_info:
            return tiles, tiling_info
        return tiles

    @classmethod
    def get_tiles_with_disk_size(
        cls,
        raster,
        tile_type,
        tile_disk_width,
        tile_disk_height,
        input_tile_zoom_level=None,
        input_tile_size_in_meter=None,
        input_tile_size_in_pixel=None,
    ):
        tiles = cls.get_tiles(
            raster,
            tile_type,
            input_tile_zoom_level,
            input_tile_size_in_meter,
            input_tile_size_in_pixel,
        )
        for tile in tiles:
            tile.disk_width = tile_disk_width
            tile.disk_height = tile_disk_height
        return tiles
