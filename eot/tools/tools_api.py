import argparse
import copy
import glob
import os
import sys
from importlib import import_module

from eot.utility.log import Logs

from eot.tools.aggregate import main as aggregate_main
from eot.tools.cover import main as cover_main
from eot.tools.tile import main as tile_main
from eot.tools.rasterize import main as rasterize_main
from eot.tools.compare import main as compare_main
from eot.utility.os_ext import get_regex_fps_in_dp


def log_status(tool_name, output):
    Logs.sinfo(
        "Skipping {:12} already performed ({}) ".format(tool_name, output)
    )


def to_shell_str(param_list):
    return " ".join(map(str, param_list))


def log_shell_command(tool_name, param_list):
    Logs.sinfo("neo " + tool_name + " " + to_shell_str(param_list))


def run_tile_images(
    tif_idp,
    tif_search_regex,
    tif_ignore_regex,
    tile_odp,
    output_tile_size_pixel,
    tiling_scheme,
    compute_tiling_statistic=False,
    create_aux_files=False,
    create_polygon_files=False,
    bands=None,
    write_labels=False,
    cover_csv_ifp=None,
    convert_images_to_labels=False,
    categories=None,
    no_data_threshold=100,
    clear_split_data=True,
    debug_max_number_tiles_per_image=None,
    lazy=False,
):
    if lazy and os.path.isdir(tile_odp):
        log_status("tile", tile_odp)
        return

    tool_param_list = ["--tiling_scheme", str(tiling_scheme.name)]
    if tiling_scheme.represents_mercator_tiling():
        zoom_level = tiling_scheme.get_zoom_level()
        assert zoom_level is not None and isinstance(zoom_level, int)
        tool_param_list += ["--zoom", str(zoom_level)]
    elif tiling_scheme.is_in_pixel():
        assert tiling_scheme.get_tile_size_in_pixel(True) is not None
        tile_size_string = ",".join(
            str(tile_size)
            for tile_size in tiling_scheme.get_tile_size_in_pixel(True)
        )
        tool_param_list += ["--input_tile_size_in_pixel", tile_size_string]
        if tiling_scheme.get_tile_stride_in_pixel(True) is not None:
            tile_stride_string = ",".join(
                str(tile_stride)
                for tile_stride in tiling_scheme.get_tile_stride_in_pixel(True)
            )
            tool_param_list += [
                "--input_tile_stride_in_pixel",
                tile_stride_string,
            ]
    elif tiling_scheme.is_in_meter():
        assert tiling_scheme.get_tile_size_in_meter(True) is not None
        tile_size_string = ",".join(
            str(tile_size)
            for tile_size in tiling_scheme.get_tile_size_in_meter(True)
        )
        tool_param_list += ["--input_tile_size_in_meter", tile_size_string]
        if tiling_scheme.get_tile_stride_in_meter(True) is not None:
            tile_stride_string = ",".join(
                str(tile_stride)
                for tile_stride in tiling_scheme.get_tile_stride_in_meter(True)
            )
            tool_param_list += [
                "--input_tile_stride_in_meter",
                tile_stride_string,
            ]
    else:
        assert False

    if tiling_scheme.uses_border_tiles():
        tool_param_list += ["--keep_borders"]

    if tiling_scheme.represents_local_image_tiling():
        tool_param_list += [
            "--tiling_alignment",
            tiling_scheme.get_alignment(),
        ]
        if tiling_scheme.is_aligned_to_base_tile_area():
            tool_param_list += ["--align_to_base_tile_area"]
        if tiling_scheme.uses_overhanging_tiles():
            assert (
                tiling_scheme.uses_border_tiles()
            ), "--tile_overhang requires --keep_borders"
            tool_param_list += ["--tile_overhang"]

    if output_tile_size_pixel is not None:
        tile_size_string = ",".join(
            str(tile_size) for tile_size in output_tile_size_pixel
        )
        tool_param_list += ["--output_tile_size_pixel", tile_size_string]

    if bands is not None:
        band_string = ",".join(str(b) for b in bands)
        tool_param_list += ["--bands", band_string]
    tool_param_list += ["--no_data_threshold", str(no_data_threshold)]

    tif_ifps = get_regex_fps_in_dp(tif_idp, tif_search_regex, tif_ignore_regex)

    tool_param_list += ["--raster_ifps"]
    for tif_ifp in tif_ifps:
        tool_param_list.append(tif_ifp)
    if create_aux_files:
        tool_param_list += ["--create_aux_files"]
    if create_polygon_files:
        tool_param_list += ["--create_polygon_files"]
    tool_param_list += ["--out", tile_odp]
    if compute_tiling_statistic:
        tool_param_list += ["--compute_tiling_statistic"]

    if write_labels:
        tool_param_list += ["--write_labels"]
        if convert_images_to_labels:
            tool_param_list += ["--convert_images_to_labels"]

        assert categories is not None
        tool_param_list += ["--categories"]
        tool_param_list += [categories.to_json_string()]

    if cover_csv_ifp is not None:
        tool_param_list += ["--cover_csv_ifp", cover_csv_ifp]

    if debug_max_number_tiles_per_image is not None:
        tool_param_list += [
            "--debug_max_number_tiles_per_image",
            str(debug_max_number_tiles_per_image),
        ]

    tool_param_list += ["--clear_split_data", str(clear_split_data)]
    Logs.sinfo(f"tool_param_list {tool_param_list}")
    log_shell_command(tool_name="tile", param_list=tool_param_list)
    tile_args = create_args(
        tool_name="tile",
        tool_param_list=tool_param_list,
        module_dp="eot.tools",
    )
    tile_main(tile_args)


def run_cover(
    tile_idp=None,
    cover_ifp=None,
    splits=None,
    output_type="cover",
    ofp_list=None,
    lazy=False,
):
    if splits is None:
        splits = []

    if lazy and os.path.isfile(ofp_list[-1]):
        log_status("cover", ofp_list)
        return

    # rsp cover: Generate a tiles covering, in csv format: X,Y,Z
    # If the parameter splits is provided, multiple outputs are generated
    assert bool(tile_idp is not None) != bool(cover_ifp is not None)
    if tile_idp is not None:
        assert os.path.isdir(tile_idp), f"{tile_idp}"
    if cover_ifp is not None:
        assert os.path.isfile(cover_ifp), f"{cover_ifp}"

    tool_param_list = []
    if tile_idp is not None:
        tool_param_list += ["--dir", tile_idp]
    if cover_ifp is not None:
        tool_param_list += ["--cover", cover_ifp]

    if len(splits) > 0:
        tool_param_list += ["--splits", "/".join(list(map(str, splits)))]
        assert len(splits) == len(ofp_list)

    if output_type == "extent":
        tool_param_list += ["--type", output_type]
        if ofp_list is not None:
            tool_param_list += ["--out"] + ofp_list
    else:
        tool_param_list += ["--out"] + ofp_list
    cover_args = create_args(
        tool_name="cover",
        tool_param_list=tool_param_list,
        module_dp="eot.tools",
    )
    cover_main(cover_args)


def run_rasterize(
    geojson_idp,
    geojson_search_regex,
    geojson_ignore_regex,
    cover_csv_ifp,
    geojson_category,
    tile_data_categories,
    label_odp,
    output_tile_size_pixel,
    raster_idp=None,
    raster_search_regex=None,
    raster_ignore_regex=None,
    lazy=False,
):
    # NB: Parameter raster_search_regex and raster_ignore_regex is only
    #  required for eot tiles.

    if lazy and os.path.isdir(label_odp):
        log_status("rasterize", label_odp)
        return

    geojson_ifps = get_regex_fps_in_dp(
        geojson_idp, geojson_search_regex, geojson_ignore_regex
    )
    tool_param_list = ["--geojson_ifp_list"]
    for geojson_ifp in geojson_ifps:
        tool_param_list.append(geojson_ifp)

    if raster_idp is not None:
        # Required for eot tiles
        assert raster_search_regex is not None
        assert raster_ignore_regex is not None
        raster_ifps = get_regex_fps_in_dp(
            raster_idp, raster_search_regex, raster_ignore_regex
        )
        tool_param_list += ["--raster_ifp_list"]
        for raster_ifp in raster_ifps:
            tool_param_list.append(raster_ifp)

    assert tile_data_categories is not None
    tool_param_list += [
        "--tile_data_categories",
        tile_data_categories.to_json_string(),
    ]
    assert geojson_category is not None
    tool_param_list += [
        "--geojson_category",
        geojson_category.to_json_string(),
    ]
    tool_param_list += ["--cover_csv_ifp", cover_csv_ifp]

    if output_tile_size_pixel is not None:
        tile_size_string = ",".join(
            str(tile_size) for tile_size in output_tile_size_pixel
        )
        tool_param_list += ["--output_tile_size_pixel", tile_size_string]

    tool_param_list += ["--odp", label_odp]

    rasterize_args = create_args(
        tool_name="rasterize",
        tool_param_list=tool_param_list,
        module_dp="eot.tools",
    )
    rasterize_main(rasterize_args)


def run_aggregate(
    masks_idp,
    categories,
    masks_raster_name=None,
    geojson_odp=None,
    geojson_grid_ofn=None,
    mask_gray_png_ofp=None,
    mask_color_png_ofp=None,
    mask_overlay_png_ofp=None,
    overlay_grid_png_ofp=None,
    original_raster_ifp=None,
    normalized_raster_fp=None,
    save_normalized_raster=False,
    use_pixel_projection=True,
    use_contours=False,  # or filled shapes otherwise
    overlay_weight=192,  # Between 0 an 255
    tile_boundary_color=(128, 255, 0),
    lazy=False,
):

    ofp_list = [
        mask_gray_png_ofp,
        mask_color_png_ofp,
        mask_overlay_png_ofp,
    ]
    ofp_list = [ofp for ofp in ofp_list if ofp is not None]
    ofp_list_exists = all([os.path.isfile(ofp) for ofp in ofp_list])

    if geojson_odp is not None:
        geojson_ofps_exists = True
        for category in categories:
            cagerory_geojson_fp_list = glob.glob(
                os.path.join(geojson_odp, f"*{category.name}.json")
            )
            if len(cagerory_geojson_fp_list) == 0:
                geojson_ofps_exists = False
                break
            elif len(cagerory_geojson_fp_list) == 1:
                ofp_list.append(cagerory_geojson_fp_list[0])
            else:
                assert False
    else:
        geojson_ofps_exists = True

    output_exists = ofp_list_exists and geojson_ofps_exists
    if lazy and output_exists:
        for ofp in ofp_list:
            log_status("aggregate", ofp)
        return

    tool_param_list = ["--masks_idp", masks_idp]

    tool_param_list += ["--categories"]
    tool_param_list += [categories.to_json_string()]

    if masks_raster_name:
        tool_param_list += ["--masks_raster_name", masks_raster_name]
    if geojson_odp is not None:
        tool_param_list += ["--geojson_odp", geojson_odp]
    if geojson_grid_ofn is not None:
        tool_param_list += ["--geojson_grid_ofn", geojson_grid_ofn]
    if mask_gray_png_ofp is not None:
        tool_param_list += ["--gray_mask_png_ofp", mask_gray_png_ofp]
    if mask_color_png_ofp is not None:
        tool_param_list += ["--color_mask_png_ofp", mask_color_png_ofp]
    if original_raster_ifp is not None:
        tool_param_list += ["--original_raster_ifp", original_raster_ifp]
    if normalized_raster_fp is not None:
        tool_param_list += ["--normalized_raster_fp", normalized_raster_fp]
    if mask_overlay_png_ofp is not None:
        assert original_raster_ifp is not None
        tool_param_list += ["--overlay_mask_png_ofp", mask_overlay_png_ofp]
    if overlay_grid_png_ofp is not None:
        assert original_raster_ifp is not None
        tool_param_list += ["--overlay_grid_png_ofp", overlay_grid_png_ofp]

    tool_param_list += [
        "--save_normalized_raster",
        str(save_normalized_raster),
    ]
    tool_param_list += ["--use_pixel_projection", str(use_pixel_projection)]

    tool_param_list += ["--use_contours", str(use_contours)]

    tool_param_list += ["--overlay_weight", str(overlay_weight)]
    tile_boundary_color_string = ",".join(
        str(value) for value in tile_boundary_color
    )
    tool_param_list += ["--tile_boundary_color", tile_boundary_color_string]
    Logs.sinfo(tool_param_list)
    aggregate_args = create_args(
        tool_name="aggregate",
        tool_param_list=tool_param_list,
        module_dp="eot.tools",
    )
    aggregate_main(aggregate_args)


def run_compare(
    comparison_odp,
    segmentation_categories,
    comparison_categories,
    geojson=False,
    label_idp=None,
    mask_idp=None,
    lazy=False,
):

    if lazy and os.path.isdir(comparison_odp):
        log_status("compare", comparison_odp)
        return

    tool_param_list = []

    if geojson:
        tool_param_list += ["--geojson"]
    if label_idp is not None:
        tool_param_list += ["--label_idp", label_idp]
    if mask_idp is not None:
        tool_param_list += ["--mask_idp", mask_idp]

    tool_param_list += ["--comparison_odp", comparison_odp]

    tool_param_list += ["--segmentation_categories"]
    tool_param_list += [segmentation_categories.to_json_string()]
    tool_param_list += ["--comparison_categories"]
    tool_param_list += [comparison_categories.to_json_string()]

    Logs.sinfo(tool_param_list)
    compare_args = create_args(
        tool_name="compare",
        tool_param_list=tool_param_list,
        module_dp="eot.tools",
    )
    compare_main(compare_args)


def create_args(tool_name, tool_param_list, module_dp="neat_eo.tools"):
    # log_shell_command(tool_name, tool_param_list)
    unmodified_sys_argv = copy.copy(sys.argv)
    sys.argv.append(tool_name)
    sys.argv += tool_param_list
    formatter_class = lambda prog: argparse.RawTextHelpFormatter(
        prog, max_help_position=40, indent_increment=1
    )  # noqa: E731
    parser = argparse.ArgumentParser(
        prog="neo", formatter_class=formatter_class
    )
    subparser = parser.add_subparsers(title="eot tools", metavar="")
    module = import_module(module_dp + ".{}".format(tool_name))
    module.add_parser(subparser, formatter_class=formatter_class)
    res = parser.parse_args()
    sys.argv = unmodified_sys_argv
    return res
