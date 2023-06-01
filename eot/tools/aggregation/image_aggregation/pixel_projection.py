import os
import sys
import numpy as np
from tqdm import tqdm
import cv2
from contextlib import contextmanager
from PIL import Image
from rasterio.enums import Resampling
from eot.crs.crs import IDENTITY, EPSG_3857
from eot.rasters.raster import Raster
from eot.rasters.raster_writing import (
    write_numpy_as_raster,
    write_raster,
    get_written_raster_generator,
)
from eot.rasters.raster_reprojection import (
    reproject_raster,
)
from eot.geojson_ext import get_feature_shapes
from eot.tools.aggregation import get_tile_mask
from eot.tiles.tile_reading import (
    read_label_tile_from_file,
    read_image_tile_from_file,
)
from eot.utility.np_ext import get_non_black_pixel_indices
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.image_pixel_tile import ImagePixelTile
from eot.utility.conversion import convert_rasterio_to_opencv_resampling


@contextmanager
def _get_tiling_raster(original_raster, args, tile_class, resampling):
    if tile_class == ImagePixelTile:
        with Raster.get_from_file(
            args.original_raster_ifp, mode="r"
        ) as tiling_raster:
            yield tiling_raster
    elif tile_class == MercatorTile:
        # Working with normalized rasters (in EPSG_3857) is necessary to avoid
        # incorrect tile projections, e.g. skewed tiles, no north-up alignment,
        # ...
        if args.normalized_raster_fp is not None and os.path.isfile(
            args.normalized_raster_fp
        ):
            print("Reading normalized raster from disk ...")
            with Raster.get_from_file(
                args.normalized_raster_fp, mode="r"
            ) as tiling_raster:
                assert tiling_raster.crs == EPSG_3857
                yield tiling_raster
        else:
            print("Must normalizing raster. This might take a while ...")
            assert resampling is not None
            with original_raster.get_normalized_dataset_generator(
                dst_crs=EPSG_3857, resampling=resampling
            ) as tiling_raster:
                if args.save_normalized_raster:
                    assert args.normalized_raster_fp != "None"

                    write_raster(
                        tiling_raster,
                        args.normalized_raster_fp,
                        build_overviews=True,
                        label_compatible_meta_data=False,
                    )
                yield tiling_raster
    else:
        assert False


def _compute_contour_pixels(tile_mask):
    tile_x_coords = []
    tile_y_coords = []
    for shape, value in get_feature_shapes(
        tile_mask, transform=IDENTITY, mask=tile_mask
    ):
        shape_crs_coordinate_list = shape["coordinates"]
        for shape_crs_coordinates in shape_crs_coordinate_list:
            current_x_coords, current_y_coords = zip(*shape_crs_coordinates)
            tile_x_coords += current_x_coords
            tile_y_coords += current_y_coords
    return tile_x_coords, tile_y_coords


def _compute_segmentation_pixels(tile_mask):
    coords = np.argwhere(tile_mask > 0)
    coords_T = coords.T
    tile_x_coords = coords_T[1]
    tile_y_coords = coords_T[0]
    return tile_x_coords, tile_y_coords


def _compute_tile_category_pixels(tile_mask, use_contours):
    # https://numpy.org/devdocs/user/basics.indexing.html#index-arrays
    if use_contours:
        tile_x_pixels, tile_y_pixels = _compute_contour_pixels(tile_mask)
    else:
        tile_x_pixels, tile_y_pixels = _compute_segmentation_pixels(tile_mask)
    return tile_x_pixels, tile_y_pixels


def _convert_affine_to_numpy(affine_trans):
    return np.reshape(np.asarray(affine_trans), (3, 3))


def _compute_transform_tile_pixel_to_raster_pixel(raster, tile):
    tile_pixel_to_raster_pixel_transform = (
        raster.get_transform_tile_pixel_to_raster_pixel(tile)
    )
    tile_pixel_to_raster_pixel_transform_mat = _convert_affine_to_numpy(
        tile_pixel_to_raster_pixel_transform
    )
    return tile_pixel_to_raster_pixel_transform_mat


def _create_1d_hom_idx_mat_from_lists(x_index_list, y_index_list):
    # print('y_indices', y_indices)
    # print('x_indices', x_indices)
    assert len(x_index_list) == len(y_index_list)
    hom_part = np.ones((len(x_index_list)))
    coords_1d_hom = np.array([x_index_list, y_index_list, hom_part])
    return coords_1d_hom.T


def _convert_tile_pixels_to_raster_pixels(
    tile_pixel_to_raster_pixel_transform_mat, tile_x_coords, tile_y_coords
):
    tile_coords_1d_hom = _create_1d_hom_idx_mat_from_lists(
        tile_x_coords, tile_y_coords
    )
    tile_coords_1d_hom_t = tile_coords_1d_hom.T
    raster_coords_1d_hom_t = (
        tile_pixel_to_raster_pixel_transform_mat @ tile_coords_1d_hom_t
    )
    raster_coords_1d_hom_t = np.asarray(raster_coords_1d_hom_t).astype(int)

    raster_x_coords = raster_coords_1d_hom_t[0]
    raster_y_coords = raster_coords_1d_hom_t[1]

    return raster_x_coords, raster_y_coords


def _compute_tile_border_pixels(tile_mask, boundary_thickness=6):
    height, width = tile_mask.shape[:2]
    tile_x_coords = []
    tile_y_coords = []

    # The following expression creates:
    # [-boundary_thickness, ..., -1, 0, 1, ..., boundary_thickness]
    boundary_offsets = list(range(-boundary_thickness + 1, boundary_thickness))
    for offset in boundary_offsets:
        # Top boundary
        tile_x_coords += list(range(width))  # 0 .... width -1
        tile_y_coords += [offset] * width
        # Bottom boundary
        tile_x_coords += list(range(width))  # 0 .... width -1
        tile_y_coords += [height - 1 + offset] * width
        # Left boundary
        tile_x_coords += [offset] * height  # 0 .... width -1
        tile_y_coords += list(range(height))
        # Right boundary
        tile_x_coords += [width - 1 + offset] * height  # 0 .... width -1
        tile_y_coords += list(range(height))

    return tile_x_coords, tile_y_coords


def _print_aggregation_msg(categories, idp, ofp):
    category_names = categories.get_category_names(
        only_active=True, include_ignore=True
    )
    print(
        f"neo aggregate {category_names} from {idp} to {ofp}",
        file=sys.stderr,
        flush=True,
    )


def _save_image(
    ofp,
    tiling_data,
    tile_class,
    original_raster=None,
    tiling_raster=None,
    overlay_with_raster=False,
    resampling=None,
    **kwargs,
):
    if original_raster is None:
        write_numpy_as_raster(
            tiling_data,
            ofp,
            transform=None,
            crs=None,
            image_axis_order=True,
        )
    else:
        assert tiling_raster is not None
        if overlay_with_raster:
            tiling_raster_data = tiling_raster.get_raster_data_as_numpy(
                image_axis_order=True, add_alpha_channel=True
            )
            mask_non_black_pixels = get_non_black_pixel_indices(tiling_data)
            tiling_raster_data[mask_non_black_pixels] = tiling_data[
                mask_non_black_pixels
            ]
            tiling_overwrite_data = tiling_raster_data
        else:
            tiling_overwrite_data = tiling_data

        if tile_class == MercatorTile:
            with get_written_raster_generator(
                tiling_raster,
                overwrite_data=tiling_overwrite_data,
                image_axis_order=True,
                build_overviews=True,
                label_compatible_meta_data=False,
                **kwargs,
            ) as tiling_overwrite_raster:
                transform, crs = original_raster.get_geo_transform_with_crs()
                assert resampling is not None
                reproject_raster(
                    tiling_overwrite_raster,
                    crs,
                    transform,
                    original_raster.width,
                    original_raster.height,
                    ofp,
                    resampling=resampling,
                )
        elif tile_class == ImagePixelTile:
            write_raster(
                tiling_raster,
                ofp,
                overwrite_data=tiling_overwrite_data,
                image_axis_order=True,
                build_overviews=True,
                label_compatible_meta_data=False,
                **kwargs,
            )
        else:
            assert False


def _get_raster_masks(tiling_raster):
    raster_mask = np.zeros(
        (tiling_raster.height, tiling_raster.width), dtype=np.uint8
    )
    raster_mask_color = np.zeros(
        (tiling_raster.height, tiling_raster.width, 4),
        dtype=np.uint8,
    )
    # The alpha component is not a binary switch,
    # but makes the other colors more or less transparent
    raster_mask_overlay = np.zeros(
        (tiling_raster.height, tiling_raster.width, 4),
        dtype=np.uint8,
    )
    raster_grid_overlay = np.zeros(
        (tiling_raster.height, tiling_raster.width, 4),
        dtype=np.uint8,
    )
    return (
        raster_mask,
        raster_mask_color,
        raster_mask_overlay,
        raster_grid_overlay,
    )


def create_images_with_pixel_projection(args, masks, categories, resampling):
    reference_tile = masks[0]
    if isinstance(reference_tile, ImagePixelTile):
        tile_class = ImagePixelTile
    elif isinstance(reference_tile, MercatorTile):
        tile_class = MercatorTile
    else:
        assert False
    create_images_from_tiles_with_pixel_projection(
        args,
        masks,
        categories,
        tile_class=tile_class,
        resampling=resampling,
    )


def _get_target_tile_raster_area(tile, tiling_raster):
    if isinstance(tile, MercatorTile):
        left, bottom, right, top = tile.get_bounds_crs(tiling_raster.get_crs())
        # https://rasterio.readthedocs.io/en/latest/api/rasterio.windows.html#rasterio.windows.WindowMethodsMixin.window
        # https://github.com/rasterio/rasterio/blob/master/rasterio/windows.py
        tile_window = tiling_raster.window(left, bottom, right, top)
        size = int(tile_window.height), int(tile_window.width)
        offset = int(tile_window.col_off), int(tile_window.row_off)
    elif isinstance(tile, ImagePixelTile):
        size = tile.get_source_size()
        offset = tile.get_source_offset()
    else:
        assert False
    return offset, size


def _check_tile_raster_area(tile_offset, tile_size, raster):
    tile_x_offset, tile_y_offset = tile_offset
    tile_width, tile_height = tile_size
    valid = True
    if tile_x_offset < 0:
        valid = False
    if tile_y_offset < 0:
        valid = False
    if tile_x_offset + tile_width >= raster.width:
        valid = False
    if tile_y_offset + tile_height >= raster.height:
        valid = False
    return valid


def create_images_from_tiles_with_pixel_projection(
    args, tiles, categories, tile_class, resampling
):
    original_raster = Raster.get_from_file(args.original_raster_ifp)
    if tile_class == MercatorTile:
        assert original_raster.crs is not None

    # Use a nearest neighbor resampling for label masks to prevent the
    # introduction of non-label values
    label_mask_resampling = Resampling.nearest

    img = Image.open(tiles[0].get_absolute_tile_fp())
    use_color_palette = img.getpalette() is not None

    with _get_tiling_raster(
        original_raster, args, tile_class, resampling
    ) as tiling_raster:
        (
            raster_mask,
            raster_mask_color,
            raster_mask_overlay,
            raster_grid_overlay,
        ) = _get_raster_masks(tiling_raster)
        for tile in tqdm(tiles, ascii=True, unit="mask"):
            if use_color_palette:
                tile_data, _ = read_label_tile_from_file(
                    tile.get_absolute_tile_fp()
                )
            else:
                tile_data = read_image_tile_from_file(
                    tile.get_absolute_tile_fp()
                )
            tile_offset, tile_size = _get_target_tile_raster_area(
                tile, tiling_raster
            )
            if isinstance(tile, MercatorTile):
                if not _check_tile_raster_area(
                    tile_offset, tile_size, tiling_raster
                ):
                    continue

            # If a tile has a lower resolution than the corresponding raster image,
            # the mapping of tile data to the corresponding raster area potentially
            # introduces holes. See for example forward vs. reverse mapping in
            # https://www.cs.princeton.edu/courses/archive/spr11/cos426/notes/cos426_s11_lecture03_warping.pdf
            # To avoid this we resize the tile data.
            label_mask_resampling_cv = convert_rasterio_to_opencv_resampling(
                label_mask_resampling
            )
            tile_data = cv2.resize(
                tile_data,
                tile_size,
                interpolation=label_mask_resampling_cv,
            )
            assert (
                tile_size == tile_data.shape[:2]
            ), f"{tile_size} vs {tile_data.shape}"
            tile.set_disk_size(*tile_size)

            tile_pixel_to_raster_pixel_transform_mat = (
                _compute_transform_tile_pixel_to_raster_pixel(
                    tiling_raster, tile
                )
            )
            for idx, category in enumerate(categories):
                category_color = category.palette_color
                category_color_opaque = (*category_color, 255)
                category_color_alpha = (*category_color, args.overlay_weight)

                tile_mask = get_tile_mask(
                    tile_data, category, use_palette_index=use_color_palette
                )

                # Compute tile/raster category pixels
                t_cat_x_pix, t_cat_y_pix = _compute_tile_category_pixels(
                    tile_mask, args.use_contours
                )
                (
                    r_cat_x_pix,
                    r_cat_y_pix,
                ) = _convert_tile_pixels_to_raster_pixels(
                    tile_pixel_to_raster_pixel_transform_mat,
                    t_cat_x_pix,
                    t_cat_y_pix,
                )

                # Filter x values out of bounds
                r_cat_x_pix_in_bounds = r_cat_x_pix < tiling_raster.width
                r_cat_x_pix = r_cat_x_pix[r_cat_x_pix_in_bounds]
                r_cat_y_pix = r_cat_y_pix[r_cat_x_pix_in_bounds]

                # Filter y values out of bounds
                r_cat_y_pix_in_bounds = r_cat_y_pix < tiling_raster.height
                r_cat_x_pix = r_cat_x_pix[r_cat_y_pix_in_bounds]
                r_cat_y_pix = r_cat_y_pix[r_cat_y_pix_in_bounds]

                # This assumes that the dataset is normalized (i.e. using a
                # north-up-convention). Otherwise the x and y axes of the tile data
                # are not aligned with the x and y axes of the raster images.
                raster_mask[r_cat_y_pix, r_cat_x_pix] = category.palette_index
                raster_mask_color[
                    r_cat_y_pix, r_cat_x_pix
                ] = category_color_opaque
                raster_mask_overlay[
                    r_cat_y_pix, r_cat_x_pix
                ] = category_color_alpha

            if args.tile_boundary_color is not None:
                # Compute tile/raster border pixels
                t_border_x_pix, t_border_y_pix = _compute_tile_border_pixels(
                    tile_mask, boundary_thickness=3
                )
                (
                    r_border_x_pix,
                    r_border_y_pix,
                ) = _convert_tile_pixels_to_raster_pixels(
                    tile_pixel_to_raster_pixel_transform_mat,
                    t_border_x_pix,
                    t_border_y_pix,
                )

                # Filter x values out of bounds
                r_border_x_pix_in_bounds = r_border_x_pix < tiling_raster.width
                r_border_x_pix = r_border_x_pix[r_border_x_pix_in_bounds]
                r_border_y_pix = r_border_y_pix[r_border_x_pix_in_bounds]

                # Filter y values out of bounds
                r_border_y_pix_in_bounds = (
                    r_border_y_pix < tiling_raster.height
                )
                r_border_x_pix = r_border_x_pix[r_border_y_pix_in_bounds]
                r_border_y_pix = r_border_y_pix[r_border_y_pix_in_bounds]

                raster_mask_overlay[r_border_y_pix, r_border_x_pix] = (
                    *args.tile_boundary_color,
                    255,
                )
                raster_grid_overlay[r_border_y_pix, r_border_x_pix] = (
                    *args.tile_boundary_color,
                    255,
                )

        # https://pillow.readthedocs.io/en/4.1.x/handbook/concepts.html#modes
        if args.gray_mask_png_ofp is not None:
            _print_aggregation_msg(
                categories,
                args.masks_idp,
                args.gray_mask_png_ofp,
            )
            _save_image(
                args.gray_mask_png_ofp,
                raster_mask,
                tile_class=tile_class,
                original_raster=original_raster,
                tiling_raster=tiling_raster,
                overlay_with_raster=False,
                compress="DEFLATE",
                resampling=label_mask_resampling,
            )
        if args.color_mask_png_ofp is not None:
            _print_aggregation_msg(
                categories,
                args.masks_idp,
                args.color_mask_png_ofp,
            )
            _save_image(
                args.color_mask_png_ofp,
                raster_mask_color,
                tile_class=tile_class,
                original_raster=original_raster,
                tiling_raster=tiling_raster,
                overlay_with_raster=False,
                compress="DEFLATE",
                resampling=label_mask_resampling,
            )
        if args.overlay_mask_png_ofp is not None:
            _print_aggregation_msg(
                categories,
                args.masks_idp,
                args.overlay_mask_png_ofp,
            )
            _save_image(
                args.overlay_mask_png_ofp,
                raster_mask_overlay,
                tile_class=tile_class,
                original_raster=original_raster,
                tiling_raster=tiling_raster,
                overlay_with_raster=True,
                resampling=resampling,
            )
        if args.overlay_grid_png_ofp is not None:
            _print_aggregation_msg(
                categories,
                args.masks_idp,
                args.overlay_grid_png_ofp,
            )
            _save_image(
                args.overlay_grid_png_ofp,
                raster_grid_overlay,
                tile_class=tile_class,
                original_raster=original_raster,
                tiling_raster=tiling_raster,
                overlay_with_raster=True,
                resampling=resampling,
            )
