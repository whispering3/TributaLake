# Briefing de Produção do Projeto 1: Camada Analítica Fiscal (SPED + NF-e/CT-e)

Versão 1.0 | 29/10/2026 | Público: engenheiro(a) sênior responsável pela implementação

## 1. Objetivo e definição de pronto

**Objetivo.** Entregar uma biblioteca Python (com CLI) que lê arquivos SPED (EFD Contribuições e EFD ICMS/IPI) e XMLs de NF-e, NFC-e e CT-e e produz tabelas Parquet tipadas, rastreáveis e consultáveis por DuckDB, com validações estruturadas e sem perda de dados. É a fundação dos projetos de auditoria de créditos, conciliação e anomalias.

**Fora de escopo da v1:** gerar ou transmitir SPED, substituir o PVA da Receita, regras de auditoria, interface gráfica, ECD, ECF, NFS-e municipal, custódia de certificados digitais.

**Definição de pronto (v1.0).**

1. Lê EFD Contribuições e EFD ICMS/IPI de pelo menos 2 vigências de leiaute cada, detectando a versão pelo registro 0000.
2. Para cada arquivo, contagem de registros por tipo no Parquet igual ao total declarado no registro 9900, ou divergência registrada como achado.
3. Nenhuma linha perdida: toda linha vai para a tabela do registro ou para a quarentena, com motivo.
4. Converte NF-e/NFC-e e CT-e para tabelas (cabeçalho, itens, impostos, eventos), com 100 mil documentos processados de forma idempotente.
5. Cruzamento NF-e × SPED disponível por chave de acesso.
6. Spec dos layouts gerada e versionada; adicionar uma nova vigência não exige código manual de registro.
7. Benchmarks publicados e dentro das metas da seção 5.6.
8. Documentação gerada a partir da spec; pacote publicável com versionamento semântico.

## 2. Requisitos

### 2.1 Funcionais

| ID | Requisito |
| --- | --- |
| FR-01 | Detectar módulo (Contribuições ou ICMS/IPI) e versão do leiaute a partir do registro 0000 |
| FR-02 | Ler em streaming, sem carregar o arquivo inteiro em memória |
| FR-03 | Detectar codificação (UTF-8 com fallback Latin-1/cp1252) e registrá-la |
| FR-04 | Associar cada registro filho ao pai pela hierarquia do leiaute |
| FR-05 | Tipar campos conforme a spec (texto, inteiro, decimal com precisão, data, enumeração) |
| FR-06 | Registrar lineage em toda linha: arquivo, número da linha, linha do pai, versão do leiaute, versão do parser |
| FR-07 | Enviar registros inválidos à quarentena sem interromper o restante (modo tolerante); modo estrito disponível |
| FR-08 | Modelar arquivos originais e retificadores e expor a versão vigente por competência |
| FR-09 | Converter NF-e/NFC-e/CT-e em tabelas via nfelib, validando contra os XSDs |
| FR-10 | Validar chave de acesso (44 dígitos e dígito verificador) e coerência com os campos do documento |
| FR-11 | Reprocessamento idempotente por arquivo e por partição |
| FR-12 | Expor catálogo DuckDB (views) sobre os Parquet |
| FR-13 | CLI para ingestão, validação, diff de specs e inspeção |

### 2.2 Não funcionais

| ID | Requisito |
| --- | --- |
| NFR-01 | Desempenho: metas da seção 5.6 (hipóteses a confirmar por benchmark) |
| NFR-02 | Memória estável independentemente do tamanho do arquivo |
| NFR-03 | Determinismo: mesma entrada e mesma versão produzem o mesmo conteúdo (exceto timestamps de ingestão) |
| NFR-04 | Sem acesso à rede em tempo de execução |
| NFR-05 | Python 3.12 ou superior; Linux, macOS e Windows |
| NFR-06 | Nenhum dado pessoal em logs; mascaramento por padrão |
| NFR-07 | Tipagem estática estrita nos pacotes de núcleo; cobertura de testes mínima de 90% no parser |

## 3. Arquitetura do módulo

### 3.1 Pacotes

| Pacote | Responsabilidade |
| --- | --- |
| fiscal-spec | Specs YAML dos layouts por módulo e vigência, ferramentas de extração e diff |
| sped-reader | Gerador de código/schemas a partir da spec e leitor streaming |
| dfe-tabular | Achatamento de NF-e, NFC-e e CT-e (sobre a nfelib) |
| fiscal-model | Modelo silver, normalizadores e validadores (CPF, CNPJ, chave, NCM) |
| fiscal-store | Escrita de Parquet, particionamento, catálogo DuckDB, controle de versões |
| fiscal-synth | Gerador de dados sintéticos e injetor de falhas |
| fiscal-cli | Interface de linha de comando |

Nome de trabalho: fiscal-lake (checar disponibilidade no PyPI antes de adotar).

### 3.2 Pipeline de ingestão

| Estágio | Entrada | Saída | Em caso de falha |
| --- | --- | --- | --- |
| 1. Fingerprint | Arquivo | SHA-256, tamanho, tenant | Arquivo repetido é ignorado (idempotência) |
| 2. Detecção | Primeiras linhas | Módulo, versão, codificação | Rejeita com erro claro e registra |
| 3. Parse | Linhas | Registros tipados + lineage | Linha vai à quarentena |
| 4. Validação | Registros | Achados estruturados | Nunca descarta dados |
| 5. Escrita bronze | Registros | Parquet por registro e partição | Escrita atômica: grava em temporário e renomeia |
| 6. Normalização silver | Bronze | Tabelas canônicas | Falha do contrato de dados bloqueia a publicação da partição |
| 7. Publicação | Parquet | Catálogo DuckDB atualizado | Mantém a versão anterior visível |

## 4. Spec declarativa dos layouts

### 4.1 Princípios

- A spec é a fonte de verdade; nenhum registro é codificado à mão.
- Cada módulo tem um arquivo por vigência de leiaute. O diff entre vigências é gerado por ferramenta e revisado em pull request.
- A spec é derivada dos manuais oficiais (Guia Prático da EFD e leiautes publicados pela Receita Federal e pelo Confaz). Antes de fixar qualquer vigência, confirmar a versão atual nos portais oficiais.

### 4.2 Formato (exemplo ilustrativo; números de campo e nomes devem ser conferidos com o leiaute vigente)

```yaml
module: efd_icms_ipi
layout_version: '<cod_ver>'
valid_from: 2026-01-01
records:
  C100:
    block: C
    parent: C010
    description: Documento - nota fiscal (código 01), nota fiscal avulsa (código 1B), NF de produtor (04) e NF-e (55)
    fields:
      - {n: 1, name: REG, type: str, size: 4, req: O}
      - {n: 2, name: IND_OPER, type: enum, size: 1, req: O, values: ['0', '1']}
      - {n: 4, name: COD_PART, type: str, size: 60, req: OC, ref: '0150.COD_PART'}
      - {n: 9, name: CHV_NFE, type: str, size: 44, req: OC, check: chave_acesso}
      - {n: 10, name: DT_DOC, type: date, format: ddmmyyyy, req: O}
      - {n: 12, name: VL_DOC, type: decimal, precision: 18, scale: 2, req: O}
```

Legenda de obrigatoriedade: O (obrigatório), OC (obrigatório condicional), N (não preencher). A condição de OC fica em campo separado da spec (expressão avaliável) quando o manual a define de forma objetiva; caso contrário, vira aviso e não erro.

### 4.3 Regras de formato do arquivo SPED

- Cada linha começa e termina com o caractere pipe e traz o código do registro no primeiro campo.
- Datas no formato ddmmaaaa; decimais com vírgula, sem separador de milhar. Campos vazios são permitidos conforme obrigatoriedade.
- Registros de abertura (x001) indicam se o bloco tem dados; encerramento (x990) traz o total de linhas do bloco; o bloco 9 traz os totalizadores (9900 por tipo de registro, 9999 total de linhas do arquivo).

Exemplo de linhas (fictício):

```text
|0000|<cod_ver>|0|01012026|31012026|EMPRESA FICTICIA LTDA|00000000000191|...|
|C001|0|
|C100|0|1|F001|55|00|1|123|<chave 44 dígitos>|05012026|05012026|1500,00|...|
|C990|3|
```

### 4.4 Geração de código

Da spec saem: schema Arrow por registro, tabela de despacho (código do registro para classe/parser), docstrings e a página de documentação de cada campo. Mudança de spec exige regenerar e passar os testes de snapshot.

### 4.5 Runbook: nova vigência de leiaute

1. Baixar o novo manual e registrar a fonte e a data.
2. Rodar o extrator para gerar a spec candidata.
3. Rodar `fiscal-cli spec diff <anterior> <nova>` e revisar campos adicionados, removidos e alterados.
4. Revisão humana linha a linha das mudanças; contador consultor valida regras de obrigatoriedade condicional.
5. Gerar código e schemas; atualizar golden files e dados sintéticos.
6. Rodar a suíte completa; abrir PR com o diff da spec como corpo.
7. Release de patch ou minor com nota de migração, se o schema silver mudar.

## 5. Leitor SPED

### 5.1 Algoritmo (visão geral)

```python
def ingest(path, tenant, store, mode='tolerant'):
    fp = fingerprint(path)
    if store.has_file(fp):
        return store.report(fp)            # idempotência
    enc = detect_encoding(path)
    head = read_record_0000(path, enc)      # módulo, versão, período
    spec = load_spec(head.module, head.cod_ver)
    stack = HierarchyStack(spec)
    with store.writer(fp, spec) as out:
        for line_no, raw in stream_lines(path, enc):
            rec = parse_line(raw, spec)            # split, tipagem
            findings = validate_record(rec, spec)
            parent = stack.resolve(rec.reg)         # linha do pai
            if rec.is_invalid and mode == 'tolerant':
                out.quarantine(line_no, raw, findings)
            else:
                out.write(rec, line_no, parent)
            out.add_findings(findings)
        out.add_findings(validate_totals(out.counters, spec))   # x990, 9900, 9999
    return store.report(fp)
```

### 5.2 Decisões de implementação

- Leitura em blocos binários, decodificação incremental e divisão de linhas por terminador (CRLF ou LF).
- Acúmulo em buffers colunares (Arrow) por tipo de registro, com descarga ao atingir o tamanho de row group configurado.
- Para velocidade, avaliar três caminhos e escolher por benchmark: Python puro com otimizações, Polars (leitura CSV com separador pipe, uma passada por tipo de registro) e extensão em Rust. Começar pela opção mais simples que cumpra a meta.
- Hierarquia: pilha por nível do registro conforme a spec; a linha do pai é gravada como coluna.
- Campos com vírgula decimal convertidos para decimal exato (nunca float) com a precisão definida na spec.

### 5.3 Quarentena e achados

- Tabela de quarentena: arquivo, linha, texto bruto, código do achado, mensagem.
- Tabela de achados: arquivo, linha, registro, campo, código (seção 8), severidade, valor observado, valor esperado.
- A taxa de quarentena por arquivo é exposta como métrica e no relatório de ingestão.

### 5.4 Retificações

- Cada arquivo guarda finalidade (original ou retificador, conforme o campo do registro 0000 de cada módulo), período e data de ingestão.
- A view de versão vigente por tenant e competência escolhe a retificadora mais recente.
- Reingerir um arquivo já conhecido não duplica; ingerir uma retificadora não apaga o original.

### 5.5 Escrita e particionamento

- Layout: `store/<camada>/<tabela>/tenant_id=<id>/competencia=<aaaamm>/arquivo=<id>.parquet`.
- Compressão zstd; estatísticas de coluna habilitadas; row groups entre 256 mil e 1 milhão de linhas como ponto de partida, calibrados por benchmark no DuckDB.
- Escrita atômica (arquivo temporário e renomeação) e manifesto por partição com contagens e hash.

### 5.6 Metas de desempenho (hipóteses a confirmar)

| Cenário | Meta inicial |
| --- | --- |
| Arquivo SPED de 1 GB em máquina com 8 núcleos | Menos de 5 minutos |
| Pico de memória no mesmo cenário | Abaixo de 2 GB |
| 100 mil NF-e (XML) para Parquet | Menos de 10 minutos |
| Consulta DuckDB de contagem por registro em 100 arquivos | Menos de 2 segundos |

Se a meta não for atingida em Python, o gargalo é medido com profiling antes de decidir por Polars ou Rust.

## 6. Modelo de dados

### 6.1 Colunas de lineage (todas as tabelas bronze)

| Coluna | Tipo | Uso |
| --- | --- | --- |
| \_tenant\_id | string | Isolamento |
| \_file\_id | string | SHA-256 do arquivo |
| \_line\_no | int64 | Linha de origem |
| \_parent\_line\_no | int64, nulo | Linha do registro pai |
| \_layout\_version | string | Versão do leiaute |
| \_parser\_version | string | Versão do parser |
| \_competencia | date | Primeiro dia do mês do período |

### 6.2 Tabelas de controle

| Tabela | Conteúdo |
| --- | --- |
| sped\_file | file\_id, tenant\_id, módulo, cod\_ver, finalidade, dt\_ini, dt\_fim, CNPJ, UF, perfil, codificação, bytes, linhas, status, versão do parser, data de ingestão |
| sped\_quarantine | file\_id, linha, texto bruto, código, mensagem |
| sped\_finding | file\_id, linha, registro, campo, código, severidade, observado, esperado |
| ingest\_run | run\_id, file\_id, início, fim, duração por estágio, contadores |

### 6.3 Bronze SPED

Uma tabela por tipo de registro (por exemplo sped\_icms\_C100, sped\_contrib\_M210), com as colunas da spec nos tipos definidos e as colunas de lineage. Nomes de coluna iguais aos do manual (minúsculas).

### 6.4 Silver (modelo canônico)

| Tabela | Origem | Chave | Observações |
| --- | --- | --- | --- |
| dim\_participante | 0150 | tenant, cod\_part, competência | CNPJ/CPF normalizado e com flag de validade; histórico por competência |
| dim\_item | 0200 | tenant, cod\_item, competência | NCM, unidade, tipo; vínculo com 0205/0206/0220 em tabelas auxiliares |
| doc\_fiscal | C100 e equivalentes de outros blocos | doc\_key | doc\_key é a chave de acesso quando existir; senão, hash de tenant, modelo, série, número e participante |
| doc\_fiscal\_item | C170 e equivalentes | doc\_key, num\_item | Impostos do item em colunas por tributo |
| doc\_fiscal\_resumo | C190 (ICMS/IPI) | doc\_key, cst, cfop, aliquota | Resumo analítico do documento |
| apuracao\_icms | E110 e correlatos | tenant, competência | Valores por período |
| apuracao\_pis\_cofins | Bloco M | tenant, competência, código | Base, alíquota, valor e ajustes |
| sped\_documento\_origem | Todas | doc\_key, file\_id | Liga cada documento às linhas do arquivo de origem |

Tipos: valores monetários como decimal conforme a spec (precisão e escala por campo), datas como date, códigos como string, enumerações com tabela de domínio. O mapeamento bronze para silver é declarativo (arquivo YAML por tabela silver) e testado.

### 6.5 NF-e, NFC-e e CT-e

| Tabela | Conteúdo principal |
| --- | --- |
| nfe\_header | chave, modelo, série, número, data de emissão, emitente e destinatário (CNPJ/CPF, UF), totais, status de autorização, versão do leiaute |
| nfe\_item | chave, número do item, produto, NCM, CFOP, quantidade, valor unitário, valor total |
| nfe\_item\_imposto | chave, item, tributo (ICMS, IPI, PIS, COFINS, e campos de IBS/CBS quando presentes no leiaute), CST ou CSOSN, base, alíquota, valor |
| nfe\_pagamento | chave, forma, valor |
| nfe\_transporte | chave, modalidade, transportadora, volumes |
| nfe\_evento | chave, tipo, sequência, data, protocolo, justificativa |
| cte\_header | chave, modelo, tomador, remetente, destinatário, valor da prestação, modal |
| cte\_componente | chave, nome do componente, valor |
| cte\_doc\_transportado | chave do CT-e, chave da NF-e |

Convenções: nomes em snake\_case derivados do caminho da tag; imposto com estrutura de escolha (grupos de ICMS) normalizado em colunas únicas (cst/csosn, base, alíquota, valor) preservando o nome do grupo original em coluna própria. Campos novos do leiaute entram como colunas opcionais; a versão do schema vai nos metadados do Parquet.

Chave de acesso: validar 44 dígitos, dígito verificador (módulo 11) e coerência entre a chave e os campos do documento (UF, ano e mês, CNPJ do emitente, modelo, série e número).

### 6.6 Catálogo DuckDB

Views criadas sobre os Parquet: v\_doc\_fiscal\_vigente (resolve retificações), v\_nfe\_vs\_sped (cruzamento por chave de acesso) e v\_quarentena\_resumo. As views são parte da API pública e versionadas.

## 7. Cruzamento NF-e × SPED

- Junção por chave de acesso (campo CHV\_NFE dos registros de documento do SPED e chave da NF-e).
- Resultados classificados: presente nos dois, só no XML, só no SPED, valores divergentes (com o campo e a diferença), data divergente.
- Entregue como view e como tabela materializada por competência, base do projeto de auditoria.

## 8. Catálogo de validações

| Código | Camada | Descrição | Severidade |
| --- | --- | --- | --- |
| V-STR-001 | Estrutural | Linha sem pipe inicial ou final | Erro |
| V-STR-002 | Estrutural | Registro desconhecido para a versão do leiaute | Erro |
| V-STR-003 | Estrutural | Bloco sem abertura (x001) ou sem encerramento (x990) | Erro |
| V-STR-004 | Estrutural | Total do x990 diferente do contado | Erro |
| V-STR-005 | Estrutural | Contagem do 9900 diferente do contado por registro | Erro |
| V-STR-006 | Estrutural | Total do 9999 diferente das linhas do arquivo | Erro |
| V-FLD-001 | Campo | Tipo inválido (data, decimal, inteiro) | Erro |
| V-FLD-002 | Campo | Tamanho acima do definido | Aviso |
| V-FLD-003 | Campo | Campo obrigatório ausente | Erro |
| V-FLD-004 | Campo | Valor fora da enumeração | Erro |
| V-REF-001 | Referencial | Código de participante inexistente no 0150 | Erro |
| V-REF-002 | Referencial | Código de item inexistente no 0200 | Erro |
| V-ARI-001 | Aritmética | Soma dos itens incompatível com o total do documento (fórmula validada por contador, com tolerância configurável) | Aviso |
| V-KEY-001 | Chave | Chave de acesso inválida (tamanho ou dígito verificador) | Erro |
| V-KEY-002 | Chave | Chave incoerente com os campos do documento | Aviso |
| V-XML-001 | Cruzada | Chave do SPED sem XML no repositório | Info |
| V-XML-002 | Cruzada | Valor do XML diferente do escriturado | Aviso |

Cada validação tem teste positivo e negativo e documentação do racional. Severidades são configuráveis por tenant, exceto as estruturais.

## 9. API e CLI

```python
from fiscal_lake import Store, SpedReader, DfeReader

store = Store('~/dados/fiscal')
report = SpedReader().ingest('efd.txt', tenant='acme', store=store)
print(report.summary())            # linhas, registros, quarentena, achados

DfeReader().ingest_dir('xmls/', tenant='acme', store=store)

con = store.duckdb()
con.sql('select count(*) from v_doc_fiscal_vigente').show()
con.sql('select * from v_nfe_vs_sped where situacao <> \'ok\' limit 20').show()
```

```bash
fiscal-cli ingest sped efd.txt --tenant acme --store ~/dados/fiscal
fiscal-cli ingest dfe xmls/ --tenant acme
fiscal-cli validate --tenant acme --competencia 2026-01
fiscal-cli spec diff efd_icms_ipi <versao_anterior> <versao_nova>
fiscal-cli inspect arquivo efd.txt
```

A API pública é pequena e estável; tudo o mais é interno. Mudanças incompatíveis exigem versão major.

## 10. Plano de testes

### 10.1 Matriz

| ID | Tipo | Objetivo | Dados | Critério |
| --- | --- | --- | --- | --- |
| T-01 | Unidade | Tipagem de campos (data, decimal, enum) | Casos de borda por tipo | 100% dos casos da spec |
| T-02 | Propriedade (hypothesis) | Para qualquer registro válido gerado, parse seguido de serialização reproduz a linha | Gerador por spec | Sem contraexemplo em 10 mil execuções |
| T-03 | Propriedade | Chaves de acesso geradas têm DV válido e passam em V-KEY-001 | Gerador | 100% |
| T-04 | Snapshot de spec | Specs geradas não mudam sem PR | Specs versionadas | Falha em mudança não revisada |
| T-05 | Golden | Saída Parquet de arquivos reais anonimizados igual à esperada | 3 empresas, 2 vigências por módulo | Igualdade de conteúdo |
| T-06 | Integridade | Contagem por registro igual ao 9900 | Golden e sintéticos | Igualdade |
| T-07 | Falhas injetadas | Validador detecta falhas plantadas | Sintéticos com manifesto de falhas | Recall igual a 100% nas estruturais e alto nas demais (meta definida por regra) |
| T-08 | Robustez (fuzz) | Arquivo truncado, codificação errada, linhas extras, blocos fora de ordem | Mutações automáticas | Nunca falha com exceção não tratada; sempre quarentena ou rejeição com motivo |
| T-09 | Idempotência | Reingerir o mesmo arquivo e reprocessar partição | Qualquer | Estado final idêntico |
| T-10 | Retificação | Original seguido de retificadora | Sintéticos | View vigente correta |
| T-11 | Contrato de dados | Schema e domínios silver | Todas as tabelas | Falha bloqueia publicação |
| T-12 | DF-e | NF-e e CT-e de várias versões e formatos (com e sem protocolo, eventos) | Amostras oficiais e sintéticas | Totais por documento batem com o XML |
| T-13 | Cruzamento | NF-e × SPED | Sintéticos com divergências conhecidas | Classificação correta |
| T-14 | Desempenho | Metas da seção 5.6 | Sintéticos grandes (1 GB) | Dentro da meta; regressão acima de 15% falha o CI |
| T-15 | Diferencial | Comparar contagens e valores com um leitor alternativo existente em amostra pequena | Arquivos reais anonimizados | Divergências explicadas |
| T-16 | Multi-plataforma | Linux, macOS e Windows, terminadores de linha diferentes | Sintéticos | Mesma saída |

### 10.2 Gerador de dados sintéticos (fiscal-synth)

- Modelo: empresa, participantes, itens (com NCM), documentos de entrada e saída com itens e impostos coerentes, apurações coerentes com os documentos.
- Saídas consistentes entre si: os mesmos documentos geram os XMLs (usando a nfelib) e o SPED correspondente, com chaves de acesso de DV válido.
- Semente fixa para reprodutibilidade; parâmetros de volume.
- **Injetor de falhas** com manifesto: remover linha, alterar valor, duplicar documento, truncar arquivo, trocar codificação, reordenar blocos, quebrar chave, deixar documento só no XML ou só no SPED. O manifesto lista o que foi injetado, e o teste T-07 mede quanto o validador encontrou.
- Os dados sintéticos são publicáveis, permitindo que terceiros reproduzam os testes sem dados reais.

### 10.3 Dados reais

Anonimização determinística: hash com máscara de CNPJ e CPF preservando o dígito verificador, nomes substituídos por identificadores e valores mantidos ou perturbados por fator fixo. Dados reais ficam fora do repositório público; apenas versões anonimizadas entram nos golden files, com autorização escrita do titular.

## 11. Repositório, CI e entrega

- Monorepo com uv workspaces; um pacote por responsabilidade (seção 3.1).
- CI: ruff, pyright, testes em matriz de sistemas e versões do Python, cobertura, benchmarks com comparação ao baseline, verificação do snapshot de specs, build da documentação.
- Release: versionamento semântico por pacote; versão de schema de dados separada e documentada; changelog automatizado; publicação no PyPI com trusted publishing; SBOM e verificação de dependências.
- Documentação: referência gerada da spec, guia de início rápido, guia de modelo de dados, runbook de nova vigência, guia de contribuição.
- Licença: permissiva para as bibliotecas de núcleo (decisão registrada em ADR).

## 12. Backlog por épicos

Estimativas em dias de trabalho de um(a) engenheiro(a) sênior, faixas para planejamento.

| Épico | Tarefas principais | Estimativa | Depende de | Aceite |
| --- | --- | --- | --- | --- |
| E0. Descoberta | Amostras reais, leiautes vigentes, revisão de bibliotecas existentes, ADRs | 5 a 8 | Nada | ADRs aprovados; vigências-alvo definidas |
| E1. Fundação | Monorepo, CI, fiscal-synth básico, fiscal-store, controle de arquivos | 8 a 12 | E0 | Pipeline vazio ponta a ponta no CI |
| E2. DF-e | dfe-tabular para NF-e/NFC-e e CT-e, validação de chave, testes T-12 | 8 a 12 | E1 | 100 mil NF-e idempotentes |
| E3. Spec | Extrator dos manuais, formato YAML, ferramenta de diff, specs da primeira vigência | 8 a 12 | E0 | Specs revisadas pelo contador consultor |
| E4. Leitor | Gerador de código, leitor streaming, hierarquia, quarentena, achados estruturais | 12 a 18 | E1, E3 | T-05, T-06, T-08, T-09 passando |
| E5. Validações | Campo, referencial, chave, aritmética | 6 a 10 | E4 | T-07 com recall definido |
| E6. Silver | Mapeamentos declarativos, dimensões e documentos, retificações, catálogo DuckDB | 10 a 15 | E4, E2 | T-10, T-11, T-13 |
| E7. Segunda vigência e segundo módulo | Nova vigência (valida o runbook), segundo módulo SPED | 8 a 12 | E6 | Runbook executado sem código manual de registro |
| E8. Desempenho | Benchmarks, profiling, otimização (Polars ou Rust se necessário) | 5 a 10 | E4 | Metas da seção 5.6 |
| E9. Entrega | Documentação, CLI, release, exemplos | 5 a 8 | Todos | Definição de pronto cumprida |

Total: aproximadamente 75 a 120 dias de trabalho de um engenheiro sênior, o que corresponde a 4 a 6 meses com uma pessoa e 2,5 a 4 meses com duas. São faixas amplas porque dependem de acesso a dados reais e da complexidade dos leiautes encontrados.

## 13. Riscos específicos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Extração automática dos manuais produz spec incorreta | Alto | Revisão humana obrigatória, snapshot de spec, teste diferencial, contador consultor |
| Condições de obrigatoriedade (OC) difíceis de codificar | Médio | Expressões avaliáveis só quando objetivas; demais viram aviso |
| Arquivos reais fora do padrão (campos extras, codificação mista) | Médio | Modo tolerante com quarentena; fuzz e golden com casos reais |
| Desempenho em Python insuficiente | Médio | Benchmark cedo (E4); caminho de escape para Polars ou Rust |
| Mudança de leiaute durante o desenvolvimento | Médio | Spec por vigência; runbook; acompanhamento de notas técnicas |
| Acesso a dados reais atrasa | Alto | Gerador sintético desde E1; parceria com contadores na Fase 0 |
| Leitor existente já resolve parte do problema | Médio | E0 inclui teste diferencial com os leitores encontrados; reaproveitar ou contribuir se fizer sentido |

## 14. Pré-requisitos e perguntas em aberto

Resolver na Fase 0, antes de iniciar o E1:

1. Quais vigências de leiaute são alvo (as mais recentes e pelo menos uma anterior, conforme os arquivos reais disponíveis).
2. Qual módulo SPED primeiro: EFD Contribuições (recomendado, por causa da auditoria de PIS/COFINS) ou EFD ICMS/IPI.
3. Quais amostras reais (anonimizadas) estarão disponíveis, de quantas empresas e em quais perfis (varejo, indústria, serviços).
4. Contador consultor disponível para validar a spec e as fórmulas aritméticas.
5. Licença, nome do projeto e organização do repositório.
6. Tratamento dos campos de IBS e CBS: confirmar o estado do leiaute vigente da NF-e na data de início.
7. Decisão sobre o escopo de DF-e: apenas NF-e/NFC-e e CT-e na v1, ou incluir MDF-e (a nfelib já cobre).

## 15. Primeiros 10 dias úteis

1. Dias 1 e 2: levantar leiautes vigentes, baixar manuais, coletar amostras, testar diferencialmente os leitores existentes em uma amostra.
2. Dias 3 e 4: esqueleto do monorepo, CI, estrutura do store e do catálogo DuckDB.
3. Dias 5 a 7: fiscal-synth mínimo (empresa, participantes, itens, 10 documentos) gerando XML e SPED coerentes.
4. Dias 8 a 10: dfe-tabular para NF-e (cabeçalho e itens) com teste T-12 e validação de chave; primeiro Parquet consultável no DuckDB.
