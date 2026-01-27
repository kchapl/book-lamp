"""Patch for google.protobuf.json_format recursion depth bypass (CVE-2026-0994).

This patch ensures that recursion depth is correctly accounted for when parsing
WKT (Well Known Types) like Any, Struct, and Value, preventing DoS attacks via
deeply nested messages.
"""

from google.protobuf import json_format


def apply_patch():
    """Apply the monkeypatch to google.protobuf.json_format."""

    # Original _Parser class uses direct method calls for WKTs which bypass depth checks.
    # We redirect these calls back through ConvertMessage to ensure depth is tracked.

    # 1. Patch _ConvertAnyMessage
    def patched_ConvertAnyMessage(self, value, message, path):
        if isinstance(value, dict) and not value:
            return
        try:
            type_url = value["@type"]
        except KeyError as e:
            raise json_format.ParseError(
                "@type is missing when parsing any message at {0}".format(path)
            ) from e

        try:
            sub_message = json_format._CreateMessageFromTypeUrl(
                type_url, self.descriptor_pool
            )
        except TypeError as e:
            raise json_format.ParseError("{0} at {1}".format(e, path)) from e

        message_descriptor = sub_message.DESCRIPTOR
        full_name = message_descriptor.full_name

        # Use self.ConvertMessage instead of direct calls to handlers to ensure
        # recursion_depth is incremented and checked.
        if json_format._IsWrapperMessage(message_descriptor):
            self.ConvertMessage(value["value"], sub_message, "{0}.value".format(path))
        elif full_name in json_format._WKTJSONMETHODS:
            self.ConvertMessage(value["value"], sub_message, "{0}.value".format(path))
        else:
            # For regular messages, we still need to del @type to avoid 'unknown field' errors
            del value["@type"]
            try:
                self._ConvertFieldValuePair(value, sub_message, path)
            finally:
                value["@type"] = type_url

        message.value = sub_message.SerializeToString()
        message.type_url = type_url

    # 2. Patch _ConvertStructMessage
    def patched_ConvertStructMessage(self, value, message, path):
        if not isinstance(value, dict):
            raise json_format.ParseError(
                "Struct must be in a dict which is {0} at {1}".format(value, path)
            )
        message.Clear()
        for key in value:
            self.ConvertMessage(
                value[key], message.fields[key], "{0}.{1}".format(path, key)
            )

    # 3. Patch _ConvertListOrTupleValueMessage
    def patched_ConvertListOrTupleValueMessage(self, value, message, path):
        if not isinstance(value, (list, tuple)):
            raise json_format.ParseError(
                "ListValue must be in [] which is {0} at {1}".format(value, path)
            )
        message.ClearField("values")
        for index, item in enumerate(value):
            self.ConvertMessage(
                item, message.values.add(), "{0}[{1}]".format(path, index)
            )

    # Apply the patches
    json_format._Parser._ConvertAnyMessage = patched_ConvertAnyMessage
    json_format._Parser._ConvertStructMessage = patched_ConvertStructMessage
    json_format._Parser._ConvertListOrTupleValueMessage = (
        patched_ConvertListOrTupleValueMessage
    )
