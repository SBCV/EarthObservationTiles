from shapely.geometry import mapping, shape
from supermercado import burntiles

from eot.crs.crs import CRS, transform_geom
from eot.geojson_ext.parse_utility import _parse_geojson_polygon
from eot.tiles.mercator_tile import MercatorTile


def _parse_geojson_polygon_per_tile(
    tile_to_feature_list, polygon, zoom, dst_crs, detected_category
):
    polygon = _parse_geojson_polygon(polygon)

    if dst_crs != CRS.from_epsg(4326):
        try:
            polygon = transform_geom(dst_crs, CRS.from_epsg(4326), polygon)
        except:  # negative buffer could lead to empty/invalid geom
            return tile_to_feature_list

    for tile in burntiles.burn(
        [{"type": "feature", "geometry": polygon}], zoom=zoom
    ):
        tile_to_feature_list[MercatorTile(*tile)].append(
            {
                "type": "feature",
                "geometry": polygon,
                "category": detected_category,
            }
        )


def _parse_geojson_geometry_per_tile(
    tile_to_feature_list, geometry, zoom, dst_crs, detected_category, buffer
):
    if buffer:
        geometry = transform_geom(
            dst_crs, CRS.from_epsg(3857), geometry
        )  # be sure to be planar
        geometry = mapping(shape(geometry).buffer(buffer))
        dst_crs = CRS.from_epsg(3857)

    if geometry["type"] == "Polygon":
        _parse_geojson_polygon_per_tile(
            tile_to_feature_list, geometry, zoom, dst_crs, detected_category
        )

    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            _parse_geojson_polygon_per_tile(
                tile_to_feature_list,
                polygon={"type": "Polygon", "coordinates": polygon},
                zoom=zoom,
                dst_crs=dst_crs,
                detected_category=detected_category,
            )
    else:
        assert False


def parse_geojson_feature_per_tile(
    tile_to_feature_list, feature, zoom, crs, requested_categories, buffer=0
):
    # Buffer adds a geometrical area around each feature (distance in meter)
    if not feature or not feature["geometry"]:
        return

    # https://datatracker.ietf.org/doc/html/rfc7946
    feature_properties = feature["properties"]
    feature_geometry = feature["geometry"]

    detected_category = _get_category_from_feature_properties(
        feature_properties, requested_categories
    )
    if requested_categories is not None and detected_category is None:
        return

    geojson_geometry_object_type = feature_geometry["type"]
    if geojson_geometry_object_type == "GeometryCollection":
        for current_geometry in feature_geometry["geometries"]:
            _parse_geojson_geometry_per_tile(
                tile_to_feature_list,
                current_geometry,
                zoom,
                crs,
                detected_category,
                buffer,
            )
    else:
        assert geojson_geometry_object_type in ["Polygon", "MultiPolygon"]
        _parse_geojson_geometry_per_tile(
            tile_to_feature_list,
            feature_geometry,
            zoom,
            crs,
            detected_category,
            buffer,
        )


def _get_category_from_feature_properties(properties, requested_categories):
    intersection = set(properties.keys()).intersection(
        set(requested_categories)
    )
    if len(intersection) == 0:
        result = None
    elif len(intersection) == 1:
        result = intersection.pop()
    else:
        assert False
    return result
