from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccessKeyValidation:
    key: str
    is_valid: bool
    error_code: str | None = None


def calculate_access_key_digit(first_43_digits: str) -> int:
    """Calcula o dígito verificador da chave de acesso fiscal pelo módulo 11."""
    if len(first_43_digits) != 43 or not first_43_digits.isdigit():
        message = "A base da chave deve conter exatamente 43 dígitos."
        raise ValueError(message)

    total = sum(
        int(digit) * weight
        for digit, weight in zip(first_43_digits, _cyclic_weights(), strict=True)
    )
    remainder = total % 11
    return 0 if remainder in (0, 1) else 11 - remainder


def validate_access_key(value: str) -> AccessKeyValidation:
    normalized = value.strip()
    if len(normalized) != 44 or not normalized.isdigit():
        return AccessKeyValidation(normalized, False, "V-KEY-001")

    expected_digit = calculate_access_key_digit(normalized[:43])
    if int(normalized[-1]) != expected_digit:
        return AccessKeyValidation(normalized, False, "V-KEY-001")

    return AccessKeyValidation(normalized, True)


def _cyclic_weights() -> tuple[int, ...]:
    weights: list[int] = []
    current = 4
    for _ in range(43):
        weights.append(current)
        current = 9 if current == 2 else current - 1
    return tuple(weights)
