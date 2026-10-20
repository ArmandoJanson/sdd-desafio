"""Consolidação e ciclo de vida dos arquivos em ``./colaborador/`` (plan.md, 4.1 e 4.3).

Estados de uma competência no disco:
    ``{id}_{cc}_{comp}.json``            carregada, ainda não validada
    ``{id}_{cc}_{comp}_resultado.json``  auditoria gerada pela validação
    ``{id}_{cc}_{comp}_validado.json``   solicitação já validada (imutável)

Toda falha previsível sai como subclasse de ``RepositorioError``; a interface
captura esse tipo único e não precisa conhecer ``OSError`` ou ``JSONDecodeError``.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import config
from core import engine, rules
from core.models import Despesa, ResultadoAuditoria, SolicitacaoReembolso
from storage import repository
from storage.repository import RepositorioError

TENTATIVAS_RENOMEAR = 3
ESPERA_ENTRE_TENTATIVAS = 0.05  # segundos


class IdDespesaConflitanteError(RepositorioError):
    """Despesa nova reutiliza o id de outra, mas com conteúdo diferente."""

    def __init__(self, ids: Sequence[str]):
        self.ids = list(ids)
        super().__init__(
            "Já existe uma despesa com o id informado e conteúdo diferente: "
            f"{', '.join(self.ids)}. Ajuste o id ou o conteúdo e envie novamente."
        )


class CompetenciaJaValidadaError(RepositorioError):
    """A competência já foi validada e não aceita novos envios nem nova validação."""


class FalhaDePersistenciaError(RepositorioError):
    """Erro de disco (permissão, espaço, bloqueio) ao ler, gravar ou renomear."""


@dataclass(frozen=True)
class ResultadoConsolidacao:
    caminho: Path
    criado: bool
    novas: int
    ignoradas: int


@dataclass(frozen=True)
class ResultadoValidacao:
    resultado: ResultadoAuditoria
    caminho_resultado: Path
    caminho_validado: Path


@contextmanager
def _erros_de_disco():
    try:
        yield
    except RepositorioError:
        raise
    except OSError as erro:
        raise FalhaDePersistenciaError(f"falha de E/S em disco: {erro}") from erro


# --------------------------------------------------------------------------
# Consolidação (T-013)
# --------------------------------------------------------------------------


def mesclar_despesas(
    existentes: Sequence[Despesa], novas: Sequence[Despesa]
) -> Tuple[List[Despesa], int, int]:
    """Acrescenta ``novas`` a ``existentes`` identificando pelo id da despesa.

    Devolve ``(despesas, adicionadas, ignoradas)``. Id repetido com conteúdo
    idêntico é ignorado (reenvio não duplica); com conteúdo diferente levanta
    ``IdDespesaConflitanteError``. Duplicatas perfeitas com ids distintos são
    mantidas: quem as julga é o motor (RN-007).
    """
    por_id = {despesa.id: despesa for despesa in existentes}
    resultado = list(existentes)
    conflitos: List[str] = []
    adicionadas = ignoradas = 0
    for despesa in novas:
        atual = por_id.get(despesa.id)
        if atual is None:
            por_id[despesa.id] = despesa
            resultado.append(despesa)
            adicionadas += 1
        elif atual == despesa:
            ignoradas += 1
        elif despesa.id not in conflitos:
            conflitos.append(despesa.id)
    if conflitos:
        raise IdDespesaConflitanteError(conflitos)
    return resultado, adicionadas, ignoradas


def consolidar_solicitacao(
    nova: SolicitacaoReembolso, diretorio: Optional[Path] = None
) -> ResultadoConsolidacao:
    """Cria ou atualiza ``{id}_{cc}_{comp}.json`` sem duplicar lançamentos.

    Nada é gravado se houver erro: a competência inválida (RN-009), o conflito
    de ids, a competência já validada e o arquivo existente corrompido são
    detectados antes da escrita.
    """
    competencia = nova.periodo.competencia
    if not rules.competencia_valida(competencia):
        raise engine.CompetenciaInvalidaError(
            f"competência deve seguir o formato YYYY-MM, recebido: {competencia!r}"
        )
    chave = (nova.colaborador.id, nova.colaborador.centro_custo, competencia)
    caminho = repository.caminho_arquivo(*chave, diretorio=diretorio)
    validado = repository.caminho_arquivo(
        *chave, sufixo=config.SUFIXO_VALIDADO, diretorio=diretorio
    )

    with _erros_de_disco():
        if validado.is_file():
            raise CompetenciaJaValidadaError(
                f"a competência {competencia} já foi validada e não aceita novos envios"
            )
        criado = not caminho.is_file()
        if criado:
            base = nova.model_copy(update={"despesas": []})
        else:
            base = repository.ler_solicitacao_arquivo(
                caminho
            )  # cabeçalho existente vale
        despesas, adicionadas, ignoradas = mesclar_despesas(
            base.despesas, nova.despesas
        )
        if criado or adicionadas:
            repository.salvar_json(
                caminho, base.model_copy(update={"despesas": despesas})
            )
    return ResultadoConsolidacao(caminho, criado, adicionadas, ignoradas)


def carregar_arquivo(
    origem: Path, diretorio: Optional[Path] = None
) -> ResultadoConsolidacao:
    """Lê um JSON escolhido pelo usuário e o consolida em ``./colaborador/``."""
    with _erros_de_disco():
        nova = repository.ler_solicitacao_arquivo(Path(origem))
    return consolidar_solicitacao(nova, diretorio)


# --------------------------------------------------------------------------
# Validação (T-022)
# --------------------------------------------------------------------------


def _renomear(origem: Path, destino: Path) -> None:
    """Renomeia com poucas retentativas (arquivo pode estar bloqueado pelo SO)."""
    tentativa = 1
    while True:
        try:
            origem.rename(destino)
            return
        except OSError:
            if tentativa >= TENTATIVAS_RENOMEAR:
                raise
            time.sleep(ESPERA_ENTRE_TENTATIVAS)
            tentativa += 1


def validar_competencia(
    id_colaborador: str,
    centro_custo: str,
    competencia: str,
    diretorio: Optional[Path] = None,
) -> ResultadoValidacao:
    """Avalia a competência, grava ``_resultado.json`` e renomeia para ``_validado``.

    Se o renomear falhar, o ``_resultado.json`` recém-gravado é removido e o
    arquivo original permanece intacto.
    """
    chave = (id_colaborador, centro_custo, competencia)
    original = repository.caminho_arquivo(*chave, diretorio=diretorio)
    validado = repository.caminho_arquivo(
        *chave, sufixo=config.SUFIXO_VALIDADO, diretorio=diretorio
    )
    caminho_resultado = repository.caminho_arquivo(
        *chave, sufixo=config.SUFIXO_RESULTADO, diretorio=diretorio
    )

    with _erros_de_disco():
        if validado.is_file():
            raise CompetenciaJaValidadaError(
                f"a competência {competencia} já foi validada"
            )
        solicitacao = repository.ler_solicitacao_arquivo(original)
        resultado = engine.avaliar(solicitacao)
        repository.salvar_json(caminho_resultado, resultado)
        try:
            _renomear(original, validado)
        except OSError:
            caminho_resultado.unlink(missing_ok=True)
            raise
    return ResultadoValidacao(resultado, caminho_resultado, validado)
