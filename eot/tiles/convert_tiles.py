import json

import psycopg2
import supermercado
from eot.tiles.mercator_tile import MercatorTile


def convert_tiles_to_granules(tiles, pg):
    """Retrieve Intersecting Sentinel Granules from tiles."""

    conn = psycopg2.connect(pg)
    db = conn.cursor()
    assert db

    granules = set()
    tiles = [
        "-".join(str(val) for val in tile.get_x_y_z()) + "\n" for tile in tiles
    ]
    for feature in supermercado.uniontiles.union(tiles, True):
        geom = json.dumps(feature["geometry"])
        query = """SELECT id FROM neo.s2_granules
                   WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromGeoJSON('{}'), 4326))""".format(
            geom
        )
        db.execute(query)
        granules.update([str(granule[0]) for granule in db.fetchall()])

    return granules


def convert_tiles_to_geojson(tiles, union=True):
    """Convert tiles to their footprint GeoJSON."""

    first = True
    geojson = '{"type":"FeatureCollection","features":['

    if union:  # smaller tiles union geometries (but losing properties)
        for tile in tiles:
            assert isinstance(tile, MercatorTile)
        tiles = ["-".join(map(str, tile.get_z_x_y())) + "\n" for tile in tiles]
        for feature in supermercado.uniontiles.union(tiles, True):
            geojson += (
                json.dumps(feature) if first else "," + json.dumps(feature)
            )
            first = False
    else:  # keep each tile geometry and properties (but fat)
        for tile in tiles:
            assert isinstance(tile, MercatorTile)
            prop = '"properties":{{"x":{},"y":{},"z":{}}}'.format(
                *tile.get_x_y_z()
            )
            geom = '"geometry":{}'.format(json.dumps(tile.feature("geometry")))
            geojson += '{}{{"type":"Feature",{},{}}}'.format(
                "," if not first else "", geom, prop
            )
            first = False

    geojson += "]}"
    return geojson
