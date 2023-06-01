import numpy as np

from eot.categories.dataset_categories import DatasetCategories
from eot.categories.dataset_category import DatasetCategory


class CategoryComparison:

    true_positive_name = "prediction and reference (true positive)"
    false_positive_name = "prediction and not reference (false positive)"
    false_negative_name = "not prediction and reference (false negative)"
    true_negative_name = "not prediction and not reference (true negative)"

    def __init__(
        self,
        ground_truth_mask,
        prediction_mask,
        category_name,
        comparison_categories=None,
    ):
        if comparison_categories is None:
            comparison_categories = self._get_default_comparison_categories()
        self.comparison_categories = comparison_categories
        self.palette_colors = (
            comparison_categories.get_category_palette_colors(
                only_active=False, include_ignore=True
            )
        )

        self.category_name = category_name

        # NB: Mask consist of boolean values, while mat contains integer values
        self.comparison_mat = np.zeros_like(ground_truth_mask, dtype=int)

        # https://en.wikipedia.org/wiki/Sensitivity_and_specificity
        # True positive
        true_positive_mask = np.logical_and(prediction_mask, ground_truth_mask)
        true_positive_index = self.comparison_categories.get_category(
            self.__class__.true_positive_name
        ).palette_index
        self.comparison_mat[true_positive_mask] = true_positive_index

        # False positive
        false_positive_mask = np.logical_and(
            prediction_mask, np.logical_not(ground_truth_mask)
        )
        false_positive_index = self.comparison_categories.get_category(
            self.__class__.false_positive_name
        ).palette_index
        self.comparison_mat[false_positive_mask] = false_positive_index

        # False negative
        false_negative_mask = np.logical_and(
            np.logical_not(prediction_mask), ground_truth_mask
        )
        false_negative_index = self.comparison_categories.get_category(
            self.__class__.false_negative_name
        ).palette_index
        self.comparison_mat[false_negative_mask] = false_negative_index

        # # True negative
        true_negative_mask = np.logical_and(
            np.logical_not(prediction_mask), np.logical_not(ground_truth_mask)
        )
        true_negative_index = self.comparison_categories.get_category(
            self.__class__.true_negative_name
        ).palette_index
        self.comparison_mat[true_negative_mask] = true_negative_index

    @classmethod
    def _get_default_comparison_categories(cls):
        # fmt:off
        true_positive_category = DatasetCategory(name=cls.true_positive_name, palette_index=1, palette_color=(0, 0, 127))       # noqa
        false_positive_category = DatasetCategory(name=cls.false_positive_name, palette_index=2, palette_color=(0, 127, 0))     # noqa
        false_negative_category = DatasetCategory(name=cls.false_negative_name, palette_index=3, palette_color=(127, 0, 0))     # noqa
        true_negative_category = DatasetCategory(name=cls.true_negative_name, palette_index=4, palette_color=(127, 127, 127))   # noqa
        # fmt:on
        comparison_categories = DatasetCategories(
            [
                true_positive_category,
                false_positive_category,
                true_negative_category,
                false_negative_category,
            ]
        )
        return comparison_categories
