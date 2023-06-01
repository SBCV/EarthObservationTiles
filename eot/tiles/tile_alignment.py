from enum import Enum


class TileAlignment(Enum):
    optimized = "optimized"
    centered_to_image = "centered_to_image"
    aligned_to_image_border = "aligned_to_image_border"

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
