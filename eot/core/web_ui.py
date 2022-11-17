import os
import glob
import re
from pathlib import Path

from eot.tiles.convert_tiles import convert_tiles_to_geojson
from eot.tiles.convert_tile import convert_tile_pixel_to_location
from eot.tiles.mercator_tile import MercatorTile
from eot.tiles.tile_path_manager import TilePathManager


def process_template(
    template, odp, base_url, ext, selected_tiles, coverage_tiles
):
    web_ui = open(template, "r").read()
    parent_dir = TilePathManager.get_parent_dir_of_tile_class(MercatorTile)
    web_ui = re.sub("{{base_url}}", os.path.join(base_url, parent_dir), web_ui)
    x_prefix, y_prefix, z_prefix = TilePathManager.get_prefixes_of_tile_class(
        MercatorTile
    )
    web_ui = re.sub("{{x}}", x_prefix + "{x}", web_ui)
    web_ui = re.sub("{{y}}", y_prefix + "{y}", web_ui)
    web_ui = re.sub("{{z}}", z_prefix + "{z}", web_ui)
    web_ui = re.sub("{{ext}}", ext, web_ui)
    web_ui = re.sub(
        "{{tiles}}", "tiles.json" if selected_tiles else "''", web_ui
    )

    if coverage_tiles:
        # For now take the first tile for centering
        tile = list(coverage_tiles)[0]
        assert isinstance(tile, MercatorTile)
        web_ui = re.sub("{{zoom}}", str(tile.get_zoom()), web_ui)
        web_ui = re.sub(
            "{{center}}",
            str(list(convert_tile_pixel_to_location(tile, 0.5, 0.5))[::-1]),
            web_ui,
        )

    with open(
        os.path.join(odp, os.path.basename(template)),
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write(web_ui)


def create_web_ui(
    odp,
    base_url,
    coverage_tiles,
    selected_tiles,
    ext,
    template_ifp,
    union_tiles=True,
):
    # The creation of the Web UI requires geo-registered tiles
    selected_tiles = [
        tile for tile in selected_tiles if isinstance(tile, MercatorTile)
    ]
    coverage_tiles = [
        tile for tile in coverage_tiles if isinstance(tile, MercatorTile)
    ]

    odp = os.path.expanduser(odp)
    template_ifp = os.path.expanduser(template_ifp)
    template_ifps = glob.glob(
        os.path.join(Path(__file__).parent.parent, "web_ui", "*")
    )

    if os.path.isfile(template_ifp):
        template_ifps.append(template_ifp)
    if os.path.lexists(os.path.join(odp, "index.html")):
        os.remove(
            os.path.join(odp, "index.html")
        )  # if already existing output dir, as symlink can't be overwriten
    os.symlink(os.path.basename(template_ifp), os.path.join(odp, "index.html"))

    # The parameters of leafletjs's TileLayer are described here:
    # https://leafletjs.com/reference-1.7.1.html#tilelayer-option
    # and here:
    # https://leafletjs.com/reference-1.7.1.html#gridlayer-option
    for template_fp in template_ifps:
        process_template(
            template_fp, odp, base_url, ext, selected_tiles, coverage_tiles
        )

    if selected_tiles:
        with open(
            os.path.join(odp, "tiles.json"), "w", encoding="utf-8"
        ) as fp:
            fp.write(convert_tiles_to_geojson(selected_tiles, union_tiles))
