from datetime import date
from pathlib import Path

from fiscal_spec import FieldSpec, LayoutSpec, RecordSpec
from fiscal_store import Store
from sped_reader import SpedReader


def test_ingests_typed_records_with_lineage_and_quarantine(tmp_path: Path) -> None:
    source = tmp_path / "efd.txt"
    source.write_text(
        "|0000|016|0|01012026|\n|C100|PARTNER|\n|C170|1|\n|UNKNOWN|x|\ninvalid\n",
        encoding="utf-8",
    )
    store = Store(tmp_path / "lake")

    report = SpedReader().ingest(source, tenant="acme", store=store, spec=_spec())
    connection = store.duckdb()

    assert report.records_written == 3
    assert report.records_quarantined == 2
    assert connection.sql(
        "SELECT _parent_line_no FROM v_bronze_sped_efd_contrib_c170"
    ).fetchall() == [(2,)]
    assert connection.sql("SELECT count(*) FROM v_bronze_sped_quarantine").fetchall() == [(2,)]


def _spec() -> LayoutSpec:
    return LayoutSpec(
        module="efd_contrib",
        layout_version="016",
        valid_from=date(2026, 1, 1),
        records={
            "0000": RecordSpec(
                "0000",
                "0",
                None,
                (
                    FieldSpec(1, "REG", "str", "O"),
                    FieldSpec(2, "COD_VER", "str", "O"),
                    FieldSpec(3, "COD_FIN", "int", "O"),
                    FieldSpec(4, "DT_INI", "date", "O"),
                ),
            ),
            "C100": RecordSpec(
                "C100",
                "C",
                None,
                (FieldSpec(1, "REG", "str", "O"), FieldSpec(2, "COD_PART", "str", "O")),
            ),
            "C170": RecordSpec(
                "C170",
                "C",
                "C100",
                (FieldSpec(1, "REG", "str", "O"), FieldSpec(2, "NUM_ITEM", "int", "O")),
            ),
        },
    )
