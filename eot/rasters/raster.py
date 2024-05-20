from contextlib import contextmanager
from ast import literal_eval as make_tuple
from enum import Enum
import numpy as np
import rasterio
from rasterio.enums import Resampling
from eot.bounds.bounded_area import BoundedPixelArea
from eot.rasters.raster_reprojection import (
    get_reprojected_raster_with_default_transform_generator,
)
from eot.rasters.raster_writing import write_raster
from eot.bounds import transform_from_bounds
from eot.tiles.tiling import Tiler
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.rasters.raster_geo_data import (
    has_valid_matrix_geo_transform,
    has_valid_gcps_geo_transform,
    has_default_geo_transform,
    get_geo_transform_pixel_to_crs,
)
from eot.rasters.raster_tile_data import get_raster_data_of_tile
from eot.rasters.raster_tile_size import (
    compute_tile_size_in_meter,
    compute_tile_size_in_source_pixel,
)

InterpolationMethod = Enum("InterpolationMethod", "nearest bilinear")


class Raster(BoundedPixelArea):
    @classmethod
    def get_from_file(
        cls,
        fp,
        mode="r",
        driver=None,
        width=None,
        height=None,
        count=None,
        crs=None,
        transform=None,
        dtype=None,
        nodata=None,
        sharing=False,
        **kwargs,
    ):
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.io.html#rasterio.io.DatasetReader
        raster = rasterio.open(
            fp,
            mode,
            driver,
            width,
            height,
            count,
            crs,
            transform,
            dtype,
            nodata,
            sharing,
            **kwargs,
        )
        # https://stackoverflow.com/questions/100003/what-are-metaclasses-in-python
        # https://stackoverflow.com/questions/9539052/how-to-dynamically-change-base-class-of-instances-at-runtime
        if cls not in raster.__class__.__bases__:
            raster.__class__.__bases__ += (cls,)
        return raster

    @contextmanager
    def get_normalized_dataset_generator(
        self, dst_crs, resampling=Resampling.nearest
    ):
        """
        This method mimics

        with WarpedVRT(raster, crs=dst_crs, resampling=Resampling.nearest) as warped_vrt:

        but provides an object of type of "eot.rasters.raster.Raster"
        instead of "rasterio.vrt.WarpedVRT".

        Usage with something like

        with raster.get_normalized_dataset_generator(EPSG_3857) as raster_normalized:
            raster_normalized.get_left_top_bound_corner(EPSG_3857)
        """
        with get_reprojected_raster_with_default_transform_generator(
            self, dst_crs, resampling
        ) as normalized_data:
            normalized_data.__class__ = self.__class__
            assert has_default_geo_transform(normalized_data)
            yield normalized_data

    @staticmethod
    def _add_alpha_channel(raster_data, image_axis_order=False):
        if not image_axis_order:
            # channel, height, width -> height, width, channel
            raster_data = np.moveaxis(raster_data, 0, 2)
        if raster_data.shape[2] == 3:
            opacity = np.full(
                (raster_data.shape[:2]), 255, dtype=raster_data.dtype
            )
            raster_data = np.dstack((raster_data, opacity))
        if not image_axis_order:
            # height, width, channel -> channel, height, width
            raster_data = np.moveaxis(raster_data, 2, 0)
        return raster_data

    def get_raster_data_as_numpy(
        self,
        image_axis_order=True,
        add_alpha_channel=False,
        apply_color_palette=False,
        **kwargs
    ):
        data = self.read(**kwargs)
        if apply_color_palette:
            # https://rasterio.groups.io/g/main/topic/exporting_single_banc_with_a/67571864
            #   Author of rasterio: The library doesn't automatically convert
            #    single band color-mapped data to 3-band RGB data. You'll need to
            #    construct a new output array filled with values from the colormap
            #    and then write that to the output file.
            assert len(data.shape) == 3
            channel, height, width = data.shape
            assert channel == 1
            colormap = self.colormap(1)
            palette = np.array(list(colormap.values()), dtype=np.uint8)
            rgb_image = np.zeros((3, height, width), dtype=np.uint8)
            for i in range(3):
                # palette[image] is a (height, width, 3) array where each index
                # in image is replaced by the corresponding RGB color from the
                # palette. Essentially, it looks up the RGB color for each
                # index in image.
                rgb_image[i] = palette[data, i]
            data = rgb_image
        if image_axis_order:
            # channel, height, width -> height, width, channel
            data = np.moveaxis(data, 0, 2)
        if add_alpha_channel:
            data = self._add_alpha_channel(
                data, image_axis_order=image_axis_order
            )
        return data

    def get_data_type(self):
        assert len(set(self.dtypes)) == 1
        return self.dtypes[0]

    def write_to_file(self, ofp):
        write_raster(
            self, ofp, transform=self.transform, crs=self.crs, gcps=self.gcps
        )

    def write_as_normalized_raster_to_file(
        self, ofp, dst_crs, resampling=Resampling.nearest
    ):
        with self.get_normalized_dataset_generator(
            dst_crs, resampling=resampling
        ) as normalized_raster:
            write_raster(
                normalized_raster,
                ofp,
                transform=normalized_raster.transform,
                crs=normalized_raster.crs,
                gcps=normalized_raster.gcps,
            )

    ###########################################################################
    #                          Transformations
    ###########################################################################

    def has_default_geo_transform(self):
        return has_default_geo_transform(self)

    def has_valid_matrix_geo_transform(self):
        return has_valid_matrix_geo_transform(self)

    def has_valid_gcps_geo_transform(self):
        return has_valid_gcps_geo_transform(self)

    def get_transform_pixel_to_crs(self, check_validity=True):
        # Returns a geo-transformation using the matrix or a list of gcps
        (
            transform_pixel_to_crs,
            crs,
        ) = get_geo_transform_pixel_to_crs(self, check_validity)
        return transform_pixel_to_crs, crs

    def get_transform_crs_to_pixel(self, check_validity=True):
        (
            transform_pixel_to_crs,
            crs,
        ) = self.get_transform_pixel_to_crs(check_validity)
        transform_crs_to_pixel = ~transform_pixel_to_crs
        return transform_crs_to_pixel, crs

    def get_geo_transform_with_crs(self, check_validity=True):
        # Alias for get_transform_pixel_to_crs()

        # NB: Can NOT name this method "get_transform()", since this already
        #  defined in rasterio
        #  https://rasterio.readthedocs.io/en/latest/api/rasterio.io.html#rasterio.io.DatasetReader.get_transform

        # Get transform from matrix or gcps
        transform, crs = self.get_transform_pixel_to_crs(check_validity)
        if check_validity:
            assert crs is not None
        return transform, crs

    def get_crs(self):
        # Return the crs of the transformation matrix or the crs of the gcps
        _, crs = self.get_transform_pixel_to_crs()
        assert crs is not None
        return crs

    ###########################################################################
    #                           Geo Coordinates
    ###########################################################################
    def get_geo_coord(self, row, col, offset="center"):
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.io.html#rasterio.io.DatasetReader.xy
        #   xy(row, col)
        #   Returns the coordinates (x, y) of a pixel at row and col.
        #   The pixel’s center is returned by default, but a corner can be
        #   returned by setting offset to one of ul, ur, ll, lr.
        return self.xy(row, col, offset=offset)

    ###########################################################################
    #                           Pixel Corner
    ###########################################################################
    def get_left_top_pixel_corner(self):
        return 0, 0

    def get_right_top_pixel_corner(self):
        return self.width, 0

    def get_left_bottom_pixel_corner(self):
        return 0, self.height

    def get_right_bottom_pixel_corner(self):
        return self.width, self.height

    ###########################################################################
    #                               Bounds
    ###########################################################################

    def compute_bounds_in_crs(self):
        """Overrides the method in BoundedPixelArea for efficiency reasons.

        The method is supposed to yield the same results. Numerical differences
         might occur.
        """

        # https://rasterio.readthedocs.io/en/latest/quickstart.html#dataset-georeferencing
        # Bounds contain:
        #   lower left x, lower left y, upper right x, upper right y
        # The value of the bounds attribute is derived from a more fundamental
        # attribute: the dataset’s geospatial transform.
        # For example: Given a transform T with
        #       s_x     0       t_x
        #   T = 0       s_y     t_y
        #       0       0       1
        # Then, the bounds are defined as
        #   bounds = (
        #       left=t_x,                           # lower left x
        #       bottom=t_y + s_y * height,          # lower left y
        #       right=t_x + s_x * width,            # upper right x
        #       top=t_y                             # upper right y
        #   )
        # The usage of self.bounds requires a valid geospatial transform
        # (see explanation above)
        assert self.has_valid_matrix_geo_transform()
        l, b, r, t = self.bounds
        return l, b, r, t

    ###########################################################################
    #                    Bound based Transformations
    ###########################################################################

    def _check_transformation_requirements(self):
        error_message = "Only valid for rasters with default transformation"
        assert self.has_default_geo_transform(), error_message

    def get_transform_pixel_to_epsg_4326(self):
        # https://epsg.io/4326
        #   used in GPS
        self._check_transformation_requirements()
        w, s, e, n = self.get_bounds_epsg_4326()
        pixel_to_epsg_4326_trans = transform_from_bounds(
            w, s, e, n, self.width, self.height
        )
        # Return an affine transformation
        return pixel_to_epsg_4326_trans

    def get_transform_epsg_4326_to_pixel(self):
        self._check_transformation_requirements()
        # ~ denotes the inverse operator
        return ~self.get_transform_pixel_to_epsg_4326()

    def get_transform_pixel_to_epsg_3857(self):
        # https://epsg.io/3857
        #   used in Google Maps, OpenStreetMap, Bing, ArcGIS, ESRI
        self._check_transformation_requirements()
        w, s, e, n = self.get_bounds_epsg_3857()
        pixel_to_epsg_3857_trans = transform_from_bounds(
            w, s, e, n, self.width, self.height
        )
        # Return an affine transformation
        return pixel_to_epsg_3857_trans

    def get_transform_epsg_3857_to_pixel(self):
        self._check_transformation_requirements()
        # ~ denotes the inverse operator
        return ~self.get_transform_pixel_to_epsg_3857()

    ###########################################################################
    #                               Tiles
    ###########################################################################

    def get_transform_tile_pixel_to_raster_pixel(self, tile):
        if isinstance(tile, MercatorTile):
            epsg_4326_to_raster_pixel_transform = (
                self.get_transform_epsg_4326_to_pixel()
            )
            tile_pixel_to_epsg_4326_transform = (
                tile.get_transform_pixel_to_epsg_4326()
            )

            # The following transformation expects FIRST x (width) and THEN
            # Y (height) coordinates. This is NOT consistent with numpy!!!
            tile_pixel_to_raster_pixel_transform = (
                epsg_4326_to_raster_pixel_transform
                * tile_pixel_to_epsg_4326_transform
            )
        elif isinstance(tile, ImagePixelTile):
            offset = tile.get_source_offset()
            tile_pixel_to_raster_pixel_transform = np.identity(
                3, dtype=np.float
            )
            tile_pixel_to_raster_pixel_transform[0:2, 2] = offset
        else:
            assert False
        return tile_pixel_to_raster_pixel_transform

    def compute_tiling(self, tiling_scheme):
        return Tiler.compute_tiling(
            raster=self,
            tiling_scheme=tiling_scheme,
        )

    def get_raster_data_of_tile(self, tile, bands, resampling, legacy=False):
        return get_raster_data_of_tile(self, tile, bands, resampling, legacy)

    def _get_mercator_tile_pixel_corners(self, tile):
        [
            tile_left_top_raster_crs,
            tile_right_top_raster_crs,
            tile_right_bottom_raster_crs,
            tile_left_bottom_raster_crs,
        ] = tile.compute_bound_corners(dst_crs=self.crs)
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.io.html#rasterio.io.BufferedDatasetWriter.xy
        tile_lt_pixel = self.index(*tile_left_top_raster_crs)
        tile_rt_pixel = self.index(*tile_right_top_raster_crs)
        tile_rb_pixel = self.index(*tile_right_bottom_raster_crs)
        tile_lb_pixel = self.index(*tile_left_bottom_raster_crs)
        return tile_lt_pixel, tile_rt_pixel, tile_rb_pixel, tile_lb_pixel

    @staticmethod
    def _get_local_tile_pixel_corners(tile):
        source_x_offset, source_y_offset = tile.get_source_offset()
        source_width, source_height = tile.get_source_size()
        # NB: self.index(...) returns the (row, col) index of the pixel
        # fmt:off
        tile_lt_pixel = (source_y_offset, source_x_offset)
        tile_rt_pixel = (source_y_offset, source_x_offset + source_width)
        tile_rb_pixel = (source_y_offset + source_height, source_x_offset + source_width)
        tile_lb_pixel = (source_y_offset + source_height, source_x_offset)
        # fmt:on
        return tile_lt_pixel, tile_rt_pixel, tile_rb_pixel, tile_lb_pixel

    def get_tile_bound_pixel_corners(self, tile):
        if isinstance(tile, MercatorTile):
            tile_pixel_corners = self._get_mercator_tile_pixel_corners(tile)
        elif isinstance(tile, ImagePixelTile):
            tile_pixel_corners = self._get_local_tile_pixel_corners(tile)
        else:
            assert False
        return tile_pixel_corners

    def compute_tile_size_in_meter(self, tile):
        return compute_tile_size_in_meter(self, tile)

    def compute_tile_size_in_source_pixel(self, tile):
        return compute_tile_size_in_source_pixel(self, tile)

    ###########################################################################
    #                               GSD
    ###########################################################################
    def get_meta_data_dict(self):
        meta_data_dict = self.tags()
        return meta_data_dict

    def add_meta_data(self, meta_data_dict):
        assert self.mode == "r+" or self.mode == "w"
        # https://rasterio.readthedocs.io/en/latest/topics/tags.html
        self.update_tags(**meta_data_dict)

    def get_gsd(self, tag="GSD"):
        meta_data_dict = self.get_meta_data_dict()
        if tag is not None and tag in meta_data_dict:
            gsd_meter_per_pixel_str = meta_data_dict[tag]
            try:
                gsd_meter_per_pixel_x, gsd_meter_per_pixel_y = make_tuple(
                    gsd_meter_per_pixel_str
                )
            except TypeError:
                gsd_meter_per_pixel_float = float(gsd_meter_per_pixel_str)
                gsd_meter_per_pixel_x = gsd_meter_per_pixel_float
                gsd_meter_per_pixel_y = gsd_meter_per_pixel_float
        else:
            # https://gis.stackexchange.com/questions/243639/how-to-take-cell-size-from-raster-using-python-or-gdal-or-rasterio/243648
            # Note: rasterio does not allow writing raster.res
            gsd_meter_per_pixel_x, gsd_meter_per_pixel_y = self.res
            gsd_meter_per_pixel_x = abs(gsd_meter_per_pixel_x)
            gsd_meter_per_pixel_y = abs(gsd_meter_per_pixel_y)

        return gsd_meter_per_pixel_x, gsd_meter_per_pixel_y

    def get_meter_as_x_pixel(self, length, gsd_tag="GSD"):
        gsd_meter_per_pixel_x, _ = self.get_gsd(gsd_tag)
        return length / gsd_meter_per_pixel_x

    def get_meter_as_y_pixel(self, length, gsd_tag="GSD"):
        _, gsd_meter_per_pixel_y = self.get_gsd(gsd_tag)
        return length / gsd_meter_per_pixel_y

    def get_meter_as_pixel(self, length_x_y_tuple, gsd_tag="GSD"):
        x_pixel = self.get_meter_as_x_pixel(
            length_x_y_tuple[0], gsd_tag=gsd_tag
        )
        y_pixel = self.get_meter_as_y_pixel(
            length_x_y_tuple[1], gsd_tag=gsd_tag
        )
        return x_pixel, y_pixel

    ###########################################################################
    #                               Geojson
    ###########################################################################

    def write_mask_as_geojson(self, geo_json_ofp):
        from eot.geojson_ext.geo_segmentation import GeoSegmentation

        # https://rasterio.readthedocs.io/en/latest/index.html?highlight=polygon#rasterio-access-to-geospatial-raster-data
        # Read the dataset's valid data mask as a ndarray.
        mask = self.dataset_mask()
        transform, crs = self.get_transform_pixel_to_crs()
        geo_segmentation = GeoSegmentation.from_raster_data(
            mask, transform, crs
        )
        assert geo_segmentation.get_number_polygons() == 1
        geo_segmentation.write_as_geojson_feature_collection(geo_json_ofp)
