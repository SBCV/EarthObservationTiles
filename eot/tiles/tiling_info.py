from varname import nameof
from eot.tiles.tiling_scheme import TilingScheme
from eot.tiles.structured_representation import StructuredRepresentation
from eot.utility.quantity import unit_reg, parse_quantity_string


class RasterTilingInfo(StructuredRepresentation):
    """Represents the result obtained by applying a tiling scheme to a raster.

    A TilingLayout contains (in addition to the properties of a TilingScheme)
    attributes that are specific for the corresponding raster image such as
    the tile size or the tiling scheme offset in pixel.
    """

    def __init__(
        self,
        tiling_source_offset_int=None,
        tiling_source_stride_float=None,
        tiling_source_size_int=None,
        tiling_scheme=None,
    ):
        if tiling_scheme is not None:
            assert isinstance(tiling_scheme, TilingScheme)
        # Offset, stride and size are defined in (x,y) order

        self._tiling_source_offset_int = self._ensure_quantity_or_none(
            tiling_source_offset_int
        )
        self._tiling_source_stride_float = self._ensure_quantity_or_none(
            tiling_source_stride_float
        )
        self._tiling_source_size_int = self._ensure_quantity_or_none(
            tiling_source_size_int
        )
        self._tiling_scheme = tiling_scheme

    @staticmethod
    def _ensure_quantity(value):
        if isinstance(value, unit_reg.Quantity):
            quantity = value
        elif isinstance(value, str):
            quantity = parse_quantity_string(value)
        else:
            quantity = unit_reg.Quantity(value, unit_reg.pixel)
        return quantity

    @classmethod
    def _ensure_quantity_or_none(cls, value):
        result = None
        if value is not None:
            result = cls._ensure_quantity(value)
        return result

    @property
    def source_tiling_offset_x_int(self):
        return self._tiling_source_offset_int[0]

    @property
    def source_tiling_offset_y_int(self):
        return self._tiling_source_offset_int[1]

    @property
    def source_tile_stride_x_float(self):
        return self._tiling_source_stride_float[0]

    @property
    def source_tile_stride_y_float(self):
        return self._tiling_source_stride_float[1]

    @property
    def tiling_scheme(self):
        return self._tiling_scheme

    @tiling_scheme.setter
    def tiling_scheme(self, tiling_scheme):
        self._tiling_scheme = tiling_scheme

    def to_object_dict(self, include_properties=False):
        attr_attr_list = [
            nameof(self._tiling_source_offset_int),
            nameof(self._tiling_source_stride_float),
            nameof(self._tiling_source_size_int),
        ]
        selected_obj_dict = self._to_object_dict(
            include_properties=include_properties,
            include_attr_list=attr_attr_list,
        )
        return selected_obj_dict
