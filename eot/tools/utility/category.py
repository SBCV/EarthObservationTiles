def _check_category_presence(defined_category_names, requested_category_name):
    if requested_category_name not in defined_category_names:
        msg = (
            f"Requested category type {requested_category_name} in the"
            " *.toml not found among the defined category titles"
            f" {defined_category_names} in the *.toml config file."
        )
        assert False, msg


def get_requested_category_indices(
    defined_categories, requested_category_names
):
    assert len(requested_category_names) > 0
    requested_category_names = [
        category_name.lower() for category_name in requested_category_names
    ]

    name_to_category = {
        defined_category.title.lower(): defined_category
        for defined_category in defined_categories
    }

    requested_category_indices = []
    for requested_category_name in requested_category_names:
        _check_category_presence(
            name_to_category.keys(), requested_category_name
        )
        requested_category = name_to_category[requested_category_name]
        requested_category_index = defined_categories.index(requested_category)
        requested_category_indices.append(requested_category_index)

    return requested_category_indices


def get_requested_category_names_to_indices(
    defined_categories, requested_category_names
):
    requested_category_indices = get_requested_category_indices(
        defined_categories, requested_category_names
    )
    category_names_to_indices = {}
    for name, index in zip(
        requested_category_names, requested_category_indices
    ):
        category_names_to_indices[name] = index
    return category_names_to_indices
