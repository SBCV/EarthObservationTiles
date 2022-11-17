from collections import OrderedDict


def _get_data_line(
    prefix,
    value,
    unit_str=None,
    min_value=None,
    max_value=None,
    comment=None,
    add_relative_deviations=True,
    key_value_separator="\t",
):
    if unit_str is not None:
        brackets_unit_str = f"[{unit_str}]"
    else:
        brackets_unit_str = ""
    if type(value) in [float, int]:
        value_str = f"{value:.2f}"
    else:
        value_str = value
    data_line = (
        f"{prefix}{key_value_separator} {value_str} {brackets_unit_str}"
    )
    if min_value is not None and max_value is not None:
        data_line += f" ({min_value: .2f} {brackets_unit_str} - {max_value: .2f} {brackets_unit_str})"
        if add_relative_deviations:
            data_line += f", deviation: (-{value - min_value: .2f} {brackets_unit_str} / +{max_value - value: .2f} {brackets_unit_str})"
    if comment is not None:
        data_line += f" {comment}"
    return data_line


def _get_data_dict(
    prefix,
    value,
    unit_str=None,
    min_value=None,
    max_value=None,
):
    data_dict = OrderedDict()

    value_info_list = []
    if unit_str is not None:
        value_info_list.append(unit_str)
    if min_value is not None:
        value_info_list.append(min_value)
    if max_value is not None:
        value_info_list.append(max_value)

    if len(value_info_list) > 0:
        data = [value] + value_info_list
    else:
        data = value

    key = prefix.rstrip()
    assert key[-1] == ":"
    key = key[:-1]
    data_dict[key] = data
    return data_dict


def _get_formatted_data(
    prefix,
    value,
    unit_str=None,
    min_value=None,
    max_value=None,
    comment=None,
    add_relative_deviations=True,
    key_value_separator="\t",
):
    data_line = _get_data_line(
        prefix,
        value,
        unit_str=unit_str,
        min_value=min_value,
        max_value=max_value,
        comment=comment,
        add_relative_deviations=add_relative_deviations,
        key_value_separator=key_value_separator,
    )
    data_dict = _get_data_dict(
        prefix,
        value,
        unit_str=unit_str,
        min_value=min_value,
        max_value=max_value,
    )
    return data_line, data_dict


def create_meta_info(
    tile_type,
    input_tile_zoom_level,
    input_tile_size_in_pixel,
    input_tile_size_in_meter,
    input_tile_stride_in_pixel,
    input_tile_stride_in_meter,
):
    data_list = [
        _get_formatted_data(
            "tile type:\t\t\t\t",
            str(tile_type),
        )
    ]
    if input_tile_zoom_level is not None:
        data_list.append(
            _get_formatted_data(
                "zoom_level:\t\t\t\t",
                input_tile_zoom_level,
            )
        )
    if input_tile_size_in_pixel is not None:
        data_list.append(
            _get_formatted_data(
                "input_tile_size_in_pixel:",
                input_tile_size_in_pixel,
            )
        )
    if input_tile_size_in_meter is not None:
        data_list.append(
            _get_formatted_data(
                "input_tile_size_in_meter:",
                input_tile_size_in_meter,
            )
        )
    if input_tile_stride_in_pixel is not None:
        data_list.append(
            _get_formatted_data(
                "input_tile_stride_in_pixel:",
                input_tile_stride_in_pixel,
            )
        )
    if input_tile_stride_in_meter is not None:
        data_list.append(
            _get_formatted_data(
                "input_tile_stride_in_meter:",
                input_tile_stride_in_meter,
            )
        )
    return data_list
