# Relatório — Desafio SDD

**Aluno:** `Armando Alcantara` · **Repositório:** `https://github.com/ArmandoJanson/sdd-desafio` · **Data:** `19/10/2026`

> Isto não é redação. São **evidências**. Toda afirmação deve vir acompanhada de
> arquivo, hash de commit ou trecho de sessão exportada. Um parágrafo bonito sem
> evidência vale menos que uma frase curta com um hash.
>
> Vale 20 dos 100 pontos, e é a seção que mais separa notas.

---

## Delegação

*O que você fez, o que o Claude fez, e por que dividiu assim.*

**A divisão:**

| Atividade | Quem | Por quê |
|---|---|---|
| Identificar ambiguidades | **Aluno** as 9 de partida (`spec.md` §6, AMB-001 a AMB-009; commits `bc54d1c` e `1deafc6`, 18/10). **Claude** as que só aparecem ao executar a regra: 23 itens em `spec.md` §10 (12 confirmados, 11 provisórios), por exemplo duração da viagem, teto esgotado, id mais recente. | O aluno leu a política e o JSON de exemplo antes de codar. O Claude achou os buracos na hora de escrever a função que aplica a regra (`rules.py`). |
| Decidir as ambiguidades | **Aluno** | 15 perguntas de múltipla escolha (4+4+4+1+2) mais respostas livres. O aluno aceitou a opção recomendada em 11 e **divergiu em 4**: RN-009 "recusar o arquivo sem gerar resultado", status `rejeitado - duplicidade`, mesmo id com conteúdo diferente "interrompe e pede ajuste", RN-012 "só competência futura, só no carregamento". Registradas como "Confirmada" na §10 e em `DECISIONS.md` (D-001 a D-004); commits `92b44be`, `fa94dc9`, `8b6d5ab`, `deb4e9d`, `1db4bf8`. |
| Escrever a spec | **Aluno** regras e cenários (RN-001 a RN-011). **Claude** a §10, a RN-012, o campo `justificativa`, a reescrita da RN-009 e o `DECISIONS.md`. | O Claude só escreve na spec o que o aluno decidiu; o `CLAUDE.md` manda a regra de negócio morar na spec, não no chat. Em cada mudança o commit `docs(spec)` vem antes do `feat`. |
| Desenhar a arquitetura | **Aluno** a stack e as camadas (`CLAUDE.md`, `plan.md` já existiam no início da sessão: PyWebView, Pydantic, `Decimal`, `core/storage/ui`). **Claude** o detalhamento: `service.py`, controller, escrita atômica, retentativa de renomeação. | Decisão estrutural é do aluno; o detalhe entrou no plano antes do código (`c23d648`, `ecff840`, `588d4bc`). |
| Implementar | **Claude** | O aluno dava a fase e o critério (testes obrigatórios, 100% de cobertura) e aprovava os commits. |
| Escrever testes | **Claude** (599 testes), por exigência do aluno | O aluno impôs `pytest`, `tmp_path` e cobertura de 100%. Ver riscos em "Diligência". |
| Absorver o envelope |  O envelope do Dia 2 não aparece nesta sessão. |

**Onde deleguei e me arrependi:**
 Delegar ao Claude o texto das mensagens de erro da tela sem fixar nada na spec. Ele repassou o erro bruto do Pydantic: `src/storage/repository.py:228` em `1339d84` (`f"schema inválido em {caminho}: {erro}"`). Só o uso real da tela mostrou o problema; a correção virou a T-025 (`7062512`).

**Onde não deleguei e deveria ter delegado:**
Uma revisão da spec antes de implementar. O Claude achou, já durante o código, defeitos que uma passada de revisão teria pegado:
- o exemplo de saída da §4 era JSON inválido e contradizia a própria tabela (`spec.md` §10, "Formato do exemplo de saída");
- o cenário 03 da RN-003 cita um "valor do reembolsado solicitado" que não existe na entrada (§10, "Valor solicitado");
- o `plan.md` §5 tinha campos antigos (`estabelecimento`, `id_despesa`) que divergiam da spec (corrigido em `97606c2`);
- a matriz do `tasks.md` ligava a AMB-005 à RN-009 (corrigido em `075cb1a`).

**Usei subagentes / skills / MCP / hooks?** Não. Nesta sessão não usei subagentes, skills, servidores MCP nem hooks (o `.claude/settings.json` não define hooks). A única ferramenta de processo foi a pergunta estruturada (`AskUserQuestion`) para colher as decisões. Não usei subagentes porque as fases eram sequenciais e dependentes (cada uma consome o código da anterior); em paralelo o custo de repassar contexto superaria o ganho.

---

## Descrição

*Como você transformou requisito ambíguo em requisito verificável.*

Requisito escolhido: **RN-005 — "Colaborador em viagem tem limites ampliados em 50%"** (política do RH, item 6).

**Versão 1 (minha primeira escrita):** `spec.md` em `bc54d1c` / `1deafc6`, RN-005, "Regra":
> ```
> O funcionário estará em viagem quando o valor informado no campo categoria for hospedagem
> e no fornecedor contiver uma das palavras a seguir: hotel, airbnb, pousada, hostel ou camping.
> Será necessário verificar a quantidade de diárias/noites informadas na descrição. Caso não
> seja informado nenhum valor numérico, deverá ser considerada uma diária.
> Caso seja informada no campo descricao mais de uma diária/noite, para noites somar mais uma
> dia, os limites tratados nas regras anteriores para as desepesas deverão ser ampliados em 50%.
> ```

**Versão final:** `spec.md` §10, "Duração da viagem (RN-005)" (linha 861), mais os cenários da própria RN-005:
> ```
> A viagem começa na data da despesa de hospedagem (com fornecedor reconhecido, que passou por
> RN-010, RN-008, RN-007 e RN-006) e dura N dias quando a descrição fala em diárias, ou N + 1
> dias quando fala em noites (cenário 04). Sem número, dura 1 dia. A viagem existe mesmo que a
> hospedagem seja depois rejeitada por falta de nota fiscal. Nos dias de viagem, os tetos
> diários de alimentação e de transporte urbano valem 50% a mais; viagens que se sobrepõem não
> ampliam mais de uma vez.
> ```

**O que estava ambíguo:** a regra dizia *que* os limites sobem 50%, mas não *em quais datas*. Faltava:
1. a partir de que dia a viagem vale e quantos dias dura;
2. o "+1 dia" valer só para "noites" e não para "diárias";
3. se a viagem continua valendo quando a hospedagem é rejeitada;
4. o que fazer com viagens sobrepostas;
5. se a hospedagem também é ampliada.

**Como percebi:** ao escrever `dias_em_viagem` (`src/core/rules.py`) o Claude precisou escolher a janela de datas. No JSON de exemplo, `d-010` ("Hotel Rio - 2 diarias", 14/07) e `d-011` ("Cafe da manha hotel", 15/07) não permitem dizer se 15/07 é dia de viagem, e `d-013` ("Airbnb 3 noites") não tem nota fiscal. A dúvida foi levada ao aluno como pergunta ("Duração da viagem") e ele escolheu "diárias = N dias, noites = N+1".

**Commit da mudança:** `92b44be` (decisão registrada) e `5069168` (redação final em linguagem de negócio).

---

## Discernimento

*Onde o Claude errou e você pegou.*

> **Sem um caso concreto e verificável, esta seção vale zero.** Não existe projeto
> de dois dias em que o modelo acertou tudo. A ausência do caso não prova que o
> modelo foi perfeito — prova que ninguém estava conferindo.

### Caso 1

**O que ele propôs:** que o erro de leitura de arquivo exibido na tela fosse o texto bruto do Pydantic: `raise ArquivoCorrompidoError(f"schema inválido em {caminho}: {erro}")` (`src/storage/repository.py:228`, commit `1339d84`). E escreveu testes que **exigiam** essa mensagem: `tests/test_repository.py:330`, `tests/test_service.py:327` e `:692`, `tests/test_controller.py:336` (commits `b4b4689`, `32503ae`, `131045e`).

**Por que estava errado:** a tela mostrava `2 validation errors for SolicitacaoReembolso ... [type=value_error, input_value='2026-11-31', input_type=str] For further information visit https://errors.pydantic.dev/...`, com o caminho completo do disco e sem dizer qual despesa tinha o problema. Era jargão técnico, em inglês, para quem não programa. A spec nunca definiu texto de erro, então nenhuma regra apontava o defeito.

**Como eu detectei:** Rodei a aplicação com um arquivo meu (`exemplos/despesas-armando-09.json`, com as datas inexistentes `2026-11-31` e `2026-09-31`), vi a caixa vermelha e mandei o print. Nenhum teste detectou: eram 522 testes passando, com 100% de cobertura, porque os testes validavam justamente a mensagem ruim.

**O que eu fiz:** pedi mensagem amigável. O resultado foi a **T-025** (`7062512`): `descrever_erros_de_validacao` (`src/storage/repository.py:255`) traduz cada erro para "Despesa nº 13 (id d-13), campo 'data': a data '2026-09-31' não existe no calendário.", limita a 5 problemas e esconde o jargão; os testes `test_dados_invalidos_em_portugues` e `TestMensagensAmigaveis` agora **falham se o jargão voltar** (`validation error`, `type=`, `pydantic`, `https://`). A spec ganhou o critério correspondente (§9, commit `deb4e9d`).

**Onde está a evidência:** `docs/sessions/01-desenvolvimento-completo.md`, mensagem do usuário de 19/10/2026 22:40 (linha 5974): "Ao carregar um arquivo para validação foi apresentado o erro da imagem em anexo". O print em si foi omitido do export.

### Caso 2 *(opcional)*

**Padrão que eu notei:** o Claude fecha o trabalho contra os documentos que o prompt lista e contra os próprios testes; as lacunas apareceram quando algo **de fora** foi consultado:
- **Uso real da tela:** achou a mensagem bruta (Caso 1) e a falta do botão de baixar o resultado, que o aluno apontou (T-026, `1db4bf8` a `dbc58d6`).
- **`DESAFIO.md`:** o enunciado fixa uma CLI (`<comando> calcular --input ... --output ...`, linhas 25 a 31) que o projeto não tem. Nem o Claude nem o plano a tinham notado; só foi vista quando o aluno perguntou sobre o download, e o aluno decidiu **não** fazer a CLI.
- **Comando de lint com `-q`:** o `isort -q` pulou `tests/test_engine.py` (dígitos de largura total no código, que o cp1252 não codifica) em três fases (2 a 4), e o `OK` era falso. Só apareceu na regressão final; corrigido em `0c4640f`.
- **Numeração das tasks:** os prompts do aluno usavam T-NNN diferentes dos do `tasks.md` em todas as fases, e o Claude teve que mapear e avisar a cada vez.

---

## Diligência

*O que você verificou antes de aceitar.*

**Meu procedimento de verificação:**
- **Antes de cada commit:** `pytest --cov=src --cov-branch -W error` (src/ em 100%), `black --check`, `isort --check-only` e `flake8`.
- **Testes no teste:** a matriz de rastreabilidade tem teste próprio (`tests/test_rastreabilidade.py`), e o Claude simulou 5 erros na matriz (teste inexistente, AMB removida, regra errada para a AMB, task inexistente, AMB faltando) para ver se o teste os pegava; os 5 foram detectados.
- **Janela real:** duas verificações com o PyWebView de verdade (lista, painel de resultado e botão de baixar), lendo a tela via JavaScript.
- **Aluno:** Executou a aplicação e carregou arquivos próprios (`colaborador/c-0413_*`, competências 2026-09, 2026-10 e 2026-11) e encontrou dois defeitos de uso (mensagem bruta; ausência de download).

**Li o diff inteiro em que porcentagem das entregas?**  Registro objetivo da sessão: o aluno não pediu para ver código ou diff; as aprovações dos commits ("Sim") foram dadas sobre resumos que o Claude escreveu. Só você sabe se leu os arquivos no editor.

**O que aceitei sem verificar direito, e o que me custou:**
- A **mensagem de erro** (Caso 1): custou um ciclo de correção, a T-025 e a revisão de 4 asserções de teste.
- **Cobertura de 100% como prova de qualidade:** passou a dar conforto falso, já que o código com defeito também estava coberto.
- **`isort -q`** (Caso 2): três fases com um arquivo de teste fora da verificação.
- **Mapeamento de tasks:** as divergências de numeração só foram resolvidas porque o Claude as sinalizou; nenhuma foi detectada por mim antes.

**Testes: quem escreveu, e como você sabe que eles testam a coisa certa?**
Quem escreveu: **o Claude**, os 599, sob exigência do aluno. Como se sabe que testam a coisa certa:
1. Os cenários dos testes vêm dos cenários da spec **escrita pelo aluno** (RN-001 a RN-011, "Cenário NN"), e cada teste de regra leva `@pytest.mark.req("RN-NNN")`.
2. `test_rastreabilidade.py` falha se uma RN/AMB da spec não tem linha na matriz, se um teste citado não existe ou se uma task citada não está concluída. Na adição da RN-012 ele falhou na hora (2 falhas) enquanto faltava teste e linha de matriz.
3. **O limite:** quem escreve código e teste é o mesmo agente. O Caso 1 prova: o teste "passava" porque consagrava o defeito. Teste do mesmo agente confirma o que ele entendeu, não o que o aluno quis.

---

## O envelope

*A mudança de requisito do Dia 2.*


**Quantos arquivos toquei na mão:**  `<0>` (a preencher)
**Quanto tempo levou:**  `<não medi o Claude executou as mudanças autimaticamente>` (a preencher)
**Diff de absorção:** Não tenho essa informação

**Mudanças de requisito absorvidas durante o desenvolvimento** (pedidas pelo aluno ao usar a aplicação; medidas com `git diff --stat`):

| Mudança | Commits | Diff |
|---|---|---|
| Justificativa por item na saída (D-002, T-023) | `8b6d5ab`, `ecff840`, `55fe4b6`, `23a0d07` | 9 arquivos, +249/-42 |
| Competência futura não pode ser carregada + mensagens (RN-012, T-024/T-025, D-003) | `deb4e9d` a `809b588` | 15 arquivos, +576/-15 |
| Botão "Baixar resultado" (T-026, D-004) | `1db4bf8` a `dbc58d6` | 13 arquivos, +411/-4 |

**Absorveu de graça:**
- **RN-012:** o `engine.py` não mudou. Entrou como função pura (`rules.competencia_futura`) mais uma chamada em `service.consolidar_solicitacao`; o controller e a tela exibiram a mensagem sem alteração, porque o erro tipado já era capturado como `RepositorioError`.
- **Baixar resultado:** reaproveitou `service.obter_resultado`, a escrita atômica de `repository.salvar_json` e o padrão de diálogo injetável do `seletor_arquivo`.

**Resistiu:**
- **Justificativa:** mudou o contrato interno do motor (`_Avaliacao` de 2 para 3 itens em `engine.py`) e tornou o campo obrigatório em `ItemAuditoria`, o que quebrou os testes de modelo e repositório.
- **RN-012:** todos os testes com datas passaram a depender do dia em que rodam; exigiu um relógio injetável (`service.hoje`) e um `tests/conftest.py` que o fixa em 31/12/2026.
- **Baixar resultado:** criou um risco novo (sobrescrever um `_validado.json` pelo "Salvar como"), tratado com `DestinoInvalidoError`; o painel precisou de área de mensagem própria.

**Ordem em que fiz:** spec → tasks → código, em todas as três mudanças: o commit `docs(spec)` precede os `feat`/`test` (`deb4e9d` < `29c4c49`; `1db4bf8` < `6a7390a`). Atenção: os commits foram feitos em lotes ao fim de cada etapa, então o timestamp é o mesmo dentro do lote (22:50 e 23:03 em 19/10); a ordem real de trabalho está no transcript da sessão, não nas horas do `git log`.

**Se eu tivesse escrito a spec original sabendo desta mudança:**
 Teria definido já na §4 o campo `justificativa`; o idioma e o conteúdo das mensagens de erro; a regra de competência futura com o relógio do computador; e o download do resultado como parte do fluxo de validação.

**O que a spec me poupou, em concreto:**
Cada mudança entrou por um caminho fixo: regra e cenários na spec, uma task, um teste marcado e uma linha na matriz, e o `test_rastreabilidade.py` apontou o que faltava na hora. As 15 decisões já tomadas e registradas (§10 e `DECISIONS.md`) não precisaram ser rediscutidas quando a RN-012 e o download chegaram.

---

## Fechamento

**Para qual tamanho de projeto isto valeu a pena?**
Para um sistema com regras interdependentes, como este (12 regras, 26 tasks, 599 testes, 4 mudanças de requisito no meio do caminho): a matriz de rastreabilidade pegou um erro real (AMB-005 ligada à RN-009, `075cb1a`) e as mudanças foram absorvidas em poucos commits.

**Para qual não valeria?**
 Para um script de um arquivo ou um protótipo descartável: aqui a spec passa de 860 linhas e o log de decisões, as tasks e a matriz custam mais que o código.

**O que eu faria diferente:**
- Exportar as sessões desde a primeira. Hoje só há **uma** sessão registrada (19/10/2026 21:02 a 20/10/2026 09:23), exportada ao fim; a spec de 18/10 (`bc54d1c`, `1deafc6`) e a criação de `CLAUDE.md`, `plan.md` e `tasks.md` aconteceram antes e **não têm sessão exportada**.
- Revisar a spec antes de implementar (erros de redação, exemplo de saída inconsistente, cenário com dado inexistente).
- Definir na spec o texto das mensagens de erro, o relógio e os formatos.
- Rodar a aplicação de verdade já na primeira versão da tela (Fase 4), e não só no fim.

**A coisa mais desconfortável que aprendi sobre como eu trabalho com IA:**
Ponto de partida, a partir do que a sessão mostra: com 100% de cobertura e testes verdes eu aprovei etapas lendo resumos, e o defeito que mais me incomodou só apareceu quando eu mesmo usei a tela.
