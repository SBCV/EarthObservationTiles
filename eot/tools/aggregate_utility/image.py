from eot.tools.aggregate_utility.img.pixel_projection import (
    create_images_with_pixel_projection,
)
from eot.tools.aggregate_utility.img.polygon_projection import (
    create_images_with_polgyon_projection,
)


def create_images(args, masks, use_pixel_projection=True, resampling=None):
    if use_pixel_projection:
        assert resampling is not None
        create_images_with_pixel_projection(args, masks, resampling)
    else:
        create_images_with_polgyon_projection(args, masks)
