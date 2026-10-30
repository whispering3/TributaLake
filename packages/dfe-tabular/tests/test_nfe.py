from pathlib import Path

from dfe_tabular.nfe import parse_nfe
from fiscal_model import calculate_access_key_digit


def test_parses_nfe_header_and_item(tmp_path: Path) -> None:
    base = "3518060000000000000055001000000001100000000"
    key = f"{base}{calculate_access_key_digit(base)}"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe{key}" versao="4.00">
    <ide><mod>55</mod><serie>1</serie><nNF>1</nNF><dhEmi>2026-01-15T10:00:00-03:00</dhEmi></ide>
    <emit><CNPJ>00000000000191</CNPJ><enderEmit><UF>SP</UF></enderEmit></emit>
    <dest><CNPJ>00000000000272</CNPJ><enderDest><UF>RJ</UF></enderDest></dest>
    <det nItem="1"><prod><cProd>ABC</cProd><xProd>Produto</xProd><NCM>12345678</NCM>
    <CFOP>5102</CFOP><qCom>2.0000</qCom><vUnCom>10.0000</vUnCom><vProd>20.00</vProd></prod></det>
    <total><ICMSTot><vNF>20.00</vNF></ICMSTot></total></infNFe></NFe>"""
    path = tmp_path / "nfe.xml"
    path.write_text(xml, encoding="utf-8")

    document = parse_nfe(path)

    assert document.header["document_key"] == key
    assert document.header["total_value"] == 20
    assert document.items[0]["item_number"] == 1
