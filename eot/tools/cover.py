import os
import sys

import json
import math
import psycopg2
import collections

from tqdm import tqdm
from random import shuffle

from eot.core import web_ui
from eot.tiles.tile_manager import TileManager
from eot.geojson_ext.read_utility import (
    read_geojson_features,
)
from neat_eo.geojson_ext.parse_per_tile_utility import (
    parse_geojson_feature_per_tile,
)
from eot.tiles.tile import Tile
from eot.rasters.raster import Raster
from eot.crs.crs import EPSG_4326
from eot.crs.crs import transform_bounds
from neat_eo.core.log import Logs


def add_parser(subparser, formatter_class):

    help = "Generate a tiles covering list (i.e either X,Y,Z or relative path excluding filename extension)"
    parser = subparser.add_parser(
        "cover", help=help, formatter_class=formatter_class
    )

    inp = parser.add_argument_group(
        "Input [one among the following is required]"
    )
    inp.add_argument("--dir", type=str, help="plain tiles dir path")
    inp.add_argument(
        "--bbox",
        type=str,
        help="a lat/lon bbox: xmin,ymin,xmax,ymax or a bbox: xmin,xmin,xmax,xmax,EPSG:xxxx",
    )
    inp.add_argument(
        "--geojson", type=str, nargs="+", help="path to GeoJSON features files"
    )
    inp.add_argument("--cover", type=str, help="a cover file path")
    inp.add_argument(
        "--raster", type=str, nargs="+", help="a raster file path"
    )
    inp.add_argument(
        "--sql",
        type=str,
        help="SQL to retrieve geometry features (e.g SELECT geom FROM a_table)",
    )

    db = parser.add_argument_group(
        "Spatial DataBase [required with --sql input]"
    )
    db.add_argument(
        "--pg",
        type=str,
        help="PostgreSQL dsn using psycopg2 syntax (e.g 'dbname=db user=postgres')",
    )

    out = parser.add_argument_group("Outputs")
    out.add_argument(
        "--zoom",
        type=int,
        help="zoom level of tiles [required, except with --dir or --cover inputs]",
    )
    help = "Output type (default: cover)"
    out.add_argument(
        "--type",
        type=str,
        choices=["cover", "extent", "ui", "geojson"],
        default="cover",
        help=help,
    )
    out.add_argument(
        "--union",
        action="store_true",
        help="if set, union adjacent tiles, imply --type geojson",
    )
    out.add_argument(
        "--splits",
        type=str,
        help="if set, shuffle and split in several cover subpieces (e.g 50/15/35)",
    )
    out.add_argument(
        "--out",
        type=str,
        nargs="*",
        help="cover output paths [required except with --type extent]",
    )
    out.add_argument(
        "--web_ui_base_url",
        type=str,
        help="alternate Web UI base URL, if ui mode",
    )
    out.add_argument(
        "--web_ui_template",
        type=str,
        help="alternate Web UI template path, if ui mode",
    )

    parser.set_defaults(func=main)


def _get_cover_from_raster(args):
    print(
        "neo cover from {} at zoom {}".format(args.raster, args.zoom),
        file=sys.stderr,
        flush=True,
    )
    cover = set()
    for raster_file in args.raster:
        with Raster.get_from_file(os.path.expanduser(raster_file)) as raster:
            try:
                tiles = raster.get_tiles(
                    tile_type=args.tile_type, zoom=args.zoom
                )
            except:
                print(
                    "WARNING: projection error, SKIPPING: {}".format(
                        raster_file
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                continue

            cover.update(tiles)

    cover = list(cover)
    return cover


def _get_cover_from_geojson(args):
    print(
        "neo cover from {} at zoom {}".format(args.geojson, args.zoom),
        file=sys.stderr,
        flush=True,
    )
    tile_to_feature_list = collections.defaultdict(list)
    for geojson_ifp in args.geojson:
        features, crs = read_geojson_features(geojson_ifp)
        for feature in tqdm(features, ascii=True, unit="feature"):
            parse_geojson_feature_per_tile(
                tile_to_feature_list=tile_to_feature_list,
                feature=feature,
                zoom=args.zoom,
                crs=crs,
                requested_categories=None,
            )
    cover = tile_to_feature_list.keys()
    return cover


def _get_cover_from_sql(args):
    print(
        "neo cover from {} {} at zoom {}".format(args.sql, args.pg, args.zoom),
        file=sys.stderr,
        flush=True,
    )
    conn = psycopg2.connect(args.pg)
    assert conn, "Unable to connect to PostgreSQL database."
    db = conn.cursor()

    query = """
                WITH
                  sql  AS ({}),
                  geom AS (SELECT "1" AS geom FROM sql AS t("1"))
                  SELECT '{{"type": "Feature", "geometry": '
                         || ST_AsGeoJSON((ST_Dump(ST_Transform(ST_Force2D(geom.geom), 4326))).geom, 6)
                         || '}}' AS features
                  FROM geom
                """.format(
        args.sql
    )

    db.execute(query)
    assert (
        db.rowcount is not None and db.rowcount != -1
    ), "SQL Query return no result."

    tile_to_feature_list = collections.defaultdict(list)

    for feature in tqdm(
        db.fetchall(), ascii=True, unit="feature"
    ):  # FIXME: fetchall will not always fit in memory...
        parse_geojson_feature_per_tile(
            tile_to_feature_list,
            feature=json.loads(feature[0]),
            zoom=args.zoom,
            crs=4326,
            requested_categories=None,
        )

    cover = tile_to_feature_list.keys()
    return cover


def _get_cover_from_bbox(args):
    try:
        w, s, e, n, crs = args.bbox.split(",")
        w, s, e, n = map(float, (w, s, e, n))
    except:
        crs = None
        w, s, e, n = map(float, args.bbox.split(","))
    assert (
        isinstance(w, float) and isinstance(s, float) and w < e and s < n
    ), "Invalid bbox parameter."

    print(
        "neo cover from {} at zoom {}".format(args.bbox, args.zoom),
        file=sys.stderr,
        flush=True,
    )
    if crs:
        w, s, e, n = transform_bounds(crs, EPSG_4326, w, s, e, n)
        assert isinstance(w, float) and isinstance(
            s, float
        ), "Unable to deal with raster projection"
    cover = Tile.get_mercator_tiles(w, s, e, n, args.zoom)
    return cover


def _get_cover_from_csv(args):
    print("neo cover from {}".format(args.cover), file=sys.stderr, flush=True)
    cover = [
        tile
        for tile in TileManager.read_tiles_from_csv(
            os.path.expanduser(args.cover)
        )
    ]
    return cover


def _get_cover_from_dir(args):
    print("neo cover from {}".format(args.dir), file=sys.stderr, flush=True)
    cover = [
        tile
        for tile in TileManager.read_tiles_from_dir(
            os.path.expanduser(args.dir)
        )
    ]
    return cover


def _get_cover_at_zoom_level(args, cover):
    cover_at_zoom = []
    for tile in tqdm(cover, ascii=True, unit="tile"):
        if args.zoom and tile.get_zoom() != args.zoom:
            w, s, e, n = tile.get_bounds_epsg_4326()

            for t in Tile.get_mercator_tiles(w, s, e, n, args.zoom):
                unique = True
                for _t in cover_at_zoom:
                    if _t == t:
                        unique = False
                if unique:
                    cover_at_zoom.append(t)
        else:
            cover_at_zoom.append(tile)
    return cover_at_zoom


def _split_cover(args, cover):
    splits = [int(split) for split in args.splits.split("/")]
    assert (
        len(splits) == len(args.out) and 0 < sum(splits) <= 100
    ), "Invalid split value or incoherent with out paths."

    shuffle(cover)  # in-place
    cover_splits = [
        math.floor(len(cover) * split / 100)
        for i, split in enumerate(splits, 1)
    ]
    if (
        len(splits) > 1
        and sum(map(int, splits)) == 100
        and len(cover) > sum(map(int, splits))
    ):
        cover_splits[0] = len(cover) - sum(
            map(int, cover_splits[1:])
        )  # no tile waste
    s = 0
    covers = []
    for e in cover_splits:
        covers.append(cover[s : s + e])
        s += e
    return covers


def _write_extent(args, cover):
    extent_w, extent_s, extent_n, extent_e = (180.0, 90.0, -180.0, -90.0)
    for tile in tqdm(cover, ascii=True, unit="tile"):
        w, s, e, n = tile.get_bounds_epsg_4326()
        extent_w, extent_s, extent_n, extent_e = (
            min(extent_w, w),
            min(extent_s, s),
            max(extent_n, n),
            max(extent_e, e),
        )
    extent = "{:.8f},{:.8f},{:.8f},{:.8f}".format(
        extent_w, extent_s, extent_n, extent_e
    )

    if args.out:
        if os.path.dirname(args.out[0]) and not os.path.isdir(
            os.path.dirname(args.out[0])
        ):
            os.makedirs(os.path.dirname(args.out[0]), exist_ok=True)

        with open(args.out[0], "w") as fp:
            fp.write(extent)
    else:
        print(extent)


def _write_covers_as_ui(args, covers):
    template = (
        "leaflet.html" if not args.web_ui_template else args.web_ui_template
    )
    base_url = args.web_ui_base_url if args.web_ui_base_url else "."
    os.makedirs(args.out[0], exist_ok=True)
    web_ui(args.out[0], base_url, covers[0], covers[0], "png", template)


def _write_covers_as_csv(args, covers):
    for i, cover in enumerate(covers):
        if os.path.dirname(args.out[i]) and not os.path.isdir(
            os.path.dirname(args.out[i])
        ):
            os.makedirs(os.path.dirname(args.out[i]), exist_ok=True)
        TileManager.write_tiles_as_csv(args.out[i], cover)


def _write_covers_as_geojson(args, covers):
    for i, cover in enumerate(covers):
        if os.path.dirname(args.out[i]) and not os.path.isdir(
            os.path.dirname(args.out[i])
        ):
            os.makedirs(os.path.dirname(args.out[i]), exist_ok=True)
        TileManager.write_tiles_as_geojson(args.out[i], cover, args.union)


def main(args):

    assert not (
        args.type == "extent" and args.splits
    ), "--splits and --type extent are mutually exclusive options"
    assert not (
        args.type == "extent" and args.out and len(args.out) > 1
    ), "--type extent option imply a single --out path"
    assert not (
        args.type == "ui" and len(args.out) != 1
    ), "--type ui option imply a single --out path"
    assert not (
        args.type != "extent" and not args.out
    ), "--out mandatory [except with --type extent]"
    assert not (
        args.union and args.type != "geojson"
    ), "--union imply --type geojson"
    assert not (args.sql and not args.pg), "--sql option imply --pg"
    assert (
        int(args.bbox is not None)
        + int(args.geojson is not None)
        + int(args.sql is not None)
        + int(args.dir is not None)
        + int(args.raster is not None)
        + int(args.cover is not None)
        == 1
    ), "One, and only one, input type must be provided, among: --dir, --bbox, --cover, --raster, --geojson or --sql"

    assert args.zoom or (args.dir or args.cover), "Zoom parameter is required."

    args.out = (
        [os.path.expanduser(out) for out in args.out] if args.out else None
    )

    cover = []
    if args.raster:
        Logs.sinfo("Get cover from raster")
        cover = _get_cover_from_raster(args)
    if args.geojson:
        Logs.sinfo("Get cover from Geojson")
        cover = _get_cover_from_geojson(args)
    if args.sql:
        Logs.sinfo("Get cover from SQL")
        cover = _get_cover_from_sql(args)
    if args.bbox:
        Logs.sinfo("Get cover from BBOX")
        cover = _get_cover_from_bbox(args)
    if args.cover:
        Logs.sinfo("Get cover from CSV")
        cover = _get_cover_from_csv(args)
    if args.dir:
        Logs.sinfo("Get cover from Directory")
        cover = _get_cover_from_dir(args)
    assert len(cover), "No tiles in cover"

    cover_at_zoom = _get_cover_at_zoom_level(args, cover)

    if args.splits:
        covers_at_zoom = _split_cover(args, cover_at_zoom)
    else:
        covers_at_zoom = [cover_at_zoom]

    if args.type == "extent":
        _write_extent(args, cover)
    if args.type == "ui":
        _write_covers_as_ui(args, covers_at_zoom)
    if args.type == "geojson":
        _write_covers_as_geojson(args, covers_at_zoom)
    if args.type == "cover":
        _write_covers_as_csv(args, covers_at_zoom)
