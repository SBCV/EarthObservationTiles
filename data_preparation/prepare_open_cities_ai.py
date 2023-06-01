#########################
# https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/page/150/
# https://www.drivendata.org/competitions/60/building-segmentation-disaster-resilience/page/151/
# http://registry.mlhub.earth/10.34911/rdnt.f94cxb/
#   https://radiant-mlhub.s3-us-west-2.amazonaws.com/open-cities-ai-challenge/documentation.pdf
#########################

##########################################
# OpenCitiesAI Challenge Dataset Structure
##########################################
# open_cities_ai_challenge_train_tier_1_source
#   open_cities_ai_challenge_train_tier_1_source_acc_665946
#       image.tif
#   open_cities_ai_challenge_train_tier_1_source_acc_a42435
#       image.tif
#   ...
# open_cities_ai_challenge_train_tier_1_labels
#   open_cities_ai_challenge_train_tier_1_labels_acc_665946
#       labels.geojson
#   open_cities_ai_challenge_train_tier_1_labels_acc_a42435
#       labels.geojson
#   ...

####################################
# OpenCitiesAI Challenge Dataset CRS
####################################
# All training images have been reprojected to the appropriate UTM zone
# projection for the region that they represent.

####################################
# OpenCitiesAI Challenge Dataset GSD
####################################
# GSD Information is provided for each image in the meta data ("Pixel Size")

######################################
# OpenCitiesAI Challenge Dataset Notes
######################################
# City 	Data class 	    Scene   AOI   	Building  	Total   	    Average  	    Building ratio  GSD
#                       count   area    count       building        building        (portion of
#                               (sq km)             size (sq km)    size (sq m)     area covered
#                                                                                   by buildings)
#
# acc 	train_tier_1 	4 	    7.86 	33585 	    2.85 	        84.84 	        0.36            0.02, 0.03, 0.05, 0.05
# dar 	train_tier_1 	6 	    42.90 	121171 	    12.02 	        99.20 	        0.28            0.07, 0.07, 0.05,
#                                                                                                   0.04, 0.05, 0.05
# dar 	train_tier_2 	31 	    223.28 	571047 	    53.77 	        94.16 	        0.24            -
# gao 	train_tier_2 	2 	    12.54 	15792 	    1.28 	        81.05 	        0.10            -
# kam 	train_tier_1 	1 	    1.14 	4056 	    0.22 	        53.14 	        0.19            0.04
# kin 	train_tier_2 	2 	    1.01 	2357 	    0.17 	        71.29 	        0.17            -
# mah 	train_tier_2 	4 	    19.40 	7313 	    1.51 	        206.48      	0.08            -
# mon 	train_tier_1 	4 	    2.90 	6947 	    1.05 	        150.71 	        0.36            0.08, 0.08, 0.04, 0.04
# nia 	train_tier_1 	1 	    0.68 	634 	    0.03 	        47.43 	        0.04            0.10
# nia 	train_tier_2 	2 	    2.46 	7444 	    0.47 	        62.76 	        0.19            -
# ptn 	train_tier_1 	2 	    1.87 	8731 	    0.64 	        72.73 	        0.34            0.2, 0.2
# znz 	train_tier_1 	13 	    102.61 	13407 	    1.62 	        120.83 	        0.02            0.07, 0.08, 0.06,
#                                                                                                   0.07, 0.08, 0.06,
#                                                                                                   0.06, 0.08, 0.07,
#                                                                                                   0.07, 0.08, 0.06,
#                                                                                                   0.07

import os
from shutil import copyfile
from eot.utility.os_ext import mkdir_safely
from data_preparation.gsd import convert_pixel_size_to_gsd
from eot.geojson_ext.geojson_raster_conversion import convert_geojson_to_raster


def create_open_cities_ai_training_dataset(
    image_idp,
    label_idp,
    odp,
    burn_color,
    background_color,
    use_color_map=False,
    burn_value_color_map=1,
    background_value_color_map=0,
):
    data_dp_stem = "open_cities_ai_challenge_train_tier_1_"
    tif_dp_stem = data_dp_stem + "source_"
    geojson_dp_stem = data_dp_stem + "labels_"

    mkdir_safely(odp)

    for tif_dn in os.listdir(image_idp):
        tif_dp = os.path.join(image_idp, tif_dn)
        # skip files
        if os.path.isfile(tif_dp):
            continue
        assert tif_dn.startswith(tif_dp_stem)

        id_str = tif_dn.split(tif_dp_stem, maxsplit=1)[1]
        geojson_dn = geojson_dp_stem + id_str
        label_geojson_dp = os.path.join(label_idp, geojson_dn)
        assert os.path.isdir(label_geojson_dp)

        tif_ifp = os.path.join(tif_dp, "image.tif")
        label_geojson_ifp = os.path.join(label_geojson_dp, "labels.geojson")

        assert os.path.isfile(tif_ifp)
        assert os.path.isfile(label_geojson_ifp)

        print("id_str", id_str)
        print("tif_ifp", tif_ifp)
        print("label_geojson_ifp", label_geojson_ifp)

        tif_odp = os.path.join(odp, id_str)
        label_odp = tif_odp + "-labels"

        mkdir_safely(tif_odp)
        mkdir_safely(label_odp)

        tif_ofp = os.path.join(tif_odp, id_str + ".tif")
        label_geojson_ofp = os.path.join(label_odp, id_str + ".geojson")

        copyfile(tif_ifp, tif_ofp)
        copyfile(label_geojson_ifp, label_geojson_ofp)

        label_tif_ofp = os.path.join(label_odp, id_str + ".tif")
        convert_geojson_to_raster(
            raster_ifp=tif_ifp,
            label_geojson_ifp=label_geojson_ifp,
            label_raster_ofp=label_tif_ofp,
            burn_color=burn_color,
            background_color=background_color,
            use_color_map=use_color_map,
            burn_value_color_map=burn_value_color_map,
            background_value_color_map=background_value_color_map,
        )

        convert_pixel_size_to_gsd(tif_ifp, tif_ofp)
        convert_pixel_size_to_gsd(tif_ifp, label_tif_ofp)


def main():
    open_cities_ai_image_idp = "/path/to/raw_open_cities_ai_mini/open_cities_ai_challenge_train_tier_1_source"
    open_cities_ai_label_idp = "/path/to/raw_open_cities_ai_mini/open_cities_ai_challenge_train_tier_1_labels"
    open_cities_ai_odp = "/path/to/examples_open_cities_ai_mini/raster"

    burn_color = (0, 0, 255)
    background_color = (0, 0, 0)
    use_color_map = True
    burn_value_color_map = 1
    background_value_color_map = 0

    create_open_cities_ai_training_dataset(
        open_cities_ai_image_idp,
        open_cities_ai_label_idp,
        open_cities_ai_odp,
        burn_color,
        background_color,
        use_color_map,
        burn_value_color_map,
        background_value_color_map,
    )


if __name__ == "__main__":
    main()
