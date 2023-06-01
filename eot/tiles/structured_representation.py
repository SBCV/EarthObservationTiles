from collections import OrderedDict
import json
import copy
import rasterio


class StructuredRepresentation:
    def __init__(self, **kwargs):
        pass

    @classmethod
    def from_json_file(cls, json_fp):
        with open(json_fp) as json_file:
            object_dict = json.load(json_file)
        obj = cls.from_dict(object_dict)
        return obj

    @classmethod
    def from_json_string(cls, json_str):
        object_dict = json.loads(json_str)
        obj = cls.from_dict(object_dict)
        return obj

    @classmethod
    def from_dict(cls, object_dict):
        obj = cls(**object_dict)
        return obj

    def get_attribute_dict(self):
        # From the documentation:
        #     vars([object]) -> dictionary
        #
        #     Without arguments, equivalent to locals().
        #     With an argument, equivalent to object.__dict__.
        attribute_dict = OrderedDict(self.__dict__)
        return attribute_dict

    def get_property_dict(self):
        # https://stackoverflow.com/questions/17330160/how-does-the-property-decorator-work-in-python/17330273#17330273
        # https://docs.python.org/3/howto/descriptor.html
        property_dict = OrderedDict(
            {
                # NB: "value" represents the property object while
                #  "getattr(self, key)" represents the actual value
                key: getattr(self, key)
                for key, value in self.__class__.__dict__.items()
                if isinstance(value, property)
            }
        )
        return property_dict

    def get_attribute_and_property_dict(self):
        result_dict = copy.deepcopy(self.get_attribute_dict())
        property_dict = copy.deepcopy(self.get_property_dict())
        result_dict.update(property_dict)
        return result_dict

    # def get_dict_key(self, value):
    #     # NB: Better use "from varname import nameof"
    #     found = False
    #     key = None
    #     attributes_and_properties = self.get_attribute_and_property_dict()
    #     found_keys = []
    #     for current_key, current_value in attributes_and_properties.items():
    #         if value == current_value:
    #             found_keys.append(current_key)
    #             msg = f"Found multiple keys {found_keys} with identical value {value}!"
    #             if found:
    #                 assert False, msg
    #             key = current_key
    #             found = True
    #     if key is None:
    #         assert False, f"{key}:{value} not found in {self}"
    #     return key

    def _to_object_dict(
        self,
        include_properties,
        include_attr_list=None,
        ignore_attr_list=None,
        remove_underscore=True,
    ):
        assert not (include_attr_list and ignore_attr_list)
        if include_properties:
            full_obj_dict = self.get_attribute_and_property_dict()
        else:
            full_obj_dict = self.get_attribute_dict()

        selected_obj_dict = OrderedDict()
        if include_attr_list:
            for key, val in full_obj_dict.items():
                if key in include_attr_list:
                    selected_obj_dict[key] = val
        elif ignore_attr_list:
            for key, val in full_obj_dict.items():
                if key not in ignore_attr_list:
                    selected_obj_dict[key] = val
        else:
            selected_obj_dict = full_obj_dict

        final_object_dict = OrderedDict()
        if remove_underscore:
            for key, val in selected_obj_dict.items():
                final_object_dict[self._strip_leading_underscore(key)] = val
        else:
            final_object_dict = selected_obj_dict

        return final_object_dict

    def to_object_dict(self, include_properties=False):
        """Representation as dict where values might be complex objects"""
        object_dict = self._to_object_dict(
            include_properties=include_properties
        )
        return object_dict

    def to_plain_dict(self, include_properties=False):
        """Representation as dict where values consist of nested sub-dicts"""
        plain_dict = self.to_object_dict(include_properties=include_properties)
        for key, value_or_list in plain_dict.items():
            plain_dict[
                key
            ] = self._convert_value_or_value_list_to_plain_representation(
                value_or_list
            )
        return plain_dict

    @classmethod
    def _convert_value_or_value_list_to_plain_representation(
        cls, value_or_list, include_properties=False, float_format_str=None
    ):
        if isinstance(value_or_list, rasterio.Affine):
            value_or_list = list(value_or_list)[:6]
        if isinstance(value_or_list, list) or isinstance(value_or_list, tuple):
            converted_list = [
                cls._convert_value_to_plain_representation(
                    value, include_properties, float_format_str
                )
                for value in value_or_list
            ]
            value_or_list_type = type(value_or_list)
            result = value_or_list_type(converted_list)
        else:
            result = cls._convert_value_to_plain_representation(
                value_or_list, include_properties, float_format_str
            )
        return result

    @classmethod
    def _convert_value_to_plain_representation(
        cls, value, include_properties=False, float_format_str=None
    ):
        try:
            res = value.to_plain_dict(include_properties)
        except AttributeError:
            if type(value) in [bool, int, float, str] or value is None:
                res = value
            else:
                # Conversion of Quantity, CRS
                res = cls._convert_val_to_str(value, float_format_str)
        return res

    @staticmethod
    def _convert_val_to_str(value, float_format_str=None):
        if isinstance(value, float) and float_format_str:
            value_str = f"{value:float_format_str}"
        else:
            value_str = str(value)
        return value_str

    @classmethod
    def _convert_value_or_value_list_to_str(
        cls, value_or_list, include_properties=False, float_format_str=None
    ):
        plain_repr = cls._convert_value_or_value_list_to_plain_representation(
            value_or_list, include_properties, float_format_str
        )
        if isinstance(plain_repr, tuple) or isinstance(plain_repr, list):
            val = [str(v) for v in plain_repr]
            plain_repr = ", ".join(val)
        return plain_repr

    def create_header_line(self):
        line = f"================ {self.__class__.__name__} ================\n"
        return line

    @staticmethod
    def _strip_leading_underscore(input_str):
        return input_str.lstrip("_")

    @classmethod
    def _create_line_str(
        cls,
        key,
        value,
        value_offset=40,
        comment_offset=50,
        float_format_str=".2f",
    ):
        value_str = cls._convert_value_or_value_list_to_str(
            value, float_format_str=float_format_str
        )
        line_str = f"{cls._strip_leading_underscore(key):<{value_offset}}"

        if hasattr(value, "comment") and value.comment:
            line_str += f"{value_str:<{comment_offset}}{value.comment}"
        else:
            line_str += f"{value_str}"

        line_str += "\n"
        return line_str

    def to_lines(self, include_properties=False):
        lines = [self.create_header_line()]
        object_dict = self.to_object_dict(
            include_properties=include_properties
        )
        for key, value in object_dict.items():
            try:
                value_lines = value.to_lines()
                lines.extend(value_lines)
            except AttributeError:
                line_str = self._create_line_str(key, value)
                lines.append(line_str)
        return lines
