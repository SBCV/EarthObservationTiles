import geojson
from eot.crs.crs import transform_geom, CRS


def parse_mask(tile_mask, tile_transform, src_crs):
    from eot.geometry.geometry import get_feature_shapes

    geojson_feature_list = []
    for shape, value in get_feature_shapes(
        tile_mask,
        transform=tile_transform,
        mask=tile_mask,
    ):
        if src_crs is not None:
            if src_crs != CRS.from_epsg(4326):
                shape = transform_geom(src_crs, CRS.from_epsg(4326), shape)

        geojson_polygon = geojson.Polygon(
            coordinates=shape["coordinates"], precision=16
        )
        geojson_feature = geojson.Feature(geometry=geojson_polygon)
        geojson_feature_list.append(geojson_feature)
    return geojson_feature_list
