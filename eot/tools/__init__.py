from eot.categories.dataset_categories import (
    DatasetCategory,
    DatasetCategories,
)


def initialize_category(args, attribute_name="category"):
    args_category = getattr(args, attribute_name)
    if args_category is not None:
        setattr(
            args,
            attribute_name,
            DatasetCategory.from_json_string(args_category),
        )
    return args


def initialize_categories(
    args, include_ignore=True, attribute_name="categories"
):
    args_categories = getattr(args, attribute_name)
    if args_categories is not None:
        setattr(
            args,
            attribute_name,
            DatasetCategories.from_json_string(args_categories),
        )
        if not include_ignore:
            args_categories = getattr(args, attribute_name)
            setattr(
                args,
                attribute_name,
                args_categories.get_non_ignore_categories(),
            )
    return args
