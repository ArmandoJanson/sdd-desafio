"""Testes do motor de reembolso (T-005 a T-012 e T-021).

Cada teste de regra roda a esteira completa (``engine.avaliar``); os testes de
``rules`` exercitam as funções puras isoladamente.
"""

import ast
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core import engine, rules
from core.models import (
    Despesa,
    Periodo,
    ResultadoAuditoria,
    SolicitacaoReembolso,
)

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "despesas-exemplo.json"

APROVADO = "aprovado"
PARCIAL = "parcial"
REJEITADO = "rejeitado"
CATEGORIA_INVALIDA = "rejeitado - categoria inválida"
DUPLICIDADE = "rejeitado - duplicidade"


def d(
    id_="d-1",
    categoria="alimentacao",
    valor="10",
    data="2026-10-15",
    descricao="Almoco",
    fornecedor="Restaurante",
    nf=True,
):
    return {
        "id": id_,
        "data": data,
        "categoria": categoria,
        "descricao": descricao,
        "fornecedor": fornecedor,
        "valor": valor,
        "tem_nota_fiscal": nf,
    }


def solicitacao(despesas, competencia="2026-10", inicio="2026-10-01", fim="2026-10-31"):
    return SolicitacaoReembolso.model_validate(
        {
            "colaborador": {"id": "c-1", "nome": "Ana", "centro_custo": "CC-X"},
            "periodo": {"competencia": competencia, "inicio": inicio, "fim": fim},
            "despesas": despesas,
        }
    )


def itens(resultado):
    return resultado.historico_despesas[0].despesas


def avaliar(despesas, **periodo):
    """Lista de ``(status_item, valor_reembolsado como texto)`` por despesa."""
    resultado = engine.avaliar(solicitacao(despesas, **periodo))
    return [(i.status_item, str(i.valor_reembolsado)) for i in itens(resultado)]


def um(despesa, **periodo):
    (resultado,) = avaliar([despesa], **periodo)
    return resultado


# --------------------------------------------------------------------------
# T-005 — RN-009, RN-010, RN-011
# --------------------------------------------------------------------------


@pytest.mark.req("RN-009")
@pytest.mark.req("RN-010")
@pytest.mark.req("RN-011")
def test_validacao_formato_e_valores():
    # RN-009: competência válida segue o fluxo
    assert um(d(valor="45")) == (APROVADO, "45.00")
    # RN-010: negativo e zero
    assert um(d(valor="-25")) == (REJEITADO, "0.00")
    assert um(d(valor="0")) == (REJEITADO, "0.00")
    # RN-011: arredondamento matemático
    assert um(d(categoria="coworking", valor="80.456")) == (APROVADO, "80.46")


class TestRN009Competencia:
    @pytest.mark.req("RN-009")
    @pytest.mark.parametrize(
        "competencia",
        ["10/2026", "2026/10", "202610", "2026-10-15", "", None, "2026-13", "2026-00"],
    )
    def test_competencia_invalida_recusa_o_arquivo_sem_resultado(self, competencia):
        entrada = solicitacao([d("d-1"), d("d-2", valor="5")], competencia=competencia)
        with pytest.raises(engine.CompetenciaInvalidaError, match="YYYY-MM"):
            engine.avaliar(entrada)

    @pytest.mark.req("RN-009")
    def test_erro_de_competencia_e_value_error_e_informa_o_valor(self):
        with pytest.raises(ValueError, match="2026-13"):
            engine.avaliar(solicitacao([d()], competencia="2026-13"))

    @pytest.mark.req("RN-009")
    @pytest.mark.parametrize("competencia", ["2026-10", "2026-01", "2026-12"])
    def test_formato_valido_segue_o_fluxo(self, competencia):
        assert um(d(), competencia=competencia) == (APROVADO, "10.00")

    @pytest.mark.req("RN-009")
    def test_competencia_invalida_prevalece_sobre_despesas_invalidas(self):
        entrada = solicitacao([d(categoria="x", valor="-1")], competencia="2026-13")
        with pytest.raises(engine.CompetenciaInvalidaError):
            engine.avaliar(entrada)

    @pytest.mark.req("RN-009")
    @pytest.mark.parametrize(
        "competencia, esperado",
        [
            ("2026-10", True),
            ("2026-01", True),
            ("2026-12", True),
            ("2026-13", False),
            ("2026-00", False),
            ("2026-10\n", False),
            ("\uff12\uff10\uff12\uff16-10", False),  # dígitos não ASCII (largura total)
            (" 2026-10", False),
            ("", False),
            (None, False),
            (202610, False),
        ],
    )
    def test_funcao_competencia_valida(self, competencia, esperado):
        assert rules.competencia_valida(competencia) is esperado


class TestRN010Negativos:
    @pytest.mark.req("RN-010")
    @pytest.mark.parametrize(
        "valor, esperado",
        [("50", True), ("0.01", True), ("0", False), ("-25", False), ("-0.01", False)],
    )
    def test_valor_elegivel(self, valor, esperado):
        assert rules.valor_elegivel(Decimal(valor)) is esperado

    @pytest.mark.req("RN-010")
    @pytest.mark.parametrize("categoria", ["alimentacao", "hospedagem", "coworking"])
    def test_negativo_rejeitado_em_qualquer_categoria(self, categoria):
        despesa = d(categoria=categoria, valor="-25", fornecedor="Hotel X")
        assert um(despesa) == (REJEITADO, "0.00")

    @pytest.mark.req("RN-010")
    def test_estorno_nao_abate_o_acumulado_do_dia(self):
        resultado = avaliar([d("d-1", valor="-45"), d("d-2", valor="50")])
        assert resultado == [(REJEITADO, "0.00"), (APROVADO, "50.00")]

    @pytest.mark.req("RN-010")
    def test_negativo_com_categoria_invalida_sai_como_rejeitado_simples(self):
        # spec §8: RN-010 (passo 1) vem antes de RN-008 (passo 2).
        assert um(d(categoria="x", valor="-1")) == (REJEITADO, "0.00")

    @pytest.mark.req("RN-010")
    def test_valor_que_arredonda_para_zero_e_rejeitado(self):
        assert um(d(valor="0.004")) == (REJEITADO, "0.00")


class TestRN011Precisao:
    @pytest.mark.req("RN-011")
    @pytest.mark.parametrize(
        "valor, esperado",
        [
            ("45.50", "45.50"),
            ("80.456", "80.46"),
            ("60.005", "60.01"),
            ("80.454", "80.45"),
            ("60.002", "60.00"),
            ("100", "100.00"),
            (33.333, "33.33"),
        ],
    )
    def test_valor_reembolsado_com_duas_casas(self, valor, esperado):
        assert um(d(categoria="coworking", valor=valor)) == (APROVADO, esperado)

    @pytest.mark.req("RN-011")
    def test_arredonda_antes_de_aplicar_a_nota_fiscal(self):
        # 100.004 -> 100.00 (isento); 100.005 -> 100.01 (exige NF).
        assert um(d("a", "coworking", "100.004", nf=False)) == (APROVADO, "100.00")
        assert um(d("b", "coworking", "100.005", nf=False)) == (REJEITADO, "0.00")

    @pytest.mark.req("RN-011")
    def test_arredonda_antes_do_limite(self):
        # 60.004 -> 60.00: cabe exatamente no teto, sem virar parcial.
        assert um(d(valor="60.004")) == (APROVADO, "60.00")
        assert um(d(valor="60.005")) == (PARCIAL, "60.00")

    @pytest.mark.req("RN-011")
    def test_motor_normaliza_valor_mesmo_sem_passar_pelo_schema(self):
        crua = Despesa.model_construct(
            id="d-1",
            data=date(2026, 10, 15),
            categoria="coworking",
            descricao="x",
            fornecedor="y",
            valor=Decimal("80.456"),
            tem_nota_fiscal=True,
        )
        bruta = solicitacao([d()]).model_copy(update={"despesas": [crua]})
        (item,) = itens(engine.avaliar(bruta))
        assert str(item.valor_reembolsado) == "80.46"

    @pytest.mark.req("RN-011")
    def test_normalizar_valor(self):
        assert str(rules.normalizar_valor(Decimal("80.456"))) == "80.46"
        assert str(rules.normalizar_valor(Decimal("5"))) == "5.00"

    @pytest.mark.req("RN-011")
    def test_saida_nunca_usa_float(self):
        resultado = engine.avaliar(solicitacao([d(valor="33.333")]))
        assert all(isinstance(i.valor_reembolsado, Decimal) for i in itens(resultado))


# --------------------------------------------------------------------------
# T-006 — RN-008
# --------------------------------------------------------------------------


@pytest.mark.req("RN-008")
def test_categorias_permitidas():
    permitidas = {
        "alimentacao": (APROVADO, "10.00"),
        "coworking": (APROVADO, "10.00"),
        "hospedagem": (REJEITADO, "0.00"),  # sem fornecedor de viagem (RN-003)
        "transporte_urbano": (APROVADO, "10.00"),
    }
    for categoria, esperado in permitidas.items():
        assert um(d(categoria=categoria)) == esperado
        assert rules.categoria_permitida(categoria)
    hotel = d(categoria="hospedagem", fornecedor="Hotel X", valor="10")
    assert um(hotel) == (APROVADO, "10.00")


class TestRN008Categorias:
    @pytest.mark.req("RN-008")
    @pytest.mark.parametrize(
        "categoria",
        [
            "estacionamento",
            "alimentação",
            "Hospedagem",
            "ALIMENTACAO",
            "transporte urbano",
            "transporte-urbano",
            " alimentacao",
            "alimentacao ",
            "Coworking",
            "",
        ],
    )
    def test_grafia_diferente_e_rejeitada(self, categoria):
        assert um(d(categoria=categoria, valor="80")) == (CATEGORIA_INVALIDA, "0.00")
        assert not rules.categoria_permitida(categoria)

    @pytest.mark.req("RN-008")
    def test_categoria_invalida_nao_gera_viagem_nem_consome_teto(self):
        resultado = avaliar(
            [
                d(
                    "d-1",
                    categoria="Hospedagem",
                    fornecedor="Hotel X",
                    descricao="3 noites",
                ),
                d("d-2", valor="85"),
            ]
        )
        assert resultado == [(CATEGORIA_INVALIDA, "0.00"), (PARCIAL, "60.00")]


# --------------------------------------------------------------------------
# T-012 — RN-007
# --------------------------------------------------------------------------


@pytest.mark.req("RN-007")
def test_tratar_duplicatas():
    antigo = d(
        "101", categoria="alimentacao", valor="50", fornecedor="Restaurante Sabor"
    )
    novo = d("105", categoria="alimentacao", valor="50", fornecedor="Restaurante Sabor")
    assert avaliar([antigo, novo]) == [(DUPLICIDADE, "0.00"), (APROVADO, "50.00")]


class TestRN007Duplicatas:
    @pytest.mark.req("RN-007")
    def test_ordem_de_lancamento_nao_importa_vale_o_id_mais_recente(self):
        antigo = d("101", valor="50")
        novo = d("105", valor="50")
        assert avaliar([novo, antigo]) == [(APROVADO, "50.00"), (DUPLICIDADE, "0.00")]

    @pytest.mark.req("RN-007")
    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("valor", "45"),  # cenário 02
            ("data", "2026-10-16"),
            ("categoria", "transporte_urbano"),
            ("fornecedor", "Outro"),
            ("descricao", "Outra"),
        ],
    )
    def test_variacao_em_um_campo_nao_e_duplicata(self, campo, valor):
        a = d("201", "coworking", "35")
        b = d("202", **{"categoria": "coworking", "valor": "35", campo: valor})
        resultado = avaliar([a, b])
        assert [s for s, _ in resultado] == [APROVADO, APROVADO]

    @pytest.mark.req("RN-007")
    def test_nota_fiscal_so_e_cobrada_do_registro_mais_recente(self):
        # cenário 03: o 301 (sem NF) é descartado; o 305 (com NF) segue.
        antigo = d("301", "coworking", "150", nf=False)
        novo = d("305", "coworking", "150", nf=True)
        assert avaliar([antigo, novo]) == [(DUPLICIDADE, "0.00"), (APROVADO, "150.00")]

    @pytest.mark.req("RN-007")
    def test_mais_recente_sem_nota_fiscal_e_rejeitado_pela_rn004(self):
        antigo = d("301", "coworking", "150", nf=True)
        novo = d("305", "coworking", "150", nf=False)
        assert avaliar([antigo, novo]) == [(DUPLICIDADE, "0.00"), (REJEITADO, "0.00")]

    @pytest.mark.req("RN-007")
    def test_so_o_mais_recente_consome_o_teto(self):
        resultado = avaliar([d("101", valor="50"), d("105", valor="50")])
        assert resultado == [(DUPLICIDADE, "0.00"), (APROVADO, "50.00")]

    @pytest.mark.req("RN-007")
    def test_ids_comparados_de_forma_natural(self):
        resultado = avaliar([d("d-10", valor="20"), d("d-9", valor="20")])
        assert resultado == [(APROVADO, "20.00"), (DUPLICIDADE, "0.00")]

    @pytest.mark.req("RN-007")
    def test_tres_duplicatas_mantem_apenas_a_mais_recente(self):
        resultado = avaliar([d("d-2"), d("d-3"), d("d-1")])
        assert resultado == [
            (DUPLICIDADE, "0.00"),
            (APROVADO, "10.00"),
            (DUPLICIDADE, "0.00"),
        ]

    @pytest.mark.req("RN-007")
    def test_empate_de_id_vale_o_ultimo_lancado(self):
        a = d("d-1", descricao="mesma")
        resultado = avaliar([a, a])
        assert resultado == [(DUPLICIDADE, "0.00"), (APROVADO, "10.00")]

    @pytest.mark.req("RN-007")
    def test_grupos_de_duplicatas_sao_independentes(self):
        resultado = avaliar(
            [
                d("1", valor="10"),
                d("2", valor="10"),
                d("3", valor="20"),
                d("4", valor="20"),
            ]
        )
        assert [s for s, _ in resultado] == [
            DUPLICIDADE,
            APROVADO,
            DUPLICIDADE,
            APROVADO,
        ]

    @pytest.mark.req("RN-007")
    def test_fornecedor_e_comparado_sem_diferenciar_caixa(self):
        resultado = avaliar(
            [d("1", fornecedor="CANTINA"), d("2", fornecedor="cantina")]
        )
        assert [s for s, _ in resultado] == [DUPLICIDADE, APROVADO]

    @pytest.mark.req("RN-007")
    def test_invalidas_antes_da_deduplicacao_nao_participam(self):
        # as duas são "categoria inválida"; nenhuma vira "rejeitado" por duplicidade.
        resultado = avaliar([d("1", categoria="x"), d("2", categoria="x")])
        assert [s for s, _ in resultado] == [CATEGORIA_INVALIDA, CATEGORIA_INVALIDA]

    @pytest.mark.req("RN-007")
    def test_chave_id(self):
        assert rules.chave_id("d-9") < rules.chave_id("d-10")
        assert rules.chave_id("101") < rules.chave_id("105")
        assert rules.chave_id("abc") == rules.chave_id("abc")
        assert rules.chave_id("a-1") < rules.chave_id("b-1")

    @pytest.mark.req("RN-007")
    def test_posicoes_duplicadas(self):
        despesas = solicitacao([d("1"), d("2"), d("3", valor="99")]).despesas
        assert rules.posicoes_duplicadas(despesas) == {0}
        assert rules.posicoes_duplicadas([]) == set()


# --------------------------------------------------------------------------
# T-007 — RN-006
# --------------------------------------------------------------------------


@pytest.mark.req("RN-006")
def test_vigencia_competencia():
    casos = {
        "2026-10-15": APROVADO,
        "2026-10-01": APROVADO,  # início inclusivo
        "2026-10-31": APROVADO,  # fim inclusivo
        "2026-09-30": REJEITADO,
        "2026-11-01": REJEITADO,
    }
    for data, status in casos.items():
        esperado = (status, "10.00" if status == APROVADO else "0.00")
        assert um(d(data=data)) == esperado, data


class TestRN006Periodo:
    @pytest.mark.req("RN-006")
    def test_funcao_dentro_da_competencia(self):
        periodo = Periodo(competencia="2026-10", inicio="2026-10-01", fim="2026-10-31")
        assert rules.dentro_da_competencia(date(2026, 10, 1), periodo)
        assert rules.dentro_da_competencia(date(2026, 10, 31), periodo)
        assert not rules.dentro_da_competencia(date(2026, 9, 30), periodo)
        assert not rules.dentro_da_competencia(date(2026, 11, 1), periodo)

    @pytest.mark.req("RN-006")
    def test_periodo_de_um_dia(self):
        assert um(d(data="2026-10-05"), inicio="2026-10-05", fim="2026-10-05") == (
            APROVADO,
            "10.00",
        )

    @pytest.mark.req("RN-006")
    def test_periodo_invertido_rejeita_tudo(self):
        assert um(d(), inicio="2026-10-31", fim="2026-10-01") == (REJEITADO, "0.00")

    @pytest.mark.req("RN-006")
    def test_fora_do_periodo_nao_consome_teto(self):
        resultado = avaliar(
            [
                d("1", data="2026-11-01", valor="60"),
                d("2", data="2026-10-31", valor="60"),
            ],
            fim="2026-10-31",
        )
        assert resultado == [(REJEITADO, "0.00"), (APROVADO, "60.00")]

    @pytest.mark.req("RN-006")
    def test_datas_de_outro_mes_dentro_do_periodo_informado_sao_aceitas(self):
        # a competência (texto) não é conferida contra inicio/fim.
        assert um(d(data="2026-11-10"), inicio="2026-11-01", fim="2026-11-30") == (
            APROVADO,
            "10.00",
        )


# --------------------------------------------------------------------------
# T-008 — RN-005 e RN-003
# --------------------------------------------------------------------------


def hospedagem(
    id_="h-1",
    data="2026-10-10",
    descricao="Hospedagem a trabalho",
    fornecedor="Hotel Beira Mar",
    valor="200",
    nf=True,
):
    return d(id_, "hospedagem", valor, data, descricao, fornecedor, nf)


@pytest.mark.req("RN-003")
@pytest.mark.req("RN-005")
def test_contexto_viagem_e_hospedagem():
    # RN-003: limite de R$ 250,00 por diária, fornecedor case-insensitive
    assert um(hospedagem(valor="250", fornecedor="Hotel Beira Mar")) == (
        APROVADO,
        "250.00",
    )
    assert um(hospedagem(valor="180", fornecedor="AIRBNB Studio Centro")) == (
        APROVADO,
        "180.00",
    )
    assert um(hospedagem(valor="300", fornecedor="Hostel Central")) == (
        PARCIAL,
        "250.00",
    )
    assert um(hospedagem(valor="200", fornecedor="Residência Particular João")) == (
        REJEITADO,
        "0.00",
    )
    # RN-005: diárias lidas da descrição e viagem com limites ampliados
    assert rules.numero_de_diarias("Reserva de 3 noites") == 3
    assert rules.dias_de_viagem("Reserva de 3 noites") == 4
    assert rules.numero_de_diarias("Hospedagem a trabalho") == 1
    comida = d("c-1", valor="85", data="2026-10-10")
    assert avaliar([hospedagem(), comida]) == [
        (APROVADO, "200.00"),
        (APROVADO, "85.00"),
    ]


class TestRN003Hospedagem:
    @pytest.mark.req("RN-003")
    @pytest.mark.parametrize(
        "palavra", ["hotel", "airbnb", "pousada", "hostel", "camping"]
    )
    def test_cada_palavra_chave(self, palavra):
        despesa = hospedagem(fornecedor=f"Meu {palavra.upper()} Legal", valor="100")
        assert um(despesa) == (APROVADO, "100.00")

    @pytest.mark.req("RN-003")
    def test_palavra_chave_dentro_de_outra_palavra(self):
        assert um(hospedagem(fornecedor="Pousadinha do Zé", valor="100")) == (
            REJEITADO,
            "0.00",
        )
        assert um(hospedagem(fornecedor="Hoteleira Sul", valor="100")) == (
            APROVADO,
            "100.00",
        )

    @pytest.mark.req("RN-003")
    def test_limite_inclusivo_e_excedente_parcial(self):
        assert um(hospedagem(valor="250.00")) == (APROVADO, "250.00")
        assert um(hospedagem(valor="250.01")) == (PARCIAL, "250.00")

    @pytest.mark.req("RN-003")
    @pytest.mark.parametrize(
        "descricao, valor, esperado",
        [
            ("Hotel Rio - 2 diarias", "480", (APROVADO, "480.00")),
            ("Hotel Rio - 2 diarias", "500", (APROVADO, "500.00")),
            ("Hotel Rio - 2 diarias", "520", (PARCIAL, "500.00")),
            ("Airbnb 3 noites", "690", (APROVADO, "690.00")),
            ("Airbnb 3 noites", "800", (PARCIAL, "750.00")),  # cobra 3, não 4
        ],
    )
    def test_teto_e_por_diaria(self, descricao, valor, esperado):
        assert um(hospedagem(descricao=descricao, valor=valor)) == esperado

    @pytest.mark.req("RN-003")
    def test_hospedagem_nao_recebe_ampliacao_de_viagem(self):
        assert um(hospedagem(valor="400")) == (PARCIAL, "250.00")

    @pytest.mark.req("RN-003")
    def test_outra_categoria_com_palavra_chave_segue_as_proprias_regras(self):
        # cenário 04: "Hotel e Restauração" em alimentação não é hospedagem.
        despesa = d(valor="100", fornecedor="Hotel e Restauração", descricao="x")
        assert um(despesa) == (PARCIAL, "60.00")
        assert not rules.hospedagem_de_viagem(Despesa(**d(fornecedor="Hotel")))

    @pytest.mark.req("RN-003")
    def test_hospedagem_aceita_fornecedor_nao_normalizado(self):
        crua = Despesa.model_construct(
            id="h-1",
            data=date(2026, 10, 10),
            categoria="hospedagem",
            descricao="x",
            fornecedor="HOTEL X",
            valor=Decimal("100.00"),
            tem_nota_fiscal=True,
        )
        assert rules.hospedagem_de_viagem(crua)

    @pytest.mark.req("RN-003")
    def test_avaliar_hospedagem(self):
        despesa = Despesa(**hospedagem(valor="300"))
        status, valor, justificativa = rules.avaliar_hospedagem(despesa)
        assert (status, valor) == (PARCIAL, Decimal("250.00"))
        assert "RN-003" in justificativa
        sem_hotel = Despesa(**hospedagem(valor="300", fornecedor="Casa"))
        status, valor, _ = rules.avaliar_hospedagem(sem_hotel)
        assert (status, valor) == (REJEITADO, Decimal("0.00"))


class TestRN005Diarias:
    @pytest.mark.req("RN-005")
    @pytest.mark.parametrize(
        "descricao, diarias, dias",
        [
            ("Hospedagem a trabalho", 1, 1),  # cenário 05: sem número
            ("", 1, 1),
            ("Reserva de 3 noites", 3, 4),  # cenário 04: noites somam +1 dia
            ("Reserva de 3 diárias", 3, 3),
            ("Hotel Rio - 2 diarias", 2, 2),
            ("Airbnb 3 NOITES", 3, 4),
            ("1 noite", 1, 2),
            ("Noite extra", 1, 1),  # "noite" sem número: 1 diária
            ("0 noites", 1, 2),  # zero vale 1
            ("12 diárias", 12, 12),
            ("2 noites 3 pessoas", 2, 3),  # primeiro número
        ],
    )
    def test_diarias_e_dias_de_viagem(self, descricao, diarias, dias):
        assert rules.numero_de_diarias(descricao) == diarias
        assert rules.dias_de_viagem(descricao) == dias

    @pytest.mark.req("RN-005")
    def test_dias_em_viagem(self):
        hospedagens = [
            Despesa(**hospedagem(data="2026-10-10", descricao="3 noites")),
            Despesa(**hospedagem("h-2", data="2026-10-13", descricao="2 diarias")),
        ]
        assert rules.dias_em_viagem(hospedagens) == {
            date(2026, 10, dia) for dia in (10, 11, 12, 13, 14)
        }
        assert rules.dias_em_viagem([]) == set()

    @pytest.mark.req("RN-005")
    def test_dias_em_viagem_atravessa_a_virada_de_mes(self):
        h = Despesa(**hospedagem(data="2026-10-30", descricao="3 noites"))
        assert date(2026, 11, 2) in rules.dias_em_viagem([h])


class TestRN005Ampliacao:
    @pytest.mark.req("RN-005")
    def test_limites_diarios(self):
        assert rules.limite_diario("alimentacao", False) == Decimal("60.00")
        assert rules.limite_diario("alimentacao", True) == Decimal("90.00")
        assert rules.limite_diario("transporte_urbano", False) == Decimal("80.00")
        assert rules.limite_diario("transporte_urbano", True) == Decimal("120.00")

    @pytest.mark.req("RN-005")
    @pytest.mark.parametrize(
        "fornecedor",
        ["Hotel Beira Mar", "AIRBNB Studio", "Pousada Recanto", "Camping Verde"],
    )
    def test_cenarios_1_e_2_alimentacao_em_viagem(self, fornecedor):
        base = [hospedagem(fornecedor=fornecedor)]
        assert avaliar(base + [d("c", valor="85", data="2026-10-10")])[1] == (
            APROVADO,
            "85.00",
        )
        assert avaliar(base + [d("c", valor="110", data="2026-10-10")])[1] == (
            PARCIAL,
            "90.00",
        )

    @pytest.mark.req("RN-005")
    def test_cenario_3_transporte_em_viagem(self):
        base = [hospedagem(fornecedor="Pousada Recanto")]
        t115 = d("t", "transporte_urbano", "115", "2026-10-10")
        t130 = d("t", "transporte_urbano", "130", "2026-10-10")
        assert avaliar(base + [t115])[1] == (APROVADO, "115.00")
        assert avaliar(base + [t130])[1] == (PARCIAL, "120.00")

    @pytest.mark.req("RN-005")
    def test_cenario_4_todos_os_dias_da_viagem_sao_ampliados(self):
        hosp = hospedagem(
            descricao="Reserva de 3 noites", fornecedor="Hostel Central", valor="600"
        )
        refeicoes = [
            d(f"a-{dia}", valor="90", data=f"2026-10-{dia}") for dia in (10, 11, 12, 13)
        ]
        resultado = avaliar([hosp] + refeicoes)
        assert resultado[0] == (APROVADO, "600.00")
        assert resultado[1:] == [(APROVADO, "90.00")] * 4
        # soma do período: 4 x 90 = 360
        assert sum(Decimal(v) for _, v in resultado[1:]) == Decimal("360.00")

    @pytest.mark.req("RN-005")
    def test_dias_fora_da_viagem_usam_limite_padrao(self):
        hosp = hospedagem(descricao="Reserva de 3 noites")
        antes = d("a", valor="90", data="2026-10-09")
        depois = d("b", valor="90", data="2026-10-14")
        resultado = avaliar([hosp, antes, depois])
        assert resultado[1:] == [(PARCIAL, "60.00"), (PARCIAL, "60.00")]

    @pytest.mark.req("RN-005")
    def test_diarias_nao_somam_dia_extra(self):
        hosp = hospedagem(descricao="2 diarias")
        no_dia_2 = d("a", valor="90", data="2026-10-11")
        no_dia_3 = d("b", valor="90", data="2026-10-12")
        assert avaliar([hosp, no_dia_2, no_dia_3])[1:] == [
            (APROVADO, "90.00"),
            (PARCIAL, "60.00"),
        ]

    @pytest.mark.req("RN-005")
    def test_cenario_5_sem_numero_amplia_so_o_dia_da_hospedagem(self):
        hosp = hospedagem(descricao="Hospedagem a trabalho", fornecedor="Camping Verde")
        dia = d("a", valor="90", data="2026-10-10")
        t = d("t", "transporte_urbano", "120", "2026-10-10")
        proximo = d("b", valor="90", data="2026-10-11")
        resultado = avaliar([hosp, dia, t, proximo])
        assert resultado[1:] == [
            (APROVADO, "90.00"),
            (APROVADO, "120.00"),
            (PARCIAL, "60.00"),
        ]

    @pytest.mark.req("RN-005")
    @pytest.mark.parametrize(
        "hosp",
        [
            hospedagem(fornecedor="Residência Particular"),  # sem palavra-chave
            d(
                "d-0", "alimentacao", "50", fornecedor="Hotel Restaurante"
            ),  # outra categoria
        ],
    )
    def test_cenario_6_sem_viagem_aplica_limite_padrao(self, hosp):
        resultado = avaliar([hosp, d("c", valor="80", data="2026-10-10")])
        assert resultado[1] == (PARCIAL, "60.00")

    @pytest.mark.req("RN-005")
    def test_sem_hospedagem_no_mesmo_dia_aplica_limite_padrao(self):
        assert um(d(valor="80")) == (PARCIAL, "60.00")

    @pytest.mark.req("RN-005")
    def test_viagens_sobrepostas_ampliam_uma_vez_so(self):
        h1 = hospedagem("h-1", data="2026-10-10", descricao="2 diarias")
        h2 = hospedagem("h-2", data="2026-10-11", descricao="2 diarias", valor="210")
        comida = d("c", valor="200", data="2026-10-11")
        assert avaliar([h1, h2, comida])[2] == (PARCIAL, "90.00")

    @pytest.mark.req("RN-005")
    def test_viagem_vale_mesmo_se_hospedagem_for_rejeitada_por_nota_fiscal(self):
        hosp = hospedagem(valor="200", nf=False)  # > 100 sem NF
        comida = d("c", valor="85", data="2026-10-10")
        assert avaliar([hosp, comida]) == [(REJEITADO, "0.00"), (APROVADO, "85.00")]

    @pytest.mark.req("RN-005")
    def test_hospedagem_fora_da_competencia_nao_cria_viagem(self):
        hosp = hospedagem(data="2026-09-30", descricao="3 noites")
        comida = d("c", valor="85", data="2026-10-01")
        assert avaliar([hosp, comida]) == [(REJEITADO, "0.00"), (PARCIAL, "60.00")]

    @pytest.mark.req("RN-005")
    def test_hospedagem_duplicada_antiga_nao_cria_viagem_propria(self):
        antiga = hospedagem("h-1", descricao="Hospedagem")
        nova = hospedagem("h-2", descricao="Hospedagem")
        comida = d("c", valor="85", data="2026-10-10")
        assert avaliar([antiga, nova, comida]) == [
            (DUPLICIDADE, "0.00"),
            (APROVADO, "200.00"),
            (APROVADO, "85.00"),
        ]


# --------------------------------------------------------------------------
# T-009 — RN-001
# --------------------------------------------------------------------------


@pytest.mark.req("RN-001")
def test_limite_alimentacao():
    assert um(d(valor="45")) == (APROVADO, "45.00")
    assert um(d(valor="60")) == (APROVADO, "60.00")
    assert um(d(valor="85")) == (PARCIAL, "60.00")
    # cenário 4: outra categoria não é limitada por esta regra
    assert um(d(categoria="coworking", valor="85")) == (APROVADO, "85.00")


class TestRN001Alimentacao:
    @pytest.mark.req("RN-001")
    def test_somatorio_do_dia_abaixo_do_limite(self):
        assert avaliar([d("1", valor="20"), d("2", valor="25")]) == [
            (APROVADO, "20.00"),
            (APROVADO, "25.00"),
        ]

    @pytest.mark.req("RN-001")
    def test_somatorio_exatamente_no_limite(self):
        assert avaliar([d("1", valor="35"), d("2", valor="25")]) == [
            (APROVADO, "35.00"),
            (APROVADO, "25.00"),
        ]

    @pytest.mark.req("RN-001")
    def test_caso_de_borda_40_mais_30(self):
        # spec §7: a primeira integral, a segunda parcial até o teto de 60.
        assert avaliar([d("1", valor="40"), d("2", valor="30")]) == [
            (APROVADO, "40.00"),
            (PARCIAL, "20.00"),
        ]

    @pytest.mark.req("RN-001")
    def test_teto_esgotado_rejeita_as_demais(self):
        resultado = avaliar([d("1", valor="72.50"), d("2", valor="38")])
        assert resultado == [(PARCIAL, "60.00"), (REJEITADO, "0.00")]

    @pytest.mark.req("RN-001")
    def test_teto_consumido_na_ordem_de_lancamento_nao_de_id(self):
        resultado = avaliar([d("9", valor="40"), d("1", valor="30")])
        assert resultado == [(APROVADO, "40.00"), (PARCIAL, "20.00")]

    @pytest.mark.req("RN-001")
    def test_dias_diferentes_tem_tetos_independentes(self):
        resultado = avaliar(
            [
                d("1", valor="60", data="2026-10-14"),
                d("2", valor="60", data="2026-10-15"),
            ]
        )
        assert resultado == [(APROVADO, "60.00"), (APROVADO, "60.00")]

    @pytest.mark.req("RN-001")
    def test_alimentacao_nao_divide_teto_com_transporte(self):
        resultado = avaliar([d("1", valor="60"), d("2", "transporte_urbano", "80")])
        assert resultado == [(APROVADO, "60.00"), (APROVADO, "80.00")]

    @pytest.mark.req("RN-001")
    def test_centavos_no_excedente(self):
        resultado = avaliar([d("1", valor="59.99"), d("2", valor="0.02")])
        assert resultado == [(APROVADO, "59.99"), (PARCIAL, "0.01")]

    @pytest.mark.req("RN-001")
    def test_limite_ampliado_em_viagem_para_somatorio_do_dia(self):
        hosp = hospedagem()
        resultado = avaliar(
            [
                hosp,
                d("1", valor="50", data="2026-10-10", descricao="almoco"),
                d("2", valor="50", data="2026-10-10", descricao="jantar"),
            ]
        )
        assert resultado[1:] == [(APROVADO, "50.00"), (PARCIAL, "40.00")]

    @pytest.mark.req("RN-001")
    def test_aplicar_teto(self):
        assert rules.aplicar_teto(Decimal("45"), Decimal("60")) == (
            APROVADO,
            Decimal("45.00"),
        )
        assert rules.aplicar_teto(Decimal("85"), Decimal("60")) == (
            PARCIAL,
            Decimal("60.00"),
        )
        assert rules.aplicar_teto(Decimal("85"), Decimal("0")) == (
            REJEITADO,
            Decimal("0.00"),
        )
        assert rules.aplicar_teto(Decimal("85"), Decimal("-5")) == (
            REJEITADO,
            Decimal("0.00"),
        )


# --------------------------------------------------------------------------
# T-010 — RN-002
# --------------------------------------------------------------------------


@pytest.mark.req("RN-002")
def test_limite_transporte():
    assert um(d(categoria="transporte_urbano", valor="75")) == (APROVADO, "75.00")
    assert um(d(categoria="transporte_urbano", valor="80")) == (APROVADO, "80.00")
    assert um(d(categoria="transporte_urbano", valor="105")) == (PARCIAL, "80.00")
    # cenário 4: outra categoria não é limitada por esta regra
    assert um(d(categoria="coworking", valor="105")) == (APROVADO, "105.00")


class TestRN002Transporte:
    @pytest.mark.req("RN-002")
    def test_somatorio_do_dia_com_excedente(self):
        resultado = avaliar(
            [
                d("1", "transporte_urbano", "50", descricao="ida"),
                d("2", "transporte_urbano", "50", descricao="volta"),
            ]
        )
        assert resultado == [(APROVADO, "50.00"), (PARCIAL, "30.00")]

    @pytest.mark.req("RN-002")
    def test_teto_esgotado(self):
        resultado = avaliar(
            [
                d("1", "transporte_urbano", "80", descricao="ida"),
                d("2", "transporte_urbano", "80", descricao="volta"),
            ]
        )
        assert resultado == [(APROVADO, "80.00"), (REJEITADO, "0.00")]

    @pytest.mark.req("RN-002")
    def test_dia_de_viagem_limite_ampliado(self):
        resultado = avaliar(
            [
                hospedagem(),
                d("1", "transporte_urbano", "70", "2026-10-10", "ida"),
                d("2", "transporte_urbano", "70", "2026-10-10", "volta"),
            ]
        )
        assert resultado[1:] == [(APROVADO, "70.00"), (PARCIAL, "50.00")]

    @pytest.mark.req("RN-002")
    def test_dia_de_viagem_so_amplia_o_proprio_dia(self):
        resultado = avaliar(
            [hospedagem(), d("1", "transporte_urbano", "120", "2026-10-11")]
        )
        assert resultado[1] == (PARCIAL, "80.00")


# --------------------------------------------------------------------------
# T-011 — RN-004
# --------------------------------------------------------------------------


@pytest.mark.req("RN-004")
def test_obrigatoriedade_nota_fiscal():
    assert um(d("a", "coworking", "100.01", nf=True)) == (APROVADO, "100.01")
    assert um(d("b", "coworking", "150", nf=False)) == (REJEITADO, "0.00")
    assert um(d("c", "coworking", "100", nf=False)) == (APROVADO, "100.00")
    assert um(d("d", "coworking", "45.50", nf=False)) == (APROVADO, "45.50")


class TestRN004NotaFiscal:
    @pytest.mark.req("RN-004")
    @pytest.mark.parametrize(
        "valor, nf, esperado",
        [
            ("100.01", True, False),
            ("150", False, True),
            ("100.01", False, True),
            ("100.00", False, False),
            ("45.50", False, False),
            ("100.00", True, False),
        ],
    )
    def test_falta_nota_fiscal(self, valor, nf, esperado):
        despesa = Despesa(**d(categoria="coworking", valor=valor, nf=nf))
        assert rules.falta_nota_fiscal(despesa) is esperado

    @pytest.mark.req("RN-004")
    def test_considera_o_valor_da_despesa_e_nao_o_reembolsado(self):
        # alimentação de 120 sem NF seria parcial (60), mas é rejeitada.
        assert um(d(valor="120", nf=False)) == (REJEITADO, "0.00")
        assert um(d(valor="120", nf=True)) == (PARCIAL, "60.00")

    @pytest.mark.req("RN-004")
    def test_exemplo_do_desafio_100_e_100_01(self):
        a = d("d-003", "transporte_urbano", "100.00", nf=False)
        b = d("d-004", "transporte_urbano", "100.01", nf=False)
        assert avaliar([a, b]) == [(PARCIAL, "80.00"), (REJEITADO, "0.00")]

    @pytest.mark.req("RN-004")
    def test_vale_para_hospedagem(self):
        assert um(hospedagem(valor="200", nf=False)) == (REJEITADO, "0.00")
        assert um(hospedagem(valor="100", nf=False)) == (APROVADO, "100.00")

    @pytest.mark.req("RN-004")
    def test_rejeitada_por_nota_fiscal_nao_consome_o_teto_do_dia(self):
        resultado = avaliar([d("1", valor="120", nf=False), d("2", valor="40")])
        assert resultado == [(REJEITADO, "0.00"), (APROVADO, "40.00")]

    @pytest.mark.req("RN-004")
    def test_nota_fiscal_nao_altera_despesa_ja_rejeitada(self):
        assert um(d(categoria="x", valor="500", nf=False)) == (
            CATEGORIA_INVALIDA,
            "0.00",
        )

    @pytest.mark.req("RN-004")
    def test_despesa_parcial_com_nota_segue_parcial(self):
        assert um(d(valor="150", nf=True)) == (PARCIAL, "60.00")


# --------------------------------------------------------------------------
# T-021 — orquestrador
# --------------------------------------------------------------------------


@pytest.mark.req("RN-001")
@pytest.mark.req("RN-002")
@pytest.mark.req("RN-003")
@pytest.mark.req("RN-004")
@pytest.mark.req("RN-005")
@pytest.mark.req("RN-006")
@pytest.mark.req("RN-007")
@pytest.mark.req("RN-008")
@pytest.mark.req("RN-009")
@pytest.mark.req("RN-010")
@pytest.mark.req("RN-011")
def test_esteira_completa():
    entrada = SolicitacaoReembolso.model_validate_json(EXEMPLO.read_text("utf-8"))
    resultado = engine.avaliar(entrada)

    esperado = {
        "d-001": (PARCIAL, "60.00"),  # 72,50 limitado ao teto de 60 (RN-001)
        "d-002": (REJEITADO, "0.00"),  # teto do dia já esgotado
        "d-003": (PARCIAL, "80.00"),  # 100,00 sem NF é isento (RN-004); teto 80
        "d-004": (REJEITADO, "0.00"),  # 100,01 sem NF (RN-004)
        "d-005": (APROVADO, "89.00"),  # coworking
        "d-006": (DUPLICIDADE, "0.00"),  # duplicata antiga (RN-007)
        "d-007": (APROVADO, "54.90"),
        "d-008": (REJEITADO, "0.00"),  # abril, fora da competência (RN-006)
        "d-009": (REJEITADO, "0.00"),  # estorno (RN-010)
        "d-010": (APROVADO, "480.00"),  # 2 diárias, 240/diária (RN-003)
        "d-011": (APROVADO, "33.33"),  # 33,333 arredondado (RN-011)
        "d-012": (APROVADO, "47.20"),
        "d-013": (REJEITADO, "0.00"),  # 690 sem NF (RN-004)
        "d-014": (CATEGORIA_INVALIDA, "0.00"),  # "ALIMENTACAO" (RN-008)
    }
    obtido = {i.id: (i.status_item, str(i.valor_reembolsado)) for i in itens(resultado)}
    assert obtido == esperado


class TestEstruturaDoResultado:
    def test_cabecalho_e_historico(self):
        resultado = engine.avaliar(solicitacao([d()]))
        assert isinstance(resultado, ResultadoAuditoria)
        assert resultado.colaborador.id == "c-1"
        assert resultado.colaborador.centro_custo == "CC-X"
        (historico,) = resultado.historico_despesas
        assert historico.competencia == "2026-10"
        assert historico.centro_custo == "CC-X"

    def test_preserva_ordem_e_dados_das_despesas(self):
        despesas = [d("b", fornecedor="Cantina"), d("a", descricao="Jantar", valor="5")]
        resultado = engine.avaliar(solicitacao(despesas))
        primeira, segunda = itens(resultado)
        assert (primeira.id, segunda.id) == ("b", "a")
        assert primeira.fornecedor == "cantina"
        assert segunda.descricao == "Jantar"
        assert segunda.data == date(2026, 10, 15)

    def test_solicitacao_sem_despesas(self):
        resultado = engine.avaliar(solicitacao([]))
        assert itens(resultado) == []

    def test_nao_altera_a_entrada(self):
        entrada = solicitacao([d(valor="85")])
        antes = entrada.model_dump()
        engine.avaliar(entrada)
        assert entrada.model_dump() == antes

    def test_resultado_serializa_em_json_valido(self):
        resultado = engine.avaliar(solicitacao([d(valor="85")]))
        dados = json.loads(resultado.model_dump_json())
        assert dados["historico_despesas"][0]["despesas"][0]["status_item"] == PARCIAL

    def test_motor_e_deterministico(self):
        entrada = solicitacao([d("1", valor="40"), d("2", valor="30")])
        assert engine.avaliar(entrada) == engine.avaliar(entrada)


def test_motor_nao_depende_de_io_nem_de_interface():
    proibidos = {
        "os",
        "pathlib",
        "json",
        "shutil",
        "sqlite3",
        "tempfile",
        "webview",
        "storage",
    }
    for arquivo in (RAIZ / "src" / "core").glob("*.py"):
        arvore = ast.parse(arquivo.read_text("utf-8"))
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.add(no.module.split(".")[0])
        assert not (importados & proibidos), (arquivo.name, importados & proibidos)
        assert "open(" not in arquivo.read_text("utf-8"), arquivo.name


# --------------------------------------------------------------------------
# T-023 — justificativa por item
# --------------------------------------------------------------------------


def justificativas(despesas, **periodo):
    resultado = engine.avaliar(solicitacao(despesas, **periodo))
    return [i.justificativa for i in itens(resultado)]


def test_justificativa_por_item():
    entrada = SolicitacaoReembolso.model_validate_json(EXEMPLO.read_text("utf-8"))
    resultado = engine.avaliar(entrada)
    textos = {i.id: i.justificativa for i in itens(resultado)}
    assert all(texto.strip() for texto in textos.values())
    assert "RN-001" in textos["d-001"] and "R$ 60,00" in textos["d-001"]
    assert "consumido" in textos["d-002"]
    assert "RN-004" in textos["d-004"]
    assert "RN-007" in textos["d-006"]
    assert "RN-006" in textos["d-008"]
    assert "RN-010" in textos["d-009"]
    assert "RN-008" in textos["d-014"]
    assert textos["d-005"] == rules.JUSTIFICATIVA_APROVADO


class TestJustificativas:
    def test_aprovado(self):
        assert justificativas([d()]) == [rules.JUSTIFICATIVA_APROVADO]

    def test_teto_parcial_alimentacao_e_transporte(self):
        (a,) = justificativas([d(valor="85")])
        assert a == "Valor limitado ao teto de R$ 60,00 (RN-001)."
        (t,) = justificativas([d(categoria="transporte_urbano", valor="105")])
        assert t == "Valor limitado ao teto de R$ 80,00 (RN-002)."

    def test_teto_esgotado(self):
        _, segunda = justificativas([d("1", valor="60"), d("2", valor="5")])
        assert segunda == (
            "Teto diário de R$ 60,00 já consumido por outras despesas do dia (RN-001)."
        )

    def test_viagem_cita_a_ampliacao(self):
        resultado = justificativas(
            [hospedagem(), d("c", valor="110", data="2026-10-10")]
        )
        assert resultado[1] == (
            "Valor limitado ao teto de R$ 90,00 "
            "(RN-001, ampliado em 50% por viagem (RN-005))."
        )

    def test_hospedagem_parcial_com_varias_diarias(self):
        (texto,) = justificativas([hospedagem(descricao="2 diarias", valor="520")])
        assert texto == (
            "Valor limitado ao teto de R$ 500,00 (RN-003, R$ 250,00 por diária x 2)."
        )

    def test_hospedagem_parcial_de_uma_diaria(self):
        (texto,) = justificativas([hospedagem(valor="300")])
        assert texto == "Valor limitado ao teto de R$ 250,00 (RN-003)."

    def test_hospedagem_sem_fornecedor_reconhecido(self):
        (texto,) = justificativas([hospedagem(fornecedor="Casa")])
        assert texto == rules.JUSTIFICATIVA_FORNECEDOR_HOSPEDAGEM

    def test_hospedagem_aprovada(self):
        assert justificativas([hospedagem(valor="100")]) == [
            rules.JUSTIFICATIVA_APROVADO
        ]

    def test_rejeicoes_citam_a_regra(self):
        casos = {
            "RN-010": d(valor="-1"),
            "RN-008": d(categoria="x"),
            "RN-006": d(data="2026-11-01"),
            "RN-004": d(valor="120", nf=False),
        }
        for regra, despesa in casos.items():
            (texto,) = justificativas([despesa])
            assert regra in texto, regra

    def test_duplicidade(self):
        antiga, _ = justificativas([d("1"), d("2")])
        assert antiga == rules.JUSTIFICATIVA_DUPLICIDADE

    def test_coworking_aprovado(self):
        assert justificativas([d(categoria="coworking")]) == [
            rules.JUSTIFICATIVA_APROVADO
        ]

    @pytest.mark.parametrize(
        "valor, esperado",
        [
            ("60", "R$ 60,00"),
            ("0.5", "R$ 0,50"),
            ("1234.5", "R$ 1.234,50"),
            ("1234567.89", "R$ 1.234.567,89"),
        ],
    )
    def test_formatar_moeda(self, valor, esperado):
        assert rules.formatar_moeda(Decimal(valor)) == esperado
