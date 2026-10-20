"""Testes dos modelos Pydantic (T-002; RN-011, RN-010, RN-009, RN-008)."""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.models import (
    ColaboradorResultado,
    Despesa,
    HistoricoCompetencia,
    ItemAuditoria,
    Periodo,
    ResultadoAuditoria,
    SolicitacaoReembolso,
)

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "despesas-exemplo.json"


def despesa_dict(**campos):
    base = {
        "id": "d-001",
        "data": "2026-07-03",
        "categoria": "alimentacao",
        "descricao": "Almoco com cliente",
        "fornecedor": "Restaurante Tavola",
        "valor": 72.50,
        "tem_nota_fiscal": True,
    }
    base.update(campos)
    return base


def solicitacao_dict():
    return {
        "colaborador": {
            "id": "c-0417",
            "nome": "Marina Volpi",
            "centro_custo": "CC-ENG-PLATAFORMA",
        },
        "periodo": {
            "competencia": "2026-07",
            "inicio": "2026-07-01",
            "fim": "2026-07-31",
        },
        "despesas": [despesa_dict()],
    }


def resultado_dict():
    return {
        "colaborador": {"id": "c-0417", "centro_custo": "CC-ENG-PLATAFORMA"},
        "historico_despesas": [
            {
                "competencia": "2026-07",
                "centro_custo": "CC-ENG-PLATAFORMA",
                "despesas": [
                    {
                        "id": "d-001",
                        "data": "2026-07-03",
                        "descricao": "Almoco com cliente",
                        "fornecedor": "Restaurante Tavola",
                        "status_item": "parcial",
                        "justificativa": "Despesa aprovada integralmente.",
                        "valor_reembolsado": 60,
                    }
                ],
            }
        ],
    }


# --------------------------------------------------------------------------
# Criação e parsing
# --------------------------------------------------------------------------


class TestParsing:
    def test_despesa_valida(self):
        d = Despesa(**despesa_dict())
        assert d.id == "d-001"
        assert d.data == date(2026, 7, 3)
        assert d.categoria == "alimentacao"
        assert d.descricao == "Almoco com cliente"
        assert d.valor == Decimal("72.50")
        assert d.tem_nota_fiscal is True

    def test_solicitacao_a_partir_de_dict(self):
        s = SolicitacaoReembolso.model_validate(solicitacao_dict())
        assert s.colaborador.id == "c-0417"
        assert s.colaborador.nome == "Marina Volpi"
        assert s.colaborador.centro_custo == "CC-ENG-PLATAFORMA"
        assert s.periodo.competencia == "2026-07"
        assert s.periodo.inicio == date(2026, 7, 1)
        assert s.periodo.fim == date(2026, 7, 31)
        assert len(s.despesas) == 1

    def test_solicitacao_a_partir_de_json(self):
        s = SolicitacaoReembolso.model_validate_json(json.dumps(solicitacao_dict()))
        assert s.despesas[0].valor == Decimal("72.50")

    def test_solicitacao_sem_despesas(self):
        dados = solicitacao_dict()
        dados["despesas"] = []
        assert SolicitacaoReembolso.model_validate(dados).despesas == []

    def test_campos_extras_sao_ignorados(self):
        dados = solicitacao_dict()
        dados["campo_novo"] = 1
        s = SolicitacaoReembolso.model_validate(dados)
        assert not hasattr(s, "campo_novo")

    def test_arquivo_de_exemplo_do_desafio(self):
        s = SolicitacaoReembolso.model_validate_json(EXEMPLO.read_text("utf-8"))
        assert s.colaborador.id == "c-0417"
        assert len(s.despesas) == 14
        por_id = {d.id: d for d in s.despesas}
        assert por_id["d-011"].valor == Decimal("33.33")  # 33.333 (RN-011)
        assert por_id["d-009"].valor == Decimal("-45.00")  # estorno chega ao motor
        assert por_id["d-014"].categoria == "ALIMENTACAO"  # grafia preservada
        assert por_id["d-013"].fornecedor == "airbnb"

    def test_resultado_auditoria_a_partir_de_json(self):
        r = ResultadoAuditoria.model_validate_json(json.dumps(resultado_dict()))
        assert isinstance(r.colaborador, ColaboradorResultado)
        assert r.colaborador.centro_custo == "CC-ENG-PLATAFORMA"
        historico = r.historico_despesas[0]
        assert isinstance(historico, HistoricoCompetencia)
        assert historico.competencia == "2026-07"
        item = historico.despesas[0]
        assert isinstance(item, ItemAuditoria)
        assert item.status_item == "parcial"
        assert item.valor_reembolsado == Decimal("60.00")

    def test_justificativa_nao_pode_ser_vazia(self):
        dados = resultado_dict()["historico_despesas"][0]["despesas"][0]
        dados["justificativa"] = ""
        with pytest.raises(ValidationError):
            ItemAuditoria.model_validate(dados)

    def test_item_auditoria_aceita_status_composto(self):
        item = ItemAuditoria(
            id="d-1",
            data="2026-07-03",
            descricao="x",
            fornecedor="y",
            status_item="rejeitado - categoria inválida",
            justificativa="Despesa aprovada integralmente.",
            valor_reembolsado=0,
        )
        assert item.status_item == "rejeitado - categoria inválida"


class TestFornecedor:
    def test_fornecedor_normalizado_para_minusculas(self):
        assert Despesa(**despesa_dict(fornecedor="AIRBNB Studio")).fornecedor == (
            "airbnb studio"
        )

    def test_fornecedor_do_resultado_tambem_normalizado(self):
        item = ItemAuditoria(
            id="d-1",
            data="2026-07-03",
            descricao="x",
            fornecedor="Restaurante Tavola",
            status_item="aprovado",
            justificativa="Despesa aprovada integralmente.",
            valor_reembolsado=1,
        )
        assert item.fornecedor == "restaurante tavola"


# --------------------------------------------------------------------------
# Decimal com duas casas (RN-011)
# --------------------------------------------------------------------------


@pytest.mark.req("RN-011")
class TestDinheiro:
    @pytest.mark.parametrize(
        "entrada, esperado",
        [
            (45.50, "45.50"),  # float já com 2 casas
            (45.5, "45.50"),  # float com 1 casa vira 2
            (100, "100.00"),  # int (cenário 04)
            ("100", "100.00"),
            ("72.5", "72.50"),
            (Decimal("10"), "10.00"),
            (80.456, "80.46"),  # arredonda para cima (cenário 02)
            (60.005, "60.01"),  # meio exato sobe; float 60.005 não pode atrapalhar
            (80.454, "80.45"),  # arredonda para baixo (cenário 03)
            (60.002, "60.00"),
            (33.333, "33.33"),
            ("0.005", "0.01"),
            ("-0.005", "-0.01"),
            ("-0.004", "0.00"),  # sem zero negativo
            (0, "0.00"),
        ],
    )
    def test_conversao_e_arredondamento(self, entrada, esperado):
        valor = Despesa(**despesa_dict(valor=entrada)).valor
        assert isinstance(valor, Decimal)
        assert valor == Decimal(esperado)
        assert str(valor) == esperado  # exatamente duas casas, sem "-0.00"
        assert valor.as_tuple().exponent == -2

    def test_json_com_float_nao_acumula_erro_binario(self):
        # 0.1 + 0.2 em float é 0.30000000000000004; deve virar 0.30.
        json_texto = json.dumps(despesa_dict(valor=0.1 + 0.2))
        assert Despesa.model_validate_json(json_texto).valor == Decimal("0.30")

    def test_json_numero_inteiro_vira_duas_casas(self):
        valor = Despesa.model_validate_json(json.dumps(despesa_dict(valor=100))).valor
        assert str(valor) == "100.00"

    def test_valor_negativo_e_zero_chegam_ao_motor(self):
        # RN-010 é aplicada pelo motor; o schema não pode barrar antes.
        assert Despesa(**despesa_dict(valor=-25)).valor == Decimal("-25.00")
        assert Despesa(**despesa_dict(valor=0)).valor == Decimal("0.00")

    def test_valor_reembolsado_do_resultado_tem_duas_casas(self):
        item = ItemAuditoria(
            id="d-1",
            data="2026-07-03",
            descricao="x",
            fornecedor="y",
            status_item="aprovado",
            justificativa="Despesa aprovada integralmente.",
            valor_reembolsado=60,
        )
        assert str(item.valor_reembolsado) == "60.00"

    def test_nenhum_campo_monetario_e_float(self):
        s = SolicitacaoReembolso.model_validate(solicitacao_dict())
        r = ResultadoAuditoria.model_validate(resultado_dict())
        assert not isinstance(s.despesas[0].valor, float)
        assert not isinstance(
            r.historico_despesas[0].despesas[0].valor_reembolsado, float
        )

    @pytest.mark.parametrize(
        "invalido",
        [
            "abc",
            "R$ 10,00",
            "",
            None,
            True,
            False,
            [1],
            {"v": 1},
            float("nan"),
            float("inf"),
            "NaN",
            "Infinity",
            "1e40",  # fora do intervalo suportado para 2 casas
        ],
    )
    def test_valor_invalido_e_rejeitado(self, invalido):
        with pytest.raises(ValidationError) as erro:
            Despesa(**despesa_dict(valor=invalido))
        assert erro.value.errors()[0]["loc"] == ("valor",)


# --------------------------------------------------------------------------
# Validação de schema
# --------------------------------------------------------------------------


class TestSchema:
    @pytest.mark.parametrize(
        "campo",
        [
            "id",
            "data",
            "categoria",
            "descricao",
            "fornecedor",
            "valor",
            "tem_nota_fiscal",
        ],
    )
    def test_despesa_campo_obrigatorio(self, campo):
        dados = despesa_dict()
        del dados[campo]
        with pytest.raises(ValidationError) as erro:
            Despesa(**dados)
        assert erro.value.errors()[0]["type"] == "missing"
        assert erro.value.errors()[0]["loc"] == (campo,)

    @pytest.mark.parametrize(
        "caminho",
        [
            ("colaborador",),
            ("colaborador", "id"),
            ("colaborador", "nome"),
            ("colaborador", "centro_custo"),
            ("periodo",),
            ("periodo", "competencia"),
            ("periodo", "inicio"),
            ("periodo", "fim"),
            ("despesas",),
        ],
    )
    def test_solicitacao_campo_obrigatorio(self, caminho):
        dados = solicitacao_dict()
        alvo = dados
        for chave in caminho[:-1]:
            alvo = alvo[chave]
        del alvo[caminho[-1]]
        with pytest.raises(ValidationError) as erro:
            SolicitacaoReembolso.model_validate(dados)
        assert erro.value.errors()[0]["type"] == "missing"
        assert erro.value.errors()[0]["loc"] == caminho

    @pytest.mark.parametrize("campo", ["id", "nome", "centro_custo"])
    def test_colaborador_nao_aceita_texto_vazio(self, campo):
        dados = solicitacao_dict()
        dados["colaborador"][campo] = ""
        with pytest.raises(ValidationError):
            SolicitacaoReembolso.model_validate(dados)

    def test_despesa_nao_aceita_id_vazio(self):
        with pytest.raises(ValidationError):
            Despesa(**despesa_dict(id=""))

    @pytest.mark.parametrize(
        "data",
        [
            "03/07/2026",
            "2026/07/03",
            "20260703",
            "2026-7-3",
            "2026-07",
            "2026-07-03T10:00:00",
            "2026-02-30",  # inexistente
            "2026-13-01",
            "",
            None,
            20260703,
            1.5,
        ],
    )
    def test_data_em_formato_invalido(self, data):
        with pytest.raises(ValidationError) as erro:
            Despesa(**despesa_dict(data=data))
        assert erro.value.errors()[0]["loc"] == ("data",)

    def test_data_aceita_objeto_date(self):
        assert Despesa(**despesa_dict(data=date(2026, 7, 3))).data == date(2026, 7, 3)

    def test_data_rejeita_datetime(self):
        with pytest.raises(ValidationError):
            Despesa(**despesa_dict(data=datetime(2026, 7, 3, 10, 0)))

    @pytest.mark.parametrize("valor", ["true", "false", 1, 0, "sim", None])
    def test_tem_nota_fiscal_exige_booleano(self, valor):
        with pytest.raises(ValidationError):
            Despesa(**despesa_dict(tem_nota_fiscal=valor))

    @pytest.mark.parametrize("campo", ["categoria", "descricao", "fornecedor"])
    def test_texto_exige_string(self, campo):
        with pytest.raises(ValidationError):
            Despesa(**despesa_dict(**{campo: 123}))

    def test_despesas_deve_ser_lista(self):
        dados = solicitacao_dict()
        dados["despesas"] = {"id": "d-001"}
        with pytest.raises(ValidationError):
            SolicitacaoReembolso.model_validate(dados)

    def test_erro_em_despesa_aninhada_indica_posicao(self):
        dados = solicitacao_dict()
        dados["despesas"].append(despesa_dict(id="d-002", valor="abc"))
        with pytest.raises(ValidationError) as erro:
            SolicitacaoReembolso.model_validate(dados)
        assert erro.value.errors()[0]["loc"] == ("despesas", 1, "valor")

    def test_json_malformado(self):
        with pytest.raises(ValidationError):
            SolicitacaoReembolso.model_validate_json("{nao e json")

    @pytest.mark.parametrize(
        "campo", ["id", "data", "status_item", "justificativa", "valor_reembolsado"]
    )
    def test_item_auditoria_campo_obrigatorio(self, campo):
        dados = resultado_dict()["historico_despesas"][0]["despesas"][0]
        del dados[campo]
        with pytest.raises(ValidationError):
            ItemAuditoria.model_validate(dados)

    @pytest.mark.parametrize("campo", ["colaborador", "historico_despesas"])
    def test_resultado_campo_obrigatorio(self, campo):
        dados = resultado_dict()
        del dados[campo]
        with pytest.raises(ValidationError):
            ResultadoAuditoria.model_validate(dados)


# --------------------------------------------------------------------------
# Dados "ruins" que devem chegar ao motor (RN-008, RN-009)
# --------------------------------------------------------------------------


class TestDadosQueOMotorRejeita:
    @pytest.mark.req("RN-008")
    @pytest.mark.parametrize(
        "categoria",
        ["alimentação", "Hospedagem", "transporte urbano", "ALIMENTACAO", "", "x"],
    )
    def test_categoria_fora_da_politica_e_preservada(self, categoria):
        assert Despesa(**despesa_dict(categoria=categoria)).categoria == categoria

    @pytest.mark.req("RN-009")
    @pytest.mark.parametrize(
        "competencia",
        ["2026-07", "10/2026", "2026/10", "202610", "2026-10-15", "2026-13", "", None],
    )
    def test_competencia_nao_e_validada_pelo_schema(self, competencia):
        periodo = Periodo(
            competencia=competencia, inicio="2026-07-01", fim="2026-07-31"
        )
        assert periodo.competencia == competencia

    def test_competencia_continua_obrigatoria(self):
        with pytest.raises(ValidationError):
            Periodo(inicio="2026-07-01", fim="2026-07-31")
