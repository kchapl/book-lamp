import sys

from google.protobuf import json_format
from google.protobuf.any_pb2 import Any


def test_recursion_limit(patched):
    if patched:
        from book_lamp.utils.protobuf_patch import apply_patch

        apply_patch()
        print("--- Testing WITH patch ---")
    else:
        print("--- Testing WITHOUT patch ---")

    # Construct a deeply nested Any structure in dict form
    # Any(Any(Any(...)))

    depth = 200

    nested = {"@type": "type.googleapis.com/google.protobuf.Any", "value": {}}
    curr = nested
    for _ in range(depth):
        curr["value"] = {
            "@type": "type.googleapis.com/google.protobuf.Any",
            "value": {},
        }
        curr = curr["value"]

    msg = Any()
    try:
        # Default max_recursion_depth is 100
        json_format.ParseDict(nested, msg, max_recursion_depth=100)
        print("Success: Parsing completed (Vulnerable or depth high enough)")
    except json_format.ParseError as e:
        print(f"Caught expected ParseError: {e}")
    except RecursionError:
        print("Vulnerable: RecursionError caught!")
    except Exception as e:
        print(f"Caught unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # We can't easily unpatch once patched in the same process, so we'll just run one mode or the other
    # based on argument
    patched = len(sys.argv) > 1 and sys.argv[1] == "--patched"
    test_recursion_limit(patched)
