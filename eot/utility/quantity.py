import pint

unit_reg = pint.UnitRegistry()
unit_reg.define("source_pixel = sp")
unit_reg.define("disk_pixel = dp")


def _convert_to_number(value_str):
    try:
        value = int(value_str)
    except ValueError:
        try:
            value = float(value_str)
        except ValueError:
            assert False, f"{value_str} represents not a proper number"
    return value


def parse_quantity_string(quantity_str):
    # Currently, the parsing methods of pint does not properly work for tuple
    #  strings such as "[512 512] pixel".
    # These include:
    #  unit_reg.Quantity(quantity_str)
    #  unit_reg(quantity_str)
    #  unit_reg.parse_expression(quantity_str)
    magnitude_str, unit_str = quantity_str.split("]")

    assert magnitude_str[0] == "["
    magnitude_str = magnitude_str.lstrip("[")
    magnitude_value_str_list = magnitude_str.split(" ")
    # NB: If the magnitude contains multiple numbers, the quantity magnitude
    #  string use the same number of characters for each number. Thus, if a
    #  number is represented with less digits, a prefix with spaces is
    #  prepended.
    #  Example:
    #   [21696 23588] pixel     # No leading spaces
    #   [10209  8976] pixel     # With leading spaces
    #  In this case str.split() creates additional empty strings in the result
    #  list.
    magnitude_value_str_list = [
        magnitude_value_str
        for magnitude_value_str in magnitude_value_str_list
        if magnitude_value_str != ""
    ]
    magnitude_value_list = [
        _convert_to_number(magnitude_value_str)
        for magnitude_value_str in magnitude_value_str_list
    ]

    assert unit_str[0] == " "
    unit_str = unit_str.lstrip(" ")

    if len(magnitude_value_list) == 1:
        magnitude = magnitude_value_list[0]
    else:
        magnitude = magnitude_value_list

    return unit_reg.Quantity(magnitude, unit_str)
