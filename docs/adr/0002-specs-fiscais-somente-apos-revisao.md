# ADR-0002: Specs fiscais somente após revisão de fonte oficial

## Status

Proposed — 2026-10-29

## Context

O parser SPED será dirigido por specs declarativas, mas o briefing ainda não
define as duas vigências-alvo, os manuais homologados nem a validação do contador.

## Decision

Não incluir registros ou campos SPED estimados no código. A primeira spec será
gerada a partir do manual oficial identificado, terá a fonte e a data registradas
e será revisada pelo contador consultor antes de ser publicada.

## Trade-offs

O leitor SPED não é iniciado com dados fictícios. Isso posterga a demonstração
completa, mas evita consolidar um contrato fiscal incorreto.

## Consequences

O próximo recorte depende da confirmação de vigências, módulo inicial e amostras
anonimizadas. A infraestrutura e o processamento de DF-e seguem evoluindo sem
criar dívida regulatória.

## Nota de implementação

A validação de schema de NF-e/NFC-e v4.00 usa a nfelib e seus bindings gerados
dos pacotes XSD oficiais. O resultado é registrado como achado `V-XML-003` e
nunca descarta os dados extraídos.
