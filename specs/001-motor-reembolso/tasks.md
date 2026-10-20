# Tasks — Motor de Cálculo e Sistema de Reembolso

> Cada task é pequena o bastante para virar **um commit**. Se você não consegue
> descrever o critério de aceite como "o teste X passa", a task está grande demais.
>
> Marque `[x]` conforme conclui — ao longo do caminho, não tudo no fim. O histórico
> de quando cada task foi marcada é lido na correção.

**Formato do commit:** `feat(T-003): <descrição>` · `test(T-003): <descrição>` · `docs(T-003): <descrição>`

---

## Fase 1 — Fundação

- [x] **T-001** — Estrutura inicial do projeto e suporte a testes com Pytest
  - **Atende:** Arquitetura Base
  - **Aceite:** Estrutura de diretórios (`src/core`, `src/storage`, `src/ui`, `tests`) criada e comando `pytest` executando com sucesso.
  - **Commit:**

- [x] **T-002** — Modelos de dados Pydantic para solicitações e itens de auditoria
  - **Atende:** DT-001, DT-002, RN-011
  - **Aceite:** `test_models.py` valida deserialização JSON de `SolicitacaoReembolso`, `Despesa`, `ResultadoAuditoria` e garante o uso de `Decimal` para campos financeiros.
  - **Commit:**

- [x] **T-003** — Repositório de I/O em `./colaborador/`
  - **Atende:** DT-001, Nomenclatura do Plan
  - **Aceite:** `test_repository.py` valida a leitura, escrita e padronização dos nomes de arquivo `{id}_{centro_custo}_{competencia}.json` no diretório `./colaborador/`.
  - **Commit:**

- [x] **T-004** — Setup básico e inicialização do PyWebView
  - **Atende:** Arquitetura UI / PyWebView
  - **Aceite:** `app.py` abre a janela desktop carregando a interface web sem erros de runtime (`test_app.py` cobre a configuração da janela; a abertura real foi conferida manualmente).
  - **Commit:**

---

## Fase 2 — Regras de Negócio e Motor de Avaliação

- [x] **T-005** — RN-009, RN-010 e RN-011: Validações básicas e formatação financeira
  - **Atende:** RN-009, RN-010, RN-011, AMB-005, AMB-008, AMB-009
  - **Aceite:** `test_engine.py::test_validacao_formato_e_valores` confirma que datas de vigência fora de `YYYY-MM` são rejeitadas, valores negativos/zerados retornam status `rejeitado` e valores decimais são ajustados com arredondamento matemático para 2 casas.
  - **Commit:**

- [x] **T-006** — RN-008: Validação de categorias permitidas e sensibilidade à grafia
  - **Atende:** RN-008, AMB-006, AMB-007
  - **Aceite:** `test_engine.py::test_categorias_permitidas` garante que apenas `"alimentacao"`, `"coworking"`, `"hospedagem"` e `"transporte_urbano"` prosseguem, e grafias incorretas ou acentuadas retornam `"rejeitado - categoria inválida"`.
  - **Commit:**

- [x] **T-007** — RN-006: Validação de data da despesa dentro do período de competência
  - **Atende:** RN-006, AMB-005
  - **Aceite:** `test_engine.py::test_vigencia_competencia` aprova despesas entre `inicio` e `fim` da competência (inclusive limites) e rejeita despesas fora desse intervalo.
  - **Commit:**

- [x] **T-008** — RN-005 e RN-003: Identificação de contexto de viagem, diárias e limite de hospedagem
  - **Atende:** RN-003, RN-005, AMB-003
  - **Aceite:** `test_engine.py::test_contexto_viagem_e_hospedagem` valida o parsing das palavras-chave no fornecedor (case-insensitive), extração do número de diárias (+1 noite) da descrição e o teto diário de R$ 250,00 para hospedagem.
  - **Commit:**

- [x] **T-009** — RN-001: Limite e cálculo de despesas com alimentação
  - **Atende:** RN-001, RN-005, AMB-001, AMB-003
  - **Aceite:** `test_engine.py::test_limite_alimentacao` valida limite padrão de R$ 60,00/dia e limite ampliado em viagem de R$ 90,00/dia, aplicando status `aprovado` ou `parcial`.
  - **Commit:**

- [x] **T-010** — RN-002: Limite e cálculo de despesas com transporte urbano
  - **Atende:** RN-002, RN-005, AMB-003
  - **Aceite:** `test_engine.py::test_limite_transporte` valida limite padrão de R$ 80,00/dia e limite ampliado em viagem de R$ 120,00/dia, aplicando status `aprovado` ou `parcial`.
  - **Commit:**

- [x] **T-011** — RN-004: Comprovação fiscal para despesas acima de R$ 100,00
  - **Atende:** RN-004, AMB-002
  - **Aceite:** `test_engine.py::test_obrigatoriedade_nota_fiscal` garante aprovação sem nota fiscal para valores $\le$ R$ 100,00 e rejeição para valores $> 100,00$ sem nota fiscal (`tem_nota_fiscal = false`).
  - **Commit:**

---

## Fase 3 — Casos de Borda e Validações Especiais

- [x] **T-012** — RN-007: Deduplicação de despesas com retenção do ID mais recente
  - **Atende:** RN-007, AMB-004
  - **Aceite:** `test_engine.py::test_tratar_duplicatas` verifica que despesas com dados exatamente iguais mantêm apenas a entrada de ID mais recente para a esteira e rejeitam a mais antiga.
  - **Commit:**

- [x] **T-013** — Consolidação e mesclagem de arquivos JSON no repositório
  - **Atende:** DT-002, Seção 4.1 do Plan
  - **Aceite:** `test_service.py::test_consolidacao_despesas` garante que novos envios para o mesmo colaborador/competência mesclam registros sem duplicar lançamentos.
  - **Commit:**

- [x] **T-014** — Resiliência no carregamento de JSONs corrompidos ou inválidos
  - **Atende:** Risco de Arquivos Corrompidos do Plan
  - **Aceite:** `test_service.py::test_json_corrompido_tratamento` valida a sinalização de erro graciosa sem crash na aplicação quando um JSON em `./colaborador/` está malformado.
  - **Commit:**

- [x] **T-022** — Serviço de validação: gera `_resultado.json` e renomeia para `_validado.json`
  - **Atende:** Seção 4.3 do Plan, DT-001
  - **Aceite:** `test_service.py::test_validacao_gera_resultado_e_renomeia` valida o ciclo carregar → validar: o `_resultado.json` é gerado com a auditoria do motor, o original é renomeado fisicamente para `_validado.json` e uma segunda validação é recusada.
  - **Commit:**

- [x] **T-023** — Justificativa por item na auditoria
  - **Atende:** Spec §4 (saída), Spec §9, D-002
  - **Aceite:** `test_engine.py::test_justificativa_por_item` confirma que cada despesa devolve uma justificativa não vazia citando a regra aplicada (RN-003, RN-004, RN-006, RN-007, RN-008, RN-010, RN-001/002).
  - **Commit:**

- [x] **T-024** — RN-012: competência futura não pode ser carregada
  - **Atende:** RN-012, D-003
  - **Aceite:** `test_service.py::test_competencia_futura_e_recusada` confirma que o carregamento recusa competência posterior ao mês do relógio, sem gravar nada, e aceita o mês atual e os anteriores; `test_controller.py::TestCompetenciaFutura` confirma a mensagem exibida.
  - **Commit:**

- [x] **T-025** — Mensagens de erro em português para dados inválidos
  - **Atende:** Spec §9 (critério de mensagens), Plan §8 (arquivos inválidos)
  - **Aceite:** `test_repository.py::test_dados_invalidos_em_portugues` confirma que uma data inexistente (ex.: 31/09) e outros erros de preenchimento geram mensagem em português com a despesa e o campo, sem termos técnicos do Pydantic.
  - **Commit:**

- [x] **T-021** — Orquestrador do motor (esteira da spec §8)
  - **Atende:** Spec §8 (ordem de aplicação), Spec §9 (critérios de aceite), RN-001 a RN-011
  - **Aceite:** `test_engine.py::test_esteira_completa` processa `exemplos/despesas-exemplo.json` e devolve um `ResultadoAuditoria` com o `status_item` e o `valor_reembolsado` esperados por despesa; o motor não faz I/O.
  - **Commit:**

---

## Fase 4 — Interface do Usuário e Integração

- [x] **T-015** — Controller API (Python Bridge para PyWebView)
  - **Atende:** Arquitetura Camada Visual
  - **Aceite:** `test_controller.py` valida, sem abrir a janela, os métodos expostos (`selecionar_arquivo`, `avaliar_reembolso`, `listar_colaboradores_competencias`, `validar_competencia`, `obter_resultado`), que respondem `{ok, ...}` e nunca levantam exceção por falha prevista.
  - **Commit:**

- [x] **T-016** — UI: Seleção, upload e exibição de competências do colaborador
  - **Atende:** Seção 4.2 do Plan
  - **Aceite:** Interface carrega o diretório `./colaborador/`, agrupa competências por colaborador e identifica visualmente as competências validadas (`_validado`), pendentes e com arquivo corrompido.
  - **Commit:**

- [x] **T-017** — UI: Fluxo de acionamento do botão Validar e desabilitação
  - **Atende:** Seção 4.3 do Plan
  - **Aceite:** Acionar "Validar" gera o arquivo `_resultado.json`, renomeia o original para `_validado.json` e desabilita permanentemente o botão "Validar" para aquela competência.
  - **Commit:**

- [x] **T-018** — UI: Modal/Visualização detalhada da auditoria
  - **Atende:** Seção 4.3 do Plan
  - **Aceite:** Botão "Resultado" exibe a lista de despesas auditadas, com valor reembolsado, status e justificativa de cada item, e um resumo (total reembolsado e contagem por status); a saída da spec não define um status geral da solicitação.
  - **Commit:**

- [x] **T-026** — UI: botão "Baixar resultado" no painel de resultado
  - **Atende:** Spec §9 (critério de download), Plan §4.3 item 3, D-004
  - **Aceite:** `test_service.py::test_exportar_resultado` confirma que a cópia gravada é idêntica à auditoria (duas casas decimais), recusa destino dentro da pasta interna e acrescenta `.json` se faltar; `test_controller.py::TestBaixarResultado` cobre o diálogo, o cancelamento e os erros; `test_app.py::TestFrontend` confirma que o botão vem antes de "Fechar".
  - **Commit:**

---

## Fase 5 — Envelope / Testes Finais e Rastreabilidade

- [x] **T-019** — Testes de integração E2E do fluxo de persistência, auditoria e renomeação
  - **Atende:** Estratégia de Testes do Plan
  - **Aceite:** `test_integration.py` executa o ciclo completo (carregar $\rightarrow$ consolidar $\rightarrow$ avaliar $\rightarrow$ validar $\rightarrow$ renomear) usando `tmp_path`.
  - **Commit:**

- [x] **T-020** — Matriz de Rastreabilidade e Documentação do Projeto
  - **Atende:** Critérios de Aceite Globais
  - **Aceite:** Tabela de cobertura preenchida e sincronizada entre `spec.md`, `plan.md` e `tasks.md`, verificada por `test_rastreabilidade.py::test_tabela_cobre_todas_as_regras_e_ambiguidades`.
  - **Commit:**

---

## Cobertura

> Esta matriz é verificada por `tests/test_rastreabilidade.py`: todo `RN-NNN` e
> `AMB-NNN` da spec precisa constar aqui, cada teste citado precisa existir e cada
> task citada precisa estar concluída. Os testes de regra também levam o marcador
> `@pytest.mark.req("RN-NNN")`.

### Regras da spec

| Regra da spec | Ambiguidades | Tasks | Testes |
|---|---|---|---|
| **RN-001** | AMB-001 | T-009, T-021 | `test_engine.py::test_limite_alimentacao`, `test_engine.py::TestRN001Alimentacao` |
| **RN-002** | — | T-010, T-021 | `test_engine.py::test_limite_transporte`, `test_engine.py::TestRN002Transporte` |
| **RN-003** | — | T-008, T-021 | `test_engine.py::test_contexto_viagem_e_hospedagem`, `test_engine.py::TestRN003Hospedagem` |
| **RN-004** | AMB-002 | T-011, T-021 | `test_engine.py::test_obrigatoriedade_nota_fiscal`, `test_engine.py::TestRN004NotaFiscal` |
| **RN-005** | AMB-003 | T-008, T-009, T-010 | `test_engine.py::test_contexto_viagem_e_hospedagem`, `test_engine.py::TestRN005Diarias`, `test_engine.py::TestRN005Ampliacao` |
| **RN-006** | AMB-005 | T-007 | `test_engine.py::test_vigencia_competencia`, `test_engine.py::TestRN006Periodo` |
| **RN-007** | AMB-004 | T-012, T-013 | `test_engine.py::test_tratar_duplicatas`, `test_engine.py::TestRN007Duplicatas`, `test_service.py::TestConflitoDeId` |
| **RN-008** | AMB-006, AMB-007 | T-006 | `test_engine.py::test_categorias_permitidas`, `test_engine.py::TestRN008Categorias` |
| **RN-009** | — | T-005, T-013 | `test_engine.py::test_validacao_formato_e_valores`, `test_engine.py::TestRN009Competencia`, `test_service.py::TestRecusas` |
| **RN-010** | AMB-008 | T-005 | `test_engine.py::test_validacao_formato_e_valores`, `test_engine.py::TestRN010Negativos` |
| **RN-012** | — | T-024 | `test_service.py::test_competencia_futura_e_recusada`, `test_service.py::TestRN012Carregamento`, `test_engine.py::TestRN012CompetenciaFutura`, `test_controller.py::TestCompetenciaFutura` |
| **RN-011** | AMB-009 | T-005, T-002 | `test_engine.py::test_validacao_formato_e_valores`, `test_engine.py::TestRN011Precisao`, `test_models.py::TestDinheiro` |

### Ambiguidades da spec

| Ambiguidade | Regra afetada | Task | Teste |
|---|---|---|---|
| **AMB-001** | RN-001 | T-009 | `test_engine.py::TestRN001Alimentacao` |
| **AMB-002** | RN-004 | T-011 | `test_engine.py::TestRN004NotaFiscal` |
| **AMB-003** | RN-005 | T-008 | `test_engine.py::TestRN005Ampliacao` |
| **AMB-004** | RN-007 | T-012 | `test_engine.py::TestRN007Duplicatas` |
| **AMB-005** | RN-006 | T-007 | `test_engine.py::TestRN006Periodo` |
| **AMB-006** | RN-008 | T-006 | `test_engine.py::TestRN008Categorias` |
| **AMB-007** | RN-008 | T-006 | `test_engine.py::test_categorias_permitidas` |
| **AMB-008** | RN-010 | T-005 | `test_engine.py::TestRN010Negativos` |
| **AMB-009** | RN-011 | T-005 | `test_engine.py::TestRN011Precisao` |

### Demais requisitos

| Requisito | Origem | Tasks | Testes |
|---|---|---|---|
| Estrutura do projeto e constantes | Arquitetura (plan §3) | T-001 | `test_config.py::test_estrutura_de_diretorios_do_projeto` |
| Modelos e valores `Decimal` | Spec §4, plan §5 | T-002 | `test_models.py::TestDinheiro`, `test_models.py::TestSchema` |
| Repositório e nomenclatura de arquivos | Plan §3.2, DT-001 | T-003 | `test_repository.py::TestNomeArquivo`, `test_repository.py::TestSalvar` |
| Esteira de avaliação | Spec §8 | T-021 | `test_engine.py::test_esteira_completa` |
| Justificativa por item na saída | Spec §4, D-002 | T-023 | `test_engine.py::test_justificativa_por_item` |
| Mensagens de erro em português | Spec §9, plan §8 | T-025 | `test_repository.py::test_dados_invalidos_em_portugues`, `test_controller.py::TestMensagensAmigaveis` |
| Recusa de competência inválida | RN-009, D-001 | T-005, T-013 | `test_service.py::TestRecusas` |
| Consolidação de despesas por id | DT-002, plan §4.1 | T-013 | `test_service.py::test_consolidacao_despesas` |
| Arquivos corrompidos ou incompletos | Plan §8 | T-014 | `test_service.py::test_json_corrompido_tratamento` |
| Validação, resultado e renomeação | Plan §4.3 | T-022 | `test_service.py::test_validacao_gera_resultado_e_renomeia` |
| API do controller | Plan §4.4 | T-015 | `test_controller.py::TestApiExposta`, `test_controller.py::TestValidarCompetencia` |
| Baixar o resultado | Spec §9, D-004 | T-026 | `test_service.py::test_exportar_resultado`, `test_controller.py::TestBaixarResultado` |
| Janela e frontend | Plan §4.2 e §4.3 | T-004, T-016, T-017, T-018 | `test_app.py::TestJanela`, `test_app.py::TestFrontend` |
| Ciclo completo de ponta a ponta | Plan §7 | T-019 | `test_integration.py::test_ciclo_completo_carregar_consolidar_validar_renomear` |
| Rastreabilidade | Critérios globais | T-020 | `test_rastreabilidade.py::test_tabela_cobre_todas_as_regras_e_ambiguidades` |
