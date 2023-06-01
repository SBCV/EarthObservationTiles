import collections
import copy
from rtree import index as rtree_index
import numpy as np
import geojson
from shapely.geometry import mapping, shape
from rasterio.features import is_valid_geom
from tqdm import tqdm
from eot.geojson_ext.geojson_reading import read_geojson_polygon_list
from eot.geojson_ext import rasterize_features
from eot.geojson_ext import geojson_precision
from eot.crs.crs import transform_geom
from eot.crs.crs import EPSG_4326, EPSG_3857
from eot.geojson_ext.geojson_writing import write_geojson_object
from eot.rasters.raster_writing import write_raster
from eot.geojson_ext import get_feature_shapes
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.tile_reading import read_label_tile_from_file
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.tile_writing import write_label_tile_to_file
from eot.bounds import transform_from_bounds


class GeoSegmentation:
    def __init__(
        self,
        polygon_list=None,
        crs=None,
        mask_color=None,
        category_name=None,
    ):
        if polygon_list is None:
            polygon_list = []
        else:
            polygon_list = self._initialize_polygons(polygon_list)
        self._polygon_list = polygon_list
        self.crs = crs
        self.mask_color = mask_color
        self.category_name = category_name

    @staticmethod
    def _initialize_polygons(polygon_list):
        for polygon in polygon_list:
            msg = f"Unexpected input type: {type(polygon)}"
            assert isinstance(polygon, geojson.geometry.Polygon), msg
        return polygon_list

    @staticmethod
    def _transform_polygon(source_crs, destination_crs, polygon):
        polygon_dict_transformed = transform_geom(
            source_crs, destination_crs, polygon
        )
        polygon_transformed = geojson.Polygon(
            coordinates=polygon_dict_transformed["coordinates"],
            precision=geojson_precision,
        )
        return polygon_transformed

    @classmethod
    def _transform_polygons(cls, source_crs, destination_crs, polygon_list):
        polygon_list_transformed = []
        if len(polygon_list) > 0:
            assert isinstance(polygon_list[0], geojson.Polygon)
            for polygon in polygon_list:
                polygon_transformed = cls._transform_polygon(
                    source_crs, destination_crs, polygon
                )
                polygon_list_transformed.append(polygon_transformed)
        return polygon_list_transformed

    def get_polygons(self, destination_crs):
        if destination_crs != self.crs:
            polygon_list = self._transform_polygons(
                self.crs, destination_crs, self._polygon_list
            )
        else:
            polygon_list = self._polygon_list
        return polygon_list

    def get_number_polygons(self):
        return len(self._polygon_list)

    def add_polygon(self, polygon):
        self._polygon_list.append(polygon)

    def add_polygons(self, polygon_list):
        polygon_list = self._initialize_polygons(polygon_list)
        self._polygon_list.extend(polygon_list)

    def add_geo_segmentation(self, geo_segmentation):
        if self.crs is None:
            self.crs = geo_segmentation.crs
        else:
            assert self.crs == geo_segmentation.crs
        if self.mask_color is None:
            self.mask_color = geo_segmentation.mask_color
        else:
            assert self.mask_color == geo_segmentation.mask_color
        self.add_polygons(geo_segmentation.get_polygons(geo_segmentation.crs))

    def add_polygon_buffer(self, polygon_buffer):
        # https://geobgu.xyz/py/shapely.html#shapely-buffer
        #  Shapely does not have a notion of CRS. The buffer distance are
        #  specified in the same (undefined) units as the geometry coordinates.
        #  Also note that the .buffer distance can be negative, in which case
        #  the buffer is “internal” rather than “external”.
        polygon_crs_with_buffer_list = []
        polygon_epsg_3857_list = self.get_polygons(EPSG_3857)
        for polygon_epsg_3857 in polygon_epsg_3857_list:
            # Make sure to execute the following operation in EPSG_3857
            polygon_epsg_3857_with_buffer = mapping(
                shape(polygon_epsg_3857).buffer(polygon_buffer)
            )
            polygon_crs_with_buffer = self._transform_polygon(
                EPSG_3857, self.crs, polygon_epsg_3857_with_buffer
            )
            polygon_crs_with_buffer_list.append(polygon_crs_with_buffer)
        self._polygon_list = polygon_crs_with_buffer_list

    ###########################################################################
    #                           Geojson
    ###########################################################################

    @classmethod
    def from_geojson_file(cls, geojson_ifp, **kwargs):
        polygon_list, src_crs = read_geojson_polygon_list(geojson_ifp)
        return cls(polygon_list=polygon_list, crs=src_crs, **kwargs)

    @classmethod
    def from_geojson_files(cls, geojson_ifp_list, **kwargs):
        aggregated_polygon_list = []
        aggregated_src_crs_list = []
        for geojson_ifp in geojson_ifp_list:
            polygon_list, src_crs = read_geojson_polygon_list(geojson_ifp)
            aggregated_polygon_list.extend(polygon_list)
            aggregated_src_crs_list.append(src_crs)
        msg = f"Detected inconsistent CRS in {geojson_ifp_list}"
        assert len(set(aggregated_src_crs_list)) == 1, msg
        src_crs = aggregated_src_crs_list[0]
        return cls(polygon_list=aggregated_polygon_list, crs=src_crs, **kwargs)

    @classmethod
    def from_feature_collection(cls, feature_collection, dst_crs, **kwargs):
        polygon_list = [
            feature.geometry for feature in feature_collection.features
        ]
        return cls(polygon_list=polygon_list, crs=dst_crs, **kwargs)

    @classmethod
    def from_feature(cls, feature, dst_crs, **kwargs):
        return cls(polygon_list=[feature.geometry], crs=dst_crs, **kwargs)

    @staticmethod
    def _rgb_to_hex(rgb):
        if isinstance(rgb, str):
            assert False, f"Invalid rgb value: {rgb}"
        if type(rgb) == int:
            rgb = (rgb, rgb, rgb)
        if len(rgb) == 4:
            rgb = rgb[0:3]
        rgb_hex = "#%02x%02x%02x" % rgb
        return rgb_hex

    def _to_geojson_polygon_list(self):
        # NB: Geojson polygons must be defined in EPSG_4326
        geojson_polygon_espg_4326_list = self.get_polygons(EPSG_4326)
        for geojson_polygon in geojson_polygon_espg_4326_list:
            msg = f"{type(geojson_polygon)}"
            assert isinstance(geojson_polygon, geojson.Polygon), msg
        return geojson_polygon_espg_4326_list

    def _to_geojson_feature_list(self):
        # NB: Geojson polygons must be defined in EPSG_4326
        geojson_polygon_espg_4326_list = self._to_geojson_polygon_list()
        geojson_feature_list = [
            geojson.Feature(geometry=geojson_polygon)
            for geojson_polygon in geojson_polygon_espg_4326_list
        ]

        if self.mask_color is None:
            return geojson_feature_list

        for tile_geojson_feature in geojson_feature_list:
            # https://github.com/mapbox/simplestyle-spec/tree/master/1.1.0
            tile_geojson_feature.properties["fill"] = self._rgb_to_hex(
                self.mask_color
            )
            tile_geojson_feature.properties["fill-opacity"] = 0.5

        return geojson_feature_list

    def _to_geojson_feature_collection(self):
        # NB: Geojson polygons must be defined in EPSG_4326
        geojson_feature_list_espg_4326 = self._to_geojson_feature_list()
        geojson_feature_collection_espg_4326 = geojson.FeatureCollection(
            geojson_feature_list_espg_4326
        )
        return geojson_feature_collection_espg_4326

    def write_as_geojson_feature_collection(self, geojson_ofp):
        # NB: Geojson polygons must be defined in EPSG_4326
        feature_collection_epsg_4326 = self._to_geojson_feature_collection()
        write_geojson_object(geojson_ofp, feature_collection_epsg_4326)

    ###########################################################################
    #                           Tiles
    ###########################################################################

    @staticmethod
    def _find_polygon_bounds(polygon):
        outer_polygon_ring_coordinates = polygon.coordinates[0]
        x_values = [coord[0] for coord in outer_polygon_ring_coordinates]
        y_values = [coord[1] for coord in outer_polygon_ring_coordinates]

        min_x = min(x_values)
        min_y = min(y_values)
        max_x = max(x_values)
        max_y = max(y_values)

        # epsilon = 1.0e-10
        # min_x = min(min_x) + epsilon
        # min_y = max(min(min_y) + epsilon, -85.0511287798066)
        # max_x = max(max_x) - epsilon
        # max_y = min(max(max_y) - epsilon, 85.0511287798066)

        return min_x, min_y, max_x, max_y

    def write_to_tiles(
        self,
        odp,
        tile_size,
        tiles,
        append_labels,
        palette_colors,
        burn_color=255,
        background_color=0,
        show_progress=True,
    ):
        # https://rtree.readthedocs.io/en/latest/tutorial.html
        polygon_bounds_rtree = rtree_index.Index(interleaved=True)
        tile_crs = tiles[0].get_crs()
        polygons_tile_crs = self.get_polygons(tile_crs)
        for index, polygon_tile_crs in enumerate(polygons_tile_crs):
            polygon_bounds_rtree.insert(
                index, self._find_polygon_bounds(polygon_tile_crs)
            )

        for tile in tiles:
            overlapping_polygon_indices = polygon_bounds_rtree.intersection(
                tile.compute_bounds_in_crs()
            )
            polygons_geo_crs = self.get_polygons(self.crs)
            polygon_list_filtered = [
                polygons_geo_crs[i] for i in overlapping_polygon_indices
            ]
            geo_segmentation_tile_truncated = self.__class__(
                polygon_list=polygon_list_filtered,
                crs=self.crs,
                mask_color=self.mask_color,
                category_name=self.category_name,
            )

            if geo_segmentation_tile_truncated.get_number_polygons():

                height, width = tile_size
                transform = tile.get_tile_transform()
                crs = tile.get_crs()

                label_data = geo_segmentation_tile_truncated.to_raster_data(
                    width,
                    height,
                    transform,
                    crs,
                    burn_color=burn_color,
                    background_color=background_color,
                    image_axis_order=True,
                )
            else:
                label_data = np.zeros(shape=tile_size, dtype=np.uint8)

            write_label_tile_to_file(
                odp,
                tile,
                label_data,
                palette_colors,
                append=append_labels,
            )

    ###########################################################################
    #                           Raster
    ###########################################################################
    @classmethod
    def from_tiles(
        cls,
        tiles,
        get_mask_callback,
        raster_transform=None,
        raster_crs=None,
    ):
        if isinstance(tiles[0], ImagePixelTile):
            msg = "ImagePixelTiles requires a valid raster_transform"
            assert raster_transform is not None, msg
            msg = "ImagePixelTiles requires a valid raster_crs"
            assert raster_crs is not None, msg

        geo_segmentation = cls()

        for tile in tqdm(tiles, ascii=True, unit="mask"):
            tile_label_mat, palette = read_label_tile_from_file(
                tile.get_absolute_tile_fp()
            )
            tile_mask, mask_color = get_mask_callback(tile_label_mat, palette)

            tile.set_disk_size(*tile_label_mat.shape[-2:])
            if isinstance(tile, ImagePixelTile):
                tile.set_crs(raster_crs)
                tile.set_raster_transform(raster_transform)
                tile.compute_and_set_tile_transform()

            tile_transform = tile.get_tile_transform()
            tile_crs = tile.get_crs()

            geo_segmentation_tile = cls.from_raster_data(
                tile_mask, tile_transform, tile_crs, mask_color=mask_color
            )
            geo_segmentation.add_geo_segmentation(geo_segmentation_tile)

        return geo_segmentation

    @classmethod
    def from_raster_data(cls, raster_data, transform, crs, mask_color=None):
        geojson_polygon_list = []
        for polygon_dict, value in get_feature_shapes(
            raster_data,
            transform=transform,
            mask=raster_data,
        ):
            geojson_polygon = geojson.Polygon(
                coordinates=polygon_dict["coordinates"],
                precision=geojson_precision,
            )
            geojson_polygon_list.append(geojson_polygon)
        geo_segmentation = cls(
            polygon_list=geojson_polygon_list,
            crs=crs,
            mask_color=mask_color,
        )
        return geo_segmentation

    def to_raster_data(
        self,
        width,
        height,
        transform,
        crs,
        burn_color=255,
        background_color=0,
        image_axis_order=False,
    ):
        msg = f"{type(burn_color)}, {type(background_color)}"
        assert type(burn_color) == type(background_color), msg
        if isinstance(burn_color, int):
            burn_color = [burn_color]
        if isinstance(background_color, int):
            background_color = [background_color]
        assert len(burn_color) == len(background_color)

        data_depth = len(background_color)
        raster_data = np.full(
            (height, width, data_depth),
            background_color,
            dtype=np.uint8,
        )

        polygons = self.get_polygons(crs)
        if len(polygons) > 0:
            assert is_valid_geom(polygons[0])
            burned_shapes_array = rasterize_features(
                shapes=polygons,
                out_shape=(height, width),
                # Used as fill value for all areas not covered by input geometries
                fill=0,
                transform=transform,
                # Used as value for all geometries, if not provided in `shapes`.
                default_value=1,
                all_touched=False,
            )
            for idx, burn_color_value in enumerate(burn_color):
                burned_colors = burn_color_value * burned_shapes_array
                raster_data[:, :, idx][
                    burned_shapes_array > 0
                ] = burned_colors[burned_shapes_array > 0]

        if not image_axis_order:
            # (height, width, channel) -> (channel, height, width)
            raster_data = np.moveaxis(raster_data, 2, 0)
        return raster_data

    def write_to_raster(
        self,
        label_raster_ofp,
        raster,
        burn_color=255,
        background_color=0,
        build_overviews=True,
        compression="DEFLATE",
        predictor="1",
        color_map=None,
    ):
        # "DEFLATE" compression creates the VERY SMALL file sizes for label images
        # "LZW" compression creates reasonable file sizes for label images
        # "PACKBITS" compression creates VERY LARGE file sizes for label images
        assert compression in ["DEFLATE", "LZW"]

        # https://kokoalberti.com/articles/geotiff-compression-optimization-guide/
        #   The Deflate, LZW and ZSTD algorithms support the use of predictors,
        #   which is a method of storing only the difference from the previous
        #   value instead of the actual value. There are three predictor settings:
        #     No predictor (1, default)
        #     Horizontal differencing (2)
        #     Floating point predition (3)

        # Depending on the value of burn_color / background_color the method
        # returns a numpy array with 1, 3 or 4 channels / bands.
        raster_data = self.to_raster_data(
            raster.width,
            raster.height,
            raster.transform,
            raster.get_crs(),
            burn_color,
            background_color,
        )
        write_raster(
            raster,
            label_raster_ofp,
            overwrite_data=raster_data,
            image_axis_order=False,
            build_overviews=build_overviews,
            label_compatible_meta_data=True,
            compress=compression,
            predictor=predictor,
            color_map=color_map,
        )
