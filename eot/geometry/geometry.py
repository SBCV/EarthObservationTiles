from rasterio.features import rasterize as _rasterize
from rasterio.features import shapes as _shapes
from rasterio.transform import from_bounds as _from_bounds


# Define some wrapper functions to obtain a lower coupling with rasterio
rasterize_features = _rasterize
get_feature_shapes = _shapes
transform_from_bounds = _from_bounds
