from eot.tools.aggregation.image_aggregation.pixel_projection import (
    create_images_with_pixel_projection,
)
from eot.tools.aggregation.image_aggregation.polygon_projection import (
    create_images_with_polgyon_projection,
)


def create_images(
    args, masks, categories, use_pixel_projection=True, resampling=None
):
    if use_pixel_projection:
        assert resampling is not None
        create_images_with_pixel_projection(
            args, masks, categories, resampling
        )
    else:
        create_images_with_polgyon_projection(args, masks, categories)
