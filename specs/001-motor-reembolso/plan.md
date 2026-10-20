# Plano Técnico — Sistema de Reembolso e Motor de Avaliação

**Versão:** 2.0 · **Baseado na spec:** 1.0 e Especificação Técnica Refinada

> Este documento estabelece a arquitetura, a stack, as decisões técnicas, a estrutura de arquivos e a estratégia de implementação do sistema desktop de gestão e avaliação de reembolsos.

---

## 1. Stack

| Escolha | O quê | Por quê | O que descartei e por quê |
|---|---|---|---|
| **Linguagem** | Python 3.10+ | Ecossistema maduro para manipulação de dados JSON, tipagem estática opcional e fácil integração com PyWebView. | Node.js / Electron (consumo de memória elevado para uma aplicação local simples). |
| **Interface / GUI** | PyWebView | Permite renderizar uma interface web moderna (HTML/CSS/JS) com backend Python leve, nativo e de fácil distribuição. | Tkinter / PyQt (complexidade de estilização visual e footprint maior). |
| **Testes** | `pytest` | Framework de testes padrão, simples, expansível por fixtures e ideal para garantir rastreabilidade das regras (`RN-NNN`). | `unittest` (sintaxe mais verbosa e menor suporte a parametrização). |
| **Parsing / Validação** | `pydantic` | Garante a validação estrita dos JSONs de entrada/saída, tipagem e conversão de schemas sem boilerplate. | Validação manual via `jsonschema` (código mais acoplado e propenso a erros). |
| **Aritmética Monetária** | `decimal.Decimal` | Evita erros de arredondamento inerentes ao ponto flutuante (`float`) em somatórios e limites orçamentários. | `float` (inviável para cálculos financeiros de auditoria). |

---

## 2. Arquitetura

O sistema adota uma arquitetura em camadas desvinculando a interface do usuário (PyWebView/Frontend), os serviços de I/O e persistência no sistema de arquivos, e o motor puro de regras de negócio.

```
[ Frontend (HTML/JS/CSS) ]
           │  (Bridge PyWebView / API REST local)
           ▼
[ Interface Controller (Python / PyWebView API) ]
           │
     ┌─────┴──────────────────────────────┐
     ▼                                    ▼
[ Gerenciador de Arquivos & I/O ]   [ Motor de Reembolso (Core) ]
     │                                    │
     ▼                                    ▼
[ Diretório ./colaborador/ ]        [ Regras de Negócio (spec.md) ]
```

### Fronteiras
- **Núcleo do Motor (`core/`):** Totalmente isolado de I/O ou biblioteca de GUI. Recebe estruturas de dados puras (modelos Pydantic/Decimal) e retorna a avaliação. Pode ser testado 100% de forma unitária sem criar arquivos em disco.
- **Camada de Persistência (`storage/`):** Responsável por ler e gravar na pasta `./colaborador/`, consolidar duplicidades e aplicar a renomeação para `_validado.json`.
- **Camada Visual (`ui/`):** Contém HTML/JS/CSS e o controller PyWebView que expõe os métodos expostos à interface.

---

## 3. Estrutura de Diretórios e Nomenclatura de Arquivos

### 3.1. Organização do Projeto

```text
/
├── colaborador/                          # Diretório de persistência dos arquivos JSON
├── src/
│   ├── core/                             # Motor de reembolso e regras de negócio
│   │   ├── rules.py                      # Regras de negócio (funções puras, RN-001..RN-011)
│   │   ├── engine.py                     # Orquestrador da esteira (spec §8)
│   │   └── models.py                     # Modelos Pydantic (Despesa, Colaborador, Resultado)
│   ├── storage/                          # Manipulação do sistema de arquivos
│   │   └── repository.py                 # Leitura, consolidação, salvamento e renomeação
│   ├── ui/                               # Frontend da aplicação
│   │   ├── static/                       # CSS, JavaScript e assets
│   │   └── index.html                    # Interface gráfica desktop
│   ├── app.py                            # Ponto de entrada PyWebView
│   └── config.py                         # Definição de caminhos e parâmetros globais
├── tests/                                # Testes unitários e de integração
│   ├── test_engine.py                    # Testes de regras de negócio
│   └── test_repository.py                # Testes de persistência e consolidação
├── spec.md                               # Especificação funcional das regras de negócio
└── plan.md                               # Plano técnico do projeto
```

### 3.2. Padrões de Nomenclatura (`./colaborador/`)

- **Arquivo de Reembolso Carregado/Consolidado:** `{id}_{centro_custo}_{competencia}.json`
- **Arquivo Validado:** `{id}_{centro_custo}_{competencia}_validado.json`
- **Arquivo de Resultado da Auditoria:** `{id}_{centro_custo}_{competencia}_resultado.json`

---

## 4. Fluxo de Dados e Regras de Manipulação de Arquivos

### 4.1. Carregamento e Consolidação
1. O usuário aciona "Avaliar Reembolso" e seleciona um arquivo JSON.
2. O sistema extrai os campos chave: `id`, `centro_custo` e `competencia`.
3. O sistema verifica a existência de `{id}_{centro_custo}_{competencia}.json` ou da versão `_validado.json` em `./colaborador/`:
   - **Caso Exista:** Lê o arquivo existente, compara a lista de despesas, elimina duplicidades (chave única: `id_despesa` ou fallback `data + valor + estabelecimento`), insere os novos registros e atualiza o arquivo.
   - **Caso Não Exista:** Salva o novo arquivo no formato padronizado `{id}_{centro_custo}_{competencia}.json`.

### 4.2. Listagem de Competências
1. Varre o diretório `./colaborador/` e filtra arquivos cujo prefixo antes do primeiro `_` seja igual ao `id` do colaborador.
2. Agrupa por competência e identifica visualmente na UI os arquivos contendo o sufixo `_validado`.

### 4.3. Processo de Validação
1. Ao acionar o botão "Validar" em uma determinada competência:
   - Executa o motor de reembolso sobre a lista de despesas.
   - Salva o arquivo de auditoria `{id}_{centro_custo}_{competencia}_resultado.json`.
   - Renomeia o arquivo original para `{id}_{centro_custo}_{competencia}_validado.json`.
   - Desabilita permanentemente o botão "Validar" para aquele registro na UI.
2. O botão "Resultado" exibe a auditoria completa gerada.

---

## 5. Modelo de Dados

### 5.1. Entrada (Despesa e Solicitação)

Espelha a entrada da spec (seção 4) e `exemplos/despesas-exemplo.json`.
Implementado em `src/core/models.py`.

```python
class Colaborador(BaseModel):
    id: str; nome: str; centro_custo: str          # não vazios

class Periodo(BaseModel):
    competencia: Optional[str]                     # formato validado pelo motor (RN-009)
    inicio: date; fim: date                        # YYYY-MM-DD

class Despesa(BaseModel):
    id: str
    data: date                                     # YYYY-MM-DD
    categoria: str                                 # validada pelo motor (RN-008)
    descricao: str
    fornecedor: str                                # normalizado para minúsculas
    valor: Decimal                                 # 2 casas, ROUND_HALF_UP (RN-011)
    tem_nota_fiscal: bool                          # booleano estrito

class SolicitacaoReembolso(BaseModel):
    colaborador: Colaborador
    periodo: Periodo
    despesas: List[Despesa]
```

O schema **não** barra valores negativos/zerados, categorias fora da política
nem competência malformada: o motor precisa recebê-los para rejeitá-los com o
status correto (RN-010, RN-008, RN-009).

### 5.2. Saída (Resultado da Auditoria)

Espelha a saída da spec (seção 4).

```python
class ItemAuditoria(BaseModel):
    id: str; data: date; descricao: str
    fornecedor: str                                # minúsculas
    status_item: str                               # "aprovado", "parcial", "rejeitado", ...
    valor_reembolsado: Decimal                     # 2 casas

class HistoricoCompetencia(BaseModel):
    competencia: str; centro_custo: str
    despesas: List[ItemAuditoria]

class ColaboradorResultado(BaseModel):
    id: str; centro_custo: str

class ResultadoAuditoria(BaseModel):
    colaborador: ColaboradorResultado
    historico_despesas: List[HistoricoCompetencia]
```

### 5.3. Serialização em disco

`Decimal` é gravado como número JSON com duas casas (`72.50`), nunca como
texto nem `float`, e lido de volta com `parse_float=Decimal`. A escrita é
atômica (arquivo temporário + `os.replace`).

---

## 6. Decisões Técnicas

### DT-001 — Persistência Baseada em Arquivos JSON Locais
- **Contexto:** Necessidade de gerenciar, consolidar e auditar solicitações localmente sem dependência de banco de dados externo.
- **Decisão:** Manter todos os registros na pasta `./colaborador/` utilizando arquivos JSON com sufixos explícitos para marcar o estado (`_validado.json` e `_resultado.json`).
- **Alternativa descartada:** SQLite local.
- **Consequência:** Simplifica a distribuição da aplicação, facilitando a inspeção manual, backups e portabilidade sem necessidade de migrações de banco.

### DT-002 — Tratamento de Duplicidades na Consolidação
- **Contexto:** Reenviar o mesmo arquivo ou arquivos sobrepostos da mesma competência não deve duplicar lançamentos.
- **Decisão:** Utilizar o campo `id_despesa` como chave primária de deduplicação. Caso ausente, utilizar a hash composta de `data + valor + estabelecimento`.
- **Alternativa descartada:** Sobrescrever integralmente o arquivo anterior sem mesclagem.
- **Consequência:** Permite reenvios incrementais de despesas sem perda de integridade dos dados já registrados.

---

## 7. Estratégia de Testes

- **Nível Unitário (`pytest`):**
  - Validação do motor de reembolso cobrindo 100% dos cenários de teste definidos na `spec.md`.
  - Testes de precisão decimal com `Decimal`.
- **Nível de Integração (`pytest` + `tmp_path`):**
  - Leitura, escrita e atualização de arquivos no diretório `./colaborador/`.
  - Testes das regras de consolidação e remoção de duplicidades.
  - Testes do fluxo de transição de estado: criação -> consolidação -> validação -> renomeação `_validado.json`.
- **Rastreabilidade:** Cada caso de teste no arquivo `tests/test_engine.py` deve ter um docstring explicitando o requisito associado (ex: `@pytest.mark.req("RN-001")`).

---

## 8. Riscos e Mitigações

| Risco | Probabilidade | O que faço se acontecer |
|---|---|---|
| Concorrência ou travamento de arquivo no SO durante renomeação | Baixa | Utilizar escritas atômicas e blocos de tratamento de exceção (`try/except OSError`) com retentativas curtas. |
| Arquivos JSON corrompidos ou com schema inválido no diretório `./colaborador/` | Média | Validar a estrutura via Pydantic antes do processamento. Em caso de falha, marcar o registro como "inválido/corrompido" na UI sem quebrar a aplicação. |
| Incompatividades do PyWebView em diferentes sistemas operacionais | Média | Utilizar o renderizador nativo padrão (`gui='qt'` ou `gui='edgehtml'`) com fallback gracioso e manter o frontend estritamente em HTML/CSS/JS genérico. |