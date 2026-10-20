"""Ponto de entrada e frontend estático (T-004, T-016 a T-018), sem abrir janela."""

import re
import sys
import types
from pathlib import Path

import pytest

import app
import config
from ui.controller import Controller

UI = Path(__file__).resolve().parent.parent / "src" / "ui"


class JanelaFalsa:
    def __init__(self, escolhidos):
        self.escolhidos = escolhidos
        self.dialogos = []

    def create_file_dialog(self, tipo, **opcoes):
        self.dialogos.append((tipo, opcoes))
        return self.escolhidos


class WebviewFalso:
    """Substitui o módulo ``webview`` registrando as chamadas."""

    class FileDialog:
        OPEN = "OPEN"
        SAVE = "SAVE"

    def __init__(self, escolhidos=None):
        self.janela = JanelaFalsa(escolhidos)
        self.janelas_criadas = []
        self.iniciado = 0

    def create_window(self, titulo, **opcoes):
        self.janelas_criadas.append((titulo, opcoes))
        return self.janela

    def start(self):
        self.iniciado += 1


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path / "colaborador")


class TestJanela:
    def test_configura_a_janela(self):
        webview = WebviewFalso()
        janela = app.criar_janela(webview)
        assert janela is webview.janela
        ((titulo, opcoes),) = webview.janelas_criadas
        assert titulo == app.TITULO
        assert Path(opcoes["url"]) == app.INDEX_HTML
        assert Path(opcoes["url"]).is_file()
        assert (opcoes["width"], opcoes["height"]) == (app.LARGURA, app.ALTURA)
        assert opcoes["min_size"] == app.TAMANHO_MINIMO

    def test_vincula_o_controller_a_ponte_js(self):
        webview = WebviewFalso()
        app.criar_janela(webview)
        assert isinstance(webview.janelas_criadas[0][1]["js_api"], Controller)

    def test_cria_a_pasta_de_persistencia(self, tmp_path):
        app.criar_janela(WebviewFalso())
        assert (tmp_path / "colaborador").is_dir()

    def test_dialogo_devolve_o_primeiro_arquivo(self):
        webview = WebviewFalso(escolhidos=("C:/x/envio.json",))
        app.criar_janela(webview)
        controller = webview.janelas_criadas[0][1]["js_api"]
        assert controller.selecionar_arquivo() == {
            "ok": True,
            "caminho": "C:/x/envio.json",
        }
        tipo, opcoes = webview.janela.dialogos[0]
        assert tipo == "OPEN"
        assert opcoes == {"allow_multiple": False, "file_types": (app.FILTRO_JSON,)}

    @pytest.mark.parametrize("escolhidos", [None, ()])
    def test_dialogo_cancelado(self, escolhidos):
        webview = WebviewFalso(escolhidos=escolhidos)
        app.criar_janela(webview)
        controller = webview.janelas_criadas[0][1]["js_api"]
        assert controller.selecionar_arquivo() == {"ok": True, "caminho": None}

    def test_main_cria_a_janela_e_inicia_o_loop(self, monkeypatch):
        webview = WebviewFalso()
        modulo = types.ModuleType("webview")
        modulo.FileDialog = WebviewFalso.FileDialog
        modulo.create_window = webview.create_window
        modulo.start = webview.start
        monkeypatch.setitem(sys.modules, "webview", modulo)
        app.main()
        assert len(webview.janelas_criadas) == 1
        assert webview.iniciado == 1


class TestFrontend:
    """Verificações estáticas: sem navegador, garantem a fiação da tela."""

    def html(self):
        return (UI / "index.html").read_text("utf-8")

    def js(self):
        return (UI / "static" / "app.js").read_text("utf-8")

    def test_arquivos_existem_e_html_referencia_os_estaticos(self):
        html = self.html()
        assert (UI / "static" / "style.css").is_file()
        assert 'href="static/style.css"' in html
        assert 'src="static/app.js"' in html
        assert '<html lang="pt-BR">' in html

    def test_elementos_usados_pelo_js_existem_no_html(self):
        ids_html = set(re.findall(r'id="([^"]+)"', self.html()))
        ids_js = set(re.findall(r'el\("([^"]+)"\)', self.js()))
        assert ids_js <= ids_html, ids_js - ids_html

    def test_botoes_e_modal_da_tela(self):
        html = self.html()
        assert "Avaliar Reembolso" in html
        assert "<dialog" in html
        for coluna in ("Data", "Descrição", "Fornecedor", "Status", "Justificativa"):
            assert coluna in html

    def test_js_chama_somente_metodos_expostos_pelo_controller(self):
        chamados = set(re.findall(r"api\(\)\.(\w+)\(", self.js()))
        publicos = {n for n in dir(Controller) if not n.startswith("_")}
        assert chamados and chamados <= publicos, chamados - publicos

    def test_js_nao_injeta_html_de_dados_externos(self):
        assert "innerHTML" not in self.js()
        assert "insertAdjacentHTML" not in self.js()

    def test_validar_fica_desabilitado_quando_validado(self):
        assert "validar.disabled = competencia.validado" in self.js()

    def test_sem_dependencias_externas(self):
        conteudo = (
            self.html() + self.js() + (UI / "static" / "style.css").read_text("utf-8")
        )
        assert "http://" not in conteudo and "https://" not in conteudo

    def test_botao_baixar_resultado_vem_antes_de_fechar(self):
        html = self.html()
        assert 'id="btn-baixar"' in html and "Baixar resultado" in html
        assert html.index('id="btn-baixar"') < html.index('id="btn-fechar"')

    def test_baixar_resultado_chama_a_api_e_mostra_a_mensagem_no_painel(self):
        js = self.js()
        assert "api().baixar_resultado(" in js
        assert '"modal-mensagem"' in js
        assert 'el("btn-baixar").addEventListener("click", baixarResultado)' in js
        assert 'id="modal-mensagem"' in self.html()


class TestDialogoDeDestino:
    """O 'Salvar como' que o Controller usa para baixar o resultado."""

    def seletor(self, webview):
        app.criar_janela(webview)
        return webview.janelas_criadas[0][1]["js_api"]._seletor_destino

    def test_abre_o_dialogo_de_salvar_com_o_nome_sugerido(self, tmp_path, monkeypatch):
        (tmp_path / "Downloads").mkdir()
        monkeypatch.setattr(app, "PASTA_DOWNLOADS", tmp_path / "Downloads")
        webview = WebviewFalso(escolhidos="C:/x/saida.json")
        escolhido = self.seletor(webview)("c-1_CC_2026-07_resultado.json")
        assert escolhido == "C:/x/saida.json"
        tipo, opcoes = webview.janela.dialogos[0]
        assert tipo == "SAVE"
        assert opcoes == {
            "directory": str(tmp_path / "Downloads"),
            "save_filename": "c-1_CC_2026-07_resultado.json",
            "file_types": (app.FILTRO_JSON,),
        }

    def test_sem_pasta_downloads_usa_o_padrao_do_sistema(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app, "PASTA_DOWNLOADS", tmp_path / "nao_existe")
        webview = WebviewFalso(escolhidos="x.json")
        self.seletor(webview)("nome.json")
        assert webview.janela.dialogos[0][1]["directory"] == ""

    @pytest.mark.parametrize(
        "devolvido, esperado",
        [
            ("C:/x/a.json", "C:/x/a.json"),
            (("C:/x/a.json",), "C:/x/a.json"),
            (["C:/x/a.json"], "C:/x/a.json"),
            ((), None),
            (None, None),
            ("", None),
        ],
    )
    def test_normaliza_o_retorno_do_dialogo(self, devolvido, esperado):
        webview = WebviewFalso(escolhidos=devolvido)
        assert self.seletor(webview)("nome.json") == esperado
