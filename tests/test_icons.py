import pytest
from pydantic import TypeAdapter, ValidationError

from chatkit.icons import IconName


def test_vendor_icon_names_are_valid():
    """Icon names prefixed with `vendor:` are valid."""
    TypeAdapter(IconName).validate_python("vendor:icon-name")
    TypeAdapter(IconName).validate_python("vendor:another-icon-name")


def test_literal_icon_names_are_valid():
    """Spot check some literal icon names."""
    TypeAdapter(IconName).validate_python("book-open")
    TypeAdapter(IconName).validate_python("phone")
    TypeAdapter(IconName).validate_python("user")


def test_invalid_icon_names_are_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(IconName).validate_python("invalid-icon")
