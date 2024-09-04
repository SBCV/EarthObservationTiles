import json
from typing import List, Tuple, Union

# https://stackoverflow.com/questions/41914522/mypy-is-it-possible-to-define-a-shortcut-for-complex-type
ColorValue = Union[
    str, Tuple[int], Tuple[int, int, int], Tuple[int, int, int, int]
]
LabelValues = List[
    Union[Tuple[int], Tuple[int, int, int], Tuple[int, int, int, int]]
]


class DatasetCategory:
    def __init__(
        self,
        name: str = None,
        palette_index: int = None,
        palette_color: ColorValue = None,
        label_values: LabelValues = None,
        weight: float = 1.0,
        is_ignore_category: bool = False,
        is_active: bool = True,
        is_thing: bool = None,
        supercategory: str = None,
    ):
        self.name = name.lower()
        self.palette_index = palette_index
        self.palette_color = palette_color
        self.label_values = label_values
        self.weight = weight
        self.is_ignore_category = is_ignore_category
        self.is_active = is_active
        self.is_thing = is_thing
        if supercategory is None:
            supercategory = self.name
        self.supercategory = supercategory

        self._ensure_tuples()

    def __getitem__(self, item):
        # https://stackoverflow.com/questions/62560890/how-to-make-custom-data-class-subscriptable
        return getattr(self, item)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, DatasetCategory):
            return self.name == other.name
        return False

    @property
    def isthing(self):
        return self.is_thing

    @property
    def color(self):
        return self.palette_color

    @classmethod
    def from_json_string(cls, cat_json_str):
        category_dict = json.loads(cat_json_str)
        category_obj = cls(**category_dict)
        return category_obj

    def _ensure_tuples(self):
        if self.label_values is None:
            self.label_values = []
        self.label_values = [
            tuple(label_value_iterable)
            for label_value_iterable in self.label_values
        ]
        self.palette_color = tuple(self.palette_color)

    def to_json_string(self):
        return json.dumps(vars(self))

    def to_coco_json_dict(self):
        coco_dict = {
            "supercategory": self.supercategory,
            "color": self.palette_color,
            "isthing": int(self.is_thing),
            "id": self.palette_index,
            "name": self.name,
        }
        return coco_dict
