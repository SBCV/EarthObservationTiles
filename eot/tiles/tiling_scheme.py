from enum import Enum
from eot.tiles.structured_representation import StructuredRepresentation
from eot.utility.quantity import unit_reg
from eot.tiles.tile_alignment import TileAlignment


def safely_delete_kwargs_value(kwargs, key, value):
    if key in kwargs:
        assert kwargs[key] == value
        del kwargs[key]
    return kwargs


class TilingScheme(StructuredRepresentation):
    def __init__(
        self,
        name=None,
        is_mercator_tile=None,
        is_local_image_tile=None,
        use_border_tiles=None,
        **kwargs,
    ):
        msg = f"{is_mercator_tile} vs {is_local_image_tile}"
        both = bool(is_mercator_tile) and bool(is_local_image_tile)
        assert not both, msg
        if name is None:
            name = self.__class__.__name__
        self.name = name
        self._is_mercator_tile = is_mercator_tile
        self._is_local_image_tile = is_local_image_tile

        self._use_border_tiles = use_border_tiles

    def __str__(self):
        return self.name

    def represents_mercator_tiling(self):
        return bool(self._is_mercator_tile)

    def represents_local_image_tiling(self):
        return bool(self._is_local_image_tile)

    def uses_border_tiles(self):
        return bool(self._use_border_tiles)

    def set_border_tiles_flag(self, use_border_tiles):
        self._use_border_tiles = use_border_tiles


class MercatorTilingScheme(TilingScheme):
    def __init__(self, zoom_level=None, **kwargs):
        kwargs = safely_delete_kwargs_value(
            kwargs, "name", self.__class__.__name__
        )
        kwargs = safely_delete_kwargs_value(kwargs, "is_mercator_tile", True)
        super().__init__(
            name=self.__class__.__name__, is_mercator_tile=True, **kwargs
        )
        self._zoom_level = zoom_level

    def get_zoom_level(self):
        return self._zoom_level

    def set_zoom_level(self, zoom_level):
        self._zoom_level = zoom_level


class LocalImageTilingScheme(TilingScheme):
    def __init__(
        self,
        unit="meter",
        alignment=TileAlignment.centered_to_image.value,
        use_overhanging_tiles=None,
        aligned_to_base_tile_area=None,
        **kwargs,
    ):
        kwargs = safely_delete_kwargs_value(
            kwargs, "name", self.__class__.__name__
        )
        kwargs = safely_delete_kwargs_value(
            kwargs, "is_local_image_tile", True
        )
        super().__init__(
            name=self.__class__.__name__, is_local_image_tile=True, **kwargs
        )
        assert unit in ["meter", "pixel"]
        self._unit = unit

        assert alignment in TileAlignment.list(), alignment
        self._alignment = alignment

        self._use_overhanging_tiles = use_overhanging_tiles
        self._aligned_to_base_tile_area = aligned_to_base_tile_area

    def is_in_meter(self):
        return self._unit == "meter"

    def is_in_pixel(self):
        return self._unit == "pixel"

    def is_centered_to_image(self):
        return self._alignment == TileAlignment.centered_to_image.value

    def is_aligned_to_image_border(self):
        return self._alignment == TileAlignment.aligned_to_image_border.value

    def is_optimal_aligned(self):
        return self._alignment == TileAlignment.optimized.value

    def get_alignment(self):
        return self._alignment

    def uses_overhanging_tiles(self):
        return self._use_overhanging_tiles

    def is_aligned_to_base_tile_area(self):
        return self._aligned_to_base_tile_area

    def set_alignment(self, alignment):
        assert alignment in TileAlignment.list()
        self._alignment = alignment

    def set_overhanging_tiles_flag(self, use_overhanging_tiles):
        self._use_overhanging_tiles = use_overhanging_tiles

    def set_aligned_to_base_tile_area_flag(self, align_to_base_tile_area):
        self._aligned_to_base_tile_area = align_to_base_tile_area


class LocalImagePixelSizeTilingScheme(LocalImageTilingScheme):
    def __init__(self, **kwargs):
        kwargs = safely_delete_kwargs_value(
            kwargs, "name", self.__class__.__name__
        )
        kwargs = safely_delete_kwargs_value(kwargs, "unit", "pixel")
        super().__init__(name=self.__class__.__name__, unit="pixel", **kwargs)
        self._tile_size_in_pixel = None
        self._tile_stride_in_pixel = None

    @classmethod
    def from_local_image_meter_size_tiling_scheme(
        cls, meter_tiling_scheme, convert_meter_as_pixel_callback
    ):
        meter_tiling_scheme_dict = meter_tiling_scheme.to_object_dict()
        del meter_tiling_scheme_dict["name"]
        del meter_tiling_scheme_dict["unit"]
        pixel_tiling_scheme = cls.from_dict(meter_tiling_scheme_dict)

        pixel_tiling_scheme.set_tile_size_in_pixel(
            convert_meter_as_pixel_callback(
                meter_tiling_scheme.get_tile_size_in_meter(True)
            )
        )
        pixel_tiling_scheme.set_tile_stride_in_pixel(
            convert_meter_as_pixel_callback(
                meter_tiling_scheme.get_tile_stride_in_meter(True)
            )
        )
        return pixel_tiling_scheme

    def get_tile_size_in_pixel(self, only_magnitude):
        if only_magnitude:
            return self._tile_size_in_pixel.magnitude
        else:
            return self._tile_size_in_pixel

    def get_tile_stride_in_pixel(self, only_magnitude):
        if only_magnitude:
            return self._tile_stride_in_pixel.magnitude
        else:
            return self._tile_stride_in_pixel

    def set_tile_size_in_pixel(self, tile_size_in_pixel):
        self._tile_size_in_pixel = unit_reg.Quantity(
            tile_size_in_pixel, unit_reg.pixel
        )

    def set_tile_stride_in_pixel(self, tile_stride_in_pixel):
        self._tile_stride_in_pixel = unit_reg.Quantity(
            tile_stride_in_pixel, unit_reg.pixel
        )


class LocalImageMeterSizeTilingScheme(LocalImageTilingScheme):
    def __init__(self, **kwargs):
        kwargs = safely_delete_kwargs_value(
            kwargs, "name", self.__class__.__name__
        )
        kwargs = safely_delete_kwargs_value(kwargs, "unit", "meter")
        super().__init__(name=self.__class__.__name__, unit="meter", **kwargs)
        self._tile_size_in_meter = None
        self._tile_stride_in_meter = None

    def get_tile_size_in_meter(self, only_magnitude):
        if only_magnitude:
            return self._tile_size_in_meter.magnitude
        else:
            return self._tile_size_in_meter

    def get_tile_stride_in_meter(self, only_magnitude):
        if only_magnitude:
            return self._tile_stride_in_meter.magnitude
        else:
            return self._tile_stride_in_meter

    def set_tile_size_in_meter(self, tile_size_in_meter):
        self._tile_size_in_meter = unit_reg.Quantity(
            tile_size_in_meter, unit_reg.meter
        )

    def set_tile_stride_in_meter(self, tile_stride_in_meter):
        self._tile_stride_in_meter = unit_reg.Quantity(
            tile_stride_in_meter, unit_reg.meter
        )


class TilingSchemes(Enum):
    MercatorTilingScheme = MercatorTilingScheme()
    LocalImagePixelSizeTilingScheme = LocalImagePixelSizeTilingScheme()
    LocalImageMeterSizeTilingScheme = LocalImageMeterSizeTilingScheme()
