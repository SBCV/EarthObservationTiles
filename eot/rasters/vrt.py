from multiprocessing import Process


def build_vrt(vrt_ofp, raster_list):

    # Use GDAL only if rasterio does NOT provide the corresponding
    #  functionality. Writing VRT's is not supported by rasterio
    #  see (https://github.com/mapbox/rasterio/issues/78).
    # To avoid any osgeo/gdal imports, wrap it in a subprocess.

    def _build_vrt_subprocess():
        try:
            # https://gis.stackexchange.com/questions/44003/python-equivalent-of-gdalbuildvrt/299218
            from osgeo import gdal

            vrt_options = gdal.BuildVRTOptions(
                resampleAlg="cubic", addAlpha=True
            )
            gdal.BuildVRT(vrt_ofp, raster_list, options=vrt_options)
            # gdal.BuildVRT(vrt_ofp, raster_list)
        except:
            msg = "VRT not created because of missing GDAL installation"
            with open(vrt_ofp + ".txt", "a") as fail_description_file:
                fail_description_file.write(msg)
            print(msg)

    p = Process(target=_build_vrt_subprocess)
    p.start()
    p.join()
