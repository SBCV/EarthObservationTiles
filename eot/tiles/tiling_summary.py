from eot.rasters.raster import Raster
from eot.tiles.tiling_result import RasterTilingResults
from eot.utility.os_ext import get_regex_fps_in_dp


def _compute_dataset_tiling_result(tif_ifps, tiling_scheme, disk_tile_size):
    raster_tiling_results = RasterTilingResults(tiling_scheme=tiling_scheme)
    for raster_fp in tif_ifps:
        raster = Raster.get_from_file(raster_fp)
        raster_tiling_result = raster.compute_tiling(
            tiling_scheme=tiling_scheme
        )
        raster_tiling_result.disk_tile_size_int = disk_tile_size
        for tile in raster_tiling_result.tiles:
            tile.disk_width = disk_tile_size[0]
            tile.disk_height = disk_tile_size[1]
        raster_tiling_result.init_tiling_statistic_from(
            raster,
            raster_tiling_result.tiles,
            disk_tile_size_x=disk_tile_size[0],
            disk_tile_size_y=disk_tile_size[1],
        )

        if (
            raster_tiling_result.tiling_info.tiling_scheme.represents_local_image_tiling()
        ):
            source_width_amm = (
                raster_tiling_result.tiling_statistic.tile_source_width_amm
            )
            source_height_amm = (
                raster_tiling_result.tiling_statistic.tile_source_height_amm
            )
            # All tiles must have the size!
            assert source_width_amm.min_value == source_width_amm.max_value
            assert source_height_amm.min_value == source_height_amm.max_value
        else:
            assert False

        raster_tiling_results.add_raster_tiling_result(raster_tiling_result)
    return raster_tiling_results


def create_dp_tiling_summary_json(
    data_idp,
    tif_search_regex,
    tif_ignore_regex,
    spatial_info_json_ofp,
    disk_tile_size,
    tiling_scheme,
):
    tif_ifps = get_regex_fps_in_dp(
        data_idp, tif_search_regex, tif_ignore_regex
    )
    create_fp_list_tiling_summary_json(
        tif_ifps,
        spatial_info_json_ofp,
        disk_tile_size,
        tiling_scheme,
    )


def create_fp_list_tiling_summary_json(
    tif_ifps,
    spatial_info_json_ofp,
    disk_tile_size,
    tiling_scheme,
):
    raster_tiling_results = _compute_dataset_tiling_result(
        tif_ifps, tiling_scheme, disk_tile_size
    )
    raster_tiling_results.write_as_json(spatial_info_json_ofp)


def create_dp_tiling_summary_txt(
    data_idp,
    tif_search_regex,
    tif_ignore_regex,
    spatial_info_txt_ofp,
    disk_tile_size,
    tiling_scheme,
):
    tif_ifps = get_regex_fps_in_dp(
        data_idp, tif_search_regex, tif_ignore_regex
    )
    create_fp_list_tiling_summary_txt(
        tif_ifps,
        spatial_info_txt_ofp,
        disk_tile_size,
        tiling_scheme,
    )


def create_fp_list_tiling_summary_txt(
    tif_ifps,
    spatial_info_txt_ofp,
    disk_tile_size,
    tiling_scheme,
):
    raster_tiling_results = _compute_dataset_tiling_result(
        tif_ifps, tiling_scheme, disk_tile_size
    )
    raster_tiling_results.write_as_txt(spatial_info_txt_ofp)
