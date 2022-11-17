from eot.crs.crs import transform_geom


def _parse_geojson_polygon(polygon):
    if isinstance(
        polygon["coordinates"], list
    ):  # https://github.com/Toblerity/Shapely/issues/245
        for i, ring in enumerate(
            polygon["coordinates"]
        ):  # GeoJSON coordinates could be N dimensionals
            polygon["coordinates"][i] = [
                [x, y]
                for point in ring
                for x, y in zip([point[0]], [point[1]])
            ]
    return polygon


def _parse_geojson_geometry(geometry):
    polygon_list = []
    if geometry["type"] == "Polygon":
        polygon_list.append(_parse_geojson_polygon(geometry))

    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            polygon_list.append(
                _parse_geojson_polygon(
                    {"type": "Polygon", "coordinates": polygon},
                )
            )
    return polygon_list


def _parse_geojson_feature(feature):
    polygon_list = []
    if not feature or not feature["geometry"]:
        return []

    if feature["geometry"]["type"] == "GeometryCollection":
        for geometry in feature["geometry"]["geometries"]:
            polygon_list.extend(_parse_geojson_geometry(geometry))
    else:
        polygon_list.extend(_parse_geojson_geometry(feature["geometry"]))
    return polygon_list


def parse_geojson_features(features, src_crs, dst_crs=None):
    polygon_list = []
    for feature in features:
        polygon_list_current = _parse_geojson_feature(feature)
        for polygon in polygon_list_current:
            # Skip empty polygons
            if len(polygon["coordinates"]) == 0:
                continue
            polygon_list.append(polygon)
    if dst_crs is None:
        dst_crs = src_crs
    else:
        for idx, polygon in enumerate(polygon_list):
            polygon_list[idx] = transform_geom(src_crs, dst_crs, polygon)
    return polygon_list, dst_crs
