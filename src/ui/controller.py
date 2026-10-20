"""API exposta à interface PyWebView (plan.md, seção 2: Interface Controller).

Todo método público é chamável pelo JavaScript e devolve um ``dict`` seguro
para JSON com a chave ``ok``. Falhas previsíveis viram
``{"ok": False, "erro": <mensagem>}`` em vez de exceção, para a tela exibi-las.
Este módulo não importa ``webview``: a escolha do arquivo é injetada.
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.engine import CompetenciaInvalidaError
from storage import service
from storage.repository import RepositorioError

SeletorArquivo = Callable[[], Optional[str]]
Resposta = Dict[str, object]

_ERROS_TRATADOS = (RepositorioError, CompetenciaInvalidaError)


def _falha(erro: Exception) -> Resposta:
    return {"ok": False, "erro": str(erro)}


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural}"


class Controller:
    def __init__(
        self,
        diretorio: Optional[Path] = None,
        seletor_arquivo: Optional[SeletorArquivo] = None,
    ):
        # Atributos privados: o PyWebView só expõe o que não começa com "_".
        self._diretorio = Path(diretorio) if diretorio is not None else None
        self._seletor_arquivo = seletor_arquivo

    def selecionar_arquivo(self) -> Resposta:
        """Abre o diálogo de escolha de JSON; ``caminho`` é ``None`` se cancelar."""
        if self._seletor_arquivo is None:
            return {"ok": False, "erro": "Seleção de arquivo indisponível."}
        return {"ok": True, "caminho": self._seletor_arquivo()}

    def avaliar_reembolso(self, caminho_json: str) -> Resposta:
        """Carrega o JSON escolhido e o consolida em ``./colaborador/``."""
        if not isinstance(caminho_json, str) or not caminho_json.strip():
            return {"ok": False, "erro": "Nenhum arquivo informado."}
        try:
            consolidacao = service.carregar_arquivo(Path(caminho_json), self._diretorio)
        except _ERROS_TRATADOS as erro:
            return _falha(erro)
        return {
            "ok": True,
            "arquivo": consolidacao.caminho.name,
            "criado": consolidacao.criado,
            "novas": consolidacao.novas,
            "ignoradas": consolidacao.ignoradas,
            "mensagem": _mensagem_consolidacao(consolidacao),
        }

    def listar_colaboradores_competencias(self) -> Resposta:
        """Colaboradores com suas competências e o indicador de validação."""
        try:
            entradas = service.listar_competencias(self._diretorio)
        except _ERROS_TRATADOS as erro:
            return _falha(erro)
        nomes: Dict[str, str] = {}
        competencias: Dict[str, List[Dict[str, object]]] = {}
        for entrada in entradas:
            if entrada.nome:
                nomes.setdefault(entrada.id_colaborador, entrada.nome)
            competencias.setdefault(entrada.id_colaborador, []).append(
                {
                    "centro_custo": entrada.centro_custo,
                    "competencia": entrada.competencia,
                    "validado": entrada.validado,
                    "tem_resultado": entrada.tem_resultado,
                    "corrompido": entrada.corrompido,
                    "erro": entrada.erro,
                    "total_despesas": entrada.total_despesas,
                }
            )
        colaboradores = [
            {"id": id_, "nome": nomes.get(id_, id_), "competencias": lista}
            for id_, lista in competencias.items()
        ]
        return {"ok": True, "colaboradores": colaboradores}

    def validar_competencia(
        self, id: str, centro_custo: str, competencia: str  # noqa: A002
    ) -> Resposta:
        """Audita a competência, grava o resultado e marca como validada."""
        try:
            validacao = service.validar_competencia(
                id, centro_custo, competencia, self._diretorio
            )
        except _ERROS_TRATADOS as erro:
            return _falha(erro)
        return {
            "ok": True,
            "arquivo_resultado": validacao.caminho_resultado.name,
            "arquivo_validado": validacao.caminho_validado.name,
            "mensagem": f"Competência {competencia} validada.",
        }

    def obter_resultado(
        self, id: str, centro_custo: str, competencia: str  # noqa: A002
    ) -> Resposta:
        """Auditoria já gerada; valores monetários como texto com 2 casas."""
        try:
            resultado = service.obter_resultado(
                id, centro_custo, competencia, self._diretorio
            )
        except _ERROS_TRATADOS as erro:
            return _falha(erro)
        return {"ok": True, "resultado": resultado.model_dump(mode="json")}


def _mensagem_consolidacao(consolidacao: service.ResultadoConsolidacao) -> str:
    novas, ignoradas = consolidacao.novas, consolidacao.ignoradas
    if consolidacao.criado:
        return f"Arquivo criado com {_plural(novas, 'despesa', 'despesas')}."
    if novas == 0:
        return "Nenhuma despesa nova: todas já estavam registradas."
    return (
        f"Arquivo atualizado: {_plural(novas, 'despesa nova', 'despesas novas')} "
        f"e {_plural(ignoradas, 'já registrada', 'já registradas')}."
    )
