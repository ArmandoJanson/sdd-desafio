# Log de Decisões e Mudanças de Spec

> Uma entrada **toda vez** que a spec mudar. Este arquivo é a prova de que a spec
> foi tratada como artefato vivo e não como cerimônia de abertura.
>
> Spec que não muda em dois dias é spec que ninguém consultou. Mudança não é
> demérito — mudança não registrada é.

Ordem cronológica inversa: a mais recente primeiro.

---

## D-004 — Baixar o resultado pela tela · `19/10/2026`

**Gatilho:** ao usar a aplicação, o responsável pelo produto notou que o painel de resultado não permite obter o arquivo, que só existia dentro da pasta interna do sistema.

**O que mudou na spec:** seção 9 (novo critério de aceite) e seção 10 (decisão sobre o botão "Baixar resultado"). A saída da seção 4 não mudou.

**Por quê:** quem usa a tela não sabe onde fica a pasta interna nem tem como levar o resultado para outro lugar.

**O que isso invalidou:** nada. O plan 4.3 só previa exibir o resultado; ganhou o item 3.

**Tasks afetadas:** nova T-026.

**Custo:** serviço, controller, ponto de entrada, tela, testes e documentação.

---

## D-003 — Competência futura não pode ser carregada · `19/10/2026`

**Gatilho:** ao usar a aplicação, o responsável pelo produto carregou arquivos de meses diferentes e pediu que o sistema não aceitasse competência fora do mês corrente; na conversa, a regra foi delimitada a competências **futuras**, só no carregamento.

**O que mudou na spec:** nova RN-012 (seção 5), item na ordem de aplicação (seção 8), dois critérios de aceite (seção 9) e a definição de "competência atual" (seção 10).

**Por quê:** impedir lançamentos para um período que ainda não começou. Competências passadas continuam válidas, pois reembolsos costumam ser lançados com atraso.

**O que isso invalidou:** nada que existia: os testes anteriores usam competências passadas, mas passaram a depender de um relógio fixo nos testes.

**Tasks afetadas:** nova T-024 (RN-012) e nova T-025 (mensagens de erro em português).

**Custo:** serviço, controller (mensagem), testes e documentação.

---

## D-002 — Justificativa por item na saída · `19/10/2026`

**Gatilho:** ao especificar a tela de Resultado, o responsável pediu a justificativa de cada item; a saída da seção 4 só tinha `status_item` e `valor_reembolsado`, e vários motivos de rejeição saíam todos como `rejeitado`.

**O que mudou na spec:** seção 4 (saída): novo campo `historico_despesas[].despesas[].justificativa` (string); seção 9: novo critério de aceite.

**Por quê:** a auditoria precisa explicar por que uma despesa foi rejeitada ou limitada; só o status não distingue falta de nota fiscal de data fora do período.

**O que isso invalidou:** o modelo de saída do plan (5.2) e os testes que montavam itens de auditoria sem justificativa.

**Tasks afetadas:** nova T-023 (motor e modelo); T-018 (modal exibe a justificativa).

**Custo:** modelo, regras, motor, 3 arquivos de teste e a spec.

---

## D-001 — Competência inválida recusa o arquivo · `19/10/2026`

**Gatilho:** ao implementar a esteira (T-021), o responsável decidiu que a RN-009 não devolve status por despesa: o arquivo é recusado.

**O que mudou na spec:** RN-009 (regra e cenários 02, 03 e 04): de "retornar o status rejeitado" para "recusar o arquivo, sem avaliar despesas nem gerar resultado, e informar o erro de formato"; seção 8 acompanha.

**Por quê:** uma competência inválida impede até nomear o arquivo de persistência; não há resultado confiável a gerar.

**O que isso invalidou:** a primeira versão do motor, que devolvia todas as despesas `rejeitado` com 0,00, e seus testes.

**Tasks afetadas:** T-005 e T-021 (refeitas); T-013 (recusa também no carregamento).

**Custo:** motor, serviço, spec e testes de RN-009.
