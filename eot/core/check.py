import re
import webcolors


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


def check_categories(categories):
    assert len(categories) >= 2, "CONFIG: At least 2 Classes are mandatory"

    for category in categories:
        assert len(category.title), "CONFIG: Empty classes.title value"
        assert _check_color(
            category.palette_color
        ), "CONFIG: Invalid classes.color value"

    # Check that there are no label duplicates
    dataset_names_list = [
        list(category.label_values.keys()) for category in categories
    ]
    dataset_names = sum(dataset_names_list, [])
    dataset_names_set = set(tuple(dataset_names))
    for dataset_name in dataset_names_set:
        dataset_label_values = [
            tuple(category.label_values[dataset_name])
            for category in categories
            if dataset_name in category.label_values
        ]
        dataset_label_values_flattened = [
            item for sublist in dataset_label_values for item in sublist
        ]
        num_elements = len(dataset_label_values_flattened)
        num_unique_elements = len(list(set(dataset_label_values_flattened)))
        err_msg = f"Found duplicated label values for {dataset_name} dataset!"
        assert num_elements == num_unique_elements, err_msg
