###############################################################################
# https://www2.isprs.org/commissions/comm2/wg4/benchmark/2d-sem-label-potsdam/
# https://www2.isprs.org/media/komfssn5/complexscenes_revision_v4.pdf
###############################################################################

#################################
# ISPRS Potsdam Dataset Structure
#################################
# ISPRS_BENCHMARK_DATASETS/Potsdam
#   2_Ortho_RGB                     (38 TIF and 38 TFW files)
#       top_potsdam_2_10_RGB.tfw
#       top_potsdam_2_10_RGB.tif
#       ...
#   5_Labels_all                    (38 TIF files)
#       top_potsdam_2_10_label.tif
#       ...
#   5_Labels_for_participants       (24 TIF and 24 TFW files)
#       top_potsdam_2_10_label.tfw
#       top_potsdam_2_10_label.tif
#       ...

###########################
# ISPRS Potsdam Dataset CRS
###########################
# The TFW files are defined in EPSG:32633 (https://epsg.io/32633) which covers
#  eastern germany (including Potsdam)

###########################
# ISPRS Potsdam Dataset GSD
###########################
# The ground sampling distance is 5cm = 0.05m

#############################
# ISPRS Potsdam Dataset Notes
#############################
# The Label files in "5_Labels_all" and "5_Labels_for_participants"
#  do not contain crs values. Therefore, even when reading the transformation
#  from the "tfw" files, the crs is still undefined.
# Thus, we copy the geo-transformations from the RGB images to the
#  corresponding label files.

import os
from shutil import copyfile
from eot.crs.crs import CRS
from eot.rasters.raster_geo_data import (
    get_geo_transform_pixel_to_crs_from_file,
    overwrite_geo_transform,
)
from eot.utility.os_ext import mkdir_safely
from eot.utility.os_ext import get_corresponding_files_in_directories
from eot.rasters.vrt import build_vrt
from eot.rasters.raster import Raster


def get_rgb_label_matching_files(rgb_idp, label_idp):
    def correspondence_callback(rgb_fn):
        # Example file names:
        #   top_potsdam_2_11_RGB.tif
        #   top_potsdam_2_10_label.tif

        suffix = rgb_fn.split("top_potsdam_", 1)[1]
        number_str = suffix.split("_RGB", 1)[0]
        label_fn = f"top_potsdam_{number_str}_label.tif"
        return label_fn

    tfw_ifp_list, tif_ifp_list = get_corresponding_files_in_directories(
        idp_1=rgb_idp,
        idp_2=label_idp,
        ext_1=".tif",
        get_correspondence_callback=correspondence_callback,
    )
    return tfw_ifp_list, tif_ifp_list


def create_isprs_potsdam_training_dataset(
    EPSG_32633, rgb_idp, label_idp, data_odp
):
    mkdir_safely(data_odp)
    label_suffix = "-labels"
    meta_data_dict = {"GSD": "0.05"}

    rgb_ifp_list, label_tif_ifp_list = get_rgb_label_matching_files(
        rgb_idp, label_idp
    )
    print(rgb_ifp_list)
    print(label_tif_ifp_list)
    rgb_tif_ofp_list = []
    label_tif_ofp_list = []
    for rgb_ifp, label_ifp in zip(rgb_ifp_list, label_tif_ifp_list):
        rgb_base_name = os.path.basename(rgb_ifp)
        rgb_stem = os.path.splitext(rgb_base_name)[0]
        rgb_stem_prefix = rgb_stem.split("_RGB", 1)[0]
        rgb_dp = os.path.join(data_odp, rgb_stem_prefix)
        mkdir_safely(rgb_dp)
        rgb_ofp = os.path.join(rgb_dp, rgb_base_name)

        label_base_name = os.path.basename(label_ifp)
        label_stem = os.path.splitext(label_base_name)[0]
        label_stem_prefix = label_stem.split("_label", 1)[0]
        label_dp = os.path.join(data_odp, label_stem_prefix + label_suffix)
        mkdir_safely(label_dp)
        label_ofp = os.path.join(label_dp, rgb_base_name)

        print(rgb_ofp)
        print(label_ofp)

        copyfile(rgb_ifp, rgb_ofp)

        # Use rgb_ofp here to ensure that the transformation of the *.tif file
        # and not the transformation of the *.tfw file is used
        rgb_transform, rgb_crs = get_geo_transform_pixel_to_crs_from_file(
            rgb_ofp, check_validity=True
        )
        assert rgb_crs == CRS.from_string(EPSG_32633)

        overwrite_geo_transform(
            label_ifp, label_ofp, transform=rgb_transform, crs=rgb_crs
        )

        output_rgb_raster = Raster.get_from_file(rgb_ofp, "r+")
        output_rgb_raster.add_meta_data(meta_data_dict)

        output_label_raster = Raster.get_from_file(label_ofp, "r+")
        output_label_raster.add_meta_data(meta_data_dict)

        rgb_tif_ofp_list.append(rgb_ofp)
        label_tif_ofp_list.append(label_ofp)

    build_vrt(os.path.join(data_odp, "rgb.vrt"), rgb_tif_ofp_list)
    build_vrt(os.path.join(data_odp, "labels.vrt"), label_tif_ofp_list)


if __name__ == "__main__":

    rgb_idp = "/path/to/raw_potsdam_dataset_mini/Potsdam/2_Ortho_RGB"
    label_idp = "/path/to/raw_potsdam_dataset_mini/Potsdam/5_Labels_all"
    data_odp = "/path/to/examples_potsdam_dataset_mini/raster"

    EPSG_32633 = "EPSG:32633"

    create_isprs_potsdam_training_dataset(
        EPSG_32633, rgb_idp, label_idp, data_odp
    )