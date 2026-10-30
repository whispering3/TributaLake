from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from fiscal_model import FileFingerprint


class Store:
    """Armazena dados particionados e mantém o controle de arquivos ingeridos."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._database_path = self.root / "catalog.duckdb"
        self._initialize_control_tables()

    def fingerprint(self, path: str | Path) -> FileFingerprint:
        source = Path(path)
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return FileFingerprint(sha256=digest.hexdigest(), size_bytes=source.stat().st_size)

    def has_file(self, file_id: str, tenant_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM ingest_file
                WHERE file_id = ? AND tenant_id = ? AND status = 'published'
                """,
                [file_id, tenant_id],
            ).fetchone()
        return row is not None

    def register_file(
        self,
        *,
        fingerprint: FileFingerprint,
        tenant_id: str,
        source_name: str,
        document_type: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingest_file (
                    file_id, tenant_id, source_name, document_type, size_bytes, status, ingested_at
                ) VALUES (?, ?, ?, ?, ?, 'processing', ?)
                ON CONFLICT (file_id, tenant_id) DO NOTHING
                """,
                [
                    fingerprint.sha256,
                    tenant_id,
                    source_name,
                    document_type,
                    fingerprint.size_bytes,
                    datetime.now(UTC),
                ],
            )

    def publish_rows(
        self,
        *,
        layer: str,
        table_name: str,
        tenant_id: str,
        competencia: date,
        file_id: str,
        rows: list[Mapping[str, Any]],
        schema: pa.Schema,
    ) -> Path:
        if not rows:
            raise ValueError("Não é possível publicar uma tabela vazia.")

        target = self._partition_path(layer, table_name, tenant_id, competencia, file_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(rows, schema=schema)
        self._write_parquet_atomically(table, target)
        self._activate_artifacts([(layer, table_name, tenant_id, file_id, target)])
        return target

    def mark_published(self, file_id: str, tenant_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingest_file
                SET status = 'published', published_at = ?
                WHERE file_id = ? AND tenant_id = ?
                """,
                [datetime.now(UTC), file_id, tenant_id],
            )

    def mark_failed(self, file_id: str, tenant_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE ingest_file SET status = 'failed' WHERE file_id = ? AND tenant_id = ?",
                [file_id, tenant_id],
            )

    def open_batch_writer(
        self,
        *,
        layer: str,
        tenant_id: str,
        competencia: date,
        file_id: str,
        flush_size: int = 10_000,
    ) -> ParquetBatchWriter:
        return ParquetBatchWriter(
            store=self,
            layer=layer,
            tenant_id=tenant_id,
            competencia=competencia,
            file_id=file_id,
            flush_size=flush_size,
        )

    def duckdb(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._database_path))

    def _initialize_control_tables(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_file (
                    file_id VARCHAR NOT NULL,
                    tenant_id VARCHAR NOT NULL,
                    source_name VARCHAR NOT NULL,
                    document_type VARCHAR NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    status VARCHAR NOT NULL,
                    ingested_at TIMESTAMPTZ NOT NULL,
                    published_at TIMESTAMPTZ,
                    PRIMARY KEY (file_id, tenant_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS published_artifact (
                    layer VARCHAR NOT NULL,
                    table_name VARCHAR NOT NULL,
                    tenant_id VARCHAR NOT NULL,
                    file_id VARCHAR NOT NULL,
                    path VARCHAR NOT NULL,
                    published_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (layer, table_name, tenant_id, file_id)
                )
                """
            )

    def _activate_artifacts(self, artifacts: list[tuple[str, str, str, str, Path]]) -> None:
        """Torna um conjunto de Parquet visível em uma única transação de catálogo."""
        affected_tables = {(layer, table_name) for layer, table_name, _, _, _ in artifacts}
        with self._connect() as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                for layer, table_name, tenant_id, file_id, path in artifacts:
                    self._validate_table_identifier(layer)
                    self._validate_table_identifier(table_name)
                    connection.execute(
                        """
                        INSERT INTO published_artifact (
                            layer, table_name, tenant_id, file_id, path, published_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT (layer, table_name, tenant_id, file_id)
                        DO UPDATE SET path = excluded.path, published_at = excluded.published_at
                        """,
                        [layer, table_name, tenant_id, file_id, path.as_posix(), datetime.now(UTC)],
                    )
                for layer, table_name in affected_tables:
                    rows = connection.execute(
                        """
                        SELECT path FROM published_artifact
                        WHERE layer = ? AND table_name = ? ORDER BY path
                        """,
                        [layer, table_name],
                    ).fetchall()
                    path_list = ", ".join(_sql_literal(row[0]) for row in rows)
                    view_name = f"v_{layer}_{table_name}"
                    connection.execute(
                        f"CREATE OR REPLACE VIEW {view_name} AS "
                        f"SELECT * FROM read_parquet([{path_list}], hive_partitioning = true)"
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        self._write_manifest(artifacts)

    def _write_manifest(self, artifacts: list[tuple[str, str, str, str, Path]]) -> None:
        file_id = artifacts[0][3]
        manifest_directory = self.root / "manifests"
        manifest_directory.mkdir(exist_ok=True)
        manifest_path = manifest_directory / f"{file_id}.json"
        if manifest_path.exists():
            return
        payload = {
            "file_id": file_id,
            "published_at": datetime.now(UTC).isoformat(),
            "artifacts": [
                {
                    "layer": layer,
                    "table": table_name,
                    "tenant_id": tenant_id,
                    "path": path.as_posix(),
                }
                for layer, table_name, tenant_id, _, path in artifacts
            ],
        }
        with NamedTemporaryFile(
            dir=manifest_directory, suffix=".json.tmp", delete=False, mode="w", encoding="utf-8"
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, sort_keys=True)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, manifest_path)

    def _validate_table_identifier(self, value: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("Nome de tabela ou camada inválido.")

    def _partition_path(
        self,
        layer: str,
        table_name: str,
        tenant_id: str,
        competencia: date,
        file_id: str,
    ) -> Path:
        safe_tenant = _safe_partition_value(tenant_id)
        return (
            self.root
            / layer
            / table_name
            / f"tenant_id={safe_tenant}"
            / f"competencia={competencia:%Y%m}"
            / f"arquivo={file_id}.parquet"
        )

    def _write_parquet_atomically(self, table: pa.Table, target: Path) -> None:
        with NamedTemporaryFile(
            dir=target.parent, suffix=".parquet.tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            pq.write_table(table, temporary_path, compression="zstd", write_statistics=True)
            os.replace(temporary_path, target)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self._database_path))


def _safe_partition_value(value: str) -> str:
    if not value or any(character in value for character in "/\\="):
        raise ValueError("O identificador do tenant contém caracteres inválidos para partição.")
    return value


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class ParquetBatchWriter:
    """Acumula pequenos lotes por tabela e publica cada arquivo de forma atômica."""

    def __init__(
        self,
        *,
        store: Store,
        layer: str,
        tenant_id: str,
        competencia: date,
        file_id: str,
        flush_size: int,
    ) -> None:
        self._store = store
        self._layer = layer
        self._tenant_id = tenant_id
        self._competencia = competencia
        self._file_id = file_id
        self._flush_size = flush_size
        self._schemas: dict[str, pa.Schema] = {}
        self._buffers: dict[str, list[Mapping[str, Any]]] = {}
        self._writers: dict[str, pq.ParquetWriter] = {}
        self._temporary_paths: dict[str, Path] = {}

    def append(self, table_name: str, row: Mapping[str, Any], schema: pa.Schema) -> None:
        existing_schema = self._schemas.setdefault(table_name, schema)
        if existing_schema != schema:
            raise ValueError(f"Schema incompatível para a tabela {table_name}.")
        buffer = self._buffers.setdefault(table_name, [])
        buffer.append(row)
        if len(buffer) >= self._flush_size:
            self._flush(table_name)

    def publish(self) -> None:
        for table_name in tuple(self._buffers):
            self._flush(table_name)
        for writer in self._writers.values():
            writer.close()
        for table_name, temporary_path in self._temporary_paths.items():
            target = self._store._partition_path(
                self._layer,
                table_name,
                self._tenant_id,
                self._competencia,
                self._file_id,
            )
            os.replace(temporary_path, target)
        artifacts = [
            (
                self._layer,
                table_name,
                self._tenant_id,
                self._file_id,
                self._store._partition_path(
                    self._layer,
                    table_name,
                    self._tenant_id,
                    self._competencia,
                    self._file_id,
                ),
            )
            for table_name in self._temporary_paths
        ]
        if artifacts:
            self._store._activate_artifacts(artifacts)

    def discard(self) -> None:
        for writer in self._writers.values():
            writer.close()
        for temporary_path in self._temporary_paths.values():
            temporary_path.unlink(missing_ok=True)

    def _flush(self, table_name: str) -> None:
        rows = self._buffers.get(table_name, [])
        if not rows:
            return
        schema = self._schemas[table_name]
        writer = self._writers.get(table_name)
        if writer is None:
            target = self._store._partition_path(
                self._layer,
                table_name,
                self._tenant_id,
                self._competencia,
                self._file_id,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                dir=target.parent, suffix=".parquet.tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
            writer = pq.ParquetWriter(temporary_path, schema, compression="zstd")
            self._writers[table_name] = writer
            self._temporary_paths[table_name] = temporary_path
        writer.write_table(pa.Table.from_pylist(rows, schema=schema))
        rows.clear()
