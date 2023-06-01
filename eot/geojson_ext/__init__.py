from rasterio.features import shapes as _shapes
from rasterio.features import rasterize as _rasterize

get_feature_shapes = _shapes
rasterize_features = _rasterize

geojson_precision = 16
