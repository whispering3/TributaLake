from datetime import date
from pathlib import Path

import pyarrow as pa
from fiscal_store import Store


def test_publishes_partition_and_catalog_view(tmp_path: Path) -> None:
    store = Store(tmp_path)
    schema = pa.schema([pa.field("document_key", pa.string(), nullable=False)])

    output = store.publish_rows(
        layer="bronze",
        table_name="nfe_header",
        tenant_id="acme",
        competencia=date(2026, 1, 1),
        file_id="a" * 64,
        rows=[{"document_key": "35180600000000000000550010000000011000000000"}],
        schema=schema,
    )

    assert output.exists()
    relation = store.duckdb().sql("SELECT count(*) FROM v_bronze_nfe_header")
    assert relation.fetchall() == [(1,)]
    assert (tmp_path / "manifests" / f"{'a' * 64}.json").exists()


def test_batch_publish_activates_all_tables_together(tmp_path: Path) -> None:
    store = Store(tmp_path)
    schema = pa.schema([pa.field("value", pa.string(), nullable=False)])
    writer = store.open_batch_writer(
        layer="bronze",
        tenant_id="acme",
        competencia=date(2026, 1, 1),
        file_id="b" * 64,
    )
    writer.append("table_a", {"value": "a"}, schema)
    writer.append("table_b", {"value": "b"}, schema)

    writer.publish()

    connection = store.duckdb()
    assert connection.sql("SELECT * FROM v_bronze_table_a").fetchall() == [("a", 202601, "acme")]
    assert connection.sql("SELECT * FROM v_bronze_table_b").fetchall() == [("b", 202601, "acme")]
