import pytest
from Backend.phone import normalize_phone


def test_standard_pakistan_mobile_with_leading_zero():
    assert normalize_phone("03001234567") == "923001234567"
    assert normalize_phone("0345-9876543") == "923459876543"
    assert normalize_phone("0321 1122334") == "923211122334"


def test_plus_92_format():
    assert normalize_phone("+923001234567") == "923001234567"
    assert normalize_phone("+92 345 9876543") == "923459876543"
    assert normalize_phone("+92 (300) 123-4567") == "923001234567"


def test_already_normalized():
    assert normalize_phone("923001234567") == "923001234567"


def test_double_zero_prefix():
    assert normalize_phone("00923001234567") == "923001234567"


def test_short_ten_digit_pakistan():
    assert normalize_phone("3001234567") == "923001234567"


def test_invalid_formats_raise_value_error():
    with pytest.raises(ValueError):
        normalize_phone("")

    with pytest.raises(ValueError):
        normalize_phone("   ")

    with pytest.raises(ValueError):
        normalize_phone("03001234")  # too short

    with pytest.raises(ValueError):
        normalize_phone("0300123456789")  # too long

    with pytest.raises(ValueError):
        normalize_phone("02131234567")  # landline, not mobile starting with 3

    with pytest.raises(ValueError):
        normalize_phone("abc03001234567")

    with pytest.raises(ValueError):
        normalize_phone(None)
