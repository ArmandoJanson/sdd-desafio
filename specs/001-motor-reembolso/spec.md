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

 **Cenário 1:** Despesa(s) abaixo do limite

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

**Cenário 4**:Despesa de outra categoria não deve ser validada por esta regra
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
    Para os registros que possuam exatamente os mesmo valores, por exemplo despesas que possuem exatamente a mesma data, categoria, fornecedor, descrição e valor, deve ser avaliada a despesa com o id mais recente. O registro com id mais antigo deverá ser rejeitado.
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

### RN-009 — Vigência deve seguir o formato "YYYY-MM"

**Regra:** 
    A competência (vigência) deve seguir o padrão "YYYY-MM", onde o "YYYY" representa o ano e o "MM" representa o mês. Se a competência não for válida, o arquivo de despesas é recusado: o sistema não avalia nenhuma despesa, não gera resultado de auditoria e informa o erro de formato.

**Origem:** política do RH, item `7`
**Aceite:** 
    **Cenário 01** — Vigência em formato válido (Aprovado / Sequência do fluxo)
        Dado que um registro de despesa é enviado com o campo vigencia preenchido com o valor "2026-10";

        Quando o sistema processar a validação da RN-009;

        Então o sistema deve reconhecer o formato como válido (ano com 4 dígitos e mês válido entre 01 e 12) e permitir o prosseguimento do registro para o fluxo das demais regras.

    **Cenário 02** — Vigência com formato incorreto / separador inválido (Arquivo recusado)
        Dado um lançamento de despesa no qual o campo vigencia foi informado em um dos seguintes formatos incorretos:

        "10/2026" (formato MM/YYYY)

        "2026/10" (uso de barra ao invés de hífen)

        "202610" (sem separador)

        "2026-10-15" (formato de data completa YYYY-MM-DD)

        Quando o sistema avaliar o campo vigencia contra a mascara "YYYY-MM";

        Então o sistema deve recusar o arquivo, sem avaliar as despesas nem gerar resultado, e informar que a competência não segue o formato YYYY-MM.

    **Cenário 03** — Vigência com mês numérico inválido (Arquivo recusado)
        Dado um lançamento de despesa no qual o campo vigencia possui 4 dígitos no ano e 2 no mês, porém com valor de mês fora do intervalo de 01 a 12 (ex.: "2026-13" ou "2026-00");

        Quando o sistema validar a consistência da data informada na regra;

        Então o sistema deve identificar a data como inválida, recusar o arquivo e informar o erro de formato.

    **Cenário 04** — Vigência não informada ou nula (Arquivo recusado)
        Dado um lançamento de despesa no qual o campo vigencia encontra-se vazio ("") ou nulo (null);

        Quando o sistema processar a validação da RN-009;

        Então a regra não é atendida e o sistema deve recusar o arquivo, sem gerar resultado, e informar o erro de formato.

### RN-010 — Tratamento de Valores Negativos

**Regra:** 
    O registros das despesas que apresentarem valores negativos, deverão ser rejeitados pois não são elegíveis ao reembolso.

**Origem:** política do RH, item `1`,`2`,`3`,`4`,`5`
**Aceite:** 
    **Cenário 01** — Despesa com valor positivo (Aprovado / Sequência do fluxo)
        Dado um lançamento de despesa no qual o campo valor é informado com um número positivo, como R$ 50,00 (ou 50.00);

        Quando o sistema processar a validação da RN-010;

        Então o valor é reconhecido como válido e o registro deve prosseguir para a avaliação das demais regras do fluxo.

    **Cenário 02** — Despesa com valor negativo (Rejeitado)
        Dado um lançamento de despesa no qual o campo valor é informado com um número negativo, como -R$ 25,00 (ou -25.00);

        Quando o sistema processar a validação da RN-010;

        Então o sistema deve identificar que o valor é inelegível para reembolso e retornar o status rejeitado.

    **Cenário 03** — Despesa com valor zero (Rejeitado)
        Dado um lançamento de despesa no qual o campo valor é informado como R$ 0,00 (ou 0.00);

        Quando o sistema avaliar a elegibilidade do valor para reembolso;

        Então o sistema não deve permitir o reembolso de valor nulo/zerado e deve retornar o status rejeitado.

### RN-011 — Precisão Decimal em Valores Monetários

**Regra:** 
    Os valores apresentados nos registros das despesas serão tratados e o valor do resultado irá conter duas casas decimais. Os arredontamentos deverão seguir o padrão matémático.

**Origem:** política do RH, item `1`,`2`,`3`,`4`,`5`
**Aceite:** 
    **Cenário 01** — Valor monetário já formatado com exatamente duas casas decimais (Aprovado / Sequência do fluxo)
        Dado que um registro de despesa é enviado com o campo valor contendo exatamente duas casas decimais, como R$ 45,50 (ou 45.50);

        Quando o sistema processar a validação da RN-011;

        Então o sistema deve reconhecer a precisão decimal correta, manter o valor inalterado e prosseguir no fluxo de validação.

    **Cenário 02** — Arredondamento matemático para cima (Terceira casa decimal ≥ 5)
        Dado um lançamento de despesa no qual o cálculo ou entrada do campo valor resulte em um número com mais de duas casas decimais, como R$ 80,456 ou R$ 60,005;

        Quando o sistema aplicar a regra de arredondamento matemático padrão;

        Então o valor deve ser ajustado para cima na segunda casa decimal, resultando em R$ 80,46 e R$ 60,01, respectivamente, e seguir para o fluxo de reembolso com o valor ajustado.

    **Cenário 03** — Arredondamento matemático para baixo (Terceira casa decimal < 5)
        Dado um lançamento de despesa no qual o cálculo ou entrada do campo valor resulte em um número com mais de duas casas decimais, como R$ 80,454 ou R$ 60,002;

        Quando o sistema aplicar a regra de arredondamento matemático padrão;

        Então o valor deve ser mantido na segunda casa decimal sem alteração, resultando em R$ 80,45 e R$ 60,00, respectivamente, e seguir para o fluxo de reembolso com o valor ajustado.

    **Cenário 04** — Entrada de valor inteiro sem casas decimais (Normalização para duas casas)
        Dado um lançamento de despesa enviado com valor inteiro, como R$ 100 (ou 100);

        Quando o sistema processar a formatação da RN-011;

        Então o sistema deve normalizar o valor exibindo/armazenando duas casas decimais (R$ 100,00) para garantir a precisão requerida pela política.
---

## 6. Ambiguidades identificadas e decisões

> **Esta seção é o coração da spec e vale a maior parte dos 25 pontos do critério 1.**
> Uma ambiguidade que você resolveu no código sem registrar aqui conta como
> não resolvida.

### AMB-001 — Limite por Despesa vs. Acumulado Diário

**Texto original do RH:** "Alimentação tem limite de R$ 60 por dia."
**O que não está claro:** O limite de R$ 60 aplica-se individualmente a cada item de despesa ou ao somatório de todas as despesas daquela categoria no mesmo dia? Se for por dia, o excesso é calculado sobre o total acumulado (R$ 110,50 - R$ 60 = R$ 50,50 de excedente)?
**Decisão:** O somatório de todas as despesas no mesmo dia terá o limite de R$ 60,00 para a categoria alimentacao, inclusive.
**Justificativa:** Garantir o cumprimento do teto orçamentário diário estabelecido pela política da empresa, impedindo que o fracionamento de refeições distintas ultrapasse o limite total permitido.
**Regra afetada:** RN-001

### AMB-002 — Limiar Exato de Obrigação de Nota Fiscal

**Texto original do RH:** "Nota fiscal é obrigatória acima de R$ 100."
**O que não está claro:** O operador lógico é estritamente maior (> 100) ou maior ou igual (>= 100)? Uma despesa de exatamente R$ 100,00 (como a d-003) exige nota fiscal ou está isenta?
**Decisão:** Para todas as desejas registradas que tiverem valor acima de 100,00, será obrigatória a apresentação da nova fiscal. Caso não seja reallizada a entrada da nota fiscal o reembolso será rejeitado.
**Justificativa:** Proteger o caixa da empresa e cumprir as regras fiscais, exigindo nota fiscal apenas quando o valor do gasto passar de R$ 100,00 para comprovar em que o dinheiro foi usado.
**Regra afetada:** RN-004

### AMB-003 — Ausência de Indicador de "Em Viagem"

**Texto original do RH:** "Colaborador em viagem tem limites ampliados em 50%."
**O que não está claro:** Como o motor sabe quais dias aplicar o acréscimo de 50% nos limites de alimentação e transporte se o JSON não possui um campo booleano ou de status informando se o colaborador estava em viagem na data da despesa?
**Decisão:** Verifica o conteúdo do campo fornecedor e a partir do conteúdo dele decidirá se o colaborador estará em viagem ou não.
**Justificativa:** Garantir o reembolso com valor ampliado aos colaboradores em viagem identificando automaticamente o local ou serviço utilizado, sem precisar exigir comprovantes ou cadastros manuais adicionais.
**Regra afetada:** RN-005

### AMB-004 — Critério e Ação para Duplicatas

**Texto original do RH:** "Duplicatas devem ser tratadas."
**O que não está claro:** O que significa "tratadas"? Devem ser rejeitadas automaticamente pelo motor, bloqueadas para auditoria humana ou consideradas refeições independentes (ex: almoço em dois horários diferentes)?
**Decisão:** Para os registros que possuam exatamente os mesmo valores, por exemplo despesas que possuem exatamente a mesma data, categoria, fornecedor, descrição e valor, deve ser avaliada a despesa com o id mais recente. O registro com id mais antigo deverá ser rejeitado.
**Justificativa:** Evitar que a empresa pague duas vezes pela mesma despesa enviada por engano, mantendo apenas o registro mais recente para garantir a cobrança correta.
**Regra afetada:** RN-007

### AMB-005 — Lançamentos Fora do Período de Competência

**Texto original do RH:** "Despesas devem ser lançadas dentro do período de competência."
**O que não está claro:** Como o motor deve agir com despesas cujo mês/ano da despesa difere da competência declarada? O item deve ser sumariamente recusado, ignorado ou retido para o mês correto?
**Decisão:** A data da despesa lançada deve estar dentro do período de competência que é registrado entre o valor de inicio e o fim do período informado.

    Os status de retorno deve ser:
    1. aprovado : caso a regra seja atendida
    2. rejeitado: caso a regra não seja atendida
**Justificativa:** Garantir o controle financeiro e o fechamento correto das contas da empresa, aceitando apenas despesas que pertençam exatamente ao período em aberto.
**Regra afetada:** RN-006

### AMB-006 — Sensibilidade a Maiúsculas e Minúsculas (Case Sensitivity) nas Categorias

**Texto original do RH:** "Categorias fora da política não são reembolsáveis."
**O que não está claro:** O motor de processamento é sensível a letras maiúsculas/minúsculas? Se for case-sensitive, "ALIMENTACAO" será tratada como uma categoria desconhecida e bloqueada pela Regra 9 do RH?
**Decisão:** Serão avaliados apenas os registros das categorias "alimentacao", "coworking", "hospedagem" e "transporte_urbano", na forma que estão escritas. Qualquer categoria diferente das listadas anterior mente deverá retornar o status "rejeitado - categoria inválida" para o registro .
**Justificativa:** Garantir a padronização dos gastos e o cumprimento estrito das categorias aprovadas pela empresa, recusando lançamentos com grafias fora do padrão para evitar erros de reembolso.
**Regra afetada:** RN-008

### AMB-007 — Categorias Não Listadas na Política (Ex: Coworking)

**Texto original do RH:** "Categorias fora da política não são reembolsáveis."
**O que não está claro:** A política restringe-se explicitamente a alimentação, transporte urbano e hospedagem. Despesas de espaço de trabalho compartilhado (coworking) são totalmente recusadas ou deveriam ser embutidas em outra rubrica?
**Decisão:** Serão avaliados apenas os registros das categorias "alimentacao", "coworking", "hospedagem" e "transporte_urbano", na forma que estão escritas. Qualquer categoria diferente das listadas anterior mente deverá retornar o status "rejeitado - categoria inválida" para o registro .
**Justificativa:** Garantir a padronização dos gastos e o cumprimento estrito das categorias aprovadas pela empresa, recusando lançamentos com grafias fora do padrão para evitar erros de reembolso.
**Regra afetada:** RN-008

### AMB-008 — Tratamento de Valores Negativos (Estornos)

**Texto original do RH:** " 1. Alimentação tem limite de R$ 60 por dia.
                            2. Transporte urbano tem limite de R$ 80 por dia.
                            3. Hospedagem tem limite de R$ 250 por diária.
                            4. Despesas acima do limite são reembolsadas parcialmente.
                            5. Nota fiscal é obrigatória acima de R$ 100."
**O que não está claro:** Como o motor processa estornos? O valor deve ser abatido do total do dia, da categoria de transporte urbano, ou gera um saldo devedor/rejeição de formato?
**Decisão:** O registros das despesas que apresentarem valores negativos, deverão ser rejeitados pois não são elegíveis ao reembolso.
**Justificativa:** Proteger a empresa contra pagamentos indevidos, garantindo que o sistema processe apenas solicitações de reembolso de gastos reais efetuados pelo colaborador.
**Regra afetada:** RN-010

### AMB-009 — Precisão Decimal em Valores Monetários

**Texto original do RH:** " 1. Alimentação tem limite de R$ 60 por dia.
                            2. Transporte urbano tem limite de R$ 80 por dia.
                            3. Hospedagem tem limite de R$ 250 por diária.
                            4. Despesas acima do limite são reembolsadas parcialmente.
                            5. Nota fiscal é obrigatória acima de R$ 100."
**O que não está claro:** A política não define regras de arredondamento para valores com mais de duas casas decimais. O motor deve truncar, arredondar para cima/baixo (regras da ABNT/matemáticas) ou rejeitar o lançamento por erro de validação de formato de moeda?
**Decisão:** Os valores apresentados nos registros das despesas serão tratados e o valor do resultado irá conter duas casas decimais. Os arredontamentos deverão seguir o padrão matémático.
**Justificativa:** Garantir a exatidão e a justiça nos cálculos financeiros, assegurando que os centavos sejam tratados de forma padronizada e transparente nos valores pagos.
**Regra afetada:** RN-011

---

## 7. Casos de borda

| Caso | Entrada | Comportamento esperado | Regra |
|---|---|---|---|
| **Lançamento no limite exato da nota fiscal sem comprovante** | Despesa de R$ 100,00 com `tem_nota_fiscal = false`. | O sistema aprova o valor integral de R$ 100,00 e define o status como `aprovado`, pois a exigência de nota fiscal aplica-se apenas a valores estritamente superiores a R$ 100,00. | RN-004 |
| **Lançamento acima de R$ 100,00 sem nota fiscal** | Despesa de R$ 100,01 com `tem_nota_fiscal = false`. | O sistema rejeita o reembolso e define o status como `rejeitado`. | RN-004 |
| **Múltiplas refeições no mesmo dia totalizando acima do limite padrão** | Duas despesas de alimentação no mesmo dia (R$ 40,00 e R$ 30,00, total R$ 70,00) para colaborador que não está em viagem. | A primeira despesa de R$ 40,00 é aprovada integralmente. A segunda é aprovada parcialmente em R$ 20,00 (atingindo o teto diário de R$ 60,00) com status `parcial`. | RN-001, RN-005 |
| **Hospedagem com fornecedor não reconhecido** | Despesa na categoria `hospedagem` no valor de R$ 200,00 com fornecedor "Residência Particular João". | O sistema rejeita a despesa com status `rejeitado`, pois o fornecedor não contém nenhuma das palavras-chave válidas (`hotel`, `airbnb`, `pousada`, `hostel`, `camping`) para caracterizar a viagem. | RN-003, RN-005 |
| **Despesa em dia com limite ampliado de viagem (Viagem + Alimentação)** | Lançamento de hospedagem válida e gasto de R$ 85,00 em `alimentacao` no mesmo dia. | O sistema identifica a condição de viagem, amplia o limite diário de alimentação em 50% (de R$ 60,00 para R$ 90,00) e aprova o valor integral de R$ 85,00 com status `aprovado`. | RN-001, RN-005 |
| **Registros idênticos com IDs distintos (Duplicatas)** | Dois lançamentos exatamente iguais (mesma data, categoria, fornecedor, descrição e valor), um com ID 101 e outro com ID 105. | O registro de ID 101 (mais antigo) é rejeitado por duplicidade. O registro de ID 105 (mais recente) é mantido para processamento das demais regras. | RN-007 |
| **Despesa com data fora do período de competência** | Competência de 01/10/2026 a 31/10/2026 e despesa lançada na data 30/09/2026 ou 01/11/2026. | O sistema rejeita a despesa com status `rejeitado`. | RN-006 |
| **Categoria com grafia ou acentuação diferente do padrão** | Despesa cadastrada como `alimentação` (com acento) ou `Hospedagem` (com maiúscula). | O sistema rejeita o lançamento com o status `rejeitado - categoria inválida`. | RN-008 |
| **Lançamento com valor zerado ou negativo** | Despesa com valor R$ 0,00 ou -R$ 25,00. | O sistema rejeita o lançamento com status `rejeitado`. | RN-010 |
| **Valor com mais de duas casas decimais** | Despesa cadastrada no valor de R$ 80,456. | O sistema aplica o arredondamento matemático padrão, ajustando o valor para R$ 80,46. | RN-011 |


## 8. Ordem de aplicação das regras

Quando uma ou mais regras incidem sobre uma mesma despesa, a esteira de avaliação do motor de cálculo segue uma ordem sequencial rígida de execução. Caso a despesa seja rejeitada em uma etapa eliminatória inicial, o processamento para esse item é encerrado sem necessidade de avaliar os critérios subsequentes.

A ordem de execução é:

1. **Formatos e Validações de Entrada Gerais (RN-009, RN-010, RN-011):**
   - **RN-009 (Formato da Vigência):** Verifica se a vigência do lote atende ao formato `YYYY-MM`. Se inválida, recusa o arquivo e encerra, sem gerar resultado.
   - **RN-010 (Valores Negativos):** Rejeita lançamentos com valores negativos.
   - **RN-011 (Precisão Decimal):** Ajusta e padroniza os valores para 2 casas decimais via arredondamento matemático.

2. **Filtro de Categorias Permitidas (RN-008):**
   - Valida se a categoria informada é exatamente uma das 4 permitidas (`alimentacao`, `coworking`, `hospedagem`, `transporte_urbano`). Se for inválida, atribui status `rejeitado - categoria inválida` e encerra a verificação do item.

3. **Deduplicação de Lançamentos (RN-007):**
   - Identifica lançamentos idênticos e mantém apenas o registro com ID mais recente para a sequência da análise, rejeitando o registro mais antigo por duplicidade.

4. **Validação do Período de Elegibilidade (RN-006):**
   - Garante que a data da despesa esteja dentro da faixa do período de competência (`inicio` e `fim`). Se estiver fora, é rejeitada.

5. **Identificação de Contexto de Viagem e Cálculo de Limites Ampliados (RN-005 e RN-003):**
   - Avalia a presença da categoria `hospedagem` e das palavras-chave no fornecedor para determinar se o colaborador está em viagem.
   - Se estiver em viagem, define os limites ampliados em 50% para `alimentacao` (R$ 90,00/dia) e `transporte_urbano` (R$ 120,00/dia), além de contabilizar o número de diárias conforme a descrição.
   - Valida a despesa da categoria `hospedagem` contra o limite diário de R$ 250,00 (RN-003).

6. **Aplicação dos Limites de Categoria (RN-001 e RN-002):**
   - Com base no contexto (viagem ou padrão), calcula o somatório diário das categorias `alimentacao` (RN-001) e `transporte_urbano` (RN-002) e aplica o teto de reembolso (`aprovado` para valores integrais dentro do limite ou `parcial` para excedentes ajustados ao teto).

7. **Comprovação Fiscal (RN-004):**
   - Para qualquer despesa aprovada ou parcial cujo valor seja superior a R$ 100,00, verifica a presença da nota fiscal (`tem_nota_fiscal = true`). Caso não possua, o status final é alterado para `rejeitado`.

## 9. Critérios de aceite

O sistema está pronto e aceito quando:

- [ ] Dado um arquivo de despesas de entrada no formato JSON, o motor gera um arquivo JSON de saída no formato exato especificado no item 4, contendo a lista de colaboradores e o histórico de despesas processadas com os respectivos `status_item` e `valor_reembolsado`.
- [ ] Todas as despesas da categoria `alimentacao` são reembolsadas integralmente se o acumulado diário for de até R$ 60,00 (ou R$ 90,00 se em viagem) e limitadas ao teto com status `parcial` se ultrapassarem esse valor.
- [ ] Todas as despesas da categoria `transporte_urbano` são reembolsadas integralmente se o acumulado diário for de até R$ 80,00 (ou R$ 120,00 se em viagem) e limitadas ao teto com status `parcial` se ultrapassarem esse valor.
- [ ] Lançamentos na categoria `hospedagem` com valor até R$ 250,00 e fornecedor contendo uma das palavras-chave (`hotel`, `airbnb`, `pousada`, `hostel`, `camping`) retornam o status `aprovado`.
- [ ] Lançamentos na categoria `hospedagem` com fornecedores que não contêm as palavras-chave exigidas retornam o status `rejeitado`.
- [ ] Qualquer despesa com valor superior a R$ 100,00 que não possua nota fiscal (`tem_nota_fiscal = false`) é classificada como `rejeitado`.
- [ ] Despesas idênticas enviadas em duplicidade preservam o registro de ID mais recente para processamento e marcam o registro antigo como `rejeitado - duplicidade`.
- [ ] Qualquer despesa com data fora do intervalo de início e fim da competência informada retorna o status `rejeitado`.
- [ ] Qualquer categoria diferente de `alimentacao`, `coworking`, `hospedagem` e `transporte_urbano` (respeitando caixa baixa e ausência de acentuação) retorna o status `rejeitado - categoria inválida`.
- [ ] Lançamentos com valores negativos ou zerados retornam o status `rejeitado`.
- [ ] Todos os valores financeiros de reembolso na saída são apresentados em formato numérico com exatamente duas casas decimais e arredondamento matemático correto.

## 10. O que fica em aberto

Decisões provisórias tomadas ao implementar os modelos (T-002/T-003); a spec deve confirmá-las ou corrigi-las.

- **Formato da saída (seção 4):** a tabela define `colaborador` e `historico_despesas[]` como campos irmãos, mas o exemplo aninha `historico_despesas` dentro de `colaborador`, envolve tudo em uma lista, omite `centro_custo` no histórico e é JSON inválido (vírgulas e chaves). **Provisório:** segue a tabela (`colaborador` e `historico_despesas` no mesmo nível, um objeto por colaborador). O empacotamento em lista (critério de aceite 1, "lista de colaboradores") fica para a task do motor.
- **`fornecedor` em minúsculas:** a tabela manda normalizar, mas o exemplo de saída mostra "Restaurante Tavola". **Provisório:** normaliza para minúsculas na entrada e na saída.
- **Status por duplicidade (RN-007):** o texto admite "rejeitado por duplicidade" ou apenas "rejeitado". **Decidido (19/10/2026):** o registro antigo recebe o status `rejeitado - duplicidade`, no mesmo padrão de `rejeitado - categoria inválida`, para deixar o motivo visível na auditoria.
- **Competência nula (RN-009, cenário 04):** o campo é obrigatório, mas `null` e `""` precisam chegar ao motor para que o arquivo seja recusado. **Provisório:** o schema aceita `null`; a chave deve existir. Sem competência não há como nomear o arquivo, então o repositório recusa gravar.
- **Arredondamento × RN-010:** a seção 8 executa RN-010 antes de RN-011. Um valor como 0,004 é positivo, mas arredonda para 0,00. **Provisório:** o arredondamento ocorre no parsing, então o motor o enxerga como zero e rejeita.
- **`id` do colaborador com `_`:** a listagem por prefixo (plan 4.2) separa o id no primeiro `_`. **Provisório:** o repositório recusa ids com `_`.
- **Categoria `coworking` (RN-008) — Confirmada:** é aceita como categoria, mas nenhuma regra define limite para ela. Fica sem limite; é reembolsada integralmente se passar nas demais regras (período, duplicidade, nota fiscal).

Decisões tomadas ao implementar o motor (T-005 a T-012 e T-021). As marcadas como **Confirmada** foram validadas com o responsável pelo produto em 19/10/2026; as demais seguem provisórias.

- **Competência inválida (RN-009) — Decidida:** o arquivo é recusado e o motor não gera auditoria nem status por despesa; o sistema informa o erro de formato. Os cenários da RN-009 descrevem essa recusa. A competência não é conferida contra `inicio` e `fim`.
- **Limite de hospedagem (RN-003) — Confirmada:** o texto original fala em "R$ 250 por diária". **Provisório:** o teto de uma despesa de hospedagem é R$ 250,00 multiplicado pelo número de diárias lido da descrição; acima disso, `parcial` com o teto. Hospedagem não recebe a ampliação de 50%.
- **Número de diárias (RN-003, RN-005):** é o primeiro número inteiro da descrição; sem número (ou com zero), vale 1.
- **Duração da viagem (RN-005) — Confirmada:** a viagem começa na data da despesa de hospedagem (com fornecedor reconhecido, que passou por RN-010, RN-008, RN-007 e RN-006) e dura N dias quando a descrição fala em diárias, ou N + 1 dias quando fala em noites (cenário 04). Sem número, dura 1 dia. A viagem existe mesmo que a hospedagem seja depois rejeitada por falta de nota fiscal. Em dia de viagem, os tetos diários de `alimentacao` e `transporte_urbano` valem ×1,5; vários dias de viagem se sobrepondo não ampliam mais de uma vez.
- **Consumo do teto diário (RN-001, RN-002) — Confirmada:** as despesas do mesmo dia e categoria consomem o teto na ordem em que aparecem no arquivo (caso de borda da seção 7). Despesa com teto já esgotado sai `rejeitado` com 0,00, pois nada é pago; `parcial` exige algum valor pago.
- **Despesa rejeitada não consome teto — Confirmada:** despesas rejeitadas por qualquer regra, inclusive por falta de nota fiscal (RN-004), não entram no acumulado do dia. O resultado de cada despesa rejeitada é o mesmo da ordem da seção 8; só muda o que sobra de teto para as demais.
- **ID mais recente (RN-007) — Confirmada:** a comparação trata os trechos numéricos do id como números (`d-9` é anterior a `d-10`). Se houver empate, vale a despesa que aparece por último no arquivo. Com três ou mais duplicatas, só a mais recente é mantida. Só participam da comparação despesas que passaram por RN-010 e RN-008.
- **Nota fiscal (RN-004):** a regra olha o valor da despesa (não o reembolsado) e se aplica a todas as categorias, inclusive hospedagem.
