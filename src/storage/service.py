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
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

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


class CompetenciaFuturaError(RepositorioError):
    """RN-012: a competência é posterior ao mês atual e não pode ser carregada."""

    def __init__(self, competencia: str, atual: str):
        self.competencia = competencia
        self.atual = atual
        super().__init__(
            f"A competência {competencia} é futura: só é possível carregar "
            f"competências até o mês atual ({atual})."
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


@dataclass(frozen=True)
class EntradaCompetencia:
    """Uma competência encontrada em ``./colaborador/`` (plan.md, 4.2)."""

    id_colaborador: str
    centro_custo: str
    competencia: str
    nome: Optional[str] = None
    validado: bool = False
    tem_resultado: bool = False
    corrompido: bool = False
    erro: Optional[str] = None
    total_despesas: Optional[int] = None


def hoje() -> date:
    """Data do relógio do computador (ponto único para os testes fixarem)."""
    return date.today()


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

    Nada é gravado se houver erro: a competência inválida (RN-009), a competência
    futura (RN-012), o conflito de ids, a competência já validada e o arquivo
    existente corrompido são detectados antes da escrita.
    """
    competencia = nova.periodo.competencia
    if not rules.competencia_valida(competencia):
        raise engine.CompetenciaInvalidaError(
            f"competência deve seguir o formato YYYY-MM, recebido: {competencia!r}"
        )
    agora = hoje()
    if rules.competencia_futura(competencia, agora):  # RN-012
        raise CompetenciaFuturaError(competencia, rules.competencia_atual(agora))
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


# --------------------------------------------------------------------------
# Listagem e consulta (T-016, T-018)
# --------------------------------------------------------------------------


def _interpretar_nome(nome: str) -> Optional[Tuple[str, str, str, str]]:
    """``(id, centro_custo, competencia, sufixo)`` ou ``None`` se não for nosso."""
    if not nome.endswith(config.EXTENSAO_JSON):
        return None
    base = nome[: -len(config.EXTENSAO_JSON)]
    sufixo = ""
    for candidato in (config.SUFIXO_VALIDADO, config.SUFIXO_RESULTADO):
        if base.endswith(candidato):
            base, sufixo = base[: -len(candidato)], candidato
            break
    partes = base.split("_")
    if len(partes) < 3:
        return None
    id_colaborador, centro_custo, competencia = (
        partes[0],
        "_".join(partes[1:-1]),
        partes[-1],
    )
    if not (id_colaborador and centro_custo and competencia):
        return None
    return id_colaborador, centro_custo, competencia, sufixo


def listar_competencias(
    diretorio: Optional[Path] = None, id_colaborador: Optional[str] = None
) -> List[EntradaCompetencia]:
    """Varre ``./colaborador/`` e descreve cada competência encontrada.

    Arquivo ilegível ou corrompido não derruba a listagem: a competência sai
    com ``corrompido=True`` e o motivo em ``erro``. Arquivos que não seguem a
    nomenclatura são ignorados. A ordem é por colaborador e competência.
    """
    pasta = Path(diretorio) if diretorio is not None else config.COLABORADOR_DIR
    grupos: Dict[Tuple[str, str, str], Dict[str, Path]] = {}
    try:
        encontrados = sorted(pasta.iterdir()) if pasta.is_dir() else []
    except OSError as erro:
        raise FalhaDePersistenciaError(f"falha ao listar {pasta}: {erro}") from erro
    for arquivo in encontrados:
        interpretado = _interpretar_nome(arquivo.name)
        if interpretado is None or not arquivo.is_file():
            continue
        id_, centro_custo, competencia, sufixo = interpretado
        if id_colaborador is not None and id_ != id_colaborador:
            continue
        grupos.setdefault((id_, centro_custo, competencia), {})[sufixo] = arquivo

    entradas = [
        _descrever_competencia(chave, arquivos) for chave, arquivos in grupos.items()
    ]
    return sorted(
        entradas, key=lambda e: (e.id_colaborador, e.competencia, e.centro_custo)
    )


def _descrever_competencia(
    chave: Tuple[str, str, str], arquivos: Dict[str, Path]
) -> EntradaCompetencia:
    id_, centro_custo, competencia = chave
    validado = config.SUFIXO_VALIDADO in arquivos
    base = dict(
        id_colaborador=id_,
        centro_custo=centro_custo,
        competencia=competencia,
        validado=validado,
        tem_resultado=config.SUFIXO_RESULTADO in arquivos,
    )
    origem = arquivos.get(config.SUFIXO_VALIDADO) or arquivos.get("")
    if origem is None:
        return EntradaCompetencia(
            **base, corrompido=True, erro="solicitação ausente (só há resultado)"
        )
    try:
        solicitacao = repository.ler_solicitacao_arquivo(origem)
    except RepositorioError as erro:
        return EntradaCompetencia(**base, corrompido=True, erro=str(erro))
    return EntradaCompetencia(
        **base,
        nome=solicitacao.colaborador.nome,
        total_despesas=len(solicitacao.despesas),
    )


def obter_resultado(
    id_colaborador: str,
    centro_custo: str,
    competencia: str,
    diretorio: Optional[Path] = None,
) -> ResultadoAuditoria:
    """Lê o ``_resultado.json`` gerado pela validação da competência."""
    caminho = repository.caminho_arquivo(
        id_colaborador,
        centro_custo,
        competencia,
        sufixo=config.SUFIXO_RESULTADO,
        diretorio=diretorio,
    )
    with _erros_de_disco():
        return repository.ler_modelo(caminho, ResultadoAuditoria)
