# TributaLake

Biblioteca Python para transformar SPED e documentos fiscais eletrônicos em dados
Parquet rastreáveis e consultáveis localmente com DuckDB.

## Estado atual

A fundação do monorepo já contém o contrato de dados compartilhado, validação da
chave de acesso de 44 dígitos, armazenamento Parquet atômico, catálogo DuckDB e
leitura inicial de NF-e (cabeçalho e itens). O leitor SPED declarativo depende da
aprovação das vigências e das specs oficiais.

## API e portal local

O TributaLake inclui uma primeira interface operacional para a EFD-Contribuições.
Ela usa a própria API HTTP do projeto, portanto o arquivo enviado no portal segue
o mesmo fluxo de ingestão, validação estrutural, quarentena e publicação em Parquet.

```powershell
uv sync --all-packages --group dev
uv run tributa-api
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000) para o portal e
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) para a documentação
OpenAPI. Por padrão, os dados locais ficam em `data/` e usam o tenant de
desenvolvimento `demo`.

> O portal ainda é local e destinado à operação assistida. Antes de uma publicação
> externa, a autenticação por usuário, o provedor de identidade, o armazenamento
> seguro dos arquivos e as specs homologadas precisam ser definidos.

## Desenvolvimento

Requer Python 3.12 ou superior e `uv`.

```powershell
uv sync --all-packages --group dev
uv run pytest --cov=packages --cov-fail-under=90
uv run ruff check .
uv run pyright
```

## Estrutura

- `fiscal-model`: tipos de domínio e validações puras.
- `fiscal-store`: Parquet, controle de idempotência e catálogo DuckDB.
- `dfe-tabular`: extração tabular de documentos fiscais eletrônicos.
- `fiscal-spec`: futura fonte declarativa dos leiautes SPED.
- `sped-reader`: futuro leitor streaming dirigido pela spec.
- `fiscal-synth`: futura geração determinística de dados sintéticos.
- `fiscal-cli`: ponto de entrada de operações locais, exposto pelo comando `tributa`.
- `tributa-api`: API HTTP e portal operacional local, exposto por `tributa-api`.

As decisões que ainda exigem validação externa estão em `docs/adr`.

O processo de release e a configuração necessária do PyPI estão em
[`docs/release.md`](docs/release.md).
