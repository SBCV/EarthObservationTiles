## Prepare the ISPRS Potsdam dataset

The examples in this repository use the [ISPRS Potsdam dataset](https://www.isprs.org/education/benchmarks/UrbanSemLab/default.aspx),
since it provides accurate labels for a reasonable amount of data.

We assume that ``Potsdam.zip`` has been downloaded to ``<raw_dataset>``,
e.g. `<raw_dataset>/Potsdam.zip`.  
Extract the zip file (for example by running ``$ unzip Potsdam.zip``).
The resulting directory contains the following structure:
```
├── <raw_dataset>
│   ├── Potsdam.zip
│   ├── Potsdam
│   │   ├── ...
│   │   ├── 2_Ortho_RGB.zip
│   │   ├── ...
│   │   ├── 5_Labels_all.zip
│   │   ├── ...
```
The required rgb and label data is located in
``<raw_dataset>/Potsdam/2_Ortho_RGB.zip`` and
``<raw_dataset>/Potsdam/5_Labels_all.zip``. Extract the corresponding color and
label images such that the extraction process creates a new folder containing
the data - for example by executing the following commands. Note the
``-d 5_Labels_all`` option in the second call.
```
cd <raw_dataset>/Potsdam
unzip 2_Ortho_RGB.zip
unzip -d 5_Labels_all 5_Labels_all.zip
``` 
This yields:
```
├── <raw_dataset>
│   ├── Potsdam.zip
│   ├── Potsdam
│   │   ├── ...
│   │   ├── 2_Ortho_RGB.zip
│   │   ├── 2_Ortho_RGB
│   │   │   ├── top_potsdam_2_10_RGB.tif
│   │   │   ├── top_potsdam_2_10_RGB.tfw
│   │   │   ├── top_potsdam_2_11_RGB.tif
│   │   │   ├── top_potsdam_2_11_RGB.tfw
│   │   │   ├── ...
│   │   ├── ...
│   │   ├── 5_Labels_all.zip
│   │   ├── 5_Labels_all
│   │   │   ├── top_potsdam_2_10_label.tif
│   │   │   ├── top_potsdam_2_11_label.tif
│   │   │   ├── ...
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
(```data_preparation/prepare_isprs_potsdam.py```) to reorganize the images and
fix the missing geo-properties of the label data. Adjust the following values
in the script before running.
```
rgb_idp = "<raw_dataset>/Potsdam/2_Ortho_RGB"
label_idp = "<raw_dataset>/Potsdam/5_Labels_all"
data_odp = "<example_dataset>/raster"
```
Note: make sure that you correctly installed the library (by following the
installation instructions such as
```export PYTHONPATH=$PYTHONPATH:/path/to/EarthObservationTiles```).
The final structure should look as follows:
```
├── <example_dataset>
│   ├── raster
│   │   ├── top_potsdam_2_10
│   │   │   ├── top_potsdam_2_10_RGB.tif
│   │   ├── top_potsdam_2_10-labels
│   │   │   ├── top_potsdam_2_10_RGB.tif
│   │   ├── top_potsdam_2_11
│   │   │   ├── top_potsdam_2_11_RGB.tif
│   │   ├── top_potsdam_2_11-labels
│   │   │   ├── top_potsdam_2_11_RGB.tif
│   │   ├── ...
├── ...
```