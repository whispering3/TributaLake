# QA e Code Review — 2026-10-29

## Escopo

Revisão da fundação do TributaLake: parser estrutural SPED, specs declarativas,
ingestão de NF-e, persistência Parquet/DuckDB, CLI e empacotamento.

## Gates executados

| Gate | Resultado |
| --- | --- |
| Pytest | 14 testes aprovados |
| Cobertura | 91,14% total |
| Ruff | aprovado |
| Pyright | 0 erros, 0 avisos |
| Compilação bytecode | aprovada |
| Wheel e sdist | aprovados para 7 pacotes |
| Instalação isolada | aprovada, inclusive resolução das dependências internas |
| CLI instalada | `tributa --help` aprovado |
| `pip check` isolado | aprovado |
| Auditoria de dependências de terceiros | nenhuma vulnerabilidade conhecida |

## Correção aplicada após a auditoria

### Publicação atômica de catálogo — resolvida

Os arquivos Parquet são concluídos antes de qualquer ativação. Depois, as
referências são gravadas em `published_artifact` e todas as views afetadas são
atualizadas em uma única transação DuckDB. O manifesto imutável por `file_id`
registra os artefatos publicados. Se a etapa anterior à transação falhar, dados
novos não ficam visíveis no catálogo.

O comportamento está coberto por teste de publicação em lote para duas tabelas.

## Achados que ainda bloqueiam produção

### P1 — Cobertura funcional fiscal ainda é incompleta

O motor suporta uma spec fornecida, mas ainda não há specs oficiais homologadas
da EFD-Contribuições, validação de totalizadores 9900/9999, regras referenciais,
retificações ou modelo silver. Portanto, o projeto não deve processar dados
reais como produto de produção nesta fase.

### P2 — Segurança de release depende de configuração externa

O workflow está pronto para OIDC/Trusted Publishing, mas a configuração do
publisher no PyPI, proteção do ambiente `pypi` e nomes de todos os pacotes
internos ainda precisam ser criados e validados na conta de Danilo Souza.

## Conclusão

A fundação é aprovada para continuidade de desenvolvimento e testes internos.
Não está aprovada para produção até o fechamento dos bloqueios P1 e a
homologação fiscal descrita acima.
