from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    from enum import Enum

    class StrEnum(str, Enum):
        """Minimal StrEnum compatibility for Python < 3.11."""


try:
    from typing import assert_never
except ImportError:  # Python < 3.11
    from typing import NoReturn

    def assert_never(arg: NoReturn) -> NoReturn:
        raise AssertionError(f"Expected code path to be unreachable, got: {arg!r}")


__all__ = ("StrEnum", "assert_never")
