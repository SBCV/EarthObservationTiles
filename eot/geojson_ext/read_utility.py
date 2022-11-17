import os
import json

from eot.geojson_ext.parse_utility import (
    parse_geojson_features,
)
from eot.crs.crs import CRS


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


def read_geojson_features(geojson_ifp):
    with open(os.path.expanduser(geojson_ifp)) as fp:
        assert fp, "Unable to open {}".format(geojson_ifp)
        features = json.load(fp)
        crs = _get_geojson_epsg(features)
        features = (
            features["features"]
            if "features" in features.keys()
            else [features]
        )
    return features, crs


def read_and_parse_geojson_features(geojson_ifp, dst_crs=None):
    features, src_crs = read_geojson_features(geojson_ifp)
    polygon_list, dst_crs = parse_geojson_features(features, src_crs, dst_crs)
    return polygon_list, dst_crs
