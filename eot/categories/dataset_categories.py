import json
import re
import webcolors

from eot.categories.dataset_category import DatasetCategory


class DatasetCategories:
    def __init__(
        self,
        categories=None,
        default_palette_color=(0, 0, 0),
    ):
        if categories is None:
            categories = []
        self._categories = categories
        self.default_palette_color = default_palette_color

    def __repr__(self):
        return str(self._categories)

    def __len__(self):
        return self.categories.__len__()

    def __iter__(self):
        return self.categories.__iter__()

    def __next__(self):
        return self.categories.__next__()

    @classmethod
    def from_json_string(cls, cat_json_str):
        categories_list = json.loads(cat_json_str)
        categories = cls(
            [
                DatasetCategory(**category_dict)
                for category_dict in categories_list
            ]
        )
        return categories

    @property
    def categories(self):
        return self._categories

    @categories.setter
    def categories(self, categories):
        self._categories = categories

    @staticmethod
    def _check_color(color):
        """Check if an input color is or not valid (i.e CSS3 color name, transparent, or #RRGGBB)."""

        if type(color) == str:
            color = "white" if color.lower() == "transparent" else color
            hex_color = (
                webcolors.CSS3_NAMES_TO_HEX[color.lower()]
                if color[0] != "#"
                else color
            )
            result = bool(re.match(r"^#([0-9a-fA-F]){6}$", hex_color))
        elif type(color) == list or type(color) == tuple:
            result = len(color) == 3
        else:
            assert False
        return result

    def _check_categories(self, categories):
        msg = "Categories: At least 2 Classes are mandatory"
        assert len(categories) >= 2, msg

        for category in categories:
            assert len(category.name), "Categories: Empty classes.name value"
            assert self._check_color(
                category.palette_color
            ), "CONFIG: Invalid classes.color value"

    def get_category(self, category_name):
        for category in self.categories:
            if category.name == category_name:
                return category

    def to_json_string(self):
        json_str_list = [
            category.to_json_string() for category in self.categories
        ]
        json_str = f"[{','.join(json_str_list)}]"
        return json_str

    def to_coco_json_list(self):
        coco_list = [
            category.to_coco_json_dict()
            for category in self.get_non_ignore_categories()
        ]
        return coco_list

    def get_non_ignore_categories(self):
        non_ignore_categories = type(self)(
            categories=[
                category
                for category in self.categories
                if not category.is_ignore_category
            ],
            default_palette_color=self.default_palette_color,
        )
        return non_ignore_categories

    def get_active_categories(self):
        active_categories = type(self)(
            categories=[
                category for category in self.categories if category.is_active
            ],
            default_palette_color=self.default_palette_color,
        )
        return active_categories

    def get_ignore_category(self):
        ignore_categories = [
            category
            for category in self.categories
            if category.is_ignore_category
        ]
        assert len(ignore_categories) <= 1
        if len(ignore_categories) == 1:
            ignore_category = ignore_categories[0]
        else:
            ignore_category = None
        return ignore_category

    def get_category_names(self, only_active=False, include_ignore=True):
        category_names = []
        for category in self.categories:
            if only_active and not category.is_active:
                continue
            if not include_ignore and category.is_ignore_category:
                continue
            category_names.append(category.name)

        return category_names

    def get_category_palette_indices(
        self, only_active=False, include_ignore=True
    ):
        category_palette_indices = []
        for category in self.categories:
            if only_active and not category.is_active:
                continue
            if not include_ignore and category.is_ignore_category:
                continue
            category_palette_indices.append(category.palette_index)
        return category_palette_indices

    def get_valid_category_palette_indices(self):
        valid_palette_indices = []
        for category in self.categories:
            if not category.is_active:
                continue
            if category.is_ignore_category:
                continue
            valid_palette_indices.append(category.palette_index)
        return valid_palette_indices

    def get_invalid_category_palette_indices(self):
        invalid_palette_indices = []
        for category in self.categories:
            if category.is_active:
                continue
            if category.is_ignore_category:
                continue
            invalid_palette_indices.append(category.palette_index)
        return invalid_palette_indices

    def get_category_palette_colors(
        self, only_active=False, include_ignore=True
    ):
        """Mimics Pillows image.palette

        Computes a dictionary with
         {color_tuple_1: index_1, color_tuple_2: index_2, ...}
        """
        category_palette_colors = {}
        for category in self.categories:
            if only_active and not category.is_active:
                continue
            if not include_ignore and category.is_ignore_category:
                continue
            category_palette_colors[
                category.palette_color
            ] = category.palette_index
        return category_palette_colors

    def get_num_categories(self):
        return len(self)

    def get_num_non_ignore_categories(self):
        return len(self.get_non_ignore_categories())
