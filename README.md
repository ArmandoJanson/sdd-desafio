# Desafio Prático — Spec Driven Development

Aula bônus de SDD, fechando a trilha:

`AI Fluency` → `Claude 101` → `Claude Code 101` → `Building with the Claude API` → `Claude Code in Action` → `Módulo SDD` → **Desafio**

**Individual · 2 dias · Claude Code**

---

## Comece por aqui

1. **[`DESAFIO.md`](DESAFIO.md)** — o enunciado. Leia inteiro antes de escrever qualquer coisa.
2. **[`RUBRICA.md`](RUBRICA.md)** — como você é avaliado. É pública de propósito; leia antes de começar.
3. **[`exemplos/despesas-exemplo.json`](exemplos/despesas-exemplo.json)** — a entrada de referência. Não é decoração: percorra item por item antes de escrever a spec.
4. **[`FAQ.md`](FAQ.md)** — travou? Comece por aqui. **O instrutor está fora durante o desafio**, então o FAQ é o canal de suporte.

---

## Como executar a aplicação

**Reembolsos — Motor de Avaliação** é um programa de computador (janela desktop) que lê arquivos JSON de despesas, aplica a política de reembolso, valida cada competência e gera um resultado de auditoria com a justificativa de cada despesa.

### O que você precisa

- **Windows 10 ou 11.** Foi desenvolvido e testado no Windows; outros sistemas não foram testados.
- **Python 3.10 ou mais novo** (testado com 3.12). Baixe em [python.org/downloads](https://www.python.org/downloads/) e, na primeira tela do instalador, **marque "Add python.exe to PATH"**.
- **Microsoft Edge WebView2.** Já vem no Windows 11 e na maioria dos Windows 10 atualizados; se faltar, instale o "WebView2 Runtime" no site da Microsoft.

### Instalar (uma vez só)

Abra o terminal **dentro da pasta do projeto** (no Explorador de Arquivos, clique na barra de endereço, digite `cmd` e tecle Enter) e rode:

```bash
pip install -r requirements.txt
```

### Abrir o programa

```bash
python src/app.py
```

A janela abre em alguns segundos. Deixe o terminal aberto enquanto usa o programa; para sair, feche a janela.

### Como usar

1. Clique em **Avaliar Reembolso** e escolha um arquivo `.json` de despesas. Para testar, use [`exemplos/despesas-exemplo.json`](exemplos/despesas-exemplo.json).
2. A competência aparece na lista, agrupada por colaborador, com a situação **Pendente de validação**. Enviar de novo o mesmo colaborador e competência soma só as despesas novas, sem duplicar.
3. Clique em **Validar**. O programa pede confirmação, porque uma competência validada **não pode mais ser alterada nem validada de novo**.
4. Clique em **Resultado** para ver, despesa por despesa, o status, o valor reembolsado e a justificativa, com o total no topo.
5. No painel de resultado, **Baixar resultado** salva uma cópia do JSON da auditoria no local que você escolher (não vale a pasta `colaborador`, de uso interno).

Regras que aparecem como mensagem na tela:

- **Competência futura não pode ser carregada** (RN-012): só vale o mês atual do relógio do computador e meses anteriores.
- **Competência fora do formato `AAAA-MM`** recusa o arquivo (RN-009).
- **Datas que não existem** (como 31/09), campos ausentes e JSON mal formado geram uma mensagem em português dizendo qual despesa e qual campo corrigir.
- **Mesmo id de despesa com conteúdo diferente** interrompe o envio e pede o ajuste.

### Onde ficam os dados

Na pasta `colaborador/`, dentro do projeto, um arquivo por competência:

| Arquivo | O que é |
|---|---|
| `{id}_{centro_custo}_{competencia}.json` | Competência carregada, ainda não validada |
| `{id}_{centro_custo}_{competencia}_resultado.json` | Auditoria gerada na validação |
| `{id}_{centro_custo}_{competencia}_validado.json` | Competência já validada |

### Como testar

```bash
pytest                                   # toda a suíte
pytest --cov=src --cov-branch            # com cobertura (src/ está em 100%)
black --check src tests                  # formatação
isort --check-only src tests             # ordem dos imports
flake8 src tests                         # estilo
```

Os testes não abrem janela e usam pastas temporárias; nunca tocam em `colaborador/`.

### O que foi construído

```
src/
├── app.py            # ponto de entrada (janela PyWebView)
├── config.py         # caminhos e constantes
├── core/             # motor puro das regras RN-001 a RN-012 (sem I/O)
├── storage/          # leitura/escrita dos arquivos, consolidação e validação
└── ui/               # controller da ponte JS e frontend (HTML, CSS e JS puros)
tests/                # testes unitários, de integração e de rastreabilidade
specs/001-motor-reembolso/
├── spec.md           # o QUÊ: regras de negócio, ambiguidades e decisões
├── plan.md           # o COMO: arquitetura e decisões técnicas
├── tasks.md          # tarefas, critérios de aceite e matriz de rastreabilidade
└── DECISIONS.md      # log de mudanças da spec
```

### Se algo der errado

- **"python não é reconhecido como comando":** o Python foi instalado sem "Add to PATH". Reinstale marcando essa opção e abra um terminal novo.
- **Janela em branco ou erro de componente:** instale o Microsoft Edge WebView2 Runtime.
- **"Competência futura" ao carregar o exemplo:** o exemplo é de 2026-07; o relógio do computador precisa estar em julho de 2026 ou depois.

---

## Como participar

**1. Faça um fork deste repositório.** Ele precisa ser público, ou você não conseguirá compartilhar depois.

**2. Clone o seu fork e prepare a estrutura de trabalho:**

```bash
git clone https://github.com/<seu-usuario>/sdd-desafio.git
cd sdd-desafio
cp template/CLAUDE.md .
cp -r template/specs .
cp -r template/docs .
git add -A && git commit -m "chore: estrutura inicial a partir do template"
```

<details>
<summary>PowerShell</summary>

```powershell
git clone https://github.com/<seu-usuario>/sdd-desafio.git
cd sdd-desafio
Copy-Item template\CLAUDE.md .
Copy-Item template\specs . -Recurse
Copy-Item template\docs . -Recurse
git add -A; git commit -m "chore: estrutura inicial a partir do template"
```
</details>

Os arquivos em `template/` são esqueletos com as perguntas que cada documento precisa responder. Deixe a pasta `template/` onde está — ela serve de referência.

**3. Trabalhe no seu fork**, seguindo as três regras do jogo descritas no [`DESAFIO.md`](DESAFIO.md):

- Nenhum commit sem task
- Explicação no chat que não está na spec é bug de spec
- Interações exportadas (`/export`) e commitadas em `docs/sessions/`

**4. No Dia 2, às 10h**, você recebe uma mudança de requisito pelo canal da turma. Ela é obrigatória e vale 20 pontos. Chegue nesse momento com o sistema base funcionando e testado.

> Durante os dois dias o instrutor está de férias e não responde mensagens. Dúvida de processo: [`FAQ.md`](FAQ.md). Dúvida sobre o que a política do RH significa não tem resposta — decidir isso é o exercício.

**5. Entregue** enviando o link do seu fork no formulário. Prazo: **Dia 2, 18h**.

---

## O que o seu fork precisa conter ao final

```
seu-fork/
├── CLAUDE.md                     # convenções do projeto para o agente
├── README.md                     # como rodar e como testar o SEU projeto
├── specs/
│   └── 001-motor-reembolso/
│       ├── spec.md               # o QUÊ e o PORQUÊ
│       ├── plan.md               # o COMO
│       ├── tasks.md              # T-001..T-0NN, com critério de aceite
│       └── DECISIONS.md          # log de mudanças de spec
├── src/
├── tests/
└── docs/
    ├── sessions/                 # exports das suas conversas com o Claude
    └── RELATORIO.md              # o relatório final
```

Sobre o `README.md`: substitua este arquivo pelo README do **seu** projeto — como rodar, como testar, o que você construiu. Um README que não permite rodar o projeto custa pontos.

---

## Antes de começar, confirme que o `/export` funciona

Abra o Claude Code, troque duas mensagens, rode `/export` e confirme que o arquivo foi gerado.

Faça isso **agora**, não no Dia 2. Sem `docs/sessions/`, o critério de relatório vale zero — e já aconteceu de gente que fez tudo certo descobrir no último dia que não tinha registro nenhum do trabalho.

Exporte ao final de **cada** sessão, nomeando `docs/sessions/01-descricao-curta.md`, `02-...`, e assim por diante.

---

## O resumo em um parágrafo

Você vai receber uma política de reembolso escrita por um RH, com a redação ruim que uma política de RH real tem. Ela é ambígua em vários pontos, e você não tem acesso a ninguém para tirar dúvida. O trabalho não é implementar — é **especificar**: encontrar cada ambiguidade, decidir explicitamente, justificar e registrar. O produto funcionando vale **10 dos 100 pontos**. Os outros 90 estão na spec, na rastreabilidade `spec → tasks → commits → testes`, na resposta à mudança de requisito do Dia 2 e no relatório.

Isso é deliberado. Um projeto que roda perfeitamente com spec fraca tira nota baixa; um projeto com bug conhecido, spec impecável e trilha limpa tira nota alta.
