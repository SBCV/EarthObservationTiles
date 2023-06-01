import geojson
from eot.geojson_ext import geojson_precision


def write_geojson_str(geojson_ofp, geojson_str):
    with open(geojson_ofp, "w", encoding="utf-8") as geojson_file:
        assert geojson_file, "Unable to write in output file"
        geojson_file.write(geojson_str)


def write_geojson_object(geojson_ofp, geojson_object):
    geojson_str = geojson.dumps(
        geojson_object, sort_keys=True, ensure_ascii=False, indent=4
    )
    write_geojson_str(geojson_ofp, geojson_str)


def write_polygon_as_geojson_polygon(geojson_ofp, polygon):
    # A polygon is filled by default in QGIS. The style can be changed in the
    # raster layer properties
    write_geojson_object(geojson_ofp, polygon)


def write_points_as_geojson_polygon(geojson_ofp, coord_list):
    polygon = geojson.Polygon(
        coordinates=[coord_list], precision=geojson_precision
    )
    write_polygon_as_geojson_polygon(geojson_ofp, polygon)


def write_points_as_geojson_points(
    geojson_ofp, coord_list, coord_name_list=None
):
    # The names in coord_name_list can be displayed in QGIS with:
    # Right-click on layer / Properties ... / Labels / Single Labels /
    # Then select set "Label with" to "name"

    # https://gis.stackexchange.com/questions/130963/write-geojson-into-a-geojson-file-with-python
    if coord_name_list is None:
        coord_name_list = len(coord_list) * []
    assert len(coord_list) == len(coord_name_list)

    features = []
    for coord, coord_name in zip(coord_list, coord_name_list):
        point = geojson.Point(coord)
        features.append(
            geojson.Feature(geometry=point, properties={"name": coord_name})
        )
    feature_collection = geojson.FeatureCollection(features)
    write_geojson_object(geojson_ofp, feature_collection)
