import os


class AggregationPathManager:
    def __init__(self, aggregation_odp, raster_dn):
        # assert isinstance(pm, TestDatasetPathManager), msg
        image_ext = ".tif"
        self.aggregation_dn = raster_dn
        self.test_aggregated_masks_dp = os.path.join(
            aggregation_odp, self.aggregation_dn + "_raster"
        )

        self.test_aggregated_masks_json_dp = os.path.join(
            aggregation_odp, self.aggregation_dn + "_json"
        )

        self.mask_png_fn = self.aggregation_dn + "_mask" + image_ext
        self.mask_png_fp = os.path.join(
            self.test_aggregated_masks_dp, self.mask_png_fn
        )
        self.mask_color_png_fn = (
            self.aggregation_dn + "_mask_color" + image_ext
        )
        self.mask_color_png_fp = os.path.join(
            self.test_aggregated_masks_dp, self.mask_color_png_fn
        )
        self.mask_overlay_png_fn = (
            self.aggregation_dn + "_mask_overlay" + image_ext
        )
        self.mask_overlay_png_fp = os.path.join(
            self.test_aggregated_masks_dp, self.mask_overlay_png_fn
        )
        self.grid_overlay_png_fn = (
            self.aggregation_dn + "_grid_overlay" + image_ext
        )
        self.grid_overlay_png_fp = os.path.join(
            self.test_aggregated_masks_dp, self.grid_overlay_png_fn
        )
