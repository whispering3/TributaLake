from pathlib import Path

from dfe_tabular import DfeReader
from fiscal_model import calculate_access_key_digit
from fiscal_store import Store


def test_ingestion_is_idempotent(tmp_path: Path) -> None:
    base = "3518060000000000000055001000000001100000000"
    key = f"{base}{calculate_access_key_digit(base)}"
    source = tmp_path / "document.xml"
    source.write_text(_nfe_xml(key), encoding="utf-8")
    store = Store(tmp_path / "lake")
    reader = DfeReader()

    published = reader.ingest_file(source, tenant="acme", store=store)
    repeated = reader.ingest_file(source, tenant="acme", store=store)

    assert published.status == "published"
    assert published.records_written == 2
    assert repeated.status == "already_processed"
    assert store.duckdb().sql("SELECT count(*) FROM v_bronze_nfe_item").fetchall() == [(1,)]


def _nfe_xml(key: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00">
    <ide><mod>55</mod><serie>1</serie><nNF>1</nNF><dhEmi>2026-01-15T10:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>00000000000191</CNPJ><enderEmit><UF>SP</UF></enderEmit></emit>
    <det nItem="1"><prod><cProd>ABC</cProd><xProd>Produto</xProd><NCM>12345678</NCM>
    <CFOP>5102</CFOP><qCom>2.0000</qCom><vUnCom>10.0000</vUnCom><vProd>20.00</vProd></prod></det>
    <total><ICMSTot><vNF>20.00</vNF></ICMSTot></total></infNFe></NFe>"""
