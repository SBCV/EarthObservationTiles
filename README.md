# Geo-Tiles
Geo-Tiles for Semantic Segmentation of Earth Observation Imagery

## Getting Started
- [Project Page](https://sbcv.github.io/projects/earth_observation_tiles)
- [Installation Instructions](doc/install_instructions.md)
- [Examples](doc/examples.md)
- [Consistent Geojson Visualization in QGIS](https://github.com/SBCV/QGIS-Plugin-Geojson-Filling)

## Example Results

### Tiling of Earth Observation Data
<p float="left" align="middle">
  <img src="doc/images/tiling/optimized_overhang_y.jpg" width="48%" />
  <img src="doc/images/tiling/mercator_border_y.jpg" width="48%" />
  <img src="doc/images/tiling/optimized_overhang_n.jpg" width="48%" />
  <img src="doc/images/tiling/mercator_border_n.jpg" width="48%" />
  Proposed tiling approach using 45m tiles (left) in comparison to commonly used web map tiles on zoom level 19 (right).
</p>

### Fusion of Semantic Segmentations
<p float="left" align="middle">
  <img src="doc/images/fusion/top_potsdam_3_14_RGB_image.jpg" width="32%" />
  <img src="doc/images/fusion/top_potsdam_3_14_RGB_ground_truth.jpg" width="32%" />
  <img src="doc/images/fusion/top_potsdam_3_14_RGB_fusion_improvement.jpg" width="32%" />
  <img src="doc/images/fusion/top_potsdam_4_14_RGB_image.jpg" width="32%" />
  <img src="doc/images/fusion/top_potsdam_4_14_RGB_ground_truth.jpg" width="32%" />
  <img src="doc/images/fusion/top_potsdam_4_14_RGB_fusion_improvement.jpg" width="32%" />
  <img src="doc/images/fusion/dar_0a4c40_site_1_image.jpg" width="32%" />
  <img src="doc/images/fusion/dar_0a4c40_site_1_ground_truth.jpg" width="32%" />
  <img src="doc/images/fusion/dar_0a4c40_site_1_fusion_improvement.jpg" width="32%" />
  <img src="doc/images/fusion/dar_f883a0_image.jpg" width="32%" />
  <img src="doc/images/fusion/dar_f883a0_ground_truth.jpg" width="32%" />
  <img src="doc/images/fusion/dar_f883a0_fusion_improvement.jpg" width="32%" />
  Left: input image. Center: ground truth of building category. Right: blue pixels are building category predictions of a ConvNext based model, pink building pixels are building predictions obtained by fusing overlapping tiles, teal pixels are building predictions removed by fusing overlapping tiles.
</p>
