from datetime import date
from decimal import Decimal

from fiscal_spec import FieldSpec, RecordSpec
from sped_reader.records import ParsedSpedLine
from sped_reader.typing import type_record


def test_types_dates_decimals_and_enums() -> None:
    definition = RecordSpec(
        "C100",
        "C",
        None,
        (
            FieldSpec(1, "REG", "str", "O"),
            FieldSpec(2, "IND_OPER", "enum", "O", values=("0", "1")),
            FieldSpec(3, "VL_DOC", "decimal", "O", precision=18, scale=2),
            FieldSpec(4, "DT_DOC", "date", "O"),
        ),
    )
    record = ParsedSpedLine(7, "|C100|0|10,50|01012026|", "C100", ("0", "10,50", "01012026"))

    typed, findings = type_record(record, definition)

    assert typed is not None
    assert typed.values["vl_doc"] == Decimal("10.50")
    assert typed.values["dt_doc"] == date(2026, 1, 1)
    assert not findings


def test_routes_invalid_required_and_enum_values_to_findings() -> None:
    definition = RecordSpec(
        "C100",
        "C",
        None,
        (
            FieldSpec(1, "REG", "str", "O"),
            FieldSpec(2, "IND_OPER", "enum", "O", values=("0",)),
            FieldSpec(3, "NUM_DOC", "int", "O"),
        ),
    )
    record = ParsedSpedLine(9, "|C100|1|abc|", "C100", ("1", "abc"))

    typed, findings = type_record(record, definition)

    assert typed is None
    assert {finding.code for finding in findings} == {"V-FLD-001", "V-FLD-004"}
