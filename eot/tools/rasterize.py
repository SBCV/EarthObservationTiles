import os
import sys
from varname import nameof
from tqdm import tqdm
from functools import partial
import concurrent.futures as futures

from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.mercator_tile import MercatorTile
from eot.rasters.raster import Raster
from eot.tiles.tile_manager import TileManager
from eot.geojson_ext.geo_segmentation import GeoSegmentation
from eot.tools import initialize_category, initialize_categories

from eot.utility.log import Logs


def add_parser(subparser, formatter_class):
    parser = subparser.add_parser(
        "rasterize",
        help="Rasterize GeoJSON or PostGIS features to tiles",
        formatter_class=formatter_class,
    )

    inp = parser.add_argument_group("Inputs")
    inp.add_argument(
        "--cover_csv_ifp",
        type=str,
        required=True,
        help="path to csv tiles cover file [required]",
    )
    inp.add_argument(
        "--tile_data_categories",
        type=str,
        help="categories used for the palette in the tiles to be created",
    )
    inp.add_argument(
        "--geojson_category",
        type=str,
        help="category presented by the geojson data",
    )
    inp.add_argument(
        "--geojson_ifp_list",
        type=str,
        nargs="+",
        help="path to GeoJSON features files",
    )
    inp.add_argument(
        "--raster_ifp_list",
        type=str,
        nargs="+",
        help="path to raster features files",
    )
    inp.add_argument(
        "--buffer",
        type=float,
        help="Add a Geometrical Buffer around each Features (distance in meter)",
    )

    out = parser.add_argument_group("Outputs")
    out.add_argument(
        "--odp",
        type=str,
        required=True,
        help="output directory path [required]",
    )
    out.add_argument(
        "--append_labels",
        action="store_true",
        help="Append to existing tile if any, useful to multiclasses labels",
    )
    out.add_argument(
        "--output_tile_size_pixel",
        type=str,
        default="512,512",
        help="output tile size in pixels [default: 512,512]",
    )

    perf = parser.add_argument_group("Performances")
    perf.add_argument(
        "--workers", type=int, help="number of workers [default: CPU]"
    )

    parser.set_defaults(func=main)


def write_geojson_to_tiles(
    odp,
    output_tile_size_pixel,
    tiles,
    geojson_category,
    polygon_buffer,
    tile_data_categories,
    append_labels,
    show_progress,
    geojson_ifp,
):
    # TODO use args.workers
    geo_segmentation = GeoSegmentation.from_geojson_file(
        geojson_ifp, category_name=geojson_category.name
    )
    if polygon_buffer:
        geo_segmentation.add_polygon_buffer(polygon_buffer)

    category_palette_colors = tile_data_categories.get_category_palette_colors(
        only_active=False, include_ignore=False
    )

    geo_segmentation.write_to_tiles(
        odp=odp,
        tile_size=output_tile_size_pixel,
        tiles=tiles,
        append_labels=append_labels,
        palette_colors=category_palette_colors,
        burn_color=geojson_category.palette_index,
        show_progress=show_progress,
    )


def _check_tile_size(args):
    assert (
        len(args.output_tile_size_pixel.split(",")) == 2
    ), "--output_tile_size_pixel expect width,height value (e.g 512,512)"


def _initialize_workers(args):
    args.workers = (
        min(os.cpu_count(), args.workers) if args.workers else os.cpu_count()
    )
    return args


def _initialize_odp(args):
    args.odp = os.path.expanduser(args.odp)
    return args


def _compute_geojson_rasterization(
    args, output_tile_size_pixel, tiles, geojson_category, log
):
    workers = min(args.workers, len(args.geojson_ifp_list))
    log.info(
        "neo rasterize - Compute spatial index with {} workers".format(workers)
    )

    if len(args.geojson_ifp_list) > 1:
        # Configure progress visualization for multiple files
        progress = tqdm(
            total=len(args.geojson_ifp_list), ascii=True, unit="file"
        )
        show_multiple_file_progress = True
        show_single_file_progress = False
    else:
        # Configure progress visualization for single files
        progress = None
        show_multiple_file_progress = False
        show_single_file_progress = True

    with futures.ProcessPoolExecutor(workers) as executor:
        # Option 1:
        # for geojson_ifp in args.geojson_ifp_list:
        #     write_geojson_to_tiles(
        #         odp=args.odp,
        #         output_tile_size_pixel=output_tile_size_pixel,
        #         tiles=tiles,
        #         geojson_category=geojson_category,
        #         polygon_buffer=args.buffer,
        #         tile_data_categories=args.tile_data_categories,
        #         append_labels=args.append_labels,
        #         show_progress=show_single_file_progress,
        #         geojson_ifp=geojson_ifp,
        #     )
        # Option 2:
        for _ in executor.map(
            partial(
                write_geojson_to_tiles,
                args.odp,
                output_tile_size_pixel,
                tiles,
                geojson_category,
                args.buffer,
                args.tile_data_categories,
                args.append_labels,
                show_single_file_progress,
            ),
            args.geojson_ifp_list,
        ):
            if show_multiple_file_progress:
                progress.update()
        if show_multiple_file_progress:
            progress.close()


def _log_rasterizing_info(args, category_names, log, log_source):
    log_info_str = f"neo rasterize - rasterizing {category_names} from"
    log_info_str += (
        f" {log_source} on cover {args.cover_csv_ifp}, with {args.workers}"
    )
    log_info_str += f" tiles/batch and {args.workers} workers"
    log.info(log_info_str)


def _initialize_tile_disk_size(tiles, output_tile_size_pixel):
    for tile in tiles:
        tile_disk_width, tile_disk_height = output_tile_size_pixel
        tile.set_disk_size(tile_disk_width, tile_disk_height)
    return tiles


def _initialize_image_tile_transform(tiles, raster_ifp_list):
    raster_name_to_geo_transform_with_crs = {}
    for raster_ifp in raster_ifp_list:
        raster = Raster.get_from_file(raster_ifp)
        transform, crs = raster.get_geo_transform_with_crs()
        raster_name_to_geo_transform_with_crs[
            os.path.splitext(os.path.basename(raster.name))[0]
        ] = (transform, crs)

    for tile in tiles:
        transform, crs = raster_name_to_geo_transform_with_crs[
            tile.get_raster_name()
        ]
        tile.set_raster_transform(transform)
        tile.set_crs(crs)
        tile.compute_and_set_tile_transform()
    return tiles


def main(args):
    _check_tile_size(args)

    args = _initialize_workers(args)
    args = _initialize_odp(args)
    args = initialize_category(
        args, attribute_name=nameof(args.geojson_category)
    )
    args = initialize_categories(
        args, attribute_name=nameof(args.tile_data_categories)
    )

    if os.path.dirname(args.odp):
        os.makedirs(args.odp, exist_ok=True)
    log = Logs(os.path.join(args.odp, "log"), out=sys.stderr)

    tiles = [
        tile
        for tile in TileManager.read_tiles_from_csv(
            os.path.expanduser(args.cover_csv_ifp)
        )
    ]
    output_tile_size_pixel = list(
        map(int, args.output_tile_size_pixel.split(","))
    )

    tiles = _initialize_tile_disk_size(tiles, output_tile_size_pixel)
    if isinstance(tiles[0], ImagePixelTile):
        tiles = _initialize_image_tile_transform(tiles, args.raster_ifp_list)

    assert len(tiles), "Empty Cover: {}".format(args.cover_csv_ifp)
    category_names = args.tile_data_categories.get_category_names(
        only_active=False, include_ignore=True
    )
    if len(args.geojson_ifp_list) == 1:
        log_source = args.geojson_ifp_list
    else:
        log_source = "{} geojson files".format(len(args.geojson_ifp_list))
    _compute_geojson_rasterization(
        args=args,
        output_tile_size_pixel=output_tile_size_pixel,
        tiles=tiles,
        geojson_category=args.geojson_category,
        log=log,
    )

    _log_rasterizing_info(args, category_names, log, log_source)

    category_names = args.tile_data_categories.get_category_names(
        only_active=True, include_ignore=True
    )
    category_string = "_".join(category_names)
    csv_ofp = os.path.join(args.odp, category_string + "_cover.csv")
    with open(csv_ofp, mode="w") as cover:
        for tile in tqdm(
            tiles,
            desc="Rasterize",
            unit="tile",
            ascii=True,
        ):
            cover.write(f"{tile}  {os.linesep}")
