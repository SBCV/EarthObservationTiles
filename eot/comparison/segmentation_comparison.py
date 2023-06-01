from eot.comparison.category_comparison import CategoryComparison


class SegmentationComparison:
    def __init__(
        self,
        ground_truth_mat,
        prediction_mat,
        categories,
        comparison_categories,
    ):
        self.categories = categories

        assert len(prediction_mat.shape) == 2
        self._comparison_dict = {}
        for category in categories.get_active_categories():
            category_index = category.palette_index
            original_category_mask = ground_truth_mat == category_index
            prediction_category_mask = prediction_mat == category_index

            category_comparison = CategoryComparison(
                original_category_mask,
                prediction_category_mask,
                category.name,
                comparison_categories,
            )
            self._comparison_dict[category.name] = category_comparison

    def get_category_comparison(self, category_name):
        return self._comparison_dict[category_name]
