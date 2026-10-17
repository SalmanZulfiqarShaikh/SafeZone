import pytest

from core.phone import PhoneError, mask, normalize_phone, try_normalize


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


def test_parenthesised_input():
    assert normalize_phone("(0300) 123 4567") == "923001234567"


def test_whitespace_padded_input():
    assert normalize_phone("   0300 123 4567   ") == "923001234567"


def test_idempotency():
    once = normalize_phone("+92 (300) 123-4567")
    assert normalize_phone(once) == once


def test_invalid_formats_raise_phone_error():
    with pytest.raises(PhoneError):
        normalize_phone("")

    with pytest.raises(PhoneError):
        normalize_phone("   ")

    with pytest.raises(PhoneError):
        normalize_phone("03001234")  # too short

    with pytest.raises(PhoneError):
        normalize_phone("0300123456789")  # too long

    with pytest.raises(PhoneError):
        normalize_phone("02131234567")  # landline, not mobile starting with 3

    with pytest.raises(PhoneError):
        normalize_phone("abc03001234567")

    with pytest.raises(PhoneError):
        normalize_phone(None)

    with pytest.raises(PhoneError):
        normalize_phone(923001234567)  # non-string input


def test_phone_error_is_a_value_error():
    # Callers written against the old contract still catch it.
    with pytest.raises(ValueError):
        normalize_phone("nope")


def test_try_normalize_returns_none_instead_of_raising():
    assert try_normalize("03001234567") == "923001234567"
    assert try_normalize("not a number") is None
    assert try_normalize("") is None
    assert try_normalize(None) is None


def test_mask_keeps_only_last_four_digits():
    assert mask("923001234567") == "********4567"
    assert mask("+92 300 123-4567") == "********4567"
    assert mask("03001234567").endswith("4567")
    assert mask("03001234567").count("*") == 7
    assert mask("") == "****"


def test_format_display():
    from core.phone import format_display

    assert format_display("923492468494") == "+92 349 2468494"
    assert format_display("03492468494") == "+92 349 2468494"
    assert format_display("+92 349 2468494") == "+92 349 2468494"
    assert format_display("invalid") == "invalid"
    assert format_display(None) == ""
