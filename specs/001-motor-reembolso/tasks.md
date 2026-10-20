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

- [ ] **T-004** — Setup básico e inicialização do PyWebView
  - **Atende:** Arquitetura UI / PyWebView
  - **Aceite:** `app.py` abre a janela desktop carregando a interface web sem erros de runtime.
  - **Commit:**

---

## Fase 2 — Regras de Negócio e Motor de Avaliação

- [ ] **T-005** — RN-009, RN-010 e RN-011: Validações básicas e formatação financeira
  - **Atende:** RN-009, RN-010, RN-011, AMB-005, AMB-008, AMB-009
  - **Aceite:** `test_engine.py::test_validacao_formato_e_valores` confirma que datas de vigência fora de `YYYY-MM` são rejeitadas, valores negativos/zerados retornam status `rejeitado` e valores decimais são ajustados com arredondamento matemático para 2 casas.
  - **Commit:**

- [ ] **T-006** — RN-008: Validação de categorias permitidas e sensibilidade à grafia
  - **Atende:** RN-008, AMB-006, AMB-007
  - **Aceite:** `test_engine.py::test_categorias_permitidas` garante que apenas `"alimentacao"`, `"coworking"`, `"hospedagem"` e `"transporte_urbano"` prosseguem, e grafias incorretas ou acentuadas retornam `"rejeitado - categoria inválida"`.
  - **Commit:**

- [ ] **T-007** — RN-006: Validação de data da despesa dentro do período de competência
  - **Atende:** RN-006, AMB-005
  - **Aceite:** `test_engine.py::test_vigencia_competencia` aprova despesas entre `inicio` e `fim` da competência (inclusive limites) e rejeita despesas fora desse intervalo.
  - **Commit:**

- [ ] **T-008** — RN-005 e RN-003: Identificação de contexto de viagem, diárias e limite de hospedagem
  - **Atende:** RN-003, RN-005, AMB-003
  - **Aceite:** `test_engine.py::test_contexto_viagem_e_hospedagem` valida o parsing das palavras-chave no fornecedor (case-insensitive), extração do número de diárias (+1 noite) da descrição e o teto diário de R$ 250,00 para hospedagem.
  - **Commit:**

- [ ] **T-009** — RN-001: Limite e cálculo de despesas com alimentação
  - **Atende:** RN-001, RN-005, AMB-001, AMB-003
  - **Aceite:** `test_engine.py::test_limite_alimentacao` valida limite padrão de R$ 60,00/dia e limite ampliado em viagem de R$ 90,00/dia, aplicando status `aprovado` ou `parcial`.
  - **Commit:**

- [ ] **T-010** — RN-002: Limite e cálculo de despesas com transporte urbano
  - **Atende:** RN-002, RN-005, AMB-003
  - **Aceite:** `test_engine.py::test_limite_transporte` valida limite padrão de R$ 80,00/dia e limite ampliado em viagem de R$ 120,00/dia, aplicando status `aprovado` ou `parcial`.
  - **Commit:**

- [ ] **T-011** — RN-004: Comprovação fiscal para despesas acima de R$ 100,00
  - **Atende:** RN-004, AMB-002
  - **Aceite:** `test_engine.py::test_obrigatoriedade_nota_fiscal` garante aprovação sem nota fiscal para valores $\le$ R$ 100,00 e rejeição para valores $> 100,00$ sem nota fiscal (`tem_nota_fiscal = false`).
  - **Commit:**

---

## Fase 3 — Casos de Borda e Validações Especiais

- [ ] **T-012** — RN-007: Deduplicação de despesas com retenção do ID mais recente
  - **Atende:** RN-007, AMB-004
  - **Aceite:** `test_engine.py::test_tratar_duplicatas` verifica que despesas com dados exatamente iguais mantêm apenas a entrada de ID mais recente para a esteira e rejeitam a mais antiga.
  - **Commit:**

- [ ] **T-013** — Consolidação e mesclagem de arquivos JSON no repositório
  - **Atende:** DT-002, Seção 4.1 do Plan
  - **Aceite:** `test_repository.py::test_consolidacao_despesas` garante que novos envios para o mesmo colaborador/competência mesclam registros sem duplicar lançamentos.
  - **Commit:**

- [ ] **T-014** — Resiliência no carregamento de JSONs corrompidos ou inválidos
  - **Atende:** Risco de Arquivos Corrompidos do Plan
  - **Aceite:** `test_repository.py::test_json_corrompido_tratamento` valida a sinalização de erro graciosa sem crash na aplicação quando um JSON em `./colaborador/` está malformado.
  - **Commit:**

---

## Fase 4 — Interface do Usuário e Integração

- [ ] **T-015** — Controller API (Python Bridge para PyWebView)
  - **Atende:** Arquitetura Camada Visual
  - **Aceite:** Métodos expostos no backend (`carregar_arquivo`, `listar_competencias`, `validar_competencia`, `obter_resultado`) operam de forma isolada e integrados ao frontend.
  - **Commit:**

- [ ] **T-016** — UI: Seleção, upload e exibição de competências do colaborador
  - **Atende:** Seção 4.2 do Plan
  - **Aceite:** Interface carrega o diretório `./colaborador/`, agrupa competências por colaborador e identifica visualmente com sufixo `_validado`.
  - **Commit:**

- [ ] **T-017** — UI: Fluxo de acionamento do botão Validar e desabilitação
  - **Atende:** Seção 4.3 do Plan
  - **Aceite:** Acionar "Validar" gera o arquivo `_resultado.json`, renomeia o original para `_validado.json` e desabilita permanentemente o botão "Validar" para aquela competência.
  - **Commit:**

- [ ] **T-018** — UI: Modal/Visualização detalhada da auditoria
  - **Atende:** Seção 4.3 do Plan
  - **Aceite:** Botão "Resultado" exibe a lista de despesas auditadas, valores aprovados, status individual de cada item e o status geral da solicitação.
  - **Commit:**

---

## Fase 5 — Envelope / Testes Finais e Rastreabilidade

- [ ] **T-019** — Testes de integração E2E do fluxo de persistência, auditoria e renomeação
  - **Atende:** Estratégia de Testes do Plan
  - **Aceite:** `test_integration.py` executa o ciclo completo (carregar $\rightarrow$ consolidar $\rightarrow$ avaliar $\rightarrow$ validar $\rightarrow$ renomear) usando `tmp_path`.
  - **Commit:**

- [ ] **T-020** — Matriz de Rastreabilidade e Documentação do Projeto
  - **Atende:** Critérios de Aceite Globais
  - **Aceite:** Tabela de cobertura preenchida e sincronizada entre `spec.md`, `plan_2.md` e `tasks.md`.
  - **Commit:**

---

## Cobertura

| Regra da spec | Ambiguidades | Task | Teste |
|---|---|---|---|
| **RN-001** | AMB-001, AMB-003 | T-009 | `test_engine.py::test_limite_alimentacao` |
| **RN-002** | AMB-003 | T-010 | `test_engine.py::test_limite_transporte` |
| **RN-003** | AMB-003 | T-008 | `test_engine.py::test_contexto_viagem_e_hospedagem` |
| **RN-004** | AMB-002 | T-011 | `test_engine.py::test_obrigatoriedade_nota_fiscal` |
| **RN-005** | AMB-003 | T-008, T-009, T-010 | `test_engine.py::test_contexto_viagem_e_hospedagem` |
| **RN-006** | AMB-005 | T-007 | `test_engine.py::test_vigencia_competencia` |
| **RN-007** | AMB-004 | T-012 | `test_engine.py::test_tratar_duplicatas` |
| **RN-008** | AMB-006, AMB-007 | T-006 | `test_engine.py::test_categorias_permitidas` |
| **RN-009** | AMB-005 | T-005 | `test_engine.py::test_validacao_formato_e_valores` |
| **RN-010** | AMB-008 | T-005 | `test_engine.py::test_validacao_formato_e_valores` |
| **RN-011** | AMB-009 | T-005 | `test_engine.py::test_validacao_formato_e_valores` |