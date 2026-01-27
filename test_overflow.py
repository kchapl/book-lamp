import sys

from google.protobuf import json_format
from google.protobuf.struct_pb2 import Struct


def test_stack_overflow(patched):
    if patched:
        from book_lamp.utils.protobuf_patch import apply_patch

        apply_patch()
        print("--- Testing WITH patch ---")
    else:
        print("--- Testing WITHOUT patch ---")

    depth = 2000
    nested = {"k": "v"}
    for i in range(depth):
        nested = {"k": nested}

    msg = Struct()
    try:
        # Set max_recursion_depth very high to see if we hit stack overflow first
        json_format.ParseDict(nested, msg, max_recursion_depth=5000)
        print("Success: Parsing completed (Stack is big enough)")
    except json_format.ParseError as e:
        print(f"Caught expected ParseError: {e}")
    except RecursionError:
        print("Vulnerable: RecursionError caught! (Stack overflowed)")
    except Exception as e:
        print(f"Caught unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    patched = len(sys.argv) > 1 and sys.argv[1] == "--patched"
    test_stack_overflow(patched)
