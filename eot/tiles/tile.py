import os
from abc import ABC, abstractmethod
from enum import Enum
import warnings
from eot.crs.crs import transform_coords

warnings.simplefilter(
    "ignore", UserWarning
)  # To prevent rasterio NotGeoreferencedWarning


class TilingScheme:
    def __init__(
        self,
        name,
        is_mercator_tile=None,
        is_local_image_tile=None,
    ):
        assert not (is_mercator_tile and is_local_image_tile)
        self.name = name
        self._is_mercator_tile = is_mercator_tile
        self._is_local_image_tile = is_local_image_tile

    def __str__(self):
        return self.name

    def represents_mercator_tiling(self):
        return self._is_mercator_tile

    def represents_local_image_tiling(self):
        return self._is_local_image_tile


class MercatorTilingScheme(TilingScheme):
    def __init__(self, name="mercator_tiling", zoom_level=None):
        super().__init__(name=name, is_mercator_tile=True)
        self._zoom_level = zoom_level

    def get_zoom_level(self):
        return self._zoom_level

    def set_zoom_level(self, zoom_level):
        self._zoom_level = zoom_level


class LocalImageTilingScheme(TilingScheme):
    def __init__(
        self,
        name="local_image_tiling",
        in_pixel=None,
        in_meter=None,
        centered_to_image=None,
        aligned_to_image=None,
        use_overhanging_tiles=None,
        use_border_tiles=None,
        aligned_to_base_tile_area=None,
    ):
        super().__init__(name=name, is_local_image_tile=True)

        assert not (in_pixel and in_meter)
        self._in_pixel = in_pixel
        self._in_meter = in_meter

        assert not (centered_to_image and aligned_to_image)
        self._centered_to_image = centered_to_image
        self._aligned_to_image = aligned_to_image
        self._use_overhanging_tiles = use_overhanging_tiles
        self._use_border_tiles = use_border_tiles
        self._aligned_to_base_tile_area = aligned_to_base_tile_area

    def is_in_meter(self):
        return self._in_meter

    def is_in_pixel(self):
        return self._in_pixel

    def is_centered_to_image(self):
        return self._centered_to_image

    def is_aligned_to_image(self):
        return self._aligned_to_image

    def uses_overhanging_tiles(self):
        return self._use_overhanging_tiles

    def uses_border_tiles(self):
        return self._use_border_tiles

    def is_aligned_to_base_tile_area(self):
        return self._aligned_to_base_tile_area

    def set_centered_to_image(self):
        self._centered_to_image = True
        self._aligned_to_image = False

    def set_aligned_to_image(self):
        self._aligned_to_image = True
        self._centered_to_image = False

    def set_overhanging_tiles_flag(self, use_overhanging_tiles):
        self._use_overhanging_tiles = use_overhanging_tiles

    def set_border_tiles_flag(self, use_border_tiles):
        self._use_border_tiles = use_border_tiles

    def set_aligned_to_base_tile_area_flag(self, align_to_base_tile_area):
        self._aligned_to_base_tile_area = align_to_base_tile_area


class PixelSizeTilingScheme(LocalImageTilingScheme):
    def __init__(
        self,
        name="local_image_pixel_size_tiling",
        centered_to_image=None,
        aligned_to_image=None,
        use_overhanging_tiles=None,
        use_border_tiles=None,
        aligned_to_base_tile_area=None,
    ):
        super().__init__(
            name=name,
            in_pixel=True,
            centered_to_image=centered_to_image,
            aligned_to_image=aligned_to_image,
            use_overhanging_tiles=use_overhanging_tiles,
            use_border_tiles=use_border_tiles,
            aligned_to_base_tile_area=aligned_to_base_tile_area,
        )
        self._tile_size_in_pixel = None
        self._tile_stride_in_pixel = None

    def get_tile_size_in_pixel(self):
        return self._tile_size_in_pixel

    def get_tile_stride_in_pixel(self):
        return self._tile_stride_in_pixel

    def set_tile_size_in_pixel(self, tile_size_in_pixel):
        self._tile_size_in_pixel = tile_size_in_pixel

    def set_tile_stride_in_pixel(self, tile_stride_in_pixel):
        self._tile_stride_in_pixel = tile_stride_in_pixel


class MeterSizeTilingScheme(LocalImageTilingScheme):
    def __init__(
        self,
        name="local_image_meter_size_tiling",
        centered_to_image=None,
        aligned_to_image=None,
        use_overhanging_tiles=None,
        use_border_tiles=None,
        aligned_to_base_tile_area=None,
    ):
        super().__init__(
            name=name,
            in_meter=True,
            centered_to_image=centered_to_image,
            aligned_to_image=aligned_to_image,
            use_overhanging_tiles=use_overhanging_tiles,
            use_border_tiles=use_border_tiles,
            aligned_to_base_tile_area=aligned_to_base_tile_area,
        )
        self._tile_size_in_meter = None
        self._tile_stride_in_meter = None

    def get_tile_size_in_meter(self):
        return self._tile_size_in_meter

    def get_tile_stride_in_meter(self):
        return self._tile_stride_in_meter

    def set_tile_size_in_meter(self, tile_size_in_meter):
        self._tile_size_in_meter = tile_size_in_meter

    def set_tile_stride_in_meter(self, tile_stride_in_meter):
        self._tile_stride_in_meter = tile_stride_in_meter


class ImageAlignedPixelSizeTilingScheme(PixelSizeTilingScheme):
    def __init__(self):
        super().__init__(
            "image_aligned_pixel_size",
            aligned_to_image=True,
        )


class ImageCenteredPixelSizeTilingScheme(PixelSizeTilingScheme):
    def __init__(self):
        super().__init__(
            "image_centered_pixel_size",
            centered_to_image=True,
        )


class ImageAlignedMeterSizeTilingScheme(MeterSizeTilingScheme):
    def __init__(self):
        super().__init__(
            "image_aligned_meter_size",
            aligned_to_image=True,
        )


class ImageCenteredMeterSizeTilingScheme(MeterSizeTilingScheme):
    def __init__(self):
        super().__init__(
            "image_centered_meter_size",
            centered_to_image=True,
        )


class TilingSchemes(Enum):
    mercator = MercatorTilingScheme()
    image_aligned_pixel_size = ImageAlignedPixelSizeTilingScheme()
    image_centered_pixel_size = ImageCenteredPixelSizeTilingScheme()
    image_aligned_meter_size = ImageAlignedMeterSizeTilingScheme()
    image_centered_meter_size = ImageCenteredMeterSizeTilingScheme()


def _transform_coord_list(src_crs_list, scr_crs, dst_crs):
    assert scr_crs is not None
    assert dst_crs is not None
    x_list, y_list = zip(*src_crs_list)
    x_list, y_list = transform_coords(scr_crs, dst_crs, x_list, y_list)
    dst_crs_list = list(zip(x_list, y_list))
    return dst_crs_list


class Tile(ABC):

    # https://codefather.tech/blog/python-abstract-class/

    @abstractmethod
    def __init__(
        self,
        disk_width=None,
        disk_height=None,
        absolute_tile_fp=None,
        relative_root_dp=None,
        relative_tile_fp=None,
    ):
        # Size of the tile on disk in pixel.
        self.disk_width = disk_width
        self.disk_height = disk_height
        assert not (bool(absolute_tile_fp) and bool(relative_tile_fp))
        self._absolute_tile_fp = absolute_tile_fp
        self._relative_root_dp = relative_root_dp
        self._relative_tile_fp = relative_tile_fp

    def set_tile_fp(self, tile_fp, is_absolute=True, root_dp=None):
        if is_absolute:
            self._absolute_tile_fp = tile_fp
            if root_dp is not None:
                self._relative_root_dp = root_dp
                self._relative_tile_fp = os.path.relpath(tile_fp, root_dp)
        else:
            assert root_dp is not None
            self._relative_root_dp = root_dp
            self._relative_tile_fp = tile_fp

    def get_absolute_tile_fp(self):
        return self._absolute_tile_fp

    def get_relative_root_dp(self):
        return self._relative_root_dp

    def get_relative_tile_fp(self):
        return self._relative_tile_fp

    def get_dataset_name(self):
        # The dataset is the top level directory of the tile
        return os.path.normpath(self._relative_tile_fp).split(os.sep)[0]

    def set_disk_size(self, width, height):
        self.disk_width = width
        self.disk_height = height

    def get_disk_size(self):
        return self.disk_width, self.disk_height

    @abstractmethod
    def to_dict(self):
        pass
