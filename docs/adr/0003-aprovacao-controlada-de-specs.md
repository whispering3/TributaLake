# ADR-0003: Aprovação controlada de specs fiscais

## Status

Accepted — 2026-10-29

## Context

Uma spec declarativa tem efeito direto sobre tipagem, hierarquia e validações do
SPED. Uma fonte desatualizada ou uma extração errada produz dados incorretos com
aparência de validade técnica.

## Decision

Toda spec deve registrar fonte oficial, hash do manual, vigência, diff contra a
versão anterior, revisor técnico e aprovação do contador consultor. Até esse
momento, permanece candidata e não entra na distribuição do pacote.

## Consequences

O projeto não publica falsos leiautes completos. A implementação do motor e dos
testes pode prosseguir, mas a cobertura fiscal só é declarada após o aceite.
