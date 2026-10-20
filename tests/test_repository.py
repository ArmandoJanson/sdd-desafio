"""Testes do repositório de I/O em ./colaborador/ (T-003)."""

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import config
from core.models import ResultadoAuditoria, SolicitacaoReembolso
from storage import repository
from storage.repository import (
    ArquivoCorrompidoError,
    ArquivoNaoEncontradoError,
    NomeArquivoInvalidoError,
    RepositorioError,
)


def solicitacao(id_="c-0417", cc="CC-ENG-PLATAFORMA", competencia="2026-07"):
    return SolicitacaoReembolso.model_validate(
        {
            "colaborador": {"id": id_, "nome": "Marina Volpi", "centro_custo": cc},
            "periodo": {
                "competencia": competencia,
                "inicio": "2026-07-01",
                "fim": "2026-07-31",
            },
            "despesas": [
                {
                    "id": "d-001",
                    "data": "2026-07-03",
                    "categoria": "alimentacao",
                    "descricao": "Almoço com cliente",
                    "fornecedor": "Restaurante Távola",
                    "valor": 72.5,
                    "tem_nota_fiscal": True,
                },
                {
                    "id": "d-002",
                    "data": "2026-07-04",
                    "categoria": "transporte_urbano",
                    "descricao": "Corrida",
                    "fornecedor": "TaxiApp",
                    "valor": 100,
                    "tem_nota_fiscal": False,
                },
            ],
        }
    )


# --------------------------------------------------------------------------
# Nomenclatura
# --------------------------------------------------------------------------


class TestNomeArquivo:
    def test_padrao_id_centro_custo_competencia(self):
        assert (
            repository.nome_arquivo("c-0417", "CC-ENG-PLATAFORMA", "2026-07")
            == "c-0417_CC-ENG-PLATAFORMA_2026-07.json"
        )

    @pytest.mark.parametrize(
        "sufixo, esperado",
        [
            ("", "c-1_CC-A_2026-07.json"),
            (config.SUFIXO_VALIDADO, "c-1_CC-A_2026-07_validado.json"),
            (config.SUFIXO_RESULTADO, "c-1_CC-A_2026-07_resultado.json"),
        ],
    )
    def test_sufixos_de_estado(self, sufixo, esperado):
        assert repository.nome_arquivo("c-1", "CC-A", "2026-07", sufixo) == esperado

    def test_sufixo_desconhecido(self):
        with pytest.raises(NomeArquivoInvalidoError):
            repository.nome_arquivo("c-1", "CC-A", "2026-07", "_qualquer")

    def test_centro_custo_pode_ter_underscore(self):
        nome = repository.nome_arquivo("c-1", "CC_ENG", "2026-07")
        assert nome == "c-1_CC_ENG_2026-07.json"

    @pytest.mark.parametrize(
        "id_, cc, comp",
        [
            ("", "CC", "2026-07"),
            ("c-1", "", "2026-07"),
            ("c-1", "CC", ""),
            ("c-1", "CC", None),
            (None, "CC", "2026-07"),
            ("   ", "CC", "2026-07"),
            ("c_1", "CC", "2026-07"),  # "_" quebraria a listagem por prefixo do id
            ("../c", "CC", "2026-07"),
            ("c-1", "CC/ENG", "2026-07"),
            ("c-1", "CC\\ENG", "2026-07"),
            ("c-1", "CC", "2026/07"),
            ("c-1", "CC", ".."),
            ("c-1", "CC", "2026-07."),
            ("c-1", "CC", " 2026-07"),
            ("c-1", "C:C", "2026-07"),
            ("c-1", "CC", "2026-07\x00"),
            ("c-1", "CC*", "2026-07"),
        ],
    )
    def test_partes_invalidas(self, id_, cc, comp):
        with pytest.raises(NomeArquivoInvalidoError):
            repository.nome_arquivo(id_, cc, comp)

    def test_erro_de_nome_e_value_error_e_repositorio_error(self):
        with pytest.raises(ValueError):
            repository.nome_arquivo("", "CC", "2026-07")
        with pytest.raises(RepositorioError):
            repository.nome_arquivo("", "CC", "2026-07")

    def test_caminho_usa_diretorio_informado(self, tmp_path):
        caminho = repository.caminho_arquivo("c-1", "CC", "2026-07", diretorio=tmp_path)
        assert caminho == tmp_path / "c-1_CC_2026-07.json"

    def test_caminho_padrao_e_a_pasta_colaborador(self):
        caminho = repository.caminho_arquivo("c-1", "CC", "2026-07")
        assert caminho.parent == config.COLABORADOR_DIR
        assert config.COLABORADOR_DIR.name == "colaborador"


# --------------------------------------------------------------------------
# Escrita
# --------------------------------------------------------------------------


class TestSalvar:
    def test_persiste_arquivo_novo_com_nome_padronizado(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        assert caminho == tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07.json"
        assert caminho.is_file()

    def test_cria_diretorio_inexistente(self, tmp_path):
        destino = tmp_path / "a" / "colaborador"
        repository.salvar_solicitacao(solicitacao(), diretorio=destino)
        assert (destino / "c-0417_CC-ENG-PLATAFORMA_2026-07.json").is_file()

    def test_sobrescreve_arquivo_existente(self, tmp_path):
        repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        nova = solicitacao()
        nova.despesas.pop()
        repository.salvar_solicitacao(nova, diretorio=tmp_path)
        lida = repository.ler_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
        )
        assert len(lida.despesas) == 1

    def test_valores_gravados_como_numero_com_duas_casas(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        texto = caminho.read_text("utf-8")
        assert '"valor": 72.50' in texto
        assert '"valor": 100.00' in texto
        assert '"72.50"' not in texto  # nunca como string
        dados = json.loads(texto)  # JSON válido para qualquer leitor
        assert dados["despesas"][0]["valor"] == 72.5

    def test_datas_gravadas_em_iso(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        dados = json.loads(caminho.read_text("utf-8"))
        assert dados["periodo"]["inicio"] == "2026-07-01"
        assert dados["despesas"][0]["data"] == "2026-07-03"

    def test_acentos_preservados_em_utf8(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        assert "Almoço com cliente" in caminho.read_bytes().decode("utf-8")

    def test_nao_deixa_temporarios(self, tmp_path):
        repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        assert [p.suffix for p in tmp_path.iterdir()] == [".json"]

    def test_falha_na_escrita_preserva_original_e_limpa_temporario(
        self, tmp_path, monkeypatch
    ):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        original = caminho.read_bytes()

        def falha(origem, destino):
            raise OSError("disco cheio")

        monkeypatch.setattr(os, "replace", falha)
        with pytest.raises(OSError, match="disco cheio"):
            repository.salvar_solicitacao(solicitacao(competencia="2026-07"), tmp_path)

        assert caminho.read_bytes() == original
        assert list(tmp_path.iterdir()) == [caminho]

    def test_competencia_nula_nao_gera_arquivo(self, tmp_path):
        with pytest.raises(NomeArquivoInvalidoError):
            repository.salvar_solicitacao(solicitacao(competencia=None), tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_salvar_json_aceita_modelo_de_saida(self, tmp_path):
        resultado = ResultadoAuditoria.model_validate(
            {
                "colaborador": {"id": "c-1", "centro_custo": "CC"},
                "historico_despesas": [
                    {
                        "competencia": "2026-07",
                        "centro_custo": "CC",
                        "despesas": [
                            {
                                "id": "d-1",
                                "data": "2026-07-03",
                                "descricao": "x",
                                "fornecedor": "y",
                                "status_item": "aprovado",
                                "justificativa": "Despesa aprovada integralmente.",
                                "valor_reembolsado": 38,
                            }
                        ],
                    }
                ],
            }
        )
        caminho = tmp_path / repository.nome_arquivo(
            "c-1", "CC", "2026-07", config.SUFIXO_RESULTADO
        )
        repository.salvar_json(caminho, resultado)
        assert '"valor_reembolsado": 38.00' in caminho.read_text("utf-8")
        assert ResultadoAuditoria.model_validate(repository.ler_json(caminho)) == (
            resultado
        )

    def test_salvar_json_aceita_estrutura_simples(self, tmp_path):
        caminho = repository.salvar_json(
            tmp_path / "x.json",
            {"v": Decimal("1.50"), "d": date(2026, 7, 3), "n": None, "s": "ok"},
        )
        assert json.loads(caminho.read_text("utf-8")) == {
            "v": 1.5,
            "d": "2026-07-03",
            "n": None,
            "s": "ok",
        }

    def test_texto_parecido_com_marcador_nao_e_alterado(self, tmp_path):
        caminho = repository.salvar_json(
            tmp_path / "x.json", {"s": '"__decimal_abc__1.00"', "v": Decimal("2")}
        )
        dados = repository.ler_json(caminho)
        assert dados["s"] == '"__decimal_abc__1.00"'
        assert dados["v"] == Decimal("2")

    def test_tipo_nao_serializavel(self, tmp_path):
        with pytest.raises(TypeError, match="object"):
            repository.salvar_json(tmp_path / "x.json", {"o": object()})
        assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# Leitura e checagem
# --------------------------------------------------------------------------


class TestLer:
    def test_roundtrip_preserva_decimais_exatos(self, tmp_path):
        original = solicitacao()
        repository.salvar_solicitacao(original, diretorio=tmp_path)
        lida = repository.ler_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
        )
        assert lida == original
        assert [str(d.valor) for d in lida.despesas] == ["72.50", "100.00"]
        assert all(isinstance(d.valor, Decimal) for d in lida.despesas)

    def test_le_arquivo_existente_escrito_por_fora(self, tmp_path):
        exemplo = Path(__file__).resolve().parent.parent / "exemplos"
        conteudo = (exemplo / "despesas-exemplo.json").read_bytes()
        (tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07.json").write_bytes(conteudo)
        lida = repository.ler_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
        )
        assert len(lida.despesas) == 14
        assert str(lida.despesas[10].valor) == "33.33"

    def test_le_arquivo_com_bom(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        caminho.write_bytes(b"\xef\xbb\xbf" + caminho.read_bytes())
        lida = repository.ler_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
        )
        assert len(lida.despesas) == 2

    def test_le_versao_validada_quando_original_nao_existe(self, tmp_path):
        original = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        validado = tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json"
        original.rename(validado)
        lida = repository.ler_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
        )
        assert lida == solicitacao()

    def test_arquivo_nao_encontrado(self, tmp_path):
        with pytest.raises(ArquivoNaoEncontradoError):
            repository.ler_solicitacao("c-1", "CC", "2026-07", diretorio=tmp_path)

    def test_nao_encontrado_e_file_not_found_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            repository.ler_json(tmp_path / "inexistente.json")

    def test_diretorio_inexistente_conta_como_nao_encontrado(self, tmp_path):
        with pytest.raises(ArquivoNaoEncontradoError):
            repository.ler_solicitacao("c-1", "CC", "2026-07", tmp_path / "nada")

    @pytest.mark.parametrize(
        "conteudo",
        [b"{nao e json", b"", b'{"colaborador": {', b"\xff\xfe\x00bad", b"[1, 2"],
    )
    def test_json_corrompido(self, tmp_path, conteudo):
        (tmp_path / "c-1_CC_2026-07.json").write_bytes(conteudo)
        with pytest.raises(ArquivoCorrompidoError):
            repository.ler_solicitacao("c-1", "CC", "2026-07", diretorio=tmp_path)

    @pytest.mark.parametrize(
        "conteudo",
        [
            "[]",
            "null",
            "{}",
            '{"colaborador": {"id": "c-1"}}',
        ],
    )
    def test_json_valido_com_schema_invalido(self, tmp_path, conteudo):
        (tmp_path / "c-1_CC_2026-07.json").write_text(conteudo, "utf-8")
        with pytest.raises(ArquivoCorrompidoError, match="schema inválido"):
            repository.ler_solicitacao("c-1", "CC", "2026-07", diretorio=tmp_path)

    def test_corrompido_e_repositorio_error(self, tmp_path):
        (tmp_path / "x.json").write_text("{", "utf-8")
        with pytest.raises(RepositorioError):
            repository.ler_json(tmp_path / "x.json")


class TestExiste:
    def test_inexistente(self, tmp_path):
        assert not repository.existe_solicitacao("c-1", "CC", "2026-07", tmp_path)
        assert (
            repository.localizar_solicitacao("c-1", "CC", "2026-07", tmp_path) is None
        )

    def test_existente(self, tmp_path):
        caminho = repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        args = ("c-0417", "CC-ENG-PLATAFORMA", "2026-07")
        assert repository.existe_solicitacao(*args, diretorio=tmp_path)
        assert repository.localizar_solicitacao(*args, diretorio=tmp_path) == caminho

    def test_versao_validada_conta_como_existente(self, tmp_path):
        (tmp_path / "c-1_CC_2026-07_validado.json").write_text("{}", "utf-8")
        assert repository.existe_solicitacao("c-1", "CC", "2026-07", tmp_path)

    def test_arquivo_de_resultado_nao_conta_como_solicitacao(self, tmp_path):
        (tmp_path / "c-1_CC_2026-07_resultado.json").write_text("{}", "utf-8")
        assert not repository.existe_solicitacao("c-1", "CC", "2026-07", tmp_path)

    def test_outra_competencia_nao_conta(self, tmp_path):
        repository.salvar_solicitacao(solicitacao(), diretorio=tmp_path)
        assert not repository.existe_solicitacao(
            "c-0417", "CC-ENG-PLATAFORMA", "2026-08", tmp_path
        )

    def test_diretorio_com_mesmo_nome_nao_conta_como_arquivo(self, tmp_path):
        (tmp_path / "c-1_CC_2026-07.json").mkdir()
        assert not repository.existe_solicitacao("c-1", "CC", "2026-07", tmp_path)

    def test_usa_pasta_colaborador_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path)
        repository.salvar_solicitacao(solicitacao())
        assert (tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07.json").is_file()
        assert repository.existe_solicitacao("c-0417", "CC-ENG-PLATAFORMA", "2026-07")
        assert repository.ler_solicitacao("c-0417", "CC-ENG-PLATAFORMA", "2026-07")
