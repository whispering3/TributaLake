# ADR-0001: Monorepo Python com Parquet e DuckDB local

## Status

Accepted — 2026-10-29

## Context

O produto precisa processar arquivos grandes em Windows, Linux e macOS, sem rede
em execução, com rastreabilidade por arquivo e consulta analítica local.

## Decision

Adotar um monorepo Python 3.12+ com pacotes independentes, Parquet como formato
de persistência e DuckDB como catálogo e mecanismo de consulta embarcado.

## Rationale

O formato Parquet atende à leitura colunar e à portabilidade. DuckDB elimina a
necessidade de serviço externo no primeiro ciclo, sem impedir que um catálogo
remoto seja adicionado posteriormente. A separação dos pacotes mantém parser,
modelo e persistência independentes.

## Trade-offs

Não haverá transação distribuída entre arquivos Parquet e catálogo. A publicação
será por arquivo temporário seguido de renomeação atômica; reprocessamentos são
protegidos pelo fingerprint SHA-256 e pelo estado do arquivo no catálogo.

## Consequences

- Positivo: instalação simples, processamento offline e dados portáveis.
- Negativo: concorrência de múltiplos processos requer desenho explícito antes
  de execução compartilhada em rede.
- Mitigação: o recorte atual é local e registra a necessidade de lock na fase
  de processamento paralelo.
