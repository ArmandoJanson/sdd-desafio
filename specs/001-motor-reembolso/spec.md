# Spec — Motor de Cálculo de Reembolso

**Versão:** 1.0 · **Status:** rascunho · **Última alteração:** `15/10/2026`

> **Regra de ouro deste arquivo:** ele descreve o QUÊ e o PORQUÊ. Nenhuma linha
> aqui pode citar linguagem, biblioteca, classe, função ou estrutura de pasta.
> Se apareceu solução, o lugar dela é o `plan.md`.
>
> **Teste de aceitação da própria spec:** uma pessoa que nunca viu o projeto
> consegue, lendo só este arquivo, verificar se o sistema está correto?

---

## 1. Problema

Atualmente, o processo de conferência manual de solicitações de reembolso é lento, caro e propenso a erros. Isso gera atrasos nas respostas aos funcionários e pode levar à aprovação ou reprovação incorreta de valores. Como resultado, a empresa perde eficiência, gasta tempo com correções e corre o risco de fazer pagamentos indevidos.

## 2. Objetivo

Validar as despesas dos colaboradores de forma ágil, precisa e automatizada, garantindo conformidade e agilidade nos pagamentos.

## 3. Fora de escopo

- Não faz Autenticação/autorização
- Não faz Checagem de autenticidade da nota fiscal, CNPJ ou chave de acesso.
- Não faz Conferência entre o valor lançado e o valor da NF
- Não faz Notificações ao colaborador
- Não faz Pagamento efetivo do reembolso
- Não faz Preencher lacunas da política com suposições
- Não faz Upload e OCR de comprovantes
- Não faz validação de documentos

## 4. Entrada e saída

**Entrada:** conforme `exemplos/despesas-exemplo.json`. Campos e significado:

| Campo | Tipo | Significado | Obrigatório |
|---|---|---|---|
| `colaborador.id`|(string) | Identificador do colaborador| sim |
| `colaborador.nome`|(string) | nome do colaborador| sim |
| `colaborador.centro_custo`|(string) | Centro de custo responsável pelo pagamento| sim |
| `periodo.competencia`|(string, formato `YYYY-MM`) | Período elegível para reembolso | sim |
| `periodo.inicio`|(string, formato `YYYY-MM-DD`) | Início da vigência| sim |
| `periodo.fim`|(string, formato `YYYY-MM-DD`) | Final da vigência| sim |
| `despesas[].id`|(string) | Identificador do colaborador| sim |
| `despesas[].data`|(string, formato `YYYY-MM-DD`) | Data da despesa | sim |
| `despesas[].categoria`|(string) | Categoria do reembolso | sim |
| `despesas[].descricao`|(string) | Descrição do reembolso| sim |
| `despesas[].fornecedor`|(string, normalizada para minúsculas) | fornecedor | sim |
| `despesas[].valor`|(float, máximo de 2 casas decimais) | Valor da despesa | sim |
| `despesas[].tem_nota_fiscal`|(boolean) | Indica se existe nota fiscal| sim |

**Saída:** definida por mim. Estrutura e significado de cada campo:

| Campo | Tipo | Significado |
|---|---|---|
| `colaborador.id`|(string) | Identificador do colaborador|
| `colaborador.centro_custo`|(string) | Centro de custo responsável pelo pagamento|
| `historico_despesas[].competencia`|(string, formato `YYYY-MM`) | Período elegível para reembolso |
| `historico_despesas[].centro_custo`|(string) | Centro de custo responsável pelo pagamento|
| `historico_despesas[].despesas[].id`|(string) | Identificador do colaborador|
| `historico_despesas[].despesas[].data`|(string, formato `YYYY-MM-DD`) | Data da despesa |
| `historico_despesas[].despesas[].descricao`|(string) | Descrição do reembolso|
| `historico_despesas[].despesas[].fornecedor`|(string, normalizada para minúsculas) | fornecedor |
| `historico_despesas[].despesas[].status_item`|(string) | Status da avaliação|
| `historico_despesas[].despesas[].valor_reembolsado`|(float, máximo de 2 casas decimais) | Valor da despesa |
| 

Exemplo da saída:
  [{
    "colaborador": {
      "id": "c-0417",
      "centro_custo": "CC-ENG-PLATAFORMA",
	  "historico_despesas": [
		{
			"competencia": "2026-07",
			"despesas": [
				{
					"id": "d-001",
					"data": "2026-07-03",
					"descricao": "Almoco com cliente",
					"fornecedor": "Restaurante Tavola",
					"status_item": "aprovado",
					"valor_reembolsado": 72.50
				},
				{
					 "id": "d-002",
					 "data": "2026-07-03",
					 "descricao": "Jantar apos reuniao",
					 "fornecedor": "Cantina do Porto",
					 "status_item": "aprovado"
					 "valor_reembolsado": 38.00
				}
			]
		}
	  ]
    }
 }]

## 5. Regras de negócio

Cada regra recebe um ID (`RN-001`, ...). As tasks vão referenciar esses IDs.

### RN-001 — Limite das despesas com alimentação

**Regra:** 
    O somatório de todas as despesas no mesmo dia terá o limite de R$ 60,00 para a categoria alimentacao, inclusive. 
    Caso o(s) valor(es) da(s) despesa(s) ultrapassar o limite da regra, deverá ser reembolsado apenas o limite.
    Caso o valor da despesa seja menor do que o do limite, deverá ser pago o valor da despesa.
    Serão valiados apenas os registros com o valor "alimentacao" informado na propriedade categoria. Nesse caso não deverá haver retorno do status, a próxima regra deverá ser verificada.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida
    3. parcial :  caso a regra seja parcialmente, quando o valor do reembolso é menor do que o valor da despesa.

**Origem:** política do RH, item `1` e `4`
**Aceite:** 
    **Cenário 1**: Despesa(s) abaixo do limite

        Dado que o colaborador cadastre uma ou mais despesas na categoria alimentação no mesmo dia somando R$ 45,00 (valor < R$ 60,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve aprovar o reembolso no valor integral de R$ 45,00 e retornar o status aprovado.

    **Cenário 2**: Despesa(s) exatamente no limite

        Dado que o colaborador cadastre uma ou mais despesas na categoria alimentação no mesmo dia somando R$ 60,00 (valor = R$ 60,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve aprovar o reembolso no valor integral de R$ 60,00 e retornar o status aprovado.

    **Cenário 3**: Despesa(s) acima do limite (Reembolso Parcial)

        Dado que o colaborador cadastre uma ou mais despesas na categoria alimentação no mesmo dia somando R$ 85,00 (valor > R$ 60,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve limitar o reembolso ao teto de R$ 60,00 e retornar o status parcial.

    **Cenário **:Despesa de outra categoria não deve ser validada por esta regra
        Dado que foi lançada uma despesa com categoria diferente de alimentacao

        Quando a RN-001 for executada

        Então a regra não deve retornar nenhum status e o fluxo deve prosseguir para a verificação da próxima regra.

### RN-002 — Limite das despesas com transporte

**Regra:** 
    O somatório de todas as despesas no mesmo dia terá o limite de R$ 80,00 para a categoria transporte_urbano, inclusive. 
    Caso o(s) valor(es) da(s) despesa(s) ultrapassar o limite da regra, deverá ser reembolsado apenas o limite.
    Caso o valor da despesa seja menor do que o do limite, deverá ser pago o valor da despesa.
    Serão valiados apenas os registros com o valor "transporte_urbano" informado na propriedade categoria. Nesse caso não deverá haver retorno do status, a próxima regra deverá ser verificada.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida
    3. parcial :  caso a regra seja parcialmente, quando o valor do reembolso é menor do que o valor da despesa.

**Origem:** política do RH, item `2` e `4`
**Aceite:** 
    **Cenário 1**: Despesa(s) abaixo do limite

        Dado que o colaborador cadastre uma ou mais despesas na categoria transporte_urbano no mesmo dia somando R$ 75,00 (valor < R$ 80,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve aprovar o reembolso no valor integral de R$ 75,00 e retornar o status aprovado.

    **Cenário 2**: Despesa(s) exatamente no limite

        Dado que o colaborador cadastre uma ou mais despesas na categoria transporte_urbano no mesmo dia somando R$ 80,00 (valor = R$ 80,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve aprovar o reembolso no valor integral de R$ 80,00 e retornar o status aprovado.

    **Cenário 3**: Despesa(s) acima do limite (Reembolso Parcial)

        Dado que o colaborador cadastre uma ou mais despesas na categoria transporte_urbano no mesmo dia somando R$ 105,00 (valor > R$ 80,00),

        Quando o sistema processar a solicitação de reembolso,

        Então o sistema deve limitar o reembolso ao teto de R$ 80,00 e retornar o status parcial.

    **Cenário **:Despesa de outra categoria não deve ser validada por esta regra
        Dado que foi lançada uma despesa com categoria diferente de transporte_urbano

        Quando a RN-002 for executada

        Então a regra não deve retornar nenhum status e o fluxo deve prosseguir para a verificação da próxima regra.


### RN-003 — Limite do valor da hospedagem

**Regra:** 
    O funcionário estará em viagem quando o valor informado no campo categoria for hospedagem e no fornecedor contiver uma das palavras a seguir: hotel, airbnb, pousada, hostel ou camping.

	Será necessário converter o valor do campo para minúsculo para que seja possível verificar de forma assertiva se uma das palavras listadas está presente no valor informado no campo fornecedor. Dessa forma, para as despesas apresentadas na mesma data da viagem e na categoria hospedagem, terá limite diário de R$ 250,00, inclusive, por dia para reembolso das hospedagem. 
	
	Serão valiados apenas os registros com o valor "hospedagem" informado na propriedade categoria. Nesse caso não deverá haver retorno do status, a próxima regra deverá ser verificada.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida
    3. parcial :  caso a regra seja parcialmente, quando o valor do reembolso é menor do que o valor da despesa.

**Origem:** política do RH, item `3` e `4`
**Aceite:** 
    **Cenário 01** — Despesa aprovada dentro do limite (Valor exatamente R$ 250,00 ou inferior com reembolso integral)
        Dado um lançamento de despesa com os seguintes dados:

        Categoria: "hospedagem"

        Fornecedor: "Hotel Beira Mar" (contém "hotel")

        Data da despesa: 20/10/2026

        Valor da despesa: R$ 250,00

        Valor do reembolso solicitado: R$ 250,00

        Quando o sistema processar a validação da RN-003;

        Então a palavra-chave no fornecedor deve ser identificada com sucesso e o sistema deve retornar o status aprovado.

    **Cenário 02** — Despesa aprovada com validação Case-Insensitive (Letras maiúsculas/mistas no fornecedor)
        Dado um lançamento de despesa com os seguintes dados:

        Categoria: "hospedagem"

        Fornecedor: "AIRBNB Studio Centro" (palavra em maiúsculas)

        Data da despesa: 20/10/2026

        Valor da despesa: R$ 180,00

        Valor do reembolso solicitado: R$ 180,00

        Quando o sistema converter a string do fornecedor para minúsculo ("airbnb studio centro") e validar a regra;

        Então a palavra-chave "airbnb" é identificada, o valor está abaixo do limite de R$ 250,00 e o sistema deve retornar o status aprovado.

    **Cenário 03** — Reembolso parcial (Valor do reembolso menor que o valor total da despesa)
        Dado um lançamento de despesa com os seguintes dados:

        Categoria: "hospedagem"

        Fornecedor: "Hostel Central" (contém "hostel")

        Data da despesa: 20/10/2026

        Valor da despesa: R$ 300,00 (diária acima do limite)

        Valor do reembolso solicitado: R$ 250,00 (solicitado apenas até o limite permitido)

        Quando o sistema avaliar a regra de reembolso onde o valor aprovado/solicitado é menor que o valor total da nota/despesa original;

        Então o sistema deve retornar o status parcial.

    **Cenário 04**— Categoria diferente de "Hospedagem" (Bypass / Passagem para a próxima regra)
        Dado um lançamento de despesa com os seguintes dados:

        Categoria: "alimentação"

        Fornecedor: "Hotel e Restauração"

        Valor da despesa: R$ 100,00

        Quando o sistema checar o campo Categoria;

        Então o sistema não deve alterar ou definir status para a RN-003 e deve encaminhar a execução diretamente para a próxima regra da esteira.

    **Cenário 05** — Categoria "Hospedagem" mas sem palavra-chave válida no fornecedor
        Dado um lançamento de despesa com os seguintes dados:

        Categoria: "hospedagem"

        Fornecedor: "Residência Particular João" (não contém hotel, airbnb, pousada, hostel ou camping)

        Valor da despesa: R$ 200,00

        Quando o sistema converter o fornecedor para minúsculo e buscar pelas palavras-chave (hotel, airbnb, pousada, hostel, camping);

        Então a condição de viagem não é caracterizada por essa regra e o sistema deve retornar o status rejeitado. 

### RN-004 — Nota fiscal é obrigatória para despesa acima de R$ 100.

**Regra:** 
    Para todas as desejas registradas que tiverem valor acima de 100,00, será obrigatória a apresentação da nova fiscal. Caso não seja reallizada a entrada da nota fiscal o reembolso será rejeitado.
    Essa regra deverá levar em consideração as regras anteriores.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida

**Origem:** política do RH, item `5`
**Aceite:** 
    **Cenário 01** — Despesa acima de R$ 100,00 com Nota Fiscal (Aprovado)
        Dado um lançamento de despesa no valor de R$ 100,01;

        E o comprovante/anexo da Nota Fiscal foi informado/anexado;

        Quando o sistema processar a validação da RN-004;

        Então o sistema deve validar o cumprimento da obrigatoriedade e retornar o status aprovado.

    **Cenário 02** — Despesa acima de R$ 100,00 sem Nota Fiscal (Rejeitado)
        Dado um lançamento de despesa no valor de R$ 150,00;

        E o comprovante/anexo da Nota Fiscal NÃO foi informado/anexado;

        Quando o sistema processar a validação da RN-004;

        Então a regra não é atendida e o sistema deve retornar o status rejeitado.

    **Cenário 03** — Despesa exatamente de R$ 100,00 sem Nota Fiscal (Aprovado / Limite Inclusivo)
        Dado um lançamento de despesa no valor exato de R$ 100,00;

        E o comprovante/anexo da Nota Fiscal NÃO foi informado/anexado;

        Quando o sistema avaliar a condição de valor "acima de R$ 100,00";

        Então o sistema entende que a exigência de Nota Fiscal se aplica apenas a valores maiores que 100,00 e deve retornar o status aprovado.

    **Cenário 04** — Despesa abaixo de R$ 100,00 sem Nota Fiscal (Aprovado)
        Dado um lançamento de despesa no valor de R$ 45,50;

        E o comprovante/anexo da Nota Fiscal NÃO foi informado/anexado;

        Quando o sistema processar a validação da RN-004;

        Então a exigência de Nota Fiscal não se aplica e o sistema deve retornar o status aprovado.

### RN-005 — Colaborador em viagem tem limites ampliados em 50%.

**Regra:** 
    O funcionário estará em viagem quando o valor informado no campo categoria for hospedagem e no fornecedor contiver uma das palavras a seguir: hotel, airbnb, pousada, hostel ou camping.
 
	Será necessário converter o valor do campo para minúsculo para que seja possível verificar de forma assertiva se uma das palavras listadas está presente no valor informado no campo fornecedor. 
    Será necessário verificar a quantidade de diárias/noites informadas na descrição. Caso não seja informado nenhum valor numérico, deverá ser considerada uma diária.
    Caso seja informada no campo descricao mais de uma diária/noite, para noites somar mais uma dia, os limites tratados nas regras anteriores para as desepesas deverão ser ampliados em 50%. 

**Origem:** política do RH, item `6`
**Aceite:** 
    **Cenário 01** — Colaborador em viagem: Limite de Alimentação ampliado em 50% (Até R$ 90,00)
        Dado que o colaborador possui lançamento de despesa com a categoria "hospedagem" na mesma data, com fornecedor "Hotel Beira Mar" (palavra "hotel" presente, caracterizando viagem);
        
        E cadastre despesa(s) na categoria "alimentacao" no mesmo dia no valor de R$ 85,00;
        
        Quando o sistema processar a solicitação de reembolso aplicando a ampliação de 50% sobre o limite diário padrão da RN-001 (R$ 60,00 × 1,5 = R$ 90,00);
        
        Então o sistema deve aprovar o reembolso no valor integral de R$ 85,00 (pois R$ 85,00 ≤ R$ 90,00) e retornar o status aprovado.
    
    **Cenário 02** — Colaborador em viagem: Excesso do limite ampliado em Alimentação (Reembolso Parcial)
        Dado que o colaborador possui lançamento de despesa com a categoria "hospedagem" na mesma data, com fornecedor "AIRBNB Studio" (palavra "airbnb" presente, caracterizando viagem);
        
        E cadastre despesa(s) na categoria "alimentacao" no mesmo dia no valor de R$ 110,00;
        
        Quando o sistema processar a solicitação aplicando o limite ampliado de R$ 90,00;
        
        Então o sistema deve limitar o reembolso ao teto de R$ 90,00 e retornar o status parcial.
        
    **Cenário 03** — Colaborador em viagem: Limite de Transporte Urbano ampliado em 50% (Até R$ 120,00)
        Dado que o colaborador possui lançamento de despesa com a categoria "hospedagem" na mesma data, com fornecedor "Pousada Recanto" (palavra "pousada" presente, caracterizando viagem);
        
        E cadastre despesa(s) na categoria "transporte_urbano" no mesmo dia no valor de R$ 115,00;
        
        Quando o sistema processar a solicitação de reembolso aplicando a ampliação de 50% sobre o limite diário padrão da RN-002 (R$ 80,00 × 1,5 = R$ 120,00);
        
        Então o sistema deve aprovar o reembolso no valor integral de R$ 115,00 (pois R$ 115,00 ≤ R$ 120,00) e retornar o status aprovado.
        
    **Cenário 04** — Múltiplas diárias/noites informadas na descrição (Somar +1 dia ao número de noites)
        Dado que no lançamento de hospedagem a propriedade descricao contenha "Reserva de 3 noites" (ou 3 diárias);
        
        E o fornecedor seja "Hostel Central" (caracterizando viagem);
        
        Quando o sistema analisar a propriedade descricao, identificar o valor numérico 3 e calcular o total de dias elegíveis ($3 \text{ noites} + 1 = 4 \text{ dias}$);
        
        Então os limites diários ampliados devem ser estendidos para cobrir os 4 dias da viagem (ex.: limite total de alimentação para o período = $4 \times \text{R\$ 90,00} = \text{R\$ 360,00}$).
        
    **Cenário 05** — Ausência de valor numérico na descrição (Default para 1 diária)
        Dado que no lançamento de hospedagem a propriedade descricao contenha "Hospedagem a trabalho" (sem valor numérico informado);
        
        E o fornecedor seja "Camping Verde" (caracterizando viagem);
        
        Quando o sistema analisar o campo descricao e não encontrar nenhum valor numérico;
        
        Então o sistema deve assumir o valor padrão de 1 diária e aplicar os limites ampliados em 50% para aquele dia (Alimentação: R$ 90,00; Transporte Urbano: R$ 120,00).
        
    **Cenário 06** — Colaborador NÃO está em viagem (Aplica-se o limite padrão sem ampliação)
        Dado que o colaborador não possui lançamento na categoria "hospedagem" na mesma data (ou o fornecedor não contém nenhuma das palavras-chave válidas);
        
        E cadastre despesa(s) na categoria "alimentacao" no valor de R$ 80,00;
        
        Quando a RN-005 for executada e constatar que a condição de viagem não foi atendida;
        
        Então o sistema deve aplicar o limite padrão da RN-001 (R$ 60,00), reembolsando o valor limite de R$ 60,00 e retornando o status parcial

### RN-006 — Despesas devem ser lançadas dentro do período de competência

**Regra:** 
    A data da despesa lançada deve estar dentro do período de competência que é registrado entre o valor de inicio e o fim do período informado.
    Essa regra deverá levar em consideração as regras anteriores.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida

**Origem:** política do RH, item `7`
**Aceite:** 
    **Cenário 01** — Despesa com data dentro do período de competência (Aprovado)
        Dado que o período de competência ativo está definido com início em 01/10/2026 e fim em 31/10/2026;

        E o colaborador cadastra uma despesa com data de lançamento de 15/10/2026;

        Quando o sistema processar a validação da RN-006;

        Então o sistema deve verificar que a data da despesa está entre o início e o fim da competência e retornar o status aprovado.

    **Cenário 02** — Despesa exatamente no dia inicial da competência (Aprovado / Limite Inclusivo)
        Dado que o período de competência ativo está definido com início em 01/10/2026 e fim em 31/10/2026;

        E o colaborador cadastra uma despesa com data de lançamento de 01/10/2026;

        Quando o sistema processar a validação da RN-006;

        Então o sistema deve considerar a data limite inicial inclusiva e retornar o status aprovado.

    **Cenário 03** — Despesa exatamente no dia final da competência (Aprovado / Limite Inclusivo)
        Dado que o período de competência ativo está definido com início em 01/10/2026 e fim em 31/10/2026;

        E o colaborador cadastra uma despesa com data de lançamento de 31/10/2026;

        Quando o sistema processar a validação da RN-006;

        Então o sistema deve considerar a data limite final inclusiva e retornar o status aprovado.

    **Cenário 04** — Despesa com data anterior ao início do período de competência (Rejeitado)
        Dado que o período de competência ativo está definido com início em 01/10/2026 e fim em 31/10/2026;

        E o colaborador cadastra uma despesa com data de lançamento de 30/09/2026;

        Quando o sistema processar a validação da RN-006;

        Então a regra não é atendida por ser anterior ao período permitido e o sistema deve retornar o status rejeitado.

    **Cenário 05** — Despesa com data posterior ao fim do período de competência (Rejeitado)
        Dado que o período de competência ativo está definido com início em 01/10/2026 e fim em 31/10/2026;

        E o colaborador cadastra uma despesa com data de lançamento de 01/11/2026;

        Quando o sistema processar a validação da RN-006;

Então a regra não é atendida por ser posterior ao período permitido e o sistema deve retornar o status rejeitado.

### RN-007 — Duplicatas devem ser tratadas

**Regra:** 
    Para os registros que possuam exatamente os mesmo valores, por exemplo despesas que possuem exatamente a mesma data, categoria, fornecedor, descrição e valor, deve ser avaliada a despesa com o id mais recente.
    Essa regra deverá ser verificada para que seja possível aplicar as regras anteriores.

**Origem:** política do RH, item `<n>`
**Aceite:** 
    **Cenário 01** — Identificação de duplicata perfeita e retenção do ID mais recente
        Dado que existem dois registros de despesas cadastrados no sistema com dados exatamente idênticos:

        Registro A: ID: 101, Data: 15/10/2026, Categoria: "alimentacao", Fornecedor: "Restaurante Sabor", Descrição: "Almoço de equipe", Valor: R$ 50,00

        Registro B: ID: 105, Data: 15/10/2026, Categoria: "alimentacao", Fornecedor: "Restaurante Sabor", Descrição: "Almoço de equipe", Valor: R$ 50,00

        Quando o sistema processar a esteira de validação da RN-007;

        Então o sistema deve identificar a duplicidade perfeita e selecionar o ID: 105 (registro mais recente) para prosseguir na aplicação das regras anteriores (RN-001 a RN-006);

        E o registro antigo (ID: 101) deve ser sinalizado/marcado como duplicata desconsiderada ou ter seu status retornado como rejeitado por duplicidade.

    **Cenário 02** — Registros com variação em ao menos um campo (Não duplicados)
        Dado que existem dois registros de despesas cadastrados no sistema:

        Registro A: ID: 201, Data: 15/10/2026, Categoria: "transporte_urbano", Fornecedor: "Uber", Descrição: "Corrida para cliente", Valor: R$ 35,00

        Registro B: ID: 202, Data: 15/10/2026, Categoria: "transporte_urbano", Fornecedor: "Uber", Descrição: "Corrida para cliente", Valor: R$ 45,00 (valor diferente)

        Quando o sistema processar a validação da RN-007;

        Então o sistema não deve classificar os registros como duplicatas;

        E ambos os registros (ID: 201 e ID: 202) devem ser mantidos e submetidos individualmente para a validação das regras anteriores.

    **Cenário 03** — Ordens de execução no fluxo de esteira (Pré-requisito das regras anteriores)
        Dado que o colaborador envia uma duplicata de despesa acima de R$ 100,00 onde o ID 301 não possui Nota Fiscal e o ID 305 (mais recente) possui Nota Fiscal anexada;

        Quando a RN-007 for executada antes do fluxo das regras anteriores;

        Então o sistema deve descartar o ID 301 por ser a versão antiga duplicada e aplicar a RN-004 apenas sobre o ID 305, retornando o status aprovado para este registro mais recente.

### RN-008 — Categorias fora da política não são reembolsáveis

**Regra:** 
    Serão avaliados apenas os registros das categorias "alimentacao", "coworking", "hospedagem" e "transporte_urbano", na forma que estão escritas. Qualquer categoria diferente das listadas anterior mente deverá retornar o status "rejeitado - categoria inválida" para o registro .

**Origem:** política do RH, item `9`
**Aceite:** 
    **Cenário 01** — Categorias permitidas pela política (Validação com sucesso)
        Dado um lançamento de despesa no qual a propriedade categoria é informada exatamente com um dos seguintes valores:
        "alimentacao"
        "coworking"
        "hospedagem"
        "transporte_urbano"

        Quando o sistema processar a validação da RN-008;

        Então a categoria deve ser reconhecida como válida e o registro deve prosseguir no fluxo para avaliação das demais regras.

    **Cenário 02** — Categoria não coberta pela política (Rejeição por categoria inválida)
        Dado um lançamento de despesa no valor de R$ 80,00 no qual a propriedade categoria foi informada como "estacionamento";

        Quando o sistema processar a validação da RN-008;

        Então o sistema deve rejeitar o registro e retornar o status "rejeitado - categoria inválida".

    **Cenário 03** — Categoria com variação de acentuação, caixa ou formatação (Rejeição por divergência exata)
        Dado um lançamento de despesa no qual a propriedade categoria foi informada com grafia diferente da especificada, tais como:
        "alimentação" (com acento)
        "Hospedagem" (com maiúscula)
        "transporte urbano" (com espaço em vez de underline)

        Quando o sistema comparar o valor do campo categoria com a lista restrita ("alimentacao", "coworking", "hospedagem", "transporte_urbano");

        Então o sistema deve identificar a inconformidade na forma escrita e retornar o status "rejeitado - categoria inválida".

---

## 6. Ambiguidades identificadas e decisões

> **Esta seção é o coração da spec e vale a maior parte dos 25 pontos do critério 1.**
> Uma ambiguidade que você resolveu no código sem registrar aqui conta como
> não resolvida.

### AMB-001 — <o que a política deixou em aberto>

**Texto original do RH:** "<citação literal>"
**O que não está claro:** <as duas ou mais leituras possíveis>
**Decisão:** <o que o sistema faz>
**Justificativa:** <por quê — uma linha; critério de negócio, não de conveniência técnica>
**Regra afetada:** RN-00X

### AMB-002 — ...

<A política tem no mínimo oito. Se você achou menos, releia
`exemplos/despesas-exemplo.json` — cada item daquele arquivo existe por um motivo.>

---

## 7. Casos de borda

| Caso | Entrada | Comportamento esperado | Regra |
|---|---|---|---|
| | | | |

## 8. Ordem de aplicação das regras

<Quando duas regras incidem sobre a mesma despesa, qual vale primeiro? A ordem
muda o resultado. Declarar isso separa spec boa de spec média.>

## 9. Critérios de aceite

O sistema está pronto quando:

- [ ] <critério verificável, sem ler código>
- [ ] <...>

## 10. O que fica em aberto

<Perguntas que você não conseguiu responder e a decisão provisória que tomou.
Honestidade aqui vale ponto — spec que finge não ter buraco é spec que esconde buraco.>
