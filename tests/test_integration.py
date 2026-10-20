"""Ciclo completo carregar -> consolidar -> avaliar -> validar -> renomear (T-019).

Integração de ponta a ponta sobre disco real em ``tmp_path``: modelos, motor,
repositório, serviço e controller trabalhando juntos.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core import engine
from core.models import ResultadoAuditoria, SolicitacaoReembolso
from storage import repository, service
from ui.controller import Controller

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "despesas-exemplo.json"
CHAVE = ("c-0417", "CC-ENG-PLATAFORMA", "2026-07")
ORIGINAL = "c-0417_CC-ENG-PLATAFORMA_2026-07.json"
VALIDADO = "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json"
RESULTADO = "c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json"


def segundo_envio(tmp_path, despesas_extras):
    """Reenvio parcial: repete d-001 e d-002 e acrescenta ``despesas_extras``."""
    dados = json.loads(EXEMPLO.read_text("utf-8"))
    dados["despesas"] = dados["despesas"][:2] + despesas_extras
    caminho = tmp_path / "segundo_envio.json"
    caminho.write_text(json.dumps(dados), "utf-8")
    return caminho


def nova_despesa(id_="d-015", valor=20.0):
    return {
        "id": id_,
        "data": "2026-07-20",
        "categoria": "alimentacao",
        "descricao": "Almoco extra",
        "fornecedor": "Bistro Central",
        "valor": valor,
        "tem_nota_fiscal": True,
    }


def nomes(pasta):
    return sorted(p.name for p in pasta.iterdir())


@pytest.mark.req("DT-001")
@pytest.mark.req("DT-002")
def test_ciclo_completo_carregar_consolidar_validar_renomear(tmp_path):
    pasta = tmp_path / "colaborador"

    # 1. carregar: nasce o arquivo padronizado, ainda não validado
    carga = service.carregar_arquivo(EXEMPLO, pasta)
    assert (carga.criado, carga.novas) == (True, 14)
    assert nomes(pasta) == [ORIGINAL]
    (estado,) = service.listar_competencias(pasta)
    assert (estado.validado, estado.tem_resultado, estado.total_despesas) == (
        False,
        False,
        14,
    )

    # 2. consolidar: reenvio parcial soma só a despesa nova, sem duplicar
    reenvio = service.carregar_arquivo(segundo_envio(tmp_path, [nova_despesa()]), pasta)
    assert (reenvio.criado, reenvio.novas, reenvio.ignoradas) == (False, 1, 2)
    assert nomes(pasta) == [ORIGINAL]
    consolidado = repository.ler_solicitacao(*CHAVE, diretorio=pasta)
    assert [d.id for d in consolidado.despesas][-2:] == ["d-014", "d-015"]
    assert len(consolidado.despesas) == 15
    conteudo_consolidado = (pasta / ORIGINAL).read_bytes()

    # 3. avaliar + validar: gera o resultado e renomeia fisicamente o original
    validacao = service.validar_competencia(*CHAVE, diretorio=pasta)
    assert nomes(pasta) == [RESULTADO, VALIDADO]
    assert not (pasta / ORIGINAL).exists()
    assert (pasta / VALIDADO).read_bytes() == conteudo_consolidado
    (estado,) = service.listar_competencias(pasta)
    assert (estado.validado, estado.tem_resultado) == (True, True)

    # 4. o resultado gravado é a auditoria do motor, com 15 despesas e 2 casas
    gravado = service.obter_resultado(*CHAVE, diretorio=pasta)
    assert gravado == validacao.resultado == engine.avaliar(consolidado)
    itens = {i.id: i for i in gravado.historico_despesas[0].despesas}
    assert len(itens) == 15
    assert itens["d-015"].status_item == "aprovado"
    total = sum(i.valor_reembolsado for i in itens.values())
    assert total == Decimal("864.43")  # 844,43 do exemplo + 20,00 da d-015
    texto = (pasta / RESULTADO).read_text("utf-8")
    assert '"valor_reembolsado": 33.33' in texto
    assert '"valor_reembolsado": 60.00' in texto

    # 5. competência validada é imutável: nem reenvio, nem nova validação
    with pytest.raises(service.CompetenciaJaValidadaError):
        service.carregar_arquivo(
            segundo_envio(tmp_path, [nova_despesa("d-016")]), pasta
        )
    with pytest.raises(service.CompetenciaJaValidadaError):
        service.validar_competencia(*CHAVE, diretorio=pasta)
    assert nomes(pasta) == [RESULTADO, VALIDADO]


class TestFidelidadeDosDados:
    def test_persistir_nao_altera_o_que_o_motor_decide(self, tmp_path):
        pasta = tmp_path / "colaborador"
        direto = engine.avaliar(
            SolicitacaoReembolso.model_validate_json(EXEMPLO.read_text("utf-8"))
        )
        service.carregar_arquivo(EXEMPLO, pasta)
        via_disco = service.validar_competencia(*CHAVE, diretorio=pasta).resultado
        assert via_disco == direto

    def test_resultado_em_disco_e_json_valido_e_reabrivel(self, tmp_path):
        pasta = tmp_path / "colaborador"
        service.carregar_arquivo(EXEMPLO, pasta)
        service.validar_competencia(*CHAVE, diretorio=pasta)
        dados = json.loads((pasta / RESULTADO).read_text("utf-8"))
        assert ResultadoAuditoria.model_validate(dados).colaborador.id == "c-0417"
        assert all(
            item["justificativa"] for item in dados["historico_despesas"][0]["despesas"]
        )


class TestIsolamentoEntreCompetencias:
    def test_validar_uma_competencia_nao_afeta_as_outras(self, tmp_path):
        pasta = tmp_path / "colaborador"
        service.carregar_arquivo(EXEMPLO, pasta)
        agosto = json.loads(EXEMPLO.read_text("utf-8"))
        agosto["periodo"] = {
            "competencia": "2026-08",
            "inicio": "2026-08-01",
            "fim": "2026-08-31",
        }
        agosto["despesas"] = [{**nova_despesa("a-1"), "data": "2026-08-10"}]
        origem = tmp_path / "agosto.json"
        origem.write_text(json.dumps(agosto), "utf-8")
        outro = json.loads(origem.read_text("utf-8"))
        outro["colaborador"]["id"] = "c-0001"
        origem_outro = tmp_path / "outro.json"
        origem_outro.write_text(json.dumps(outro), "utf-8")
        service.carregar_arquivo(origem, pasta)
        service.carregar_arquivo(origem_outro, pasta)

        service.validar_competencia(*CHAVE, diretorio=pasta)

        estados = {
            (e.id_colaborador, e.competencia): e.validado
            for e in service.listar_competencias(pasta)
        }
        assert estados == {
            ("c-0001", "2026-08"): False,
            ("c-0417", "2026-07"): True,
            ("c-0417", "2026-08"): False,
        }
        # a competência de agosto continua aceitando reenvios
        reenvio = service.carregar_arquivo(origem, pasta)
        assert (reenvio.novas, reenvio.ignoradas) == (0, 1)

    def test_arquivo_corrompido_nao_bloqueia_as_demais_competencias(self, tmp_path):
        pasta = tmp_path / "colaborador"
        service.carregar_arquivo(EXEMPLO, pasta)
        (pasta / "c-0999_CC-X_2026-07.json").write_text("{nao e json", "utf-8")

        service.validar_competencia(*CHAVE, diretorio=pasta)

        por_id = {e.id_colaborador: e for e in service.listar_competencias(pasta)}
        assert por_id["c-0417"].validado and not por_id["c-0417"].corrompido
        assert por_id["c-0999"].corrompido and not por_id["c-0999"].validado


class TestRecuperacaoDeFalhas:
    def test_falha_ao_renomear_permite_validar_de_novo(self, tmp_path, monkeypatch):
        pasta = tmp_path / "colaborador"
        service.carregar_arquivo(EXEMPLO, pasta)
        original = (pasta / ORIGINAL).read_bytes()

        with monkeypatch.context() as m:
            m.setattr(Path, "rename", _renomear_falha)
            m.setattr(service.time, "sleep", lambda s: None)
            with pytest.raises(service.FalhaDePersistenciaError):
                service.validar_competencia(*CHAVE, diretorio=pasta)
        assert nomes(pasta) == [ORIGINAL]  # sem resultado órfão
        assert (pasta / ORIGINAL).read_bytes() == original

        service.validar_competencia(*CHAVE, diretorio=pasta)
        assert nomes(pasta) == [RESULTADO, VALIDADO]

    def test_competencia_invalida_nunca_chega_ao_disco(self, tmp_path):
        pasta = tmp_path / "colaborador"
        dados = json.loads(EXEMPLO.read_text("utf-8"))
        dados["periodo"]["competencia"] = "07/2026"
        origem = tmp_path / "invalida.json"
        origem.write_text(json.dumps(dados), "utf-8")
        with pytest.raises(engine.CompetenciaInvalidaError):
            service.carregar_arquivo(origem, pasta)
        assert not pasta.exists()


def _renomear_falha(self, destino):
    raise PermissionError("arquivo em uso")


@pytest.mark.req("DT-001")
def test_ciclo_completo_pela_api_do_controller(tmp_path):
    """O mesmo ciclo que a tela executa, ponta a ponta pela ponte."""
    pasta = tmp_path / "colaborador"
    ctrl = Controller(pasta, seletor_arquivo=lambda: str(EXEMPLO))

    def competencia():
        (colaborador,) = ctrl.listar_colaboradores_competencias()["colaboradores"]
        (unica,) = colaborador["competencias"]
        return unica

    caminho = ctrl.selecionar_arquivo()["caminho"]
    carga = ctrl.avaliar_reembolso(caminho)
    assert carga["ok"] and carga["novas"] == 14
    assert competencia()["validado"] is False
    assert ctrl.obter_resultado(*CHAVE)["ok"] is False  # ainda não há resultado

    reenvio = ctrl.avaliar_reembolso(caminho)
    assert reenvio["ok"] and reenvio["novas"] == 0  # idempotente

    assert ctrl.validar_competencia(*CHAVE)["ok"]
    assert competencia()["validado"] is True
    assert ctrl.validar_competencia(*CHAVE)["ok"] is False  # botão desabilitado
    assert ctrl.avaliar_reembolso(caminho)["ok"] is False  # competência imutável

    resultado = ctrl.obter_resultado(*CHAVE)["resultado"]
    json.dumps(resultado)  # serializável pela ponte
    despesas = resultado["historico_despesas"][0]["despesas"]
    assert len(despesas) == 14
    assert nomes(pasta) == [RESULTADO, VALIDADO]
