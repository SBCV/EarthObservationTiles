def create_value_with_comment(value, comment=""):
    # https://stackoverflow.com/questions/21060073/dynamic-inheritance-in-python
    # https://stackoverflow.com/questions/2673651/inheritance-from-str-or-int
    value_type = type(value)

    class ValueWithComment(value_type):
        def __new__(cls, value, comment=""):
            obj = value_type.__new__(cls, value)
            obj.comment = comment
            return obj

    value_with_comment = ValueWithComment(value, comment)
    return value_with_comment
