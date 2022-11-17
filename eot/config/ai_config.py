import toml
from pydantic import BaseModel
from typing import List, Tuple, Dict, Union, Optional

# https://pypi.org/project/dataclasses/
# https://github.com/samuelcolvin/pydantic/


class ChannelConfig(BaseModel):
    name: str
    bands: list


class CategoryConfig(BaseModel):
    title: str
    is_ignore_category: bool = False
    palette_index: int
    palette_color: Union[str, List]
    label_values: Dict[
        str,
        List[
            Union[Tuple[int], Tuple[int, int, int], Tuple[int, int, int, int]]
        ],
    ]
    weight: float = 1.0


class ModelConfig(BaseModel):
    # NB: tile_size = (tile_width, tile_height)
    mmsegmentation_cfg_fp: str
    tile_size: Tuple[int, int]


class AuthentificationConfig(BaseModel):
    pg: str = None
    theia: str = None


class AIConfig(BaseModel):
    categories: List[CategoryConfig]
    model: ModelConfig
    auth: Optional[AuthentificationConfig]

    @classmethod
    def get_from_file(cls, toml_ifp):
        ai_config_dict = toml.load(toml_ifp)
        return cls(**ai_config_dict)
