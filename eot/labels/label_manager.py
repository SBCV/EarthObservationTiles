from eot.config.ai_config import CategoryConfig
from eot.core.check import check_categories


class LabelManager:
    @staticmethod
    def get_config_categories_sorted(config_categories):
        config_categories_sorted = sorted(
            config_categories, key=lambda x: x.palette_index
        )

        for category in config_categories_sorted:
            assert isinstance(category, CategoryConfig)

        # Check ignore_category and remove from config_categories_sorted
        ignore_category_list = [
            category
            for category in config_categories_sorted
            if category.is_ignore_category
        ]
        assert len(ignore_category_list) <= 1
        if len(ignore_category_list) == 1:
            ignore_category = ignore_category_list[0]
            assert ignore_category.palette_index == 255
            config_categories_sorted.remove(ignore_category)

        # Check that there are no missing palette_index values
        palette_index_list = [
            category.palette_index for category in config_categories_sorted
        ]
        assert palette_index_list[0] == 0
        for x, y in zip(palette_index_list, palette_index_list[1:]):
            assert x + 1 == y

        check_categories(config_categories_sorted)
        return config_categories_sorted
