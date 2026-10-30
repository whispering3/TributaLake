from datetime import date

from fiscal_spec import FieldSpec, LayoutSpec, RecordSpec, diff_specs


def test_identifies_added_removed_and_changed_fields() -> None:
    previous = _spec(
        {
            "C100": RecordSpec(
                "C100",
                "C",
                None,
                (FieldSpec(1, "REG", "str", "O"), FieldSpec(2, "VL_DOC", "decimal", "O")),
            ),
            "C170": RecordSpec("C170", "C", "C100", (FieldSpec(1, "REG", "str", "O"),)),
        }
    )
    current = _spec(
        {
            "C100": RecordSpec(
                "C100",
                "C",
                None,
                (FieldSpec(1, "REG", "str", "O"), FieldSpec(2, "VL_DOC", "decimal", "OC")),
            ),
            "C190": RecordSpec("C190", "C", "C100", (FieldSpec(1, "REG", "str", "O"),)),
        }
    )

    result = diff_specs(previous, current)

    assert result.added_records == ("C190",)
    assert result.removed_records == ("C170",)
    assert [change.field_name for change in result.changed_fields] == ["VL_DOC"]


def _spec(records: dict[str, RecordSpec]) -> LayoutSpec:
    return LayoutSpec("efd_icms_ipi", "1.0", date(2026, 1, 1), records)
