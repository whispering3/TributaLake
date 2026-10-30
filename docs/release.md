# Release do TributaLake

## Regra de publicação

O primeiro release público será `0.1.0`, somente após homologação funcional
documentada. A versão do comando público será distribuída como `tributa-lake`.

## Pré-requisitos

1. Criar o projeto `tributa-lake` no PyPI, sem enviar arquivos manualmente.
2. No PyPI, configurar Trusted Publisher para o repositório
   `whispering3/TributaLake`, workflow `publish.yml` e ambiente `pypi`.
3. Proteger o ambiente `pypi` no GitHub e exigir aprovação de Danilo Souza.
4. Executar CI, testes de compatibilidade e revisão de dependências.
5. Validar as specs fiscais aprovadas, golden files e benchmark definido para a
   versão.
6. Criar changelog e tag anotada após a aprovação do release.

## Publicação

O workflow `Publish packages` é manual. Ele constrói os pacotes e publica com
OIDC, sem token persistido no GitHub. A versão informada deve coincidir com os
metadados dos pacotes; o workflow não altera versões automaticamente.

## Observação de distribuição

Os pacotes internos serão publicados antes do comando principal. Antes do
primeiro release, seus nomes de distribuição devem ser verificados no PyPI e
reservados com o prefixo TributaLake, se necessário.
