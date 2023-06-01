from eot.tiles.structured_representation import StructuredRepresentation
from varname import nameof
from eot.utility.quantity import unit_reg
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile


class AverageMinMax:
    def __init__(self, average_value, min_value, max_value):
        self.average_value = average_value
        self.min_value = min_value
        self.max_value = max_value
        self.comment = None

    @classmethod
    def from_sequence(cls, values, add_interval_comment=False):
        if not values:
            return cls(None, None, None)
        average_value = sum(values) / len(values)
        new_amm = cls(average_value, min(values), max(values))
        if add_interval_comment:
            new_amm.add_interval_comment()
        return new_amm

    def __repr__(self):
        return f"{self.average_value:.2f} [{self.min_value:.2f}-{self.max_value:.2f}]"

    def add_interval_comment(self):
        if self.min_value is not None and self.max_value is not None:
            low_relative = self.average_value - self.min_value
            up_relative = self.max_value - self.average_value
            comment = f"relative deviation: (-{low_relative:.2f} / +{up_relative:.2f})"
        else:
            comment = ""
        self.comment = comment


class TilingInfoStatistic(StructuredRepresentation):
    def __init__(
        self,
        tile_real_world_extent_amm=None,
        tile_source_width_amm=None,
        tile_source_height_amm=None,
        tile_width_ratio_amm=None,
        tile_height_ratio_amm=None,
    ):
        self._tile_real_world_extents = []
        self._tile_source_widths = []
        self._tile_source_heights = []
        self._tile_width_ratios = []
        self._tile_height_ratios = []

        # AMM = Average, Min, Max
        self._tile_real_world_extent_amm = tile_real_world_extent_amm
        self._tile_source_width_amm = tile_source_width_amm
        self._tile_source_height_amm = tile_source_height_amm
        self._tile_width_ratio_amm = tile_width_ratio_amm
        self._tile_height_ratio_amm = tile_height_ratio_amm

    def __add__(self, other):
        # Required for sum([...])
        if other == 0:
            other = TilingInfoStatistic()

        attribute_list = [
            attr
            for attr in dir(self)
            if not attr.startswith("__")
            and not attr.endswith("_amm")
            and not callable(getattr(self, attr))
        ]
        res = TilingInfoStatistic()
        for attr in attribute_list:
            setattr(res, attr, getattr(self, attr) + getattr(other, attr))
        return res

    def __radd__(self, other):
        # Required for sum([...])
        return self.__add__(other)

    @classmethod
    def init_from(
        cls,
        raster,
        tiles,
        disk_tile_size_x_int,
        disk_tile_size_y_int,
    ):
        tiling_statistic = cls()
        for tile in tiles:
            extent = cls._compute_tile_extent_in_local_crs(raster, tile)
            source_width, source_height = cls._compute_tile_size(raster, tile)

            tiling_statistic.add_tile_real_world_extent(extent)
            tiling_statistic.add_tile_source_width(source_width)
            tiling_statistic.add_tile_source_height(source_height)
            tiling_statistic.add_tile_width_ratio(
                disk_tile_size_x_int / source_width
            )
            tiling_statistic.add_tile_height_ratio(
                disk_tile_size_y_int / source_height
            )

        tiling_statistic.compute_avg_min_max(add_ratio_comment=True)
        return tiling_statistic

    @staticmethod
    def _compute_tile_extent_in_local_crs(raster, tile):
        (
            dist_l_r_in_meter,
            dist_t_b_in_meter,
        ) = raster.compute_tile_size_in_meter(tile)
        tile_extent_meter = (dist_l_r_in_meter + dist_t_b_in_meter) / 2
        return tile_extent_meter

    @staticmethod
    def _compute_tile_size(raster, tile):
        if isinstance(tile, MercatorTile):
            (
                source_width,
                source_height,
            ) = raster.compute_tile_size_in_source_pixel(tile)
        elif isinstance(tile, ImagePixelTile):
            source_width, source_height = tile.get_source_size()
        else:
            assert False
        return source_width, source_height

    def add_tile_real_world_extent(self, extent):
        extent = unit_reg.Quantity(extent, unit_reg.meter)
        self._tile_real_world_extents.append(extent)

    def add_tile_source_width(self, source_width):
        source_width = unit_reg.Quantity(source_width, unit_reg.pixel)
        self._tile_source_widths.append(source_width)

    def add_tile_source_height(self, source_height):
        source_height = unit_reg.Quantity(source_height, unit_reg.pixel)
        self._tile_source_heights.append(source_height)

    def add_tile_width_ratio(self, width_ratio):
        self._tile_width_ratios.append(width_ratio)

    def add_tile_height_ratio(self, height_ratio):
        self._tile_height_ratios.append(height_ratio)

    @property
    def tile_real_world_extent_amm(self):
        return self._tile_real_world_extent_amm

    @property
    def tile_source_width_amm(self):
        return self._tile_source_width_amm

    @property
    def tile_source_height_amm(self):
        return self._tile_source_height_amm

    @property
    def tile_width_ratio_amm(self):
        return self._tile_width_ratio_amm

    @property
    def tile_height_ratio_amm(self):
        return self._tile_height_ratio_amm

    @staticmethod
    def _create_ratio_comment(average_value):
        if average_value is None:
            comment = ""
        elif average_value < 0.5:
            comment = f"(ratio < 0.5 (neglecting majority of tile data), consider to decrease tile source size)"  # noqa
        elif average_value > 1:
            comment = f"(ratio > 1.0 (tile data is getting blurred), consider to increase tile source size)"  # noqa
        else:
            comment = ""
        return comment

    def compute_avg_min_max(self, add_ratio_comment):
        self._tile_real_world_extent_amm = AverageMinMax.from_sequence(
            self._tile_real_world_extents, add_interval_comment=True
        )
        self._tile_source_width_amm = AverageMinMax.from_sequence(
            self._tile_source_widths, add_interval_comment=True
        )
        self._tile_source_height_amm = AverageMinMax.from_sequence(
            self._tile_source_heights, add_interval_comment=True
        )

        self._tile_width_ratio_amm = AverageMinMax.from_sequence(
            self._tile_width_ratios, add_interval_comment=True
        )
        self._tile_height_ratio_amm = AverageMinMax.from_sequence(
            self._tile_height_ratios, add_interval_comment=True
        )

        if add_ratio_comment:
            width_ratio_comment = self._create_ratio_comment(
                self._tile_width_ratio_amm.average_value
            )
            if width_ratio_comment:
                self._tile_width_ratio_amm.comment += (
                    f", {width_ratio_comment}"
                )
            height_ratio_comment = self._create_ratio_comment(
                self._tile_height_ratio_amm.average_value
            )
            if height_ratio_comment:
                self._tile_height_ratio_amm.comment += (
                    f", {height_ratio_comment}"
                )

    def to_object_dict(self, include_properties=False):
        include_attr_list = [
            nameof(self._tile_real_world_extent_amm),
            nameof(self._tile_source_width_amm),
            nameof(self._tile_source_height_amm),
            nameof(self._tile_width_ratio_amm),
            nameof(self._tile_height_ratio_amm),
        ]
        selected_obj_dict = self._to_object_dict(
            include_properties=include_properties,
            include_attr_list=include_attr_list,
        )
        return selected_obj_dict
