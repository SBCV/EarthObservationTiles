import mercantile
from eot.crs.crs import EPSG_3857, EPSG_4326, transform_coords
from eot.bounds import transform_from_bounds
from eot.tiles.tile import Tile
from eot.bounds.bounded_area import BoundedPixelArea


class MercatorTile(Tile, BoundedPixelArea):
    """
    This class provides an extension of "mercantile.Tile", i.e.
    Tile = namedtuple("Tile", ["x", "y", "z"])

    For Slippy Map Tiles see:
     https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    """

    CLASS_STR = "class"
    X_STR = "x"
    Y_STR = "y"
    Z_STR = "z"

    def __init__(
        self,
        x,
        y,
        z,
        disk_width=None,
        disk_height=None,
        absolute_tile_fp=None,
        relative_root_dp=None,
        relative_tile_fp=None,
    ):
        super().__init__(
            disk_width,
            disk_height,
            absolute_tile_fp,
            relative_root_dp,
            relative_tile_fp,
        )
        self._x = int(x)
        self._y = int(y)
        self._z = int(z)

    def to_tuple(self):
        return self._x, self._y, self._z

    def to_dict(self):
        dict_repr = {
            self.CLASS_STR: self.__class__.__name__,
            self.X_STR: self._x,
            self.Y_STR: self._y,
            self.Z_STR: self._z,
        }
        return dict_repr

    def get_zoom(self):
        return self._z

    def __repr__(self):
        return f"{self._x} {self._y} {self._z}"

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            self_as_tuple = (self._x, self._y, self._z)
            other_as_tuple = (other._x, other._y, other._z)
            return self_as_tuple == other_as_tuple
        else:
            return False

    def __lt__(self, other):
        # Required for sorting
        assert isinstance(other, self.__class__)
        self_as_tuple = (self._x, self._y, self._z)
        other_as_tuple = (other._x, other._y, other._z)
        return self_as_tuple < other_as_tuple

    def __hash__(self):
        # A hash is required to use Tile within sets
        return hash((self._x, self._y, self._z))

    def __iter__(self):
        return iter((self._x, self._y, self._z))

    def get_x_y_z(self):
        return self._x, self._y, self._z

    def get_z_x_y(self):
        return self._z, self._x, self._y

    ###########################################################################
    #                               Bounds
    ###########################################################################

    def compute_bounds_in_crs(self):
        """Overrides the method in BoundedPixelArea for efficiency reasons.

        The method is supposed to yield the same results. Numerical differences
         might occur.
        """

        # NB: The following holds:
        #   bounds_epsg_3857_ref = self.get_bounds_epsg_3857()
        #   bounds_epsg_4326_ref = self.get_bounds_epsg_4326()
        #   bounds_epsg_4326 = transform_bounds(
        #       EPSG_3857, EPSG_4326, *bounds_epsg_3857_ref
        #   )
        #   assert np.allclose(bounds_epsg_4326, bounds_epsg_4326_ref)
        if self.get_crs() == EPSG_3857:
            # Return a Bbox (left, bottom, right, top) defined in EPSG:3857
            # https://epsg.io/3857
            #   used in Google Maps, OpenStreetMap, Bing, ArcGIS, ESRI
            l, b, r, t = mercantile.xy_bounds(self.get_x_y_z())
            bounds = l, b, r, t
        elif self.get_crs() == EPSG_4326:
            # Return a LngLatBbox (west, south, east, north) defined in EPSG:4326
            # https://epsg.io/4326
            #   used in GPS, Geojson
            w, s, e, n = mercantile.bounds(self.get_x_y_z())
            bounds = w, s, e, n
        else:
            assert False
        return bounds

    def get_transform_pixel_to_epsg_3857(self):
        assert self.disk_width is not None
        assert self.disk_height is not None
        l, b, r, t = self.get_bounds_epsg_3857()
        pixel_to_epsg_3857_trans = transform_from_bounds(
            l, b, r, t, self.disk_width, self.disk_height
        )
        return pixel_to_epsg_3857_trans

    def get_transform_pixel_to_epsg_4326(self):
        assert self.disk_width is not None
        assert self.disk_height is not None
        w, s, e, n = self.get_bounds_epsg_4326()
        pixel_to_epsg_4326_trans = transform_from_bounds(
            w, s, e, n, self.disk_width, self.disk_height
        )
        return pixel_to_epsg_4326_trans

    def get_tile_transform(self):
        if self.get_crs() == EPSG_3857:
            return self.get_transform_pixel_to_epsg_3857()
        elif self.get_crs() == EPSG_4326:
            return self.get_transform_pixel_to_epsg_4326()
        else:
            assert False

    def get_crs(self):
        # Matches the crs of self.get_tile_transform()
        return EPSG_4326

    def get_transform_pixel_to_crs(self):
        return self.get_tile_transform(), self.get_crs()

    def feature(self, feature_name):
        assert feature_name in ["geometry"]
        return mercantile.feature(self.get_x_y_z(), precision=6)[feature_name]

    def get_neighbors(self):
        # 3x3 matrix (upper, center, bottom) x (left, center, right)
        # except (center, center)
        x, y, z = self.get_x_y_z()
        x, y, z = int(x), int(y), int(z)
        ul = self.__class__(x=x - 1, y=y - 1, z=z)
        uc = self.__class__(x=x + 0, y=y - 1, z=z)
        ur = self.__class__(x=x + 1, y=y - 1, z=z)

        cl = self.__class__(x=x - 1, y=y + 0, z=z)
        cr = self.__class__(x=x + 1, y=y + 0, z=z)

        bl = self.__class__(x=x - 1, y=y + 1, z=z)
        bc = self.__class__(x=x + 0, y=y + 1, z=z)
        br = self.__class__(x=x + 1, y=y + 1, z=z)
        neighbor_list = [ul, uc, ur, cl, cr, bl, bc, br]
        return neighbor_list

    def is_surrounded(self, tile_list):
        """Check if a tile is (completely) surrounded by others tiles"""
        neighbor_list = self.get_neighbors()
        is_completely_surrounded = True
        for neighbor in neighbor_list:
            if neighbor not in tile_list:
                is_completely_surrounded = False
        return is_completely_surrounded
