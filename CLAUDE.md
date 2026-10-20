# CLAUDE.md

> Este arquivo é lido pelo Claude Code no início de toda sessão. É onde moram as
> convenções que você não quer repetir em todo prompt.

## O projeto

Sistema desktop local de gerenciamento, consolidação, validação e auditoria de solicitações de reembolso de colaboradores por meio de uma interface leve (PyWebView) e um motor de processamento em Python. Lê arquivos JSON e emite arquivos de auditoria e validação na pasta `./colaborador/`.

## Fonte da verdade

`spec.md` define **o que** o sistema faz (regras de negócio).
`plan.md` define **como** (stack, arquitetura e decisões técnicas).
`tasks.md` define **em que ordem** (tarefas e rastreabilidade).

Quando o código e a spec discordarem, a spec está certa e o código é o bug —
a menos que a spec esteja errada, e nesse caso corrigimos a spec primeiro e
registramos na seção de abertos/decisões.

**Antes de implementar qualquer coisa, leia a task correspondente em `tasks.md`.**
Se o que foi pedido não está coberto por nenhuma task, avise em vez de implementar.

## Regras de trabalho

- Toda regra de negócio vive na spec, não no chat e não em comentário de código.
- Se uma regra de negócio for explicada e não estiver na spec, **pare e informe** antes
  de escrever código. Isso é um bug de spec.
- Todo commit referencia uma task: `feat(T-003): <descrição>`.
  Testes: `test(T-003): <descrição>`.
  Mudanças de documentação: `docs(spec):`, `docs(plan):`, `docs(tasks):`.
  O `git log` é lido na correção e é a trilha de auditoria do projeto.
- Nenhuma regra de negócio entra sem teste unitário ou de integração correspondente.

## Stack e comandos

- Linguagem: Python 3.10+
- Framework GUI: PyWebView
- Parsing / Validação: Pydantic
- Aritmética Monetária: `decimal.Decimal`
- Rodar aplicação: `python src/app.py`
- Testes: `pytest`
- Lint / Format: `flake8` / `black` / `isort`

## Convenções de código

- **Valores monetários:** Representados obrigatoriamente utilizando `decimal.Decimal` para garantir precisão e evitar erros de ponto flutuante em somatórios e limites de reembolso.
- **Estrutura de diretórios:** 
  - `./colaborador/`: Armazenamento de arquivos JSON de reembolsos, validados (`_validado.json`) e resultados (`_resultado.json`).
  - `src/core/`: Motor puro de regras de negócio (isolado de I/O e GUI).
  - `src/storage/`: Camada de I/O, persistência e consolidação de duplicidades.
  - `src/ui/`: Frontend (HTML/CSS/JS) e controller PyWebView.
  - `tests/`: Testes unitários e de integração (`pytest`).

## Fora de escopo

- Autenticação ou autorização de usuários.
- Checagem de autenticidade de nota fiscal, CNPJ ou chave de acesso.
- Notificações automáticas ao colaborador.
- Pagamento efetivo do reembolso.
- Upload e OCR automatizado de comprovantes.