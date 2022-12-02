from contextlib import contextmanager
from enum import Enum
import numpy as np
import rasterio
from rasterio.enums import Resampling
import cv2
from eot.rasters.area import BoundedArea
from eot.rasters.reprojection import (
    get_reprojected_dataset_with_default_transform_generator,
)
from eot.rasters.write import write_dataset
from eot.crs.crs import EPSG_3857
from eot.crs.crs import EPSG_4326
from eot.crs.crs import transform_coords, transform_bounds, transform_geom
from eot.geometry.geometry import transform_from_bounds
from eot.tiles.tiling import Tiler
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.rasters.geo import (
    has_valid_matrix_transformation,
    has_valid_gcps_transformation,
    has_default_transformation,
    get_transform_pixel_to_crs,
)
from eot.geojson_ext.write_utility import (
    write_polygon_as_geojson_polygon,
    write_points_as_geojson_polygon,
    write_points_as_geojson_points,
)
from eot.utility.conversion import convert_rasterio_to_opencv_resampling


def _normalize_data(data):
    # print('data.shape', data.shape)
    if data.dtype == "uint16":  # GeoTiff could be 16 bits
        data = np.uint8(data / 256)
    elif data.dtype == "uint32":  # or 32 bits
        data = np.uint8(data / (256 * 256))
    elif data.dtype == "int16":  # or use ESA dirty hack (sic)
        data = np.uint8(data / 10000 * 256)
    return data


InterpolationMethod = Enum("InterpolationMethod", "nearest bilinear")


class Raster(rasterio.io.DatasetReader, BoundedArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        # https://stackoverflow.com/questions/597199/converting-an-object-into-a-subclass-in-python/29256784#29256784
        raster.__class__ = cls
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
        with get_reprojected_dataset_with_default_transform_generator(
            self, dst_crs, resampling
        ) as normalized_data:
            normalized_data.__class__ = self.__class__
            assert has_default_transformation(normalized_data)
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
        self, image_axis_order=True, add_alpha_channel=False, **kwargs
    ):
        data = self.read(**kwargs)
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
        write_dataset(
            self, ofp, transform=self.transform, crs=self.crs, gcps=self.gcps
        )

    def write_as_normalized_raster_to_file(
        self, ofp, dst_crs, resampling=Resampling.nearest
    ):
        with self.get_normalized_dataset_generator(
            dst_crs, resampling=resampling
        ) as normalized_raster:
            write_dataset(
                normalized_raster,
                ofp,
                transform=normalized_raster.transform,
                crs=normalized_raster.crs,
                gcps=normalized_raster.gcps,
            )

    def has_default_transformation(self):
        return has_default_transformation(self)

    def has_valid_matrix_transformation(self):
        return has_valid_matrix_transformation(self)

    def has_valid_gcps_transformation(self):
        return has_valid_gcps_transformation(self)

    def get_transform_with_crs(self, check_validity=True):
        # Get transform from matrix or gcps
        transform, crs = get_transform_pixel_to_crs(self, check_validity)
        if check_validity:
            assert crs is not None
        return transform, crs

    def get_crs(self):
        # Return the crs of the transformation matrix or the crs of the gcps
        _, crs = get_transform_pixel_to_crs(self)
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
    #                           Pixel Corners
    ###########################################################################

    @staticmethod
    def get_left_top_pixel_corner():
        return 0, 0

    def get_right_top_pixel_corner(self):
        return self.width, 0

    def get_left_bottom_pixel_corner(self):
        return 0, self.height

    def get_right_bottom_pixel_corner(self):
        return self.width, self.height

    @staticmethod
    def _transform_coords_or_pixels(coords, transform):
        return [transform * coord for coord in coords]

    def _trarnsform_pixel_corner_to_dst_crs(self, x_pixel, y_pixel, dst_crs):
        transform_pixel_to_crs, crs = self.get_transform_pixel_to_crs()
        assert crs is not None
        x_coord, y_coord = transform_pixel_to_crs * (x_pixel, y_pixel)
        if dst_crs is not None:
            x_list, y_list = transform_coords(
                crs, dst_crs, [x_coord], [y_coord]
            )
            x_coord = x_list[0]
            y_coord = y_list[0]
        return x_coord, y_coord

    def get_upper_left_pixel_corner_crs(self, dst_crs=None):
        x_coord, y_coord = self._trarnsform_pixel_corner_to_dst_crs(
            *self.get_left_top_pixel_corner(), dst_crs
        )
        return x_coord, y_coord

    def get_upper_right_pixel_corner_crs(self, dst_crs=None):
        x_coord, y_coord = self._trarnsform_pixel_corner_to_dst_crs(
            *self.get_right_top_pixel_corner(), dst_crs
        )
        return x_coord, y_coord

    def get_lower_left_pixel_corner_crs(self, dst_crs=None):
        x_coord, y_coord = self._trarnsform_pixel_corner_to_dst_crs(
            *self.get_left_bottom_pixel_corner(), dst_crs
        )
        return x_coord, y_coord

    def get_lower_right_pixel_corner_crs(self, dst_crs=None):
        x_coord, y_coord = self._trarnsform_pixel_corner_to_dst_crs(
            *self.get_right_bottom_pixel_corner(), dst_crs
        )
        return x_coord, y_coord

    ###########################################################################
    #                               Bounds
    ###########################################################################

    def compute_bounds_from_corners(self):
        # Computing the bounds from the corners is only valid, if the
        # geographic bounds of the visible image area coincide with the
        # geographic coordinates of the image corners.

        upper_left = self.get_left_top_pixel_corner()
        upper_right = self.get_right_top_pixel_corner()
        lower_left = self.get_left_bottom_pixel_corner()
        lower_right = self.get_right_bottom_pixel_corner()
        (
            transform_pixel_to_crs,
            crs,
        ) = self.get_transform_pixel_to_crs()

        upper_left_t = transform_pixel_to_crs * upper_left
        upper_right_t = transform_pixel_to_crs * upper_right
        lower_left_t = transform_pixel_to_crs * lower_left
        lower_right_t = transform_pixel_to_crs * lower_right

        left = min(
            upper_left_t[0],
            upper_right_t[0],
            lower_left_t[0],
            lower_right_t[0],
        )
        bottom = min(
            upper_left_t[1],
            upper_right_t[1],
            lower_left_t[1],
            lower_right_t[1],
        )
        right = max(
            upper_left_t[0],
            upper_right_t[0],
            lower_left_t[0],
            lower_right_t[0],
        )
        top = max(
            upper_left_t[1],
            upper_right_t[1],
            lower_left_t[1],
            lower_right_t[1],
        )
        return left, bottom, right, top

    def get_bounds_crs(self, dst_crs=None):
        """Compute the bounds for the target crs (i.e. dst_crs)

        Nota bene: Transforming the bounds (relative to raster.crs /
         raster.gcps) to the target crs (i.e. dst_crs) would yield a DIFFERENT
         result.
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
        assert self.has_valid_matrix_transformation()
        l, b, r, t = self.bounds
        if dst_crs is not None:
            l, b, r, t = transform_bounds(self.get_crs(), dst_crs, l, b, r, t)
        return l, b, r, t

    def get_bounds_epsg_3857(self):
        # Return a Bbox(left, bottom, right, top) defined in EPSG:3857
        # https://epsg.io/3857
        #   used in Google Maps, OpenStreetMap, Bing, ArcGIS, ESRI
        l, b, r, t = self.get_bounds_crs(EPSG_3857)
        return l, b, r, t

    def get_bounds_epsg_4326(self):
        # Return a LngLatBbox(west, south, east, north) defined in EPSG:4326
        # https://epsg.io/4326
        #   used in GPS
        w, s, e, n = self.get_bounds_crs(EPSG_4326)
        return w, s, e, n

    ###########################################################################
    #                          Transformations
    ###########################################################################

    def get_transform_pixel_to_crs(self):
        # Returns a geo-transformation using the matrix or a list of gcps
        (
            transform_pixel_to_crs,
            crs,
        ) = get_transform_pixel_to_crs(self)
        return transform_pixel_to_crs, crs

    def get_transform_crs_to_pixel(self):
        (
            transform_pixel_to_crs,
            crs,
        ) = self.get_transform_pixel_to_crs()
        transform_crs_to_pixel = ~transform_pixel_to_crs
        return transform_crs_to_pixel, crs

    ###########################################################################
    #                    Bound based Transformations
    ###########################################################################

    def _check_transformation_requirements(self):
        error_message = "Only valid for rasters with default transformation"
        assert self.has_default_transformation(), error_message

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

    def get_tiles(
        self,
        tiling_scheme,
        input_tile_zoom_level=None,
        input_tile_size_in_pixel=None,
        input_tile_size_in_meter=None,
        input_tile_stride_in_pixel=None,
        input_tile_stride_in_meter=None,
        align_to_base_tile_area=None,
        tile_overhang=None,
        return_tiling_info=False,
    ):
        assert align_to_base_tile_area is not None
        tiles, tiling_info = Tiler.get_tiles(
            raster=self,
            tiling_scheme=tiling_scheme,
            input_tile_zoom_level=input_tile_zoom_level,
            input_tile_size_in_pixel=input_tile_size_in_pixel,
            input_tile_size_in_meter=input_tile_size_in_meter,
            input_tile_stride_in_pixel=input_tile_stride_in_pixel,
            input_tile_stride_in_meter=input_tile_stride_in_meter,
            align_to_base_tile_area=align_to_base_tile_area,
            tile_overhang=tile_overhang,
            return_tiling_info=True,
        )
        if return_tiling_info:
            return tiles, tiling_info
        return tiles

    def get_raster_tiles_with_disk_size(
        self,
        tiling_scheme,
        tile_disk_width,
        tile_disk_height,
        input_tile_zoom_level=None,
        input_tile_size_in_meter=None,
        input_tile_size_in_pixel=None,
    ):
        # https://mercantile.readthedocs.io/en/latest/quickstart.html
        raster = self
        tiles = Tiler.get_tiles_with_disk_size(
            raster,
            tiling_scheme,
            tile_disk_width,
            tile_disk_height,
            input_tile_zoom_level,
            input_tile_size_in_meter,
            input_tile_size_in_pixel,
        )
        return tiles

    def _get_raster_data_of_mercator_tile(self, tile, bands, resampling):
        pixel_to_epsg_3857_trans = tile.get_transform_pixel_to_epsg_3857()

        # https://rasterio.readthedocs.io/en/latest/api/rasterio.vrt.html

        # ##### Option 1 #####
        warped_vrt = rasterio.vrt.WarpedVRT(
            src_dataset=self,
            crs=EPSG_3857,
            resampling=resampling,
            add_alpha=False,
            # By providing the transform, width and height parameters, the
            # warped_vrt raster covers only the geo-spatial area defined by
            # these parameters (in this case the area of the tile).
            # This reduces the required size of warped_vrt (in memory) and
            # seems to reduce warping artifacts.
            transform=pixel_to_epsg_3857_trans,
            width=tile.disk_width,
            height=tile.disk_height,
        )
        # Since warped_vrt contains only the data of the tile, we do not need
        # to define a window to access the correct data
        tile_disk_shape = (len(bands), tile.disk_height, tile.disk_width)
        try:
            tile_disk_data = warped_vrt.read(indexes=bands)
        except rasterio.errors.RasterioIOError:
            # This try-except-clause catches errors like:
            #  rasterio.errors.RasterioIOError: Read or write failed.
            #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
            #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
            #  TIFFReadEncodedStrip() failed.
            # Usually this error appears for tiles covering areas outside the
            #  raster image.
            # Tile data with zero values is considered as no valid tile data.
            tile_disk_data = np.zeros(tile_disk_shape, dtype=np.uint8)

        msg = f"{tile_disk_data.shape} vs. {tile_disk_shape}"
        assert tile_disk_data.shape == tile_disk_shape, msg

        # ##################

        # ##### Option 2 #####
        # warped_vrt = rasterio.vrt.WarpedVRT(
        #     src_dataset=self,
        #     crs=EPSG_3857,
        #     resampling=resampling,
        #     add_alpha=False,
        # )
        # tile_disk_data_shape = (
        #     len(bands),
        #     tile.disk_width,
        #     tile.disk_height,
        # )
        # left, bottom, right, top = tile.get_bounds_epsg_3857()
        # tile_window = warped_vrt.window(left, bottom, right, top)
        # tile_disk_data = warped_vrt.read(
        #     out_shape=tile_disk_data_shape,
        #     indexes=bands,
        #     window=tile_window,
        # )
        # ##################

        tile_disk_data = _normalize_data(tile_disk_data)
        tile_disk_data = np.moveaxis(tile_disk_data, 0, 2)  # C,H,W -> H,W,C
        return tile_disk_data

    def _get_raster_data_of_local_tile(
        self, tile, bands, resampling, fill_value=None
    ):
        """
        :param tile:
        :param bands:
        :param resampling: something like Resampling in rasterio.enums
        :param fill_value: Can be a tuple like (0, 255, 0)
        :return:
        """
        cv2_resampling = convert_rasterio_to_opencv_resampling(resampling)
        source_x_offset, source_y_offset = tile.get_source_offset()
        source_width, source_height = tile.get_source_size()

        top_overhang = abs(min(0, source_y_offset))
        left_overhang = abs(min(0, source_x_offset))
        bottom_overhang = abs(
            min(0, self.height - (source_y_offset + source_height))
        )
        right_overhang = abs(
            min(0, self.width - (source_x_offset + source_width))
        )

        valid_source_height = source_height - top_overhang - bottom_overhang
        valid_source_width = source_width - left_overhang - right_overhang

        valid_source_y_offset = max(0, source_y_offset)
        valid_source_x_offset = max(0, source_x_offset)
        valid_source_window = (
            (
                valid_source_y_offset,
                valid_source_y_offset + valid_source_height,
            ),
            (
                valid_source_x_offset,
                valid_source_x_offset + valid_source_width,
            ),
        )

        # Tile data with zero values is considered as no valid tile data.
        tile_source_shape = (len(bands), source_height, source_width)
        tile_data_source = np.zeros(
            tile_source_shape, dtype=self.get_data_type()
        )
        if fill_value:
            np.moveaxis(tile_data_source, 0, 2)[:, :] = fill_value
        try:
            tile_data_source[
                :,
                top_overhang : top_overhang + valid_source_height,
                left_overhang : left_overhang + valid_source_width,
            ] = self.read(indexes=bands, window=valid_source_window)
        except rasterio.errors.RasterioIOError:
            # This try-except-clause catches errors like:
            #  rasterio.errors.RasterioIOError: Read or write failed.
            #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
            #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
            #  TIFFReadEncodedStrip() failed.
            # Usually this error appears for tiles covering areas outside the
            #  raster image.
            # Since tile_data_source is already initialized with 0 values,
            #  there is nothing left to do.
            pass

        msg = f"{tile_data_source.shape} vs. {tile_source_shape}"
        assert tile_data_source.shape == tile_source_shape, msg

        # C,H,W -> H,W,C
        tile_data_source = np.moveaxis(tile_data_source, 0, 2)
        tile_data_disk = cv2.resize(
            tile_data_source,
            tile.get_disk_size(),
            interpolation=cv2_resampling,
        )
        return tile_data_disk

    def get_raster_data_of_tile(self, tile, bands, resampling, legacy=False):
        if isinstance(tile, MercatorTile):
            tile_data = self._get_raster_data_of_mercator_tile(
                tile, bands, resampling
            )
        elif isinstance(tile, ImagePixelTile):
            if legacy:
                tile_data = self._get_raster_data_of_local_tile_legacy(
                    tile, bands, resampling
                )
            else:
                tile_data = self._get_raster_data_of_local_tile(
                    tile, bands, resampling
                )
        else:
            assert False
        return tile_data

    def _get_mercator_tile_pixel_corners(self, tile):
        [
            tile_left_top_raster_crs,
            tile_right_top_raster_crs,
            tile_right_bottom_raster_crs,
            tile_left_bottom_raster_crs,
        ] = tile.compute_tile_bound_corners(dst_crs=self.crs)
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

    ###########################################################################
    #                               GSD
    ###########################################################################
    def get_gsd(self):
        meta_data_dict = self.tags()
        assert "GSD" in meta_data_dict
        gsd_meter_per_pixel = float(meta_data_dict["GSD"])
        return gsd_meter_per_pixel

    def get_meter_as_pixel(self, length):
        return length / self.get_gsd()

    ###########################################################################
    #                               Geojson
    ###########################################################################

    def write_pixel_corners_as_geojson(self, geojson_ofp, as_polygon=False):
        # Geojson coordinates must be in EPSG_4326
        corner_epsg_4326_list = [
            self.get_upper_left_pixel_corner_crs(dst_crs=EPSG_4326),
            self.get_upper_right_pixel_corner_crs(dst_crs=EPSG_4326),
            self.get_lower_right_pixel_corner_crs(dst_crs=EPSG_4326),
            self.get_lower_left_pixel_corner_crs(dst_crs=EPSG_4326),
        ]
        if as_polygon:
            write_points_as_geojson_polygon(geojson_ofp, corner_epsg_4326_list)
        else:
            corner_name_list = [
                "upper_left",
                "upper_right",
                "lower_right",
                "lower_left",
            ]
            write_points_as_geojson_points(
                geojson_ofp, corner_epsg_4326_list, corner_name_list
            )

    def write_bound_corners_as_geojson(
        self, geojson_ofp, dst_crs=None, as_polygon=False
    ):
        corner_dst_crs_list = [
            self.get_left_top_bound_corner(dst_crs),
            self.get_right_top_bound_corner(dst_crs),
            self.get_right_bottom_bound_corner(dst_crs),
            self.get_left_bottom_bound_corner(dst_crs),
        ]

        x_list, y_list = zip(*corner_dst_crs_list)
        if dst_crs is not None:
            x_list, y_list = transform_coords(
                dst_crs, EPSG_4326, x_list, y_list
            )
        else:
            x_list, y_list = transform_coords(
                self.get_crs(), EPSG_4326, x_list, y_list
            )

        # Geojson coordinates must be in EPSG_4326
        corner_epsg_4326_list = list(zip(x_list, y_list))

        if as_polygon:
            write_points_as_geojson_polygon(geojson_ofp, corner_epsg_4326_list)
        else:
            corner_name_list = [
                "upper_left",
                "upper_right",
                "lower_right",
                "lower_left",
            ]
            write_points_as_geojson_points(
                geojson_ofp, corner_epsg_4326_list, corner_name_list
            )

    def write_mask_as_geojson(self, geo_json_ofp):
        # https://rasterio.readthedocs.io/en/latest/index.html?highlight=polygon#rasterio-access-to-geospatial-raster-data
        # Read the dataset's valid data mask as a ndarray.
        mask = self.dataset_mask()
        pixel_to_crs_transform, crs = self.get_transform_pixel_to_crs()
        # Extract feature shapes and values from the array.
        polygon_list = []
        for polygon, val in rasterio.features.shapes(
            mask, transform=pixel_to_crs_transform
        ):
            # Polygons are GeoJSON-like dicts
            # Geojson coordinates must be in EPSG_4326
            polygon = transform_geom(crs, EPSG_4326, polygon)
            polygon_list.append(polygon)
        assert len(polygon_list) == 1
        polygon = polygon_list[0]
        write_polygon_as_geojson_polygon(geo_json_ofp, polygon)

    def _get_raster_data_of_local_tile_legacy(self, tile, bands, resampling):
        cv2_resampling = convert_rasterio_to_opencv_resampling(resampling)
        source_x_offset, source_y_offset = tile.get_source_offset()
        source_width, source_height = tile.get_source_size()
        window = (
            (source_y_offset, source_y_offset + source_height),
            (source_x_offset, source_x_offset + source_width),
        )
        tile_source_shape = (len(bands), source_height, source_width)
        try:
            tile_data_source = self.read(indexes=bands, window=window)
        except rasterio.errors.RasterioIOError:
            # This try-except-clause catches errors like:
            #  rasterio.errors.RasterioIOError: Read or write failed.
            #  IReadBlock failed at X offset 0, Y offset 3: /path/to/file.tif,
            #  band 1: IReadBlock failed at X offset 0, Y offset 3599:
            #  TIFFReadEncodedStrip() failed.
            # Usually this error appears for tiles covering areas outside the
            #  raster image.
            # Tile data with zero values is considered as no valid tile data.
            tile_data_source = np.zeros(
                tile_source_shape, dtype=self.get_data_type()
            )

        if tile_data_source.shape != tile_source_shape:
            # For deployment:
            tile_data_source = np.resize(tile_data_source, tile_source_shape)

            # # For debugging:
            # #  Set invalid values / areas outside of raster to 1. Values
            # #  must not be 0, otherwise tiles are treated as "no-data".
            # tile_data_source_resized = np.ones(
            #     tile_source_shape, dtype=np.uint8
            # )
            # actual_bands, actual_height, actual_width = tile_data_source.shape
            # tile_data_source_resized[
            #     0:actual_bands, 0:actual_height, 0:actual_width
            # ] = tile_data_source
            # tile_data_source = tile_data_source_resized

        msg = f"{tile_data_source.shape} vs. {tile_source_shape}"
        assert tile_data_source.shape == tile_source_shape, msg

        # C,H,W -> H,W,C
        tile_data_source = np.moveaxis(tile_data_source, 0, 2)
        tile_data_disk = cv2.resize(
            tile_data_source,
            tile.get_disk_size(),
            interpolation=cv2_resampling,
        )
        return tile_data_disk
