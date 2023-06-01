import rasterio
from affine import Affine
from rasterio.windows import Window

from eot.bounds.bounded_area import BoundedPixelArea
from eot.tiles.tile import Tile
from eot.crs.crs import transform_bounds


class ImagePixelTile(Tile, BoundedPixelArea):
    """
    This tile is defined relative to a specfic image.
    """

    CLASS_STR = "class"
    RASTER_NAME_STR = "raster_name"
    SOURCE_X_OFFSET_STR = "source_width_offset"
    SOURCE_Y_OFFSET_STR = "source_height_offset"
    SOURCE_WIDTH_STR = "source_width"
    SOURCE_HEIGHT_STR = "source_height"

    def __init__(
        self,
        raster_name,
        source_x_offset,
        source_y_offset,
        source_width,
        source_height,
        disk_width=None,
        disk_height=None,
        raster_transform=None,
        raster_crs=None,
        absolute_tile_fp=None,
        relative_root_dp=None,
        relative_tile_fp=None,
    ):
        super().__init__(
            disk_width,
            disk_height,
            absolute_tile_fp,
            relative_root_dp,
            relative_tile_fp,
        )
        self._raster_name = raster_name
        # x denotes the axis along the width of the tile
        self._source_x_offset = int(source_x_offset)
        # y denotes the axis along the height of the tile
        self._source_y_offset = int(source_y_offset)
        self._source_width = int(source_width)
        self._source_height = int(source_height)
        self._raster_transform = raster_transform
        self._raster_crs = raster_crs
        self._tile_transform = None

    def to_tuple(self):
        tuple_repr = (
            self._raster_name,
            self._source_x_offset,
            self._source_y_offset,
            self._source_width,
            self._source_height,
        )
        return tuple_repr

    def to_dict(self):
        dict_repr = {
            self.CLASS_STR: self.__class__.__name__,
            self.RASTER_NAME_STR: self._raster_name,
            self.SOURCE_X_OFFSET_STR: self._source_x_offset,
            self.SOURCE_Y_OFFSET_STR: self._source_y_offset,
            self.SOURCE_WIDTH_STR: self._source_width,
            self.SOURCE_HEIGHT_STR: self._source_height,
        }
        return dict_repr

    def __repr__(self):
        repr_str = f"{self._raster_name} {self._source_x_offset} {self._source_y_offset}"
        repr_str += f" {self._source_width} {self._source_height}"
        return repr_str

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            self_as_tuple = self.to_tuple()
            other_as_tuple = other.to_tuple()
            return self_as_tuple == other_as_tuple
        else:
            return False

    def __lt__(self, other):
        # Required for sorting
        assert isinstance(other, self.__class__)
        self_as_tuple = self.to_tuple()
        other_as_tuple = other.to_tuple()
        return self_as_tuple < other_as_tuple

    def __hash__(self):
        # A hash is required to use Tile within sets
        return hash(self.to_tuple())

    def __iter__(self):
        return iter(self.to_tuple())

    def get_raster_name(self):
        return self._raster_name

    def get_source_offset(self):
        return self._source_x_offset, self._source_y_offset

    def get_source_x_offset(self):
        return self._source_x_offset

    def get_source_y_offset(self):
        return self._source_y_offset

    def get_source_size(self):
        return self._source_width, self._source_height

    def get_source_end_coord(self):
        x_offset, y_offset = self.get_source_offset()
        width, height = self.get_source_size()
        x_end_coord = x_offset + width - 1
        y_end_coord = y_offset + height - 1
        return x_end_coord, y_end_coord

    def get_source_rectangle(self):
        x_offset, y_offset = self.get_source_offset()
        x_end_coord, y_end_coord = self.get_source_end_coord()
        return x_offset, y_offset, x_end_coord, y_end_coord

    def get_source_to_disk_ratio(self):
        """Ratio between source and disk

        Example:
         source: 400 pixel, disk: 512 pixel => source_to_disk_ratio: 0.78125
        NB: In order to convert source pixels to disk pixels one must use the
         INVERSE ratio (i.e. get_disk_to_source_ratio())
        """
        assert self.disk_width is not None
        assert self.disk_height is not None
        scale_source_to_disk_x = self._source_width / self.disk_width
        scale_source_to_disk_y = self._source_height / self.disk_height
        return scale_source_to_disk_x, scale_source_to_disk_y

    def get_disk_to_source_ratio(self):
        """Ratio between disk and source

        Example:
         source: 400 pixel, disk: 512 pixel => disk_to_source_ratio: 1.28
        NB: In order to convert disk pixels to source pixels one must use the
         INVERSE ratio (i.e. get_source_to_disk_ratio())
        """
        assert self.disk_width is not None
        assert self.disk_height is not None
        scale_disk_to_source_x = self.disk_width / self._source_width
        scale_disk_to_source_y = self.disk_height / self._source_height
        return scale_disk_to_source_x, scale_disk_to_source_y

    def convert_source_to_disk(self, source_x, source_y):
        (
            source_to_disk_x_scale,
            source_to_disk_y_scale,
        ) = self.get_disk_to_source_ratio()
        disk_x = source_x * source_to_disk_x_scale
        disk_y = source_y * source_to_disk_y_scale
        return disk_x, disk_y

    def get_neighbors(self):
        # 3x3 matrix (upper, center, bottom) x (left, center, right)
        # except (center, center)

        raster_name = self.get_raster_name()
        x_offset, y_offset = self.get_source_offset()
        width, height = self.get_source_size()
        x_offset, y_offset = int(x_offset), int(y_offset)
        width, height = int(width), int(height)

        # fmt: off
        ul = self.__class__(raster_name=raster_name, source_x_offset=x_offset - width, source_y_offset=y_offset - height, source_width=width, source_height=height) # noqa
        uc = self.__class__(raster_name=raster_name, source_x_offset=x_offset + 0,     source_y_offset=y_offset - height, source_width=width, source_height=height) # noqa
        ur = self.__class__(raster_name=raster_name, source_x_offset=x_offset + width, source_y_offset=y_offset - height, source_width=width, source_height=height) # noqa

        cl = self.__class__(raster_name=raster_name, source_x_offset=x_offset - width, source_y_offset=y_offset + 0, source_width=width, source_height=height) # noqa
        cr = self.__class__(raster_name=raster_name, source_x_offset=x_offset + width, source_y_offset=y_offset + 0, source_width=width, source_height=height) # noqa

        bl = self.__class__(raster_name=raster_name, source_x_offset=x_offset - width, source_y_offset=y_offset + height, source_width=width, source_height=height) # noqa
        bc = self.__class__(raster_name=raster_name, source_x_offset=x_offset + 0,     source_y_offset=y_offset + height, source_width=width, source_height=height) # noqa
        br = self.__class__(raster_name=raster_name, source_x_offset=x_offset + width, source_y_offset=y_offset + height, source_width=width, source_height=height) # noqa
        # fmt: on

        neighbor_list = [ul, uc, ur, cl, cr, bl, bc, br]
        return neighbor_list

    def is_surrounded(self, tile_list):
        """Check if a tile is (completely) surrounded by other tiles"""
        neighbor_list = self.get_neighbors()
        is_completely_surrounded = True
        for neighbor in neighbor_list:
            if neighbor not in tile_list:
                is_completely_surrounded = False
        return is_completely_surrounded

    @staticmethod
    def _is_dim_overlapping(self_lower, self_upper, other_lower, other_upper):
        is_overlapping = False
        if self_lower <= other_lower <= self_upper:
            is_overlapping = True
        if self_lower <= other_upper <= self_upper:
            is_overlapping = True
        return is_overlapping

    def is_overlapping(self, other):
        x_offset, y_offset = self.get_source_offset()
        width, height = self.get_source_size()
        other_x_offset, other_y_offset = other.get_source_offset()
        other_width, other_height = other.get_source_size()
        assert other_width == width and other_height == height

        width_overlapping = self._is_dim_overlapping(
            x_offset,
            x_offset + width - 1,
            other_x_offset,
            other_x_offset + other_width - 1,
        )
        height_overlapping = self._is_dim_overlapping(
            y_offset,
            y_offset + height - 1,
            other_y_offset,
            other_y_offset + other_height - 1,
        )
        overlapping = width_overlapping and height_overlapping
        return overlapping

    def get_overlapping_tiles(self, tile_list):
        overlapping_tile_list = [
            other for other in tile_list if self.is_overlapping(other)
        ]
        return overlapping_tile_list

    def compute_relative_source_offset(self, other):
        x_offset_1, y_offset_1 = self.get_source_offset()
        x_offset_2, y_offset_2 = other.get_source_offset()
        relative_source_x_offset = x_offset_2 - x_offset_1
        relative_source_y_offset = y_offset_2 - y_offset_1
        return relative_source_x_offset, relative_source_y_offset

    def compute_relative_disk_offset(self, other):
        (
            relative_source_x_offset,
            relative_source_y_offset,
        ) = self.compute_relative_source_offset(other)
        (
            source_to_disk_x_scale,
            source_to_disk_y_scale,
        ) = self.get_disk_to_source_ratio()
        # Note: During tiling the stride values are floored to obtain
        #  discretized SOURCE offset values. Since only the discretized
        #  information is used for further processing, subsequent results
        #  solely depend on the SOURCE offset values. Thus, to obtain the best
        #  corresponding DISK offset (according to the discretized SOURCE
        #  offset) is by rounding (and not by flooring).
        relative_disk_x_offset_int = round(
            relative_source_x_offset * source_to_disk_x_scale
        )
        relative_disk_y_offset_int = round(
            relative_source_y_offset * source_to_disk_y_scale
        )
        return relative_disk_x_offset_int, relative_disk_y_offset_int

    def _compute_tile_transform_with_window(
        self, raster_transform, raster_crs
    ):
        # https://github.com/rasterio/rasterio/blob/master/docs/topics/windowed-rw.rst#window-transforms
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.windows.html#rasterio.windows.Window
        # col_off, row_off, width, height
        window = Window(
            self._source_x_offset,
            self._source_y_offset,
            self._source_width,
            self._source_height,
        )
        tile_window_transform = rasterio.windows.transform(
            window, raster_transform
        )

        (
            scale_source_to_disk_x,
            scale_source_to_disk_y,
        ) = self.get_source_to_disk_ratio()

        sign = 1
        if raster_crs is None:
            # Small hack: if there is not crs defined, we invert the affine.e
            # and affine.f to obtain a correct visualization in QGIS
            sign = -1

        tile_transform = Affine(
            tile_window_transform.a * scale_source_to_disk_x,
            tile_window_transform.b,
            tile_window_transform.c,
            tile_window_transform.d,
            tile_window_transform.e * scale_source_to_disk_y * sign,
            tile_window_transform.f * sign,
        )
        return tile_transform

    def _compute_tile_transform(self, raster_transform, raster_crs):
        assert self._source_x_offset is not None
        assert self._source_y_offset is not None
        assert self._source_width is not None
        assert self._source_height is not None
        assert self.disk_width is not None
        assert self.disk_height is not None

        tile_source_offset = (
            self._source_x_offset,
            self._source_y_offset,
        )
        tile_geo_offset = raster_transform * tile_source_offset
        tile_geo_offset_c, tile_geo_offset_f = tile_geo_offset

        (
            scale_source_to_disk_x,
            scale_source_to_disk_y,
        ) = self.get_source_to_disk_ratio()

        sign = 1
        if raster_crs is None:
            # Small hack: if there is not crs defined, we invert the affine.e
            # and affine.f to obtain a correct visualization in QGIS
            sign = -1

        tile_transform = Affine(
            raster_transform.a * scale_source_to_disk_x,
            raster_transform.b,
            tile_geo_offset_c,
            raster_transform.d,
            raster_transform.e * scale_source_to_disk_y * sign,
            tile_geo_offset_f * sign,
        )
        return tile_transform

    def compute_and_set_tile_transform_from_raster(self, raster):
        """Compute and set the tile transform using the given raster"""
        # Equivalent results could be obtained with:
        #   self._compute_tile_transform_with_window()
        self._tile_transform = self._compute_tile_transform(
            raster.transform, raster.crs
        )

    def compute_and_set_tile_transform_from_raster_transform(
        self, raster_transform, raster_crs
    ):
        # Equivalent results could be obtained with:
        #   self._compute_tile_transform_with_window()
        self._tile_transform = self._compute_tile_transform(
            raster_transform, raster_crs
        )

    def compute_and_set_tile_transform(self):
        # Equivalent results could be obtained with:
        #   self._compute_tile_transform_with_window()
        assert self._raster_transform is not None
        self._tile_transform = self._compute_tile_transform(
            self._raster_transform, self._raster_crs
        )

    def _check_tile_transform(self):
        tile_transform_1 = self._compute_tile_transform_with_window(
            self._raster_transform, self._raster_crs
        )
        tile_transform_2 = self._compute_tile_transform(
            self._raster_transform, self._raster_crs
        )
        result = tile_transform_1 == tile_transform_2
        print(f"Result of check: {result}")

    def set_raster_transform(self, raster_transform):
        self._raster_transform = raster_transform

    def get_raster_transform(self):
        return self._raster_transform

    def get_tile_transform(self):
        return self._tile_transform

    def set_crs(self, crs):
        self._raster_crs = crs

    def get_crs(self):
        return self._raster_crs

    def get_transform_pixel_to_crs(self):
        return self.get_tile_transform(), self.get_crs()

    ###########################################################################
    #                           Pixel Corner
    ###########################################################################
    def get_left_top_pixel_corner(self):
        return 0, 0

    def get_right_top_pixel_corner(self):
        return self.disk_width, 0

    def get_left_bottom_pixel_corner(self):
        return 0, self.disk_height

    def get_right_bottom_pixel_corner(self):
        return self.disk_width, self.disk_height
