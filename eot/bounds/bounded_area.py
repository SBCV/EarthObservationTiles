from eot.crs.crs import EPSG_3857
from eot.crs.crs import EPSG_4326

from eot.geojson_ext.geojson_writing import (
    write_points_as_geojson_polygon,
    write_points_as_geojson_points,
)
from eot.crs.crs import transform_coords
from eot.crs.crs import transform_bounds


class PixelArea:
    def get_transform_pixel_to_crs(self):
        raise NotImplementedError

    def get_left_top_pixel_corner(self):
        raise NotImplementedError

    def get_right_top_pixel_corner(self):
        raise NotImplementedError

    def get_left_bottom_pixel_corner(self):
        raise NotImplementedError

    def get_right_bottom_pixel_corner(self):
        raise NotImplementedError

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


class BoundedPixelArea(PixelArea):
    def get_transform_pixel_to_crs(self):
        raise NotImplementedError

    def get_crs(self):
        raise NotImplementedError

    def compute_bounds_in_crs(self):
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

        # fmt:off
        left = min(upper_left_t[0], upper_right_t[0], lower_left_t[0], lower_right_t[0])
        bottom = min(upper_left_t[1], upper_right_t[1], lower_left_t[1], lower_right_t[1])
        right = max(upper_left_t[0], upper_right_t[0], lower_left_t[0], lower_right_t[0])
        top = max(upper_left_t[1], upper_right_t[1], lower_left_t[1], lower_right_t[1])
        # fmt:on
        return left, bottom, right, top

    def get_bounds_crs(self, dst_crs=None):
        """
        Nota bene: Transforming the coordinates of the bounds (relative to
         raster.crs / raster.gcps) to the target crs (i.e. dst_crs) would yield
         a DIFFERENT result.
        """
        l, b, r, t = self.compute_bounds_in_crs()
        if dst_crs is not None:
            l, b, r, t = transform_bounds(self.get_crs(), dst_crs, l, b, r, t)
        return l, b, r, t

    def get_bounds_epsg_3857(self):
        # Return a Bbox (left, bottom, right, top) defined in EPSG:3857
        # https://epsg.io/3857
        #   used in Google Maps, OpenStreetMap, Bing, ArcGIS, ESRI
        l, b, r, t = self.get_bounds_crs(EPSG_3857)
        return l, b, r, t

    def get_bounds_epsg_4326(self):
        # Return a LngLatBbox (west, south, east, north) defined in EPSG:4326
        # https://epsg.io/4326
        #   used in GPS
        w, s, e, n = self.get_bounds_crs(EPSG_4326)
        return w, s, e, n

    def get_left_top_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return l, t

    def get_right_top_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return r, t

    def get_left_bottom_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return l, b

    def get_right_bottom_bound_corner(self, dst_crs=None):
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return r, b

    @staticmethod
    def _transform_coord_list(scr_crs, dst_crs, src_crs_list):
        assert scr_crs is not None
        assert dst_crs is not None
        x_list, y_list = zip(*src_crs_list)
        if scr_crs != dst_crs:
            x_list, y_list = transform_coords(scr_crs, dst_crs, x_list, y_list)
        dst_crs_list = list(zip(x_list, y_list))
        return dst_crs_list

    ###########################################################################
    #                               Bound Corner
    ###########################################################################

    def compute_bound_corners(self, dst_crs):
        # NB: Do not confuse "bound corners" with "bounds" or "pixel corner"
        # NB: the raster class uses EPSG_3857 for tiling
        src_crs = self.get_crs()
        bound_corner_crs_list = [
            self.get_left_top_bound_corner(),
            self.get_right_top_bound_corner(),
            self.get_right_bottom_bound_corner(),
            self.get_left_bottom_bound_corner(),
        ]
        bound_corner_crs_list = self._transform_coord_list(
            scr_crs=src_crs,
            dst_crs=dst_crs,
            src_crs_list=bound_corner_crs_list,
        )
        # tile_left_top_dst_crs, tile_right_top_dst_crs, tile_right_bottom_dst_crs, tile_left_bottom_dst_crs
        return bound_corner_crs_list

    def write_bound_corners_as_geojson(self, geojson_ofp, as_polygon=False):
        # Geojson coordinates must be in EPSG_4326
        bound_corner_epsg_4326_list = self.compute_bound_corners(EPSG_4326)

        if as_polygon:
            write_points_as_geojson_polygon(
                geojson_ofp, bound_corner_epsg_4326_list
            )
        else:
            corner_name_list = [
                "upper_left",
                "upper_right",
                "lower_right",
                "lower_left",
            ]
            write_points_as_geojson_points(
                geojson_ofp, bound_corner_epsg_4326_list, corner_name_list
            )
