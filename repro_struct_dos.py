import sys

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Struct


def test_struct_recursion(patched):
    if patched:
        from book_lamp.utils.protobuf_patch import apply_patch

        apply_patch()
        print("--- Testing WITH patch ---")
    else:
        print("--- Testing WITHOUT patch ---")

    depth = 200
    nested = {"k": "v"}
    for i in range(depth):
        nested = {"k": nested}

    msg = Struct()
    try:
        json_format.ParseDict(nested, msg, max_recursion_depth=100)
        print("Success: Parsing completed (Vulnerable or depth high enough)")
    except json_format.ParseError as e:
        print(f"Caught expected ParseError: {e}")
    except RecursionError:
        print("Vulnerable: RecursionError caught!")
    except Exception as e:
        print(f"Caught unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    patched = len(sys.argv) > 1 and sys.argv[1] == "--patched"
    test_struct_recursion(patched)
