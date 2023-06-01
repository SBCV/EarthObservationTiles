import numpy as np
import cv2
from rasterio.enums import Resampling


def convert_affine_to_numpy(affine_trans):
    return np.reshape(np.asarray(affine_trans), (3, 3))


def convert_bounds_to_numpy(bounds):
    return np.reshape(np.asarray(bounds), 4)


def convert_rasterio_to_opencv_resampling(rasterio_resampling):
    if rasterio_resampling == Resampling.nearest:
        opencv_resampling = cv2.INTER_NEAREST
    elif rasterio_resampling == Resampling.bilinear:
        opencv_resampling = cv2.INTER_LINEAR
    elif rasterio_resampling == Resampling.cubic:
        opencv_resampling = cv2.INTER_CUBIC
    elif rasterio_resampling == Resampling.lanczos:
        opencv_resampling = cv2.INTER_LANCZOS4
    else:
        assert False
    return opencv_resampling
