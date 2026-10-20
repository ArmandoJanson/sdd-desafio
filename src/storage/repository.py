"""Leitura, escrita e checagem de JSONs em ``./colaborador/`` (plan.md, seção 3.2).

Convenção de nomes:
    ``{id}_{centro_custo}_{competencia}.json``              solicitação
    ``{id}_{centro_custo}_{competencia}_validado.json``     solicitação validada
    ``{id}_{centro_custo}_{competencia}_resultado.json``    resultado da auditoria

Consolidação de duplicidades (T-013) e tratamento de JSON corrompido na
listagem (T-014) ficam fora deste módulo.
"""

import json
import os
import re
import tempfile
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

import config
from core.models import SolicitacaoReembolso

ModeloT = TypeVar("ModeloT", bound=BaseModel)

_SUFIXOS_VALIDOS = ("", config.SUFIXO_VALIDADO, config.SUFIXO_RESULTADO)
# Caracteres proibidos em nome de arquivo no Windows (inclui separadores de
# caminho, que permitiriam escapar do diretório de persistência).
_CARACTERES_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class RepositorioError(Exception):
    """Erro base da camada de persistência."""


class NomeArquivoInvalidoError(RepositorioError, ValueError):
    """Identificador que não pode compor um nome de arquivo seguro."""


class ArquivoNaoEncontradoError(RepositorioError, FileNotFoundError):
    """Arquivo esperado não existe."""


class ArquivoCorrompidoError(RepositorioError):
    """Arquivo existe, mas não é JSON válido ou não obedece ao schema."""


# --------------------------------------------------------------------------
# Nomes e caminhos
# --------------------------------------------------------------------------


def _validar_parte(rotulo: str, valor: Optional[str], permite_underscore: bool) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise NomeArquivoInvalidoError(f"{rotulo} é obrigatório para nomear o arquivo")
    if (
        valor != valor.strip()
        or valor.endswith(".")
        or _CARACTERES_INVALIDOS.search(valor)
    ):
        raise NomeArquivoInvalidoError(
            f"{rotulo} inválido para nome de arquivo: {valor!r}"
        )
    if not permite_underscore and "_" in valor:
        # A listagem de competências (plan.md 4.2) separa o id pelo primeiro "_".
        raise NomeArquivoInvalidoError(f"{rotulo} não pode conter '_': {valor!r}")
    return valor


def nome_arquivo(
    id_colaborador: str,
    centro_custo: str,
    competencia: Optional[str],
    sufixo: str = "",
) -> str:
    """Monta ``{id}_{centro_custo}_{competencia}{sufixo}.json``."""
    if sufixo not in _SUFIXOS_VALIDOS:
        raise NomeArquivoInvalidoError(f"sufixo desconhecido: {sufixo!r}")
    partes = (
        _validar_parte("id do colaborador", id_colaborador, permite_underscore=False),
        _validar_parte("centro de custo", centro_custo, permite_underscore=True),
        _validar_parte("competência", competencia, permite_underscore=True),
    )
    return "_".join(partes) + sufixo + config.EXTENSAO_JSON


def _diretorio(diretorio: Optional[Path]) -> Path:
    return Path(diretorio) if diretorio is not None else config.COLABORADOR_DIR


def caminho_arquivo(
    id_colaborador: str,
    centro_custo: str,
    competencia: Optional[str],
    sufixo: str = "",
    diretorio: Optional[Path] = None,
) -> Path:
    nome = nome_arquivo(id_colaborador, centro_custo, competencia, sufixo)
    return _diretorio(diretorio) / nome


def localizar_solicitacao(
    id_colaborador: str,
    centro_custo: str,
    competencia: Optional[str],
    diretorio: Optional[Path] = None,
) -> Optional[Path]:
    """Caminho da solicitação existente (original ou ``_validado``), se houver."""
    for sufixo in ("", config.SUFIXO_VALIDADO):
        caminho = caminho_arquivo(
            id_colaborador, centro_custo, competencia, sufixo, diretorio
        )
        if caminho.is_file():
            return caminho
    return None


def existe_solicitacao(
    id_colaborador: str,
    centro_custo: str,
    competencia: Optional[str],
    diretorio: Optional[Path] = None,
) -> bool:
    return (
        localizar_solicitacao(id_colaborador, centro_custo, competencia, diretorio)
        is not None
    )


# --------------------------------------------------------------------------
# JSON em disco
# --------------------------------------------------------------------------


def _serializar(dados: Any) -> str:
    """JSON com ``Decimal`` escrito como número (ex.: ``72.50``), não texto.

    O ``json`` da biblioteca padrão não emite ``Decimal``; converter para
    ``float`` perderia o zero à direita exigido pela spec (duas casas).
    """
    marcador = f"__decimal_{uuid.uuid4().hex}__"

    def _default(objeto: Any) -> str:
        if isinstance(objeto, Decimal):
            return f"{marcador}{objeto:f}"
        if isinstance(objeto, date):
            return objeto.isoformat()
        raise TypeError(f"{type(objeto).__name__} não serializável em JSON")

    texto = json.dumps(dados, default=_default, ensure_ascii=False, indent=2)
    return re.sub(rf'"{marcador}([^"]+)"', r"\1", texto)


def salvar_json(caminho: Path, dados: Any) -> Path:
    """Grava ``dados`` (modelo Pydantic ou estrutura JSON) de forma atômica."""
    if isinstance(dados, BaseModel):
        dados = dados.model_dump(mode="python")
    texto = _serializar(dados)

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(
        dir=caminho.parent, prefix=f"{caminho.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descritor, "w", encoding=config.ENCODING, newline="\n") as f:
            f.write(texto)
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
    return caminho


def ler_json(caminho: Path) -> Any:
    """Lê um JSON preservando números decimais como ``Decimal``."""
    caminho = Path(caminho)
    try:
        # utf-8-sig tolera BOM, comum em arquivos salvos no Windows.
        texto = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError as erro:
        raise ArquivoNaoEncontradoError(f"arquivo não encontrado: {caminho}") from erro
    except UnicodeDecodeError as erro:
        raise ArquivoCorrompidoError(
            f"O arquivo '{caminho.name}' não está em UTF-8 e não pode ser lido."
        ) from erro
    try:
        return json.loads(texto, parse_float=Decimal)
    except json.JSONDecodeError as erro:
        raise ArquivoCorrompidoError(
            f"O arquivo '{caminho.name}' está malformado: não é um JSON válido "
            f"(erro na linha {erro.lineno}, coluna {erro.colno})."
        ) from erro


# --------------------------------------------------------------------------
# Mensagens de validação em português
# --------------------------------------------------------------------------

MAXIMO_PROBLEMAS_NA_MENSAGEM = 5

_ROTULOS_DE_SECAO = {"periodo": "Período", "colaborador": "Colaborador"}

_MOTIVOS_POR_TIPO = {
    "missing": "campo obrigatório não informado",
    "string_too_short": "não pode ficar vazio",
    "string_type": "deve ser um texto",
    "bool_type": "deve ser verdadeiro ou falso",
    "list_type": "deve ser uma lista",
    "dict_type": "deve ser um objeto",
    "model_type": "deve ser um objeto",
}


def _id_da_despesa(dados: Any, indice: int) -> Optional[str]:
    try:
        identificador = dados["despesas"][indice]["id"]
    except (KeyError, IndexError, TypeError):
        return None
    return identificador if isinstance(identificador, str) and identificador else None


def _descrever_local(local: tuple, dados: Any) -> str:
    if not local:
        return "Conteúdo do arquivo"
    secao, resto = local[0], local[1:]
    if secao == "despesas" and not resto:
        return "Lista de despesas"
    if secao == "despesas":
        indice, campo = resto[0], resto[1:]
        rotulo = f"Despesa nº {indice + 1}"
        identificador = _id_da_despesa(dados, indice)
        if identificador:
            rotulo += f" (id {identificador})"
    elif secao in _ROTULOS_DE_SECAO:
        rotulo, campo = _ROTULOS_DE_SECAO[secao], resto
    else:
        return f"Campo '{'.'.join(str(parte) for parte in local)}'"
    if campo:
        rotulo += f", campo '{'.'.join(str(parte) for parte in campo)}'"
    return rotulo


def _descrever_motivo(problema: dict) -> str:
    if problema["type"] == "value_error":
        return str(problema["ctx"]["error"])
    if problema["type"] == "model_type" and not problema["loc"]:
        return "o conteúdo deve ser um objeto com colaborador, periodo e despesas"
    return _MOTIVOS_POR_TIPO.get(problema["type"], "valor inválido")


def descrever_erros_de_validacao(
    erro: ValidationError, dados: Any, nome_arquivo: str
) -> str:
    """Traduz os erros do Pydantic para uma mensagem em português e sem jargão."""
    problemas = erro.errors()
    linhas = [
        f"• {_descrever_local(p['loc'], dados)}: {_descrever_motivo(p)}."
        for p in problemas[:MAXIMO_PROBLEMAS_NA_MENSAGEM]
    ]
    restantes = len(problemas) - MAXIMO_PROBLEMAS_NA_MENSAGEM
    if restantes > 0:
        linhas.append(f"• … e mais {restantes} problema(s).")
    cabecalho = f"O arquivo '{nome_arquivo}' tem dados inválidos:"
    return cabecalho + "\n" + "\n".join(linhas)


# --------------------------------------------------------------------------
# Solicitações de reembolso
# --------------------------------------------------------------------------


def salvar_solicitacao(
    solicitacao: SolicitacaoReembolso, diretorio: Optional[Path] = None
) -> Path:
    """Grava ``{id}_{centro_custo}_{competencia}.json``, sobrescrevendo se existir."""
    caminho = caminho_arquivo(
        solicitacao.colaborador.id,
        solicitacao.colaborador.centro_custo,
        solicitacao.periodo.competencia,
        diretorio=diretorio,
    )
    return salvar_json(caminho, solicitacao)


def ler_solicitacao(
    id_colaborador: str,
    centro_custo: str,
    competencia: Optional[str],
    diretorio: Optional[Path] = None,
) -> SolicitacaoReembolso:
    caminho = localizar_solicitacao(
        id_colaborador, centro_custo, competencia, diretorio
    )
    if caminho is None:
        raise ArquivoNaoEncontradoError(
            "solicitação não encontrada para "
            f"{id_colaborador}/{centro_custo}/{competencia}"
        )
    return ler_solicitacao_arquivo(caminho)


def ler_modelo(caminho: Path, tipo: Type[ModeloT]) -> ModeloT:
    """Lê um JSON e valida o schema contra o modelo ``tipo``."""
    dados = ler_json(caminho)
    try:
        return tipo.model_validate(dados)
    except ValidationError as erro:
        raise ArquivoCorrompidoError(
            descrever_erros_de_validacao(erro, dados, Path(caminho).name)
        ) from erro


def ler_solicitacao_arquivo(caminho: Path) -> SolicitacaoReembolso:
    """Lê e valida o schema de uma solicitação em um caminho qualquer."""
    return ler_modelo(caminho, SolicitacaoReembolso)
