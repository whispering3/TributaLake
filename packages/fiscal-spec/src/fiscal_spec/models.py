from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class FieldSpec:
    position: int
    name: str
    field_type: str
    required: str
    precision: int | None = None
    scale: int | None = None
    values: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> FieldSpec:
        return cls(
            position=_required_int(value, "n"),
            name=_required_string(value, "name"),
            field_type=_required_string(value, "type"),
            required=_required_string(value, "req"),
            precision=_optional_positive_int(value.get("precision")),
            scale=_optional_non_negative_int(value.get("scale")),
            values=_string_tuple(value.get("values")),
        )


@dataclass(frozen=True, slots=True)
class RecordSpec:
    code: str
    block: str
    parent: str | None
    fields: tuple[FieldSpec, ...]

    @classmethod
    def from_mapping(cls, code: str, value: dict[str, Any]) -> RecordSpec:
        fields_value = value.get("fields", [])
        if not isinstance(fields_value, list):
            raise ValueError(f"O registro {code} deve declarar fields como uma lista.")
        fields = tuple(_field_from_value(field, code) for field in fields_value)
        return cls(
            code=code,
            block=_required_string(value, "block"),
            parent=_optional_string(value.get("parent")),
            fields=fields,
        )


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    module: str
    layout_version: str
    valid_from: date
    records: dict[str, RecordSpec]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> LayoutSpec:
        records_value = value.get("records")
        if not isinstance(records_value, dict):
            raise ValueError("A spec deve declarar records como um mapa por código.")
        records = {
            code: RecordSpec.from_mapping(code, record)
            for code, record in records_value.items()
            if isinstance(code, str) and isinstance(record, dict)
        }
        if len(records) != len(records_value):
            raise ValueError("Cada registro deve ter código texto e conteúdo em mapa.")
        return cls(
            module=_required_string(value, "module"),
            layout_version=_required_string(value, "layout_version"),
            valid_from=_parse_date(value.get("valid_from")),
            records=records,
        )


def _field_from_value(value: object, record_code: str) -> FieldSpec:
    if not isinstance(value, dict):
        raise ValueError(f"O registro {record_code} possui um campo inválido.")
    return FieldSpec.from_mapping(value)


def _required_string(value: dict[str, Any], field_name: str) -> str:
    field_value = value.get(field_name)
    if not isinstance(field_value, str) or not field_value.strip():
        raise ValueError(f"Campo obrigatório inválido: {field_name}.")
    return field_value


def _required_int(value: dict[str, Any], field_name: str) -> int:
    field_value = value.get(field_name)
    if not isinstance(field_value, int) or field_value < 1:
        raise ValueError(f"Campo numérico obrigatório inválido: {field_name}.")
    return field_value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("O pai do registro deve ser texto ou nulo.")
    return value


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("valid_from deve usar o formato ISO AAAA-MM-DD.") from error
    raise ValueError("valid_from é obrigatório.")


def _optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise ValueError("A precisão deve ser um inteiro positivo.")
    return value


def _optional_non_negative_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise ValueError("A escala deve ser um inteiro não negativo.")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Os valores permitidos devem ser uma lista de textos.")
    return tuple(value)
