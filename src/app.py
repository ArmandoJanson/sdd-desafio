"""Ponto de entrada desktop: ``python src/app.py``."""

from pathlib import Path
from typing import Optional

import config
from ui.controller import Controller

TITULO = "Reembolsos — Motor de Avaliação"
LARGURA, ALTURA = 1100, 720
TAMANHO_MINIMO = (800, 520)
INDEX_HTML = Path(__file__).resolve().parent / "ui" / "index.html"
FILTRO_JSON = "Arquivos JSON (*.json)"


def criar_janela(webview):
    """Cria a janela com o Controller vinculado à ponte JS (sem iniciar o loop)."""
    config.COLABORADOR_DIR.mkdir(parents=True, exist_ok=True)
    janelas = []

    def selecionar_arquivo() -> Optional[str]:
        escolhidos = janelas[0].create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False, file_types=(FILTRO_JSON,)
        )
        return escolhidos[0] if escolhidos else None

    controller = Controller(seletor_arquivo=selecionar_arquivo)
    janela = webview.create_window(
        TITULO,
        url=str(INDEX_HTML),
        js_api=controller,
        width=LARGURA,
        height=ALTURA,
        min_size=TAMANHO_MINIMO,
    )
    janelas.append(janela)
    return janela


def main() -> None:
    import webview  # importado aqui para os testes não exigirem uma GUI instalada

    criar_janela(webview)
    webview.start()


if __name__ == "__main__":  # pragma: no cover
    main()
