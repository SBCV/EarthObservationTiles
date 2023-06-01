## Prepare the Open Cities AI dataset

The rasterization examples in this repository use the
[Open Cities AI dataset](https://mlhub.earth/data/open_cities_ai_challenge),
since it provides the label ground truth in geojson format.

We assume that ``open_cities_ai_challenge_train_tier_1_labels.tar.gz`` and
```open_cities_ai_challenge_train_tier_1_labels.tar.gz``` has been downloaded
to ``<raw_dataset>``, i.e.
```
├── <raw_dataset>
│   ├── open_cities_ai_challenge_train_tier_1_source.tar.gz
│   ├── open_cities_ai_challenge_train_tier_1_labels.tar.gz
```
Unzipping both archives using
```
cd <raw_dataset>
unzip open_cities_ai_challenge_train_tier_1_source.tar.gz
unzip open_cities_ai_challenge_train_tier_1_labels.tar.gz
``` 
yields
```
├── <raw_dataset>
│   ├── open_cities_ai_challenge_train_tier_1_source.tar.gz
│   ├── open_cities_ai_challenge_train_tier_1_source
│   │   ├── open_cities_ai_challenge_train_tier_1_source_acc_665946
│   │   │   ├── image.tif
│   │   │   ├── stac.json
│   │   ├── open_cities_ai_challenge_train_tier_1_source_acc_a42435
│   │   │   ├── image.tif
│   │   │   ├── stac.json
│   │   ├── ...
│   ├── open_cities_ai_challenge_train_tier_1_labels.tar.gz
│   ├── open_cities_ai_challenge_train_tier_1_labels
│   │   ├── open_cities_ai_challenge_train_tier_1_labels_acc_665946
│   │   │   ├── labels.geojson
│   │   │   ├── stac.json
│   │   ├── open_cities_ai_challenge_train_tier_1_labels_acc_a42435
│   │   │   ├── labels.geojson
│   │   │   ├── stac.json
│   │   ├── ...
```
The examples of the EOT-library use the following directory structure for
processing earth observation images:
```
├── <example_dataset>
│   ├── raster
│   │   ├── <image_1>
│   │   │   ├── <image_1>.tif
│   │   ├── <image_1>-labels
│   │   │   ├── <image_1>.tif
│   │   ├── <image_2>
│   │   │   ├── <image_2>.tif
│   │   ├── <image_2>-labels
│   │   │   ├── <image_2>.tif
│   │   ├── ...
├── ...
```
The EOT-library provides a script
(```data_preparation/prepare_open_cities_ai.py```) to reorganize the images and
convert the geo-json labels to tif images using color palettes. Adjust the 
following values in the script before running.
```
rgb_idp = "<raw_dataset>/open_cities_ai_challenge_train_tier_1_source"
label_idp = "<raw_dataset>/open_cities_ai_challenge_train_tier_1_labels"
data_odp = "<example_dataset>/raster"
```
Note: make sure that you correctly installed the library (by following the
installation instructions such as
```export PYTHONPATH=$PYTHONPATH:/path/to/EarthObservationTiles```).
The final structure should look as follows:
```
├── <example_dataset>
│   ├── raster
│   │   ├── acc_665946
│   │   │   ├── acc_665946.tif
│   │   ├── acc_665946-labels
│   │   │   ├── acc_665946.tif
│   │   │   ├── acc_665946.geojson
│   │   ├── acc_a42435
│   │   │   ├── acc_a42435.tif
│   │   ├── acc_a42435-labels
│   │   │   ├── acc_a42435.tif
│   │   │   ├── acc_a42435.geojson
│   │   ├── ...
├── ...
```

