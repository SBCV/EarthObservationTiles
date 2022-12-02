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
        in_pixel=None,
        in_meter=None,
        centered_to_image=None,
        aligned_to_image=None,
    ):
        assert not (is_mercator_tile and is_local_image_tile)
        assert not (in_pixel and in_meter)
        assert not (centered_to_image and aligned_to_image)
        self.name = name
        self._is_mercator_tile = is_mercator_tile
        self._is_local_image_tile = is_local_image_tile
        self._in_pixel = in_pixel
        self._in_meter = in_meter
        self._centered_to_image = centered_to_image
        self._aligned_to_image = aligned_to_image

    def __str__(self):
        return self.name

    def represents_mercator_tiling(self):
        return self._is_mercator_tile

    def represents_local_image_tiling(self):
        return self._is_local_image_tile

    def is_in_meter(self):
        return self._in_meter

    def is_in_pixel(self):
        return self._in_pixel

    def is_centered_to_image(self):
        return self._centered_to_image

    def is_aligned_to_image(self):
        return self._aligned_to_image


class MercatorTilingScheme(TilingScheme):
    def __init__(self):
        super().__init__("mercator", is_mercator_tile=True)


class ImageAlignedPixelSizeTilingScheme(TilingScheme):
    def __init__(self):
        super().__init__(
            "image_aligned_pixel_size",
            is_local_image_tile=True,
            in_pixel=True,
            aligned_to_image=True,
        )


class ImageCenteredPixelSizeTilingScheme(TilingScheme):
    def __init__(self):
        super().__init__(
            "image_centered_pixel_size",
            is_local_image_tile=True,
            in_pixel=True,
            centered_to_image=True,
        )


class ImageAlignedMeterSizeTilingScheme(TilingScheme):
    def __init__(self):
        super().__init__(
            "image_aligned_meter_size",
            is_local_image_tile=True,
            in_meter=True,
            aligned_to_image=True,
        )


class ImageCenteredMeterSizeTilingScheme(TilingScheme):
    def __init__(self):
        super().__init__(
            "image_centered_meter_size",
            is_local_image_tile=True,
            in_meter=True,
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
