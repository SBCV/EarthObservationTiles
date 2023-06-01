import os
import geojson
from eot.crs.crs import CRS
from eot.geojson_ext import geojson_precision

# https://python-geojson.readthedocs.io/en/latest/#geojson-objects


def _reformat_geojson_polygon(polygon):
    # https://python-geojson.readthedocs.io/en/latest/#polygon
    # https://stevage.github.io/geojson-spec/#appendix-A.3
    #  No holes:
    #     {
    #         "type": "Polygon",
    #         "coordinates": [
    #             [
    #                 [100.0, 0.0],
    #                 ...
    #                 [100.0, 0.0]
    #             ]
    #         ]
    #     }
    # With holes:
    #     {
    #         "type": "Polygon",
    #         "coordinates": [
    #             [
    #                 [100.0, 0.0],
    #                 ...
    #                 [100.0, 0.0]
    #             ],
    #             [
    #                 [100.8, 0.8],
    #                 ...
    #                 [100.8, 0.8]
    #             ]
    #         ]
    #     }
    if isinstance(polygon.coordinates, list):
        # https://github.com/Toblerity/Shapely/issues/245
        for i, ring in enumerate(polygon.coordinates):
            # GeoJSON coordinates could be N dimensional
            polygon.coordinates[i] = [
                [x, y]
                for point in ring
                for x, y in zip([point[0]], [point[1]])
            ]
    return polygon


def _extract_polygon_list_from_geojson_geometry(geometry):
    # https://stevage.github.io/geojson-spec/#appendix-A.3
    # {
    #     "type": "Polygon",
    #     "coordinates": [
    #         [
    #             [100.0, 0.0],
    #             ...
    #             [100.0, 0.0]
    #         ]
    #     ]
    # }
    # https://stevage.github.io/geojson-spec/#appendix-A.6
    # {
    #     "type": "MultiPolygon",
    #     "coordinates": [
    #         [
    #             [
    #                 [102.0, 2.0],
    #                 ...
    #                 [102.0, 2.0]
    #             ]
    #         ],
    #         [
    #             [
    #                 [100.0, 0.0],
    #                 ...
    #                 [100.0, 0.0]
    #             ],
    #             [
    #                 [100.2, 0.2],
    #                 ...
    #                 [100.2, 0.2]
    #             ]
    #         ]
    #     ]
    # }
    polygon_list = []
    if isinstance(geometry, geojson.Polygon):
        polygon_list.append(_reformat_geojson_polygon(geometry))
    elif isinstance(geometry, geojson.MultiPolygon):
        for coordinate_list in geometry.coordinates:
            polygon_list.append(
                _reformat_geojson_polygon(
                    geojson.Polygon(
                        coordinates=coordinate_list,
                        precision=geojson_precision,
                    ),
                )
            )
    return polygon_list


def _extract_polygon_list_from_geojson_feature(feature):
    # https://stevage.github.io/geojson-spec/#section-1.5
    # {
    #     "type": "Feature",
    #     "geometry": {
    #        "type": "Polygon",
    #        "coordinates": [
    #            [
    #                [100.0, 0.0],
    #                ...
    #                [100.0, 0.0]
    #            ]
    #        ]
    # }
    # https://stevage.github.io/geojson-spec/#appendix-A.7
    # {
    #     "type": "Feature",
    #     "geometry": {
    #     "type": "GeometryCollection",
    #     "geometries": [
    #         {
    #             "type": "Polygon",
    #             "coordinates": [
    #                [
    #                    [100.0, 0.0],
    #                    ...
    #                    [100.0, 0.0]
    #                ]
    #            ]
    #         }, {
    #             "type": "Polygon",
    #             "coordinates": [
    #                [
    #                    [100.0, 0.0],
    #                    ...
    #                    [100.0, 0.0]
    #                ]
    #            ]
    #         }
    #     ]
    # }
    polygon_list = []
    if not feature or not feature.geometry:
        return []

    feature_geometry = feature.geometry
    if isinstance(feature_geometry, geojson.GeometryCollection):
        for geometry in feature_geometry.geometries:
            polygon_list.extend(
                _extract_polygon_list_from_geojson_geometry(geometry)
            )
    else:
        polygon_list.extend(
            _extract_polygon_list_from_geojson_geometry(feature_geometry)
        )
    return polygon_list


def _get_geojson_epsg(feature_collection):
    # https://en.wikipedia.org/wiki/Spatial_reference_system#Identifier
    #   SRID = Spatial Reference System Identifier is a unique value used to
    #   unambiguously identify projected, unprojected, and local spatial
    #   coordinate system definitions
    try:
        # Example entry:
        # "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } },
        crs_mapping = {"CRS84": "4326", "900913": "3857"}
        srid = feature_collection["crs"]["properties"]["name"].split(":")[-1]
        if srid not in crs_mapping:
            srid = int(srid)
        else:
            srid = int(crs_mapping[srid])
    except:
        srid = int(4326)
    crs = CRS.from_epsg(srid)
    return crs


def _read_geojson_feature_list(geojson_ifp):
    with open(os.path.expanduser(geojson_ifp)) as fp:
        assert fp, "Unable to open {}".format(geojson_ifp)
        feature_or_feature_collection = geojson.load(fp)
        crs = _get_geojson_epsg(feature_or_feature_collection)
        if isinstance(
            feature_or_feature_collection, geojson.FeatureCollection
        ):
            feature_list = feature_or_feature_collection.features
        elif isinstance(feature_or_feature_collection, geojson.Feature):
            feature_list = [feature_or_feature_collection]
        else:
            assert False
    return feature_list, crs


def read_geojson_polygon_list(geojson_ifp):
    feature_list, crs = _read_geojson_feature_list(geojson_ifp)
    polygon_list = []
    for feature in feature_list:
        for polygon in _extract_polygon_list_from_geojson_feature(feature):
            # Skip empty polygons
            if len(polygon.coordinates) == 0:
                continue
            polygon_list.append(polygon)
    return polygon_list, crs
