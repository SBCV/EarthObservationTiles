import os
from abc import ABC, abstractmethod
import warnings
from eot.crs.crs import transform_coords

warnings.simplefilter(
    "ignore", UserWarning
)  # To prevent rasterio NotGeoreferencedWarning


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

    def set_disk_size(self, width, height):
        self.disk_width = width
        self.disk_height = height

    def get_disk_size(self):
        return self.disk_width, self.disk_height

    def get_disk_center(self, as_int=False):
        width = self.disk_width / 2
        height = self.disk_height / 2
        if as_int:
            width = int(width)
            height = int(height)
        return width, height

    @abstractmethod
    def to_dict(self):
        pass
