from __future__ import annotations

from pathlib import Path

import typer
from dfe_tabular import DfeReader
from fiscal_spec import diff_specs, load_spec
from fiscal_store import Store
from sped_reader import SpedReader

app = typer.Typer(no_args_is_help=True, help="Ingestão e consulta local de dados fiscais.")
ingest_app = typer.Typer(no_args_is_help=True)
spec_app = typer.Typer(no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(spec_app, name="spec")


@ingest_app.command("dfe")
def ingest_dfe(
    source: Path = typer.Argument(exists=True, readable=True),
    tenant: str = typer.Option(..., "--tenant", min=1),
    store_path: Path = typer.Option(..., "--store", file_okay=False),
) -> None:
    """Ingere uma NF-e XML ou todos os XMLs de um diretório."""
    store = Store(store_path)
    reader = DfeReader()
    reports = (
        reader.ingest_dir(source, tenant=tenant, store=store)
        if source.is_dir()
        else [reader.ingest_file(source, tenant=tenant, store=store)]
    )
    for report in reports:
        typer.echo(report.summary())


@ingest_app.command("sped")
def ingest_sped(
    source: Path = typer.Argument(exists=True, readable=True),
    spec_path: Path = typer.Option(..., "--spec", exists=True, readable=True),
    tenant: str = typer.Option(..., "--tenant", min=1),
    store_path: Path = typer.Option(..., "--store", file_okay=False),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    """Ingere um SPED usando uma spec de leiaute aprovada."""
    report = SpedReader().ingest(
        source,
        tenant=tenant,
        store=Store(store_path),
        spec=load_spec(spec_path),
        mode="strict" if strict else "tolerant",
    )
    typer.echo(report.summary())


@spec_app.command("diff")
def diff_spec(previous: Path, current: Path) -> None:
    """Exibe registros e campos alterados entre duas vigências da mesma spec."""
    changes = diff_specs(load_spec(previous), load_spec(current))
    if changes.is_empty():
        typer.echo("Nenhuma alteração encontrada.")
        return
    for record in changes.added_records:
        typer.echo(f"registro adicionado: {record}")
    for record in changes.removed_records:
        typer.echo(f"registro removido: {record}")
    for change in changes.changed_fields:
        typer.echo(f"campo alterado: {change.record_code}.{change.field_name}")


if __name__ == "__main__":
    app()
