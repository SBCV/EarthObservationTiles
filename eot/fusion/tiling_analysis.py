from collections import defaultdict
from eot.tiles.image_pixel_tile import ImagePixelTile


def _get_base_and_aux_results_of_raster(
    predictions, batch_indices, tiles, raster_tiling_result, logger
):
    assert isinstance(tiles[0], ImagePixelTile)
    predictions_base = []
    batch_indices_base = []
    tiles_base = []
    predictions_aux = []
    batch_indices_aux = []
    tiles_strided_aux = []

    tiling_info = raster_tiling_result.tiling_info
    raster_width = raster_tiling_result.raster_width
    raster_height = raster_tiling_result.raster_height

    tiled_area_offset_x_int = tiling_info.source_tiling_offset_x_int.magnitude
    tiled_area_offset_y_int = tiling_info.source_tiling_offset_y_int.magnitude
    tile_stride_x_float = tiling_info.source_tile_stride_x_float.magnitude
    tile_stride_y_float = tiling_info.source_tile_stride_y_float.magnitude

    reference_tile = tiles[0]
    width, height = reference_tile.get_source_size()
    tile_stride_x_width_ratio = round(width / tile_stride_x_float)
    tile_stride_y_width_ratio = round(height / tile_stride_y_float)
    base_tile_stride_x = tile_stride_x_float * tile_stride_x_width_ratio
    base_tile_stride_y = tile_stride_y_float * tile_stride_y_width_ratio

    for index in range(len(predictions)):
        tile = tiles[index]
        tile_offset_x_int, tile_offset_y_int = tile.get_source_offset()

        relative_source_x_offset_int = (
            tile_offset_x_int - tiled_area_offset_x_int
        )
        relative_source_y_offset_int = (
            tile_offset_y_int - tiled_area_offset_y_int
        )

        base_tile_stride_x_integer_multiple = round(
            relative_source_x_offset_int / base_tile_stride_x
        )
        base_tile_stride_y_integer_multiple = round(
            relative_source_y_offset_int / base_tile_stride_y
        )

        x_offset_remaining = (
            relative_source_x_offset_int
            - base_tile_stride_x_integer_multiple * base_tile_stride_x
        )
        y_offset_remaining = (
            relative_source_y_offset_int
            - base_tile_stride_y_integer_multiple * base_tile_stride_y
        )

        x_is_base_tile = abs(x_offset_remaining) <= 1
        y_is_base_tile = abs(y_offset_remaining) <= 1

        # Catch dubious cases (assuming the stride is always bigger than 16)
        if 1 < abs(x_offset_remaining) < 16:
            assert False
        if 1 < abs(y_is_base_tile) < 16:
            assert False

        (
            tile_end_coord_x_int,
            tile_end_coord_y_int,
        ) = tile.get_source_end_coord()
        if x_is_base_tile and y_is_base_tile:
            inside_x = (
                tile_offset_x_int >= 0 and tile_end_coord_x_int < raster_width
            )
            inside_y = (
                tile_offset_y_int >= 0 and tile_end_coord_y_int < raster_height
            )
            inside_raster = inside_x and inside_y
            if inside_raster:
                batch_indices_base.append(batch_indices[index])
                predictions_base.append(predictions[index])
                tiles_base.append(tiles[index])
            else:
                # Skipp base tiles outside the image
                pass
        else:
            batch_indices_aux.append(batch_indices[index])
            predictions_aux.append(predictions[index])
            tiles_strided_aux.append(tiles[index])

    if len(tiles_base) == 0:
        logger.info(f"common_x_offset: {tiled_area_offset_x_int}")
        logger.info(f"common_y_offset: {tiled_area_offset_y_int}")
        assert False
    results_base = (predictions_base, batch_indices_base, tiles_base)
    results_aux = (predictions_aux, batch_indices_aux, tiles_strided_aux)
    return results_base, results_aux


def _compute_raster_name_to_results(predictions, batch_indices, tiles):
    raster_name_to_results = defaultdict(list)
    # Split predictions, indices and tiles according to raster names
    for prediction, index, tile in zip(predictions, batch_indices, tiles):
        raster_name = tile.get_raster_name()
        raster_name_to_results[raster_name].append([prediction, index, tile])
    return raster_name_to_results


def _compute_raster_name_to_base_and_aux_results(
    raster_name_to_results, raster_tiling_results, logger
):
    raster_name_to_results_base = defaultdict(list)
    raster_name_to_results_aux = defaultdict(list)
    for raster_name in raster_name_to_results.keys():
        logger.info(f"Determine base and aux results for {raster_name}")
        results = raster_name_to_results[raster_name]
        # Split list of results into 3 list containing predictions, ...
        predictions, batch_indices, tiles = map(list, zip(*results))
        logger.info(f"num_tiles: {len(tiles)}")
        (
            raster_results_base,
            raster_results_aux,
        ) = _get_base_and_aux_results_of_raster(
            predictions,
            batch_indices,
            tiles,
            raster_tiling_results.get_raster_tiling_result(raster_name),
            logger,
        )
        raster_name_to_results_base[raster_name].extend(raster_results_base)
        raster_name_to_results_aux[raster_name].extend(raster_results_aux)
    return raster_name_to_results_base, raster_name_to_results_aux


def get_aux_and_base_results(
    predictions, batch_indices, tiles, raster_tiling_results, logger
):
    raster_name_to_results = _compute_raster_name_to_results(
        predictions, batch_indices, tiles
    )
    logger.info("Determine base and aux results ...")
    (
        raster_name_to_results_base,
        raster_name_to_results_aux,
    ) = _compute_raster_name_to_base_and_aux_results(
        raster_name_to_results, raster_tiling_results, logger
    )
    return raster_name_to_results_base, raster_name_to_results_aux
