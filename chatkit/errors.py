from abc import ABC
from enum import Enum


# Not a closed enum, new error codes can and will be added as needed
class ErrorCode(str, Enum):
    STREAM_ERROR = "stream.error"


DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.STREAM_ERROR: 500,
}

DEFAULT_ALLOW_RETRY: dict[ErrorCode, bool] = {
    ErrorCode.STREAM_ERROR: True,
}


class BaseStreamError(ABC, Exception):
    allow_retry: bool


class StreamError(BaseStreamError):
    """
    Error with a specific error code that maps to a localized user-facing
    error message.
    """

    code: ErrorCode

    def __init__(
        self,
        code: ErrorCode,
        *,
        allow_retry: bool | None = None,
    ):
        self.code = code
        self.status_code = DEFAULT_STATUS.get(code, 500)
        if allow_retry is None:
            self.allow_retry = DEFAULT_ALLOW_RETRY.get(code, False)
        else:
            self.allow_retry = allow_retry


class CustomStreamError(BaseStreamError):
    """
    Error with a custom user-facing error message. The message should be
    localized as needed before raising the error.
    """

    message: str
    """The user-facing error message to display."""

    def __init__(
        self,
        message: str,
        *,
        allow_retry: bool = False,
    ):
        self.message = message
        self.allow_retry = allow_retry
