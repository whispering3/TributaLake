from fiscal_model import calculate_access_key_digit, validate_access_key


def test_accepts_key_with_valid_check_digit() -> None:
    base = "3518060000000000000055001000000001100000000"
    key = f"{base}{calculate_access_key_digit(base)}"

    result = validate_access_key(key)

    assert result.is_valid
    assert result.error_code is None


def test_rejects_key_with_invalid_check_digit() -> None:
    base = "3518060000000000000055001000000001100000000"
    key = f"{base}{(calculate_access_key_digit(base) + 1) % 10}"

    result = validate_access_key(key)

    assert not result.is_valid
    assert result.error_code == "V-KEY-001"
