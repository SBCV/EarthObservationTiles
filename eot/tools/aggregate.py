import os
import sys
from distutils.util import strtobool
from rasterio.enums import Resampling

from eot.core.load import load_config
from eot.tiles.tile_manager import TileManager
from eot.labels.label_manager import LabelManager
from eot.tools.utility.category import get_requested_category_indices
from eot.tools.aggregate_utility.geojson import (
    create_grid_geojson,
    create_category_geojson,
)
from eot.tools.aggregate_utility.image import create_images


def add_parser(subparser, formatter_class):
    parser = subparser.add_parser(
        "aggregate",
        help="Extract GeoJSON from tiles masks",
        formatter_class=formatter_class,
    )

    inp = parser.add_argument_group("Inputs")
    inp.add_argument(
        "--masks_idp",
        type=str,
        required=True,
        help="input masks directory path [required]",
    )
    inp.add_argument(
        "--requested_category_titles",
        type=str,
        nargs="+",
        required=True,
        help="type of features to extract (i.e class title) [required]",
    )
    inp.add_argument(
        "--masks_raster_name",
        type=str,
        help="if provided, only masks of a specific raster in masks_idp are aggregated",
    )
    inp.add_argument(
        "--config",
        type=str,
        help="path to config file [required, if no global config setting]",
    )

    # https://docs.python.org/3/library/argparse.html#mutual-exclusion
    ofp = parser.add_argument_group("Output")
    # Option 1: aggregate arbitrary geo tile masks as geojson
    ofp.add_argument(
        "--geojson_odp",
        type=str,
        help="path to output directory to store geojson with category features",
    )
    ofp.add_argument(
        "--geojson_grid_ofn",
        type=str,
        default="grid.json",
        help="file name to store the grid as geojson",
    )
    # Option 2: aggregate geo tile masks as a single image (and overlay with
    # a single raster image)
    ofp.add_argument(
        "--gray_mask_png_ofp",
        type=str,
        help="path to output file to store aggregated masks",
    )
    ofp.add_argument(
        "--color_mask_png_ofp",
        type=str,
        help="path to output file to store aggregated masks",
    )
    ofp.add_argument(
        "--overlay_mask_png_ofp",
        type=str,
        help="path to output file to overlay with aggregated masks",
    )
    ofp.add_argument(
        "--overlay_grid_png_ofp",
        type=str,
        help="path to output file to overlay with tile grid",
    )
    ofp.add_argument(
        "--use_pixel_projection",
        type=lambda x: bool(strtobool(x)),
        default=True,
        help="Defines how the aggregated masks are projected to the raster image (pixel or polygon based)",
    )
    ofp.add_argument(
        "--pixel_projection_overlay_resampling",
        type=int,
        # Meaning of resampling values:
        # nearest = 0, bilinear = 1, cubic = 2, cubic_spline = 3, lanczos = 4
        default=0,
        help="Defines how (in the case of mercator tiles) the overlay raster images are resampled",
    )
    # Additional parameter corresponding to "--mask_overlay_png_ofp"
    ofp.add_argument(
        "--original_raster_ifp",
        type=str,
        help="path to the (original) input file used for aggregating the masks",
    )
    ofp.add_argument(
        "--normalized_raster_fp",
        type=str,
        help="path to the (normalized) input file (accelerates the computation)",
    )
    ofp.add_argument(
        "--save_normalized_raster",
        type=lambda x: bool(strtobool(x)),
        default=False,
        help="If provided, writes the normalized raster to --normalized_raster_fp (accelerates future computations)",
    )
    ofp.add_argument(
        "--use_contours",
        type=lambda x: bool(strtobool(x)),
        default=True,
        help="",
    )
    ofp.add_argument(
        "--mask_values",
        type=str,
        nargs="+",
        help="",
    )
    ofp.add_argument(
        "--overlay_weight",
        type=int,
        default=192,
        help="",
    )
    ofp.add_argument(
        "--tile_boundary_color",
        type=str,
        # Chartreuse
        default="128,255,0",
        help="",
    )
    parser.set_defaults(func=main)


def _initialize_index_to_category_color(args, config_categories_sorted):
    args.idx_to_category_color = {
        category_index: config_categories_sorted[category_index].palette_color
        for category_index in args.category_indices
    }

    return args


def _initialize_tile_boundary_color(args):
    assert (
        len(args.tile_boundary_color.split(",")) == 3
    ), "--tile_boundary_color expect r,g,b (e.g 0,0,255)"
    args.tile_boundary_color = list(
        map(int, args.tile_boundary_color.split(","))
    )
    return args


def _check_masks(masks, masks_dp):
    assert len(masks), "empty masks directory: {}".format(masks_dp)


def _create_dir(odp):
    os.makedirs(os.path.expanduser(odp), exist_ok=True)


def _initialize_category_indices(args, config_categories_sorted):
    args.category_indices = get_requested_category_indices(
        defined_categories=config_categories_sorted,
        requested_category_names=args.requested_category_titles,
    )
    return args


def main(args):
    print(args)
    config = load_config(args.config)
    config_categories_sorted = LabelManager.get_config_categories_sorted(
        config.categories
    )
    args = _initialize_category_indices(args, config_categories_sorted)
    args = _initialize_index_to_category_color(args, config_categories_sorted)
    args = _initialize_tile_boundary_color(args)

    masks = list(
        TileManager.read_tiles_from_dir(
            idp=args.masks_idp, target_raster_name=args.masks_raster_name
        )
    )
    _check_masks(masks, args.masks_idp)

    if args.geojson_odp is not None:
        print(
            f"neo aggregate {args.requested_category_titles} from {args.masks_idp} to {args.geojson_odp}",
            file=sys.stderr,
            flush=True,
        )
        _create_dir(args.geojson_odp)
        geojson_ofp = os.path.join(args.geojson_odp, args.geojson_grid_ofn)
        create_grid_geojson(masks, geojson_ofp, args.original_raster_ifp)
        create_category_geojson(
            masks,
            config_categories_sorted,
            args.category_indices,
            args.original_raster_ifp,
            args.geojson_odp,
        )

    image_ofps = [
        args.gray_mask_png_ofp,
        args.color_mask_png_ofp,
        args.overlay_mask_png_ofp,
        args.overlay_grid_png_ofp,
    ]
    write_png_image = False
    for image_ofp in image_ofps:
        if image_ofp is not None:
            _create_dir(os.path.dirname(args.gray_mask_png_ofp))
            write_png_image = True

    if write_png_image:
        resampling = Resampling(args.pixel_projection_overlay_resampling)
        create_images(args, masks, args.use_pixel_projection, resampling)
