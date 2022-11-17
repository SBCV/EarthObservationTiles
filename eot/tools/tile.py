import os
import sys
from collections import defaultdict
from distutils.util import strtobool
from tqdm import tqdm
import concurrent.futures as futures
from rasterio.enums import Resampling
import numpy as np
import shutil

from eot.core.load import load_config
from eot.labels.label_manager import LabelManager
from eot.core.web_ui import create_web_ui
from eot.core.log import Logs
from eot.tiles.read_write_tile import (
    read_image_tile_from_file,
    write_image_tile_to_file,
    read_label_tile_from_file_as_indices,
    write_label_tile_to_file,
)
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.tiles.tile import TileTypes
from eot.tiles.tile_path_manager import TilePathManager
from eot.tiles.tile_manager import TileManager
from eot.rasters.raster import Raster
from eot.tools.utility.category import get_requested_category_indices
from eot.tools.tile_utility.compute_tile_spatial_info import create_meta_info
from eot.tools.aggregate_utility.geojson import create_grid_geojson
from eot.utility.os_extension import makedirs_safely


def add_parser(subparser, formatter_class):
    parser = subparser.add_parser(
        "tile",
        help="Tile a raster, or a rasters coverage",
        formatter_class=formatter_class,
    )

    inp = parser.add_argument_group("Inputs")
    inp.add_argument(
        "--raster_ifps",
        type=str,
        required=True,
        nargs="+",
        help="path to raster files to tile [required]",
    )
    inp.add_argument(
        "--cover",
        type=str,
        help="path to csv tiles cover file, to filter tiles to tile [optional]",
    )
    inp.add_argument(
        "--bands",
        type=str,
        help="list of 1-n index bands to select (e.g 1,2,3) [optional]",
    )
    inp.add_argument(
        "--dataset_type",
        type=str,
        required=True,
        help="name of the dataset",
    )

    out = parser.add_argument_group("Output")
    out.add_argument(
        "--tile_type",
        type=str,
        required=True,
        help="tile type of tiles [required]",
    )

    # https://docs.python.org/3/library/argparse.html#mutual-exclusion
    zoom_or_tile_size_group = out.add_mutually_exclusive_group(required=True)
    zoom_or_tile_size_group.add_argument(
        "--zoom",
        type=int,
        help="zoom level of tiles",
    )
    zoom_or_tile_size_group.add_argument(
        "--input_tile_size_in_pixel",
        type=str,
        help="input tile size in pixel",
    )
    zoom_or_tile_size_group.add_argument(
        "--input_tile_size_in_meter",
        type=str,
        help="input tile size in meter",
    )

    out.add_argument(
        "--input_tile_stride_in_pixel",
        type=str,
        help="input tile stride in pixel",
    )
    out.add_argument(
        "--input_tile_stride_in_meter",
        type=str,
        help="input tile stride in meter",
    )
    out.add_argument(
        "--align_to_base_tile_area",
        action="store_true",
        help="restrict tiling area to base tiles (i.e. tile stride = tile size)",
    )
    out.add_argument(
        "--tile_overhang",
        action="store_true",
        help="define if tiles are hanging over raster image boundaries",
    )

    out.add_argument(
        "--output_tile_size_pixel",
        type=str,
        default="512,512",
        help="output tile size in pixels [default: 512,512]",
    )
    help = "nodata pixel value, used by default to remove coverage border's tile [default: 0]"
    out.add_argument(
        "--nodata",
        type=int,
        default=0,
        choices=range(0, 256),
        metavar="[0-255]",
        help=help,
    )
    help = "Skip tile if nodata pixel ratio > threshold. [default: 100]"
    out.add_argument(
        "--no_data_threshold",
        type=int,
        default=100,
        choices=range(0, 101),
        metavar="[0-100]",
        help=help,
    )
    out.add_argument(
        "--keep_borders",
        action="store_true",
        help="keep tiles even if borders are empty (nodata)",
    )
    out.add_argument(
        "--create_aux_files",
        action="store_true",
        help="if set, create an aux.xml file for each tile",
    )
    out.add_argument(
        "--out",
        type=str,
        required=True,
        help="output directory path [required]",
    )
    out.add_argument(
        "--tile_overview_txt_ofn",
        type=str,
        required=True,
        help="output path to the spatial info file [required]",
    )
    lab = parser.add_argument_group("Labels")
    lab.add_argument(
        "--write_labels",
        action="store_true",
        help="if set, generate label tiles",
    )
    lab.add_argument(
        "--config",
        type=str,
        help="path to config file [required with --write_labels, if no global config setting]",
    )
    lab.add_argument(
        "--convert_images_to_labels",
        action="store_true",
        help="convert images to labels before writing [required with --write_labels, if no global config setting]",
    )
    lab.add_argument(
        "--requested_category_titles",
        type=str,
        nargs="+",
        required=False,
        help="type of features to rasterize (i.e class title) [required with --write_labels, if no global config setting]",
    )
    perf = parser.add_argument_group("Performances")
    perf.add_argument(
        "--workers", type=int, help="number of workers [default: raster files]"
    )

    ui = parser.add_argument_group("Web UI")
    ui.add_argument(
        "--web_ui_base_url", type=str, help="alternate Web UI base URL"
    )
    ui.add_argument(
        "--web_ui_template", type=str, help="alternate Web UI template path"
    )
    ui.add_argument(
        "--no_web_ui", action="store_true", help="desactivate Web UI output"
    )

    debug = parser.add_argument_group("Labels")
    debug.add_argument(
        "--debug_max_number_tiles_per_image",
        type=int,
        help="Maximum number of tiles per image",
    )
    debug.add_argument(
        "--clear_split_data",
        type=lambda x: bool(strtobool(x)),
        help="Delete intermediate split data",
    )
    parser.set_defaults(func=main)


def is_no_data(image, nodata, threshold_percent, keep_borders):
    if not keep_borders:
        if (
            np.all(image[0, :, :] == nodata)
            or np.all(image[-1, :, :] == nodata)
            or np.all(image[:, 0, :] == nodata)
            or np.all(image[:, -1, :] == nodata)
        ):
            return True  # pixel border is nodata, on all bands

    C, W, H = image.shape
    threshold = threshold_percent / 100
    num_no_data_pixels = np.sum(image[:, :, :] == nodata)
    treat_as_no_data = num_no_data_pixels >= C * W * H * threshold
    return treat_as_no_data


def _initialize_bands(args):
    try:
        if args.bands:
            args.bands = list(map(int, args.bands.split(",")))
        else:
            args.bands = None
    except:
        raise ValueError(f"invalid --args.bands value ({args.bands})")

    if not args.bands:
        raster = Raster.get_from_file(os.path.expanduser(args.raster_ifps[0]))
        args.bands = raster.indexes
        raster.close()

    return args


def _initialize_tile_values(args, attribute_name, skip_none_value):
    if skip_none_value and getattr(args, attribute_name) is None:
        return args
    try:
        attribute_values = getattr(args, attribute_name).split(",")
        msg = f"--{attribute_name} expect width,height value (e.g 512,512)"
        assert len(attribute_values) == 2, msg
        if attribute_name in [
            "input_tile_size_in_pixel",
            "input_tile_stride_in_pixel",
            "output_tile_size_pixel",
        ]:
            width, height = list(map(int, attribute_values))
        elif attribute_name in [
            "input_tile_size_in_meter",
            "input_tile_stride_in_meter",
        ]:
            width, height = list(map(float, attribute_values))
        else:
            assert False
        setattr(args, attribute_name, [width, height])
    except:
        raise ValueError(f"invalid --args.{attribute_name} value,value")
    return args


def _initialize_output_tile_size_pixel(args):
    return _initialize_tile_values(args, "output_tile_size_pixel", False)


def _initialize_input_tile_size_in_pixel(args):
    return _initialize_tile_values(args, "input_tile_size_in_pixel", True)


def _initialize_input_tile_stride_in_pixel(args):
    return _initialize_tile_values(args, "input_tile_stride_in_pixel", True)


def _initialize_input_tile_stride_in_meter(args):
    return _initialize_tile_values(args, "input_tile_stride_in_meter", True)


def _initialize_input_tile_size_in_meter(args):
    return _initialize_tile_values(args, "input_tile_size_in_meter", True)


def _initialize_workers(args):
    if not args.workers:
        args.workers = min(os.cpu_count(), len(args.raster_ifps))
    return args


def _initialize_out(args):
    args.out = os.path.expanduser(args.out)
    return args


def _initialize_tile_type(args):
    args.tile_type = TileTypes[args.tile_type].value
    return args


def _compute_tile_cover(args_cover):
    cover = (
        [
            tile
            for tile in TileManager.read_tiles_from_csv(
                os.path.expanduser(args_cover)
            )
        ]
        if args_cover
        else None
    )
    return cover


def _create_odp(args_out):
    if os.path.dirname(os.path.expanduser(args_out)):
        os.makedirs(args_out, exist_ok=True)


def _create_web_ui_files(args, tiles):
    if tiles and not args.no_web_ui:
        ext = "jpg" if len(args.bands) == 3 else "tif"
        ext = "png" if len(args.bands) == 1 else ext
        template = (
            "leaflet.html"
            if not args.web_ui_template
            else args.web_ui_template
        )
        base_url = args.web_ui_base_url if args.web_ui_base_url else "."
        create_web_ui(args.out, base_url, tiles, tiles, ext, template)


def _get_config_category_sorted(write_labels, config_ifp):
    if write_labels:
        config = load_config(config_ifp)
        config_categories_sorted = LabelManager.get_config_categories_sorted(
            config.categories
        )
    else:
        config_categories_sorted = None
    return config_categories_sorted


def _compute_raster_fp_to_tiles(
    args, cover, log, align_to_base_tile_area=None, tile_overhang=None
):
    raster_fp_to_tiles = {}
    tile_disk_width, tile_disk_height = args.output_tile_size_pixel

    for raster_fp in args.raster_ifps:
        log.info(f"Determine tiles for raster {raster_fp} ...")
        raster = Raster.get_from_file(os.path.expanduser(raster_fp))
        args_band_indices = set(args.bands)
        raster_band_indices = set(raster.indexes)
        err_msg = f"Missing required bands ({args_band_indices}) in raster {raster_fp} ({raster_band_indices})"
        assert args_band_indices.issubset(raster_band_indices), err_msg

        tiles = raster.get_tiles(
            tile_type=args.tile_type,
            input_tile_zoom_level=args.zoom,
            input_tile_size_in_pixel=args.input_tile_size_in_pixel,
            input_tile_size_in_meter=args.input_tile_size_in_meter,
            input_tile_stride_in_pixel=args.input_tile_stride_in_pixel,
            input_tile_stride_in_meter=args.input_tile_stride_in_meter,
            align_to_base_tile_area=align_to_base_tile_area,
            tile_overhang=tile_overhang,
        )
        for tile in tiles:
            tile.disk_height = tile_disk_height
            tile.disk_width = tile_disk_width
        if args.tile_type.is_local_image_tile():
            for tile in tiles:
                if tile.get_raster_transform() is not None:
                    tile.compute_and_set_tile_transform()

        ######################################################################
        # try:
        #     tiles = Tile.get_raster_mercator_tiles(raster, args.zoom)
        # except:
        #     log.info(
        #         f"WARNING: missing or invalid raster projection, SKIPPING: {raster_fp}"
        #     )
        #     skipped_image_list.append(raster_fp)
        #     continue
        ######################################################################
        if cover:
            # Note: Depending on the number of tiles and the size of the cover,
            #  the existence check ("tile in cover") in the following list
            #  comprehension is really slow. Thus, use a set to accelerate
            #  the existence check from O(n) to O(1) in the average case.
            #  Further, pre-compute the cover set outside the list
            #  comprehension.
            cover_set = set(cover)
            tiles = [tile for tile in tiles if tile in cover_set]
        raster_fp_to_tiles[raster_fp] = tiles
        raster.close()

    return raster_fp_to_tiles


def _compute_tile_to_raster_fps(args, raster_fp_to_tiles):
    tile_to_raster_fps = {}
    for raster_fp in args.raster_ifps:
        tiles = raster_fp_to_tiles[raster_fp]
        for tile in tiles:
            if tile not in tile_to_raster_fps.keys():
                tile_to_raster_fps[tile] = []
            tile_to_raster_fps[tile].append(raster_fp)
    return tile_to_raster_fps


def _compute_total_tile_number(args, raster_fp_to_tiles):
    total_tile_number = 0
    for raster_fp in args.raster_ifps:
        tiles = raster_fp_to_tiles[raster_fp]
        total_tile_number += len(tiles)
    assert total_tile_number, "Found no (valid) tiles in raster data"
    return total_tile_number


def _compute_odp(args, tile_to_raster_fps, tile, raster_fp, splits_path):
    if len(tile_to_raster_fps[tile]) > 1:
        odp = os.path.join(
            splits_path,
            str(tile_to_raster_fps[tile].index(raster_fp)),
        )
    else:
        odp = args.out
    return odp


def _write_tile_data_to_disk(
    odp, args, geo_tile, tile_data, config_categories_sorted, create_aux_file
):

    if args.write_labels:
        write_label_tile_to_file(
            odp,
            geo_tile,
            tile_data,
            config_categories_sorted,
            create_aux_file=create_aux_file,
        )
    else:
        write_image_tile_to_file(
            odp,
            geo_tile,
            tile_data,
            ext=".jpg",
            create_aux_file=create_aux_file,
        )


def _get_unique_colors(img_data):
    return np.unique(img_data.reshape(-1, img_data.shape[2]), axis=0)


def _convert_images_to_labels(
    tile_data, categories, category_indices, dataset_type
):
    """Convert the labels contained presented as images"""

    shape = tile_data.shape[0:2]
    label_data = np.zeros(shape=shape, dtype=np.uint8)
    for category_index in category_indices:
        category = categories[category_index]
        if dataset_type in category.label_values:
            label_tuple_list = category.label_values[dataset_type]
            for label_tuple in label_tuple_list:
                msg = (
                    f'The label value "{label_tuple}" of category'
                    f' "{category.title}" does not match the number of channels'
                    f" of the raster data (i.e. {tile_data.shape[2]}) containing the"
                    " labels."
                )
                assert len(label_tuple) == tile_data.shape[-1], msg
                indices = np.where(np.all(tile_data == label_tuple, axis=-1))
                label_data[indices] = category_index
    return label_data


def _perform_image_or_label_tiling(
    args,
    raster_fp,
    raster_fp_to_tiles,
    tile_to_raster_fps,
    create_aux_files,
    temp_splits_dp,
    progress,
):
    if args.convert_images_to_labels:
        config_categories_sorted = _get_config_category_sorted(
            args.write_labels, args.config
        )
        category_indices = get_requested_category_indices(
            defined_categories=config_categories_sorted,
            requested_category_names=args.requested_category_titles,
        )
        dataset_type = args.dataset_type
    else:
        category_indices = None
        dataset_type = None
        config_categories_sorted = None
    if args.write_labels:
        resampling_method = Resampling.nearest
    else:
        resampling_method = Resampling.bilinear

    tiled_by_worker = []
    worker_specific_tiles = raster_fp_to_tiles[raster_fp]
    with Raster.get_from_file(raster_fp) as raster:

        for tile in worker_specific_tiles:
            odp = _compute_odp(
                args, tile_to_raster_fps, tile, raster_fp, temp_splits_dp
            )
            tile_is_in_multiple_rasters = _is_tile_in_multiple_rasters(
                tile_to_raster_fps, tile
            )

            tile_data = raster.get_raster_data_of_tile(
                tile, args.bands, resampling_method
            )

            if len(tile_data.shape) == 2:
                tile_data = tile_data[:, :, np.newaxis]

            tile_data_is_valid = not is_no_data(
                tile_data,
                args.nodata,
                args.no_data_threshold,
                args.keep_borders,
            )

            if args.convert_images_to_labels:
                tile_data = _convert_images_to_labels(
                    tile_data,
                    config_categories_sorted,
                    category_indices,
                    dataset_type,
                )

            # Always write the data to disk, if it is part of mutliple rasters
            if (
                args.write_labels
                or tile_data_is_valid
                or tile_is_in_multiple_rasters
            ):
                _write_tile_data_to_disk(
                    odp,
                    args,
                    tile,
                    tile_data,
                    config_categories_sorted,
                    create_aux_file=create_aux_files,
                )
                if not tile_is_in_multiple_rasters:
                    tiled_by_worker.append(tile)

            progress.update()

    return tiled_by_worker


def _perform_image_or_label_tiling_with_workers(
    args,
    raster_fp_to_tiles,
    tile_to_raster_fps,
    total_tile_number,
    create_aux_files,
    log,
):
    """Subdivides a set of images in images or label tiles"""

    temp_splits_dp = os.path.join(os.path.expanduser(args.out), ".splits")
    tiles_in_single_raster = []

    if args.write_labels:
        desc = "Label tiling"
    else:
        desc = "Image tiling"
    progress = tqdm(
        desc=desc,
        total=total_tile_number,
        ascii=True,
        unit="tile",
    )

    # Option 1: Parallel processing
    with futures.ThreadPoolExecutor(args.workers) as executor:

        def compute_tiles(raster_fp):
            if raster_fp not in raster_fp_to_tiles:
                return None
            tiles_of_thread = _perform_image_or_label_tiling(
                args,
                raster_fp,
                raster_fp_to_tiles,
                tile_to_raster_fps,
                create_aux_files,
                temp_splits_dp,
                progress,
            )
            return tiles_of_thread

        for tiles_of_thread in executor.map(compute_tiles, args.raster_ifps):
            if tiles_of_thread is not None:
                tiles_in_single_raster.extend(tiles_of_thread)

    # Option 2: Sequential processing
    # for raster_fp in args.raster_ifps:
    #     if raster_fp not in raster_fp_to_tiles:
    #         return None
    #     tiled = _perform_image_or_label_tiling(
    #         args,
    #         raster_fp,
    #         raster_fp_to_tiles,
    #         tile_to_raster_fps,
    #         create_aux_files,
    #         temp_splits_dp,
    #         progress,
    #     )
    #
    #     if tiled is not None:
    #         tiles_in_single_raster.extend(tiled)

    # Note: After individually processing all raster images, we aggregate the
    #  visual information of tiles covering multiple raster images.
    perform_aggregation = tiles_are_part_of_multiple_images(tile_to_raster_fps)
    log.vinfo("perform_aggregation", perform_aggregation)
    if perform_aggregation:
        tiles_in_multiple_raster = _aggregate_splitted_tiles(
            temp_splits_dp,
            tile_to_raster_fps,
            args,
            log,
            args.clear_split_data,
            args.create_aux_files,
        )
    else:
        tiles_in_multiple_raster = []

    return tiles_in_single_raster, tiles_in_multiple_raster


def _aggregate_splitted_tiles(
    temp_splits_dp,
    tile_to_raster_fps,
    args,
    log,
    clear_split_data=True,
    create_aux_file=False,
):

    """
    Aggregate tiles that are splitted over multiple (potentially adjacent
    or overlapping) satellite images.

    Consider multiple tiles corresponding to different satellite images
    that are overlapping. Many tiles in overlapping regions show large numbers
    of no data values. This function aggregates the actual visual information
    contained in the overlapping tiles.
    """

    config_categories_sorted = _get_config_category_sorted(
        args.write_labels, args.config
    )
    log.vinfo("clear_split_data", clear_split_data)
    log.vinfo("temp_splits_dp", temp_splits_dp)
    total = sum(
        [
            1
            for tile in tile_to_raster_fps.keys()
            if len(tile_to_raster_fps[tile]) > 1
        ]
    )
    progress = tqdm(
        desc="Aggregate splits", total=total, ascii=True, unit="tile"
    )
    aggregated_tiles = []
    with futures.ThreadPoolExecutor(args.workers) as executor:

        def worker(tile):
            # Check if we have work to do
            if len(tile_to_raster_fps[tile]) == 1:
                return None
            width = tile.disk_width
            height = tile.disk_height
            if args.write_labels:
                aggregated_tile_data = np.zeros((width, height, 1), np.int)
            else:
                aggregated_tile_data = np.zeros(
                    (width, height, len(args.bands)), np.uint8
                )
            for i in range(len(tile_to_raster_fps[tile])):
                root = os.path.join(temp_splits_dp, str(i))
                absolute_fp = TilePathManager.read_absolute_tile_fp_from_dir(
                    root, tile
                )
                if args.write_labels:
                    splitted_tile = read_label_tile_from_file_as_indices(
                        absolute_fp
                    )
                else:
                    splitted_tile = read_image_tile_from_file(absolute_fp)

                if len(splitted_tile.shape) == 2:
                    splitted_tile = splitted_tile.reshape(
                        (width, height, 1)
                    )  # H,W -> H,W,C

                assert (
                    aggregated_tile_data.shape == splitted_tile.shape
                ), f"{aggregated_tile_data.shape}, {splitted_tile.shape}"
                # Copy information from the splitted_tile
                indices_with_0_value = np.where(aggregated_tile_data == 0)
                aggregated_tile_data[indices_with_0_value] += splitted_tile[
                    indices_with_0_value
                ]

            if not args.write_labels and is_no_data(
                aggregated_tile_data,
                args.nodata,
                args.no_data_threshold,
                args.keep_borders,
            ):
                progress.update()
                return None

            _write_tile_data_to_disk(
                args.out,
                args,
                tile,
                aggregated_tile_data,
                config_categories_sorted,
                create_aux_file,
            )

            progress.update()
            return tile

        for tiled in executor.map(worker, tile_to_raster_fps.keys()):
            if tiled is not None:
                aggregated_tiles.append(tiled)

        if clear_split_data:
            if temp_splits_dp and os.path.isdir(temp_splits_dp):
                shutil.rmtree(temp_splits_dp)  # Delete suffixes dir if any

    log.vinfo("aggregated_tiles", aggregated_tiles)
    return aggregated_tiles


def _is_tile_in_multiple_rasters(tile_to_raster_fps, tile):
    num_images = len(tile_to_raster_fps[tile])
    assert num_images >= 0
    return len(tile_to_raster_fps[tile]) > 1


def tiles_are_part_of_multiple_images(tile_to_raster_fps):
    for tile, image_fp in tile_to_raster_fps.items():
        num_images = len(tile_to_raster_fps[tile])
        assert num_images >= 0
        if num_images > 1:
            return True
    return False


def _check_tile_to_raster_fps(tile_to_raster_fps):
    reference_tile = next(iter(tile_to_raster_fps.keys()))
    if isinstance(reference_tile, ImagePixelTile):
        for tile, raster_fps in tile_to_raster_fps.items():
            # In the case of ImagePixelTile the tile should only be part of a
            # single raster
            assert len(raster_fps) == 1


def _compute_raster_fp_to_disk_tiles(
    disk_tiles, tile_to_raster_fps, assertion
):
    raster_fp_to_disk_tiles = defaultdict(list)
    for disk_tile in disk_tiles:
        raster_fps = tile_to_raster_fps[disk_tile]
        assert assertion(raster_fps)
        for raster_fp in raster_fps:
            raster_fp_to_disk_tiles[raster_fp].append(disk_tile)
    return raster_fp_to_disk_tiles


def _write_tile_overview(
    args,
    ofp,
    disk_tiles_in_single_raster,
    disk_tiles_in_multiple_raster,
    raster_fp_to_tiles,
    tile_to_raster_fps,
    no_data_threshold,
    debug=False,
):
    num_total_tiles = sum(
        [len(tiles) for tiles in raster_fp_to_tiles.values()]
    )
    _check_tile_to_raster_fps(tile_to_raster_fps)

    # Depending on the no_data_threshold only a subset of tiles is processed
    # (i.e. is actually written to disk)

    with open(ofp, "w") as overview_file:
        sep = os.linesep
        threshold_line = (
            f"No-data-threshold to filter tiles: {no_data_threshold}%{sep}"
        )
        overview_file.write(threshold_line)
        meta_info = create_meta_info(
            tile_type=args.tile_type,
            input_tile_zoom_level=args.zoom,
            input_tile_size_in_pixel=args.input_tile_size_in_pixel,
            input_tile_size_in_meter=args.input_tile_size_in_meter,
            input_tile_stride_in_pixel=args.input_tile_stride_in_pixel,
            input_tile_stride_in_meter=args.input_tile_stride_in_meter,
        )
        for data in meta_info:
            data_line, _ = data
            overview_file.write(data_line + sep)

        non_shared_output = []
        shared_output = []

        overall_tile_line = f"{len(disk_tiles_in_single_raster)} non-shared tiles on disk ({num_total_tiles} non-shared tiles in all raster images){sep}"
        non_shared_output.append(overall_tile_line + sep)
        overall_tile_line = f"{len(disk_tiles_in_multiple_raster)} shared tiles on disk ({num_total_tiles} shared tiles in all raster images){sep}"
        shared_output.append(overall_tile_line + sep)

        raster_fp_to_disk_non_shared_tiles = _compute_raster_fp_to_disk_tiles(
            disk_tiles_in_single_raster,
            tile_to_raster_fps,
            assertion=lambda x: len(x) == 1,
        )
        raster_fp_to_disk_shared_tiles = _compute_raster_fp_to_disk_tiles(
            disk_tiles_in_multiple_raster,
            tile_to_raster_fps,
            assertion=lambda x: len(x) > 1,
        )

        for raster_fp in sorted(raster_fp_to_tiles.keys()):
            raster_tiles = raster_fp_to_tiles[raster_fp]
            num_raster_tiles = len(raster_tiles)
            disk_non_shared_tiles = raster_fp_to_disk_non_shared_tiles[
                raster_fp
            ]
            disk_shared_tiles = raster_fp_to_disk_shared_tiles[raster_fp]

            per_raster_line = f"{len(disk_non_shared_tiles)} non-shared tiles on disk ({num_raster_tiles} tiles in {raster_fp}){sep}"
            non_shared_output.append(per_raster_line)
            per_raster_line = f"{len(disk_shared_tiles)} shared tiles on disk ({num_raster_tiles} tiles in {raster_fp}){sep}"
            shared_output.append(per_raster_line)

            if debug:
                ###############################################################
                # Note: Mercator tiles use bounds to determine the
                #  corresponding tiles. Thus, also tiles that are not
                #  overlapping with the actual image content "correspond" to
                #  raster image.
                ###############################################################
                debug_odp = os.path.join(args.out, "debug")
                makedirs_safely(debug_odp)

                reference_tile = next(
                    TileManager.read_tiles_from_dir(idp=args.out)
                )
                reference_fp = reference_tile.get_absolute_tile_fp()

                raster_fn = os.path.basename(raster_fp)
                raster_tiles_geojson_ofp = os.path.join(
                    debug_odp, f"{raster_fn}_grid_all.json"
                )
                processed_non_shared_tiles_geojson_ofp = os.path.join(
                    debug_odp, f"{raster_fn}_grid_processed_non_shared.json"
                )
                processed_shared_tiles_geojson_ofp = os.path.join(
                    debug_odp, f"{raster_fn}_grid_processed_shared.json"
                )
                from itertools import chain

                for image_tile in chain(
                    raster_tiles, disk_non_shared_tiles, disk_shared_tiles
                ):
                    image_tile.set_tile_fp(reference_fp, is_absolute=True)

                if isinstance(reference_tile, ImagePixelTile):
                    original_raster_ifp = raster_fp
                else:
                    original_raster_ifp = None

                create_grid_geojson(
                    raster_tiles, raster_tiles_geojson_ofp, original_raster_ifp
                )
                create_grid_geojson(
                    disk_non_shared_tiles,
                    processed_non_shared_tiles_geojson_ofp,
                    original_raster_ifp,
                )
                create_grid_geojson(
                    disk_shared_tiles,
                    processed_shared_tiles_geojson_ofp,
                    original_raster_ifp,
                )

        for line in non_shared_output:
            overview_file.write(line)
        overview_file.write(sep)
        for line in shared_output:
            overview_file.write(line)


def main(args):

    args = _initialize_bands(args)
    args = _initialize_output_tile_size_pixel(args)
    args = _initialize_input_tile_size_in_pixel(args)
    args = _initialize_input_tile_size_in_meter(args)
    args = _initialize_input_tile_stride_in_pixel(args)
    args = _initialize_input_tile_stride_in_meter(args)
    args = _initialize_workers(args)
    args = _initialize_out(args)
    args = _initialize_tile_type(args)

    cover = _compute_tile_cover(args.cover)
    _create_odp(args.out)

    log = Logs(os.path.join(args.out, "log"), out=sys.stderr)
    log.vinfo("args", args)

    log.info(
        f"neo tile {len(args.raster_ifps)} rasters on bands {args.bands}, "
        + f"on CPU with {args.workers} workers"
    )

    raster_fp_to_tiles = _compute_raster_fp_to_tiles(
        args, cover, log, args.align_to_base_tile_area, args.tile_overhang
    )
    if args.debug_max_number_tiles_per_image:
        for raster_fp, tiles in raster_fp_to_tiles.items():
            raster_fp_to_tiles[raster_fp] = tiles[
                0 : args.debug_max_number_tiles_per_image
            ]

    tile_to_raster_fps = _compute_tile_to_raster_fps(args, raster_fp_to_tiles)
    total_tile_number = _compute_total_tile_number(args, raster_fp_to_tiles)

    (
        tiles_in_single_raster,
        tiles_in_multiple_raster,
    ) = _perform_image_or_label_tiling_with_workers(
        args,
        raster_fp_to_tiles,
        tile_to_raster_fps,
        total_tile_number,
        args.create_aux_files,
        log,
    )

    if args.tile_type.is_mercator_tile():
        _create_web_ui_files(
            args, tiles_in_single_raster + tiles_in_multiple_raster
        )

    tile_overview_ofp = os.path.join(args.out, args.tile_overview_txt_ofn)
    _write_tile_overview(
        args,
        ofp=tile_overview_ofp,
        disk_tiles_in_single_raster=tiles_in_single_raster,
        disk_tiles_in_multiple_raster=tiles_in_multiple_raster,
        raster_fp_to_tiles=raster_fp_to_tiles,
        tile_to_raster_fps=tile_to_raster_fps,
        no_data_threshold=args.no_data_threshold,
    )
