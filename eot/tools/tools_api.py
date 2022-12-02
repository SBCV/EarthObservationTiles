import argparse
import copy
import glob
import os
import sys
from importlib import import_module

from eot.core.log import Logs

from eot.tools.aggregate import main as aggregate_main
from eot.tools.cover import main as cover_main
from eot.tools.tile import main as tile_main
from eot.utility.os_extension import get_regex_fps_in_dp


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
    tile_overview_txt_ofn,
    dataset_type,
    output_tile_size_pixel,
    tile_type,
    input_tile_zoom_level=None,
    input_tile_size_in_pixel=None,
    input_tile_size_in_meter=None,
    input_tile_stride_in_pixel=None,
    input_tile_stride_in_meter=None,
    align_to_base_tile_area=None,
    tile_overhang=None,
    keep_border_tiles=None,
    create_aux_files=False,
    bands=None,
    write_labels=False,
    config_ifp=None,
    cover_csv_ifp=None,
    convert_images_to_labels=False,
    requested_category_titles=None,
    no_data_threshold=100,
    clear_split_data=True,
    debug_max_number_tiles_per_image=None,
    lazy=False,
):
    if lazy and os.path.isdir(tile_odp):
        log_status("tile", tile_odp)
        return

    tool_param_list = ["--tile_type", str(tile_type.name)]
    if tile_type.is_mercator_tile():
        assert input_tile_zoom_level is not None and isinstance(
            input_tile_zoom_level, int
        )
        tool_param_list += ["--zoom", str(input_tile_zoom_level)]
    elif tile_type.is_in_pixel():
        assert input_tile_size_in_pixel is not None
        tile_size_string = ",".join(
            str(tile_size) for tile_size in input_tile_size_in_pixel
        )
        tool_param_list += ["--input_tile_size_in_pixel", tile_size_string]
        if input_tile_stride_in_pixel is not None:
            tile_stride_string = ",".join(
                str(tile_stride) for tile_stride in input_tile_stride_in_pixel
            )
            tool_param_list += [
                "--input_tile_stride_in_pixel",
                tile_stride_string,
            ]
    elif tile_type.is_in_meter():
        assert input_tile_size_in_meter is not None
        tile_size_string = ",".join(
            str(tile_size) for tile_size in input_tile_size_in_meter
        )
        tool_param_list += ["--input_tile_size_in_meter", tile_size_string]
        if input_tile_stride_in_meter is not None:
            tile_stride_string = ",".join(
                str(tile_stride) for tile_stride in input_tile_stride_in_meter
            )
            tool_param_list += [
                "--input_tile_stride_in_meter",
                tile_stride_string,
            ]
    else:
        assert False

    if align_to_base_tile_area:
        tool_param_list += ["--align_to_base_tile_area"]
    if keep_border_tiles:
        tool_param_list += ["--keep_borders"]
    if tile_overhang:
        assert keep_border_tiles, "--tile_overhang requires --keep_borders"
        tool_param_list += ["--tile_overhang"]

    if output_tile_size_pixel is not None:
        tile_size_string = ",".join(
            str(tile_size) for tile_size in output_tile_size_pixel
        )
        tool_param_list += ["--output_tile_size_pixel", tile_size_string]

    tool_param_list += ["--dataset_type", dataset_type]
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
    tool_param_list += ["--out", tile_odp]
    tool_param_list += ["--tile_overview_txt_ofn", tile_overview_txt_ofn]

    if write_labels:
        tool_param_list += ["--write_labels"]
        assert config_ifp is not None
        tool_param_list += ["--config", config_ifp]
        if convert_images_to_labels:
            tool_param_list += ["--convert_images_to_labels"]
        assert requested_category_titles is not None
        tool_param_list += ["--requested_category_titles"]
        for category_type in requested_category_titles:
            tool_param_list += [category_type.lower()]

    if cover_csv_ifp is not None:
        tool_param_list += ["--cover", cover_csv_ifp]

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


def run_aggregate(
    config_fp,
    masks_idp,
    requested_category_titles,
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
    mask_values=None,
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
        for requested_category_title in requested_category_titles:
            cagerory_geojson_fp_list = glob.glob(
                os.path.join(geojson_odp, f"*{requested_category_title}.json")
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

    tool_param_list = ["--config", config_fp]
    tool_param_list += ["--masks_idp", masks_idp]

    tool_param_list += ["--requested_category_titles"]
    for requested_category_title in requested_category_titles:
        tool_param_list += [requested_category_title.lower()]

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
    if mask_values is not None:
        assert len(mask_values) == len(requested_category_titles)
        tool_param_list += ["--mask_values"]
        for mask_value in mask_values:
            tool_param_list += [str(mask_value)]

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
    subparser = parser.add_subparsers(title="Neat-EO.pink tools", metavar="")
    module = import_module(module_dp + ".{}".format(tool_name))
    module.add_parser(subparser, formatter_class=formatter_class)
    res = parser.parse_args()
    sys.argv = unmodified_sys_argv
    return res
