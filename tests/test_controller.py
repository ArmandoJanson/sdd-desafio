"""Testes da API do Controller, sem abrir a janela gráfica (T-015)."""

import json
import os
from datetime import date
from pathlib import Path

import pytest

import config
from core.models import ResultadoAuditoria
from storage import service
from ui.controller import Controller

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "despesas-exemplo.json"
CHAVE = ("c-0417", "CC-ENG-PLATAFORMA", "2026-07")


def envio(tmp_path, despesas, nome="envio.json", competencia="2026-07", id_="c-0417"):
    caminho = tmp_path / "origem" / nome
    caminho.parent.mkdir(exist_ok=True)
    caminho.write_text(
        json.dumps(
            {
                "colaborador": {
                    "id": id_,
                    "nome": "Marina Volpi",
                    "centro_custo": "CC-ENG-PLATAFORMA",
                },
                "periodo": {
                    "competencia": competencia,
                    "inicio": "2026-07-01",
                    "fim": "2026-07-31",
                },
                "despesas": despesas,
            }
        ),
        "utf-8",
    )
    return str(caminho)


def desp(id_, valor=10.0):
    return {
        "id": id_,
        "data": "2026-07-10",
        "categoria": "alimentacao",
        "descricao": "Almoco",
        "fornecedor": "Bistro",
        "valor": valor,
        "tem_nota_fiscal": True,
    }


@pytest.fixture
def pasta(tmp_path):
    return tmp_path / "colaborador"


@pytest.fixture
def ctrl(pasta):
    return Controller(diretorio=pasta)


def serializavel(resposta):
    """A ponte do PyWebView serializa a resposta em JSON."""
    json.dumps(resposta)
    return resposta


class TestApiExposta:
    def test_apenas_os_metodos_da_ui_sao_publicos(self):
        publicos = {n for n in dir(Controller) if not n.startswith("_")}
        assert publicos == {
            "selecionar_arquivo",
            "avaliar_reembolso",
            "listar_colaboradores_competencias",
            "validar_competencia",
            "obter_resultado",
            "baixar_resultado",
        }

    def test_atributos_de_instancia_nao_sao_expostos(self, ctrl):
        assert [n for n in vars(ctrl) if not n.startswith("_")] == []


class TestSelecionarArquivo:
    def test_sem_seletor(self, ctrl):
        resposta = ctrl.selecionar_arquivo()
        assert resposta["ok"] is False and "indisponível" in resposta["erro"]

    def test_devolve_o_caminho_escolhido(self, pasta):
        controller = Controller(pasta, seletor_arquivo=lambda: "C:/x/envio.json")
        assert controller.selecionar_arquivo() == {
            "ok": True,
            "caminho": "C:/x/envio.json",
        }

    def test_cancelar_devolve_none(self, pasta):
        controller = Controller(pasta, seletor_arquivo=lambda: None)
        assert controller.selecionar_arquivo() == {"ok": True, "caminho": None}


class TestAvaliarReembolso:
    def test_carrega_o_exemplo_do_desafio(self, ctrl, pasta):
        resposta = serializavel(ctrl.avaliar_reembolso(str(EXEMPLO)))
        assert resposta == {
            "ok": True,
            "arquivo": "c-0417_CC-ENG-PLATAFORMA_2026-07.json",
            "criado": True,
            "novas": 14,
            "ignoradas": 0,
            "mensagem": "Arquivo criado com 14 despesas.",
        }
        assert (pasta / resposta["arquivo"]).is_file()

    def test_uma_despesa_usa_singular(self, ctrl, tmp_path):
        resposta = ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1")]))
        assert resposta["mensagem"] == "Arquivo criado com 1 despesa."

    def test_reenvio_identico_nao_duplica(self, ctrl, tmp_path):
        caminho = envio(tmp_path, [desp("d-1")])
        ctrl.avaliar_reembolso(caminho)
        resposta = ctrl.avaliar_reembolso(caminho)
        assert resposta["ok"] and not resposta["criado"]
        assert resposta["mensagem"] == (
            "Nenhuma despesa nova: todas já estavam registradas."
        )

    def test_reenvio_parcial_acrescenta_so_as_novas(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1")], "a.json"))
        resposta = ctrl.avaliar_reembolso(
            envio(tmp_path, [desp("d-1"), desp("d-2", 20.0)], "b.json")
        )
        assert (resposta["novas"], resposta["ignoradas"]) == (1, 1)
        assert resposta["mensagem"] == (
            "Arquivo atualizado: 1 despesa nova e 1 já registrada."
        )

    def test_varias_novas_usam_plural(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1")], "a.json"))
        novas = [desp("d-1"), desp("d-2", 20.0), desp("d-3", 30.0)]
        resposta = ctrl.avaliar_reembolso(envio(tmp_path, novas, "b.json"))
        assert resposta["mensagem"] == (
            "Arquivo atualizado: 2 despesas novas e 1 já registrada."
        )

    def test_conflito_de_id_pede_ajuste(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1", 10.0)], "a.json"))
        resposta = serializavel(
            ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1", 99.0)], "b.json"))
        )
        assert resposta["ok"] is False
        assert "d-1" in resposta["erro"] and "Ajuste" in resposta["erro"]

    @pytest.mark.parametrize("caminho", [None, "", "   ", 123, ["a.json"]])
    def test_caminho_ausente_ou_invalido(self, ctrl, caminho):
        resposta = ctrl.avaliar_reembolso(caminho)
        assert resposta == {"ok": False, "erro": "Nenhum arquivo informado."}

    def test_arquivo_inexistente(self, ctrl, tmp_path):
        resposta = ctrl.avaliar_reembolso(str(tmp_path / "nada.json"))
        assert resposta["ok"] is False and "não encontrado" in resposta["erro"]

    @pytest.mark.parametrize(
        "conteudo", ["{malformado", "", '{"colaborador": {}}', "[]"]
    )
    def test_json_malformado_ou_incompleto(self, ctrl, tmp_path, pasta, conteudo):
        origem = tmp_path / "ruim.json"
        origem.write_text(conteudo, "utf-8")
        resposta = serializavel(ctrl.avaliar_reembolso(str(origem)))
        assert resposta["ok"] is False and resposta["erro"]
        assert not pasta.exists()

    def test_competencia_invalida(self, ctrl, tmp_path, pasta):
        caminho = envio(tmp_path, [desp("d-1")], competencia="2026-13")
        resposta = ctrl.avaliar_reembolso(caminho)
        assert resposta["ok"] is False and "YYYY-MM" in resposta["erro"]
        assert not pasta.exists()

    def test_id_de_colaborador_invalido_para_nome_de_arquivo(self, ctrl, tmp_path):
        resposta = ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1")], id_="c_1"))
        assert resposta["ok"] is False and "não pode conter" in resposta["erro"]

    def test_competencia_ja_validada(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(envio(tmp_path, [desp("d-1")]))
        ctrl.validar_competencia(*CHAVE)
        nova = envio(tmp_path, [desp("d-2", 20.0)], "b.json")
        resposta = ctrl.avaliar_reembolso(nova)
        assert resposta["ok"] is False and "já foi validada" in resposta["erro"]


class TestListarColaboradoresCompetencias:
    def test_pasta_vazia(self, ctrl):
        assert ctrl.listar_colaboradores_competencias() == {
            "ok": True,
            "colaboradores": [],
        }

    def test_agrupa_por_colaborador(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        junho = envio(tmp_path, [desp("d-1")], "a.json", competencia="2026-06")
        ctrl.avaliar_reembolso(junho)
        resposta = serializavel(ctrl.listar_colaboradores_competencias())
        (colaborador,) = resposta["colaboradores"]
        assert (colaborador["id"], colaborador["nome"]) == ("c-0417", "Marina Volpi")
        assert [c["competencia"] for c in colaborador["competencias"]] == [
            "2026-06",
            "2026-07",
        ]
        assert colaborador["competencias"][1] == {
            "centro_custo": "CC-ENG-PLATAFORMA",
            "competencia": "2026-07",
            "validado": False,
            "tem_resultado": False,
            "corrompido": False,
            "erro": None,
            "total_despesas": 14,
        }

    def test_indicador_de_validacao(self, ctrl):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        ctrl.validar_competencia(*CHAVE)
        (colaborador,) = ctrl.listar_colaboradores_competencias()["colaboradores"]
        (julho,) = colaborador["competencias"]
        assert julho["validado"] is True and julho["tem_resultado"] is True

    def test_varios_colaboradores(self, ctrl, tmp_path):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        outro = envio(tmp_path, [desp("d-1")], "a.json", id_="c-0001")
        ctrl.avaliar_reembolso(outro)
        lista = ctrl.listar_colaboradores_competencias()["colaboradores"]
        assert [c["id"] for c in lista] == ["c-0001", "c-0417"]

    def test_corrompido_e_sinalizado_sem_derrubar_a_lista(self, ctrl, pasta):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        (pasta / "c-0999_CC-X_2026-07.json").write_text("{nao e json", "utf-8")
        resposta = serializavel(ctrl.listar_colaboradores_competencias())
        por_id = {c["id"]: c for c in resposta["colaboradores"]}
        assert por_id["c-0417"]["competencias"][0]["corrompido"] is False
        ruim = por_id["c-0999"]
        assert ruim["nome"] == "c-0999"  # sem nome legível, usa o id
        assert ruim["competencias"][0]["corrompido"] is True
        assert "malformado" in ruim["competencias"][0]["erro"]

    def test_falha_ao_varrer_a_pasta(self, ctrl, pasta, monkeypatch):
        pasta.mkdir()

        def nega(self):
            raise PermissionError("acesso negado")

        monkeypatch.setattr(Path, "iterdir", nega)
        resposta = ctrl.listar_colaboradores_competencias()
        assert resposta["ok"] is False and "acesso negado" in resposta["erro"]

    def test_usa_a_pasta_colaborador_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path / "padrao")
        controller = Controller()
        controller.avaliar_reembolso(str(EXEMPLO))
        assert (tmp_path / "padrao").is_dir()
        lista = controller.listar_colaboradores_competencias()["colaboradores"]
        assert len(lista) == 1


class TestValidarCompetencia:
    def test_valida_e_renomeia(self, ctrl, pasta):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        resposta = serializavel(ctrl.validar_competencia(*CHAVE))
        assert resposta == {
            "ok": True,
            "arquivo_resultado": "c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json",
            "arquivo_validado": "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json",
            "mensagem": "Competência 2026-07 validada.",
        }
        assert sorted(p.name for p in pasta.iterdir()) == [
            resposta["arquivo_resultado"],
            resposta["arquivo_validado"],
        ]

    def test_segunda_validacao_e_recusada(self, ctrl):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        ctrl.validar_competencia(*CHAVE)
        resposta = ctrl.validar_competencia(*CHAVE)
        assert resposta["ok"] is False and "já foi validada" in resposta["erro"]

    def test_competencia_nao_carregada(self, ctrl):
        resposta = ctrl.validar_competencia(*CHAVE)
        assert resposta["ok"] is False and "não encontrado" in resposta["erro"]

    def test_arquivo_corrompido(self, ctrl, pasta):
        pasta.mkdir()
        (pasta / "c-0417_CC-ENG-PLATAFORMA_2026-07.json").write_text("{", "utf-8")
        resposta = ctrl.validar_competencia(*CHAVE)
        assert resposta["ok"] is False and "malformado" in resposta["erro"]

    def test_competencia_invalida_gravada_no_disco(self, ctrl, pasta):
        pasta.mkdir()
        dados = json.loads(EXEMPLO.read_text("utf-8"))
        dados["periodo"]["competencia"] = "2026-13"
        (pasta / "c-0417_CC-ENG-PLATAFORMA_2026-13.json").write_text(
            json.dumps(dados), "utf-8"
        )
        resposta = ctrl.validar_competencia("c-0417", "CC-ENG-PLATAFORMA", "2026-13")
        assert resposta["ok"] is False and "YYYY-MM" in resposta["erro"]

    def test_parametros_invalidos(self, ctrl):
        resposta = ctrl.validar_competencia("c_1", "CC", "2026-07")
        assert resposta["ok"] is False


class TestObterResultado:
    def test_devolve_a_auditoria_com_valores_em_texto(self, ctrl):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        ctrl.validar_competencia(*CHAVE)
        resposta = serializavel(ctrl.obter_resultado(*CHAVE))
        assert resposta["ok"] is True
        resultado = resposta["resultado"]
        assert resultado["colaborador"] == {
            "id": "c-0417",
            "centro_custo": "CC-ENG-PLATAFORMA",
        }
        (historico,) = resultado["historico_despesas"]
        por_id = {i["id"]: i for i in historico["despesas"]}
        assert por_id["d-001"]["status_item"] == "parcial"
        assert por_id["d-001"]["valor_reembolsado"] == "60.00"
        assert "RN-001" in por_id["d-001"]["justificativa"]
        assert por_id["d-011"]["valor_reembolsado"] == "33.33"
        assert por_id["d-006"]["status_item"] == "rejeitado - duplicidade"
        assert len(historico["despesas"]) == 14

    def test_antes_de_validar_nao_ha_resultado(self, ctrl):
        ctrl.avaliar_reembolso(str(EXEMPLO))
        resposta = ctrl.obter_resultado(*CHAVE)
        assert resposta["ok"] is False and "não encontrado" in resposta["erro"]

    def test_resultado_corrompido(self, ctrl, pasta):
        pasta.mkdir()
        arquivo = pasta / "c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json"
        arquivo.write_text("{}", "utf-8")
        resposta = ctrl.obter_resultado(*CHAVE)
        assert resposta["ok"] is False and "dados inválidos" in resposta["erro"]


def test_ciclo_completo_pela_api(tmp_path):
    ctrl = Controller(tmp_path / "colaborador", seletor_arquivo=lambda: str(EXEMPLO))
    caminho = ctrl.selecionar_arquivo()["caminho"]
    assert ctrl.avaliar_reembolso(caminho)["ok"]

    def competencia_de_julho():
        lista = ctrl.listar_colaboradores_competencias()["colaboradores"]
        return lista[0]["competencias"][0]

    assert competencia_de_julho()["validado"] is False
    assert ctrl.validar_competencia(*CHAVE)["ok"]
    assert competencia_de_julho()["validado"] is True
    assert ctrl.obter_resultado(*CHAVE)["ok"]
    assert EXEMPLO.exists()  # o arquivo escolhido pelo usuário nunca é movido


class TestCompetenciaFutura:
    @pytest.mark.req("RN-012")
    def test_mensagem_amigavel_e_nada_carregado(
        self, ctrl, tmp_path, pasta, monkeypatch
    ):
        monkeypatch.setattr(service, "hoje", lambda: date(2026, 10, 19))
        caminho = envio(tmp_path, [desp("d-1")], competencia="2026-11")
        resposta = serializavel(ctrl.avaliar_reembolso(caminho))
        assert resposta == {
            "ok": False,
            "erro": (
                "A competência 2026-11 é futura: só é possível carregar "
                "competências até o mês atual (2026-10)."
            ),
        }
        assert not pasta.exists()
        assert ctrl.listar_colaboradores_competencias()["colaboradores"] == []


class TestMensagensAmigaveis:
    def test_datas_inexistentes_do_arquivo_do_usuario(self, ctrl, tmp_path, pasta):
        """O caso real: 31/11 e 31/09 não existem no calendário."""
        despesas = [desp(f"d-{n:02d}") for n in range(1, 13)]
        despesas.append({**desp("d-13"), "data": "2026-09-31"})
        origem = tmp_path / "despesas.json"
        origem.write_text(
            json.dumps(
                {
                    "colaborador": {"id": "c-1", "nome": "Ana", "centro_custo": "CC"},
                    "periodo": {
                        "competencia": "2026-09",
                        "inicio": "2026-09-01",
                        "fim": "2026-11-31",
                    },
                    "despesas": despesas,
                }
            ),
            "utf-8",
        )
        resposta = serializavel(ctrl.avaliar_reembolso(str(origem)))
        assert resposta["ok"] is False
        erro = resposta["erro"]
        assert erro.startswith("O arquivo 'despesas.json' tem dados inválidos:")
        assert (
            "• Período, campo 'fim': a data '2026-11-31' não existe no calendário."
        ) in erro
        assert (
            "• Despesa nº 13 (id d-13), campo 'data': "
            "a data '2026-09-31' não existe no calendário."
        ) in erro
        for jargao in (
            "validation error",
            "type=",
            "pydantic",
            "input_value",
            "https://",
        ):
            assert jargao not in erro
        assert not pasta.exists()


class TestBaixarResultado:
    @pytest.fixture
    def baixador(self, pasta, tmp_path):
        """Controller com um 'Salvar como' falso que registra o nome sugerido."""
        escolha = {"destino": str(tmp_path / "Downloads" / "baixado.json"), "nomes": []}

        def seletor_destino(nome):
            escolha["nomes"].append(nome)
            return escolha["destino"]

        controller = Controller(pasta, seletor_destino=seletor_destino)
        controller.avaliar_reembolso(str(EXEMPLO))
        controller.validar_competencia(*CHAVE)
        return controller, escolha

    def test_grava_uma_copia_no_local_escolhido(self, baixador, tmp_path):
        controller, escolha = baixador
        resposta = serializavel(controller.baixar_resultado(*CHAVE))
        destino = tmp_path / "Downloads" / "baixado.json"
        assert resposta == {
            "ok": True,
            "cancelado": False,
            "arquivo": "baixado.json",
            "caminho": str(destino),
            "mensagem": f"Resultado salvo em {destino}",
        }
        assert escolha["nomes"] == ["c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json"]
        copia = json.loads(destino.read_text("utf-8"))
        assert len(copia["historico_despesas"][0]["despesas"]) == 14
        assert '"valor_reembolsado": 60.00' in destino.read_text("utf-8")

    def test_copia_e_igual_ao_resultado_exibido(self, baixador, tmp_path):
        controller, _ = baixador
        exibido = controller.obter_resultado(*CHAVE)["resultado"]
        controller.baixar_resultado(*CHAVE)
        baixado = ResultadoAuditoria.model_validate(
            json.loads((tmp_path / "Downloads" / "baixado.json").read_text("utf-8"))
        )
        assert baixado.model_dump(mode="json") == exibido

    @pytest.mark.parametrize("cancelou", [None, ""])
    def test_cancelar_nao_grava_nada(self, baixador, tmp_path, cancelou):
        controller, escolha = baixador
        escolha["destino"] = cancelou
        resposta = serializavel(controller.baixar_resultado(*CHAVE))
        assert resposta == {
            "ok": True,
            "cancelado": True,
            "mensagem": "Download cancelado.",
        }
        assert not (tmp_path / "Downloads").exists()

    def test_acrescenta_a_extensao_json(self, baixador, tmp_path):
        controller, escolha = baixador
        escolha["destino"] = str(tmp_path / "meu_resultado")
        resposta = controller.baixar_resultado(*CHAVE)
        assert resposta["arquivo"] == "meu_resultado.json"
        assert (tmp_path / "meu_resultado.json").is_file()

    def test_sem_dialogo_disponivel(self, ctrl):
        resposta = ctrl.baixar_resultado(*CHAVE)
        assert resposta == {"ok": False, "erro": "Salvar arquivo indisponível."}

    def test_sem_resultado_nao_abre_o_dialogo(self, pasta):
        chamadas = []
        controller = Controller(
            pasta, seletor_destino=lambda nome: chamadas.append(nome) or "x.json"
        )
        controller.avaliar_reembolso(str(EXEMPLO))  # carregado, mas não validado
        resposta = controller.baixar_resultado(*CHAVE)
        assert resposta["ok"] is False and "não encontrado" in resposta["erro"]
        assert chamadas == []

    def test_pasta_interna_e_recusada_com_mensagem_amigavel(self, baixador, pasta):
        controller, escolha = baixador
        escolha["destino"] = str(
            pasta / "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json"
        )
        antes = (pasta / "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json").read_bytes()
        resposta = serializavel(controller.baixar_resultado(*CHAVE))
        assert resposta["ok"] is False and "Escolha outro local" in resposta["erro"]
        validado = pasta / "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json"
        assert validado.read_bytes() == antes  # registro validado intacto

    def test_falha_de_disco_ao_gravar(self, baixador, monkeypatch):
        controller, _ = baixador

        def falha(origem, destino):
            raise OSError("disco cheio")

        monkeypatch.setattr(os, "replace", falha)
        resposta = controller.baixar_resultado(*CHAVE)
        assert resposta["ok"] is False and "disco cheio" in resposta["erro"]

    def test_parametros_invalidos(self, baixador):
        controller, _ = baixador
        resposta = controller.baixar_resultado("c_1", "CC", "2026-07")
        assert resposta["ok"] is False
