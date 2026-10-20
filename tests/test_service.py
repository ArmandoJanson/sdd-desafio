"""Testes do serviço de consolidação e validação (T-013, T-014, T-022).

Integração com disco real em ``tmp_path``; nenhum teste toca ``./colaborador/``.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

import config
from core import engine
from core.models import ResultadoAuditoria, SolicitacaoReembolso
from storage import repository, service
from storage.repository import (
    ArquivoCorrompidoError,
    ArquivoNaoEncontradoError,
    NomeArquivoInvalidoError,
    RepositorioError,
)
from storage.service import (
    CompetenciaJaValidadaError,
    FalhaDePersistenciaError,
    IdDespesaConflitanteError,
)

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "despesas-exemplo.json"
CHAVE = ("c-1", "CC-X", "2026-10")
ORIGINAL = "c-1_CC-X_2026-10.json"
VALIDADO = "c-1_CC-X_2026-10_validado.json"
RESULTADO = "c-1_CC-X_2026-10_resultado.json"


def desp(
    id_, valor="10", categoria="alimentacao", descricao="Almoco", data="2026-10-15"
):
    return {
        "id": id_,
        "data": data,
        "categoria": categoria,
        "descricao": descricao,
        "fornecedor": "Restaurante",
        "valor": valor,
        "tem_nota_fiscal": True,
    }


def sol(
    despesas, nome="Ana", competencia="2026-10", inicio="2026-10-01", fim="2026-10-31"
):
    return SolicitacaoReembolso.model_validate(
        {
            "colaborador": {"id": "c-1", "nome": nome, "centro_custo": "CC-X"},
            "periodo": {"competencia": competencia, "inicio": inicio, "fim": fim},
            "despesas": despesas,
        }
    )


def ids_gravados(pasta, nome=ORIGINAL):
    return [d.id for d in repository.ler_solicitacao_arquivo(pasta / nome).despesas]


def arquivos(pasta):
    return sorted(p.name for p in pasta.iterdir())


@pytest.fixture
def falha_ao_trocar_arquivo(monkeypatch):
    """Simula disco cheio/bloqueado na troca atômica de arquivos."""

    def falha(origem, destino):
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", falha)


# --------------------------------------------------------------------------
# T-013 — consolidação
# --------------------------------------------------------------------------


@pytest.mark.req("DT-002")
def test_consolidacao_despesas(tmp_path):
    primeiro = service.consolidar_solicitacao(
        sol([desp("d-1"), desp("d-2", "20")]), tmp_path
    )
    assert (primeiro.criado, primeiro.novas, primeiro.ignoradas) == (True, 2, 0)
    assert primeiro.caminho == tmp_path / ORIGINAL

    # reenvio parcial e incremental: d-2 já existe, d-3 é nova
    segundo = service.consolidar_solicitacao(
        sol([desp("d-2", "20"), desp("d-3", "30")]), tmp_path
    )
    assert (segundo.criado, segundo.novas, segundo.ignoradas) == (False, 1, 1)
    assert ids_gravados(tmp_path) == ["d-1", "d-2", "d-3"]
    assert arquivos(tmp_path) == [ORIGINAL]


class TestConsolidacao:
    def test_cria_arquivo_novo_com_nome_padronizado(self, tmp_path):
        resultado = service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert resultado.criado
        assert arquivos(tmp_path) == [ORIGINAL]

    def test_cria_diretorio_inexistente(self, tmp_path):
        destino = tmp_path / "novo" / "colaborador"
        service.consolidar_solicitacao(sol([desp("d-1")]), destino)
        assert arquivos(destino) == [ORIGINAL]

    def test_usa_pasta_colaborador_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path)
        service.consolidar_solicitacao(sol([desp("d-1")]))
        assert arquivos(tmp_path) == [ORIGINAL]

    def test_solicitacao_sem_despesas_cria_arquivo_vazio(self, tmp_path):
        resultado = service.consolidar_solicitacao(sol([]), tmp_path)
        assert (resultado.criado, resultado.novas) == (True, 0)
        assert ids_gravados(tmp_path) == []

    def test_reenvio_identico_nao_reescreve_o_arquivo(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1"), desp("d-2")]), tmp_path)
        antes = (tmp_path / ORIGINAL).read_bytes()
        resultado = service.consolidar_solicitacao(
            sol([desp("d-1"), desp("d-2")]), tmp_path
        )
        assert (resultado.criado, resultado.novas, resultado.ignoradas) == (False, 0, 2)
        assert (tmp_path / ORIGINAL).read_bytes() == antes

    def test_preserva_ordem_existentes_primeiro(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-5"), desp("d-1", "11")]), tmp_path)
        service.consolidar_solicitacao(
            sol([desp("d-3", "12"), desp("d-0", "13")]), tmp_path
        )
        assert ids_gravados(tmp_path) == ["d-5", "d-1", "d-3", "d-0"]

    def test_cabecalho_existente_prevalece(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")], nome="Ana"), tmp_path)
        service.consolidar_solicitacao(
            sol(
                [desp("d-2", "20")],
                nome="Ana Maria",
                inicio="2026-10-05",
                fim="2026-10-20",
            ),
            tmp_path,
        )
        gravada = repository.ler_solicitacao_arquivo(tmp_path / ORIGINAL)
        assert gravada.colaborador.nome == "Ana"
        assert str(gravada.periodo.inicio) == "2026-10-01"
        assert str(gravada.periodo.fim) == "2026-10-31"
        assert [d.id for d in gravada.despesas] == ["d-1", "d-2"]

    def test_duplicatas_perfeitas_com_ids_diferentes_sao_mantidas(self, tmp_path):
        # quem julga é o motor (RN-007); a consolidação não as descarta.
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        resultado = service.consolidar_solicitacao(sol([desp("d-2")]), tmp_path)
        assert resultado.novas == 1
        assert ids_gravados(tmp_path) == ["d-1", "d-2"]

    def test_mesmo_id_repetido_e_identico_no_proprio_envio_conta_uma_vez(
        self, tmp_path
    ):
        resultado = service.consolidar_solicitacao(
            sol([desp("d-1"), desp("d-1")]), tmp_path
        )
        assert (resultado.novas, resultado.ignoradas) == (1, 1)
        assert ids_gravados(tmp_path) == ["d-1"]

    def test_decimais_exatos_sobrevivem_a_consolidacao(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1", "72.5")]), tmp_path)
        service.consolidar_solicitacao(sol([desp("d-2", "100")]), tmp_path)
        texto = (tmp_path / ORIGINAL).read_text("utf-8")
        assert '"valor": 72.50' in texto
        assert '"valor": 100.00' in texto

    def test_nao_deixa_temporarios(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)
        assert arquivos(tmp_path) == [ORIGINAL]


class TestConflitoDeId:
    def test_mesmo_id_com_conteudo_diferente_interrompe_sem_gravar(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1", "10")]), tmp_path)
        antes = (tmp_path / ORIGINAL).read_bytes()
        with pytest.raises(IdDespesaConflitanteError) as erro:
            service.consolidar_solicitacao(
                sol([desp("d-2", "5"), desp("d-1", "99")]), tmp_path
            )
        assert erro.value.ids == ["d-1"]
        assert "d-1" in str(erro.value)
        assert "Ajuste" in str(erro.value)
        assert (tmp_path / ORIGINAL).read_bytes() == antes  # d-2 também não entrou

    @pytest.mark.parametrize(
        "campo, valor",
        [
            ("valor", "11"),
            ("data", "2026-10-16"),
            ("categoria", "coworking"),
            ("descricao", "Outra"),
        ],
    )
    def test_qualquer_campo_diferente_conta_como_conflito(self, tmp_path, campo, valor):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        with pytest.raises(IdDespesaConflitanteError):
            service.consolidar_solicitacao(
                sol([{**desp("d-1"), campo: valor}]), tmp_path
            )

    def test_lista_todos_os_ids_conflitantes_sem_repetir(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1"), desp("d-2", "20")]), tmp_path)
        novas = [desp("d-1", "1"), desp("d-2", "2"), desp("d-1", "3")]
        with pytest.raises(IdDespesaConflitanteError) as erro:
            service.consolidar_solicitacao(sol(novas), tmp_path)
        assert erro.value.ids == ["d-1", "d-2"]

    def test_conflito_dentro_do_proprio_envio_nao_cria_arquivo(self, tmp_path):
        with pytest.raises(IdDespesaConflitanteError):
            service.consolidar_solicitacao(
                sol([desp("d-1", "1"), desp("d-1", "2")]), tmp_path
            )
        assert arquivos(tmp_path) == []

    def test_e_repositorio_error(self):
        assert issubclass(IdDespesaConflitanteError, RepositorioError)


class TestRecusas:
    @pytest.mark.req("RN-009")
    @pytest.mark.parametrize("competencia", ["2026-13", "10/2026", "", None])
    def test_competencia_invalida_e_recusada_sem_gravar(self, tmp_path, competencia):
        with pytest.raises(engine.CompetenciaInvalidaError):
            service.consolidar_solicitacao(
                sol([desp("d-1")], competencia=competencia), tmp_path
            )
        assert arquivos(tmp_path) == []

    def test_competencia_validada_nao_aceita_novos_envios(self, tmp_path):
        (tmp_path / VALIDADO).write_text("{}", "utf-8")
        with pytest.raises(CompetenciaJaValidadaError):
            service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert arquivos(tmp_path) == [VALIDADO]
        assert (tmp_path / VALIDADO).read_text("utf-8") == "{}"

    def test_competencia_validada_recusa_mesmo_com_original_presente(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        (tmp_path / VALIDADO).write_text("{}", "utf-8")
        with pytest.raises(CompetenciaJaValidadaError):
            service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)
        assert ids_gravados(tmp_path) == ["d-1"]

    def test_id_de_colaborador_invalido_para_nome_de_arquivo(self, tmp_path):
        dados = sol([desp("d-1")]).model_dump()
        dados["colaborador"]["id"] = "c_1"
        with pytest.raises(NomeArquivoInvalidoError):
            service.consolidar_solicitacao(
                SolicitacaoReembolso.model_validate(dados), tmp_path
            )
        assert arquivos(tmp_path) == []

    def test_outra_competencia_gera_arquivo_proprio(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        service.consolidar_solicitacao(
            sol(
                [desp("d-1")],
                competencia="2026-11",
                inicio="2026-11-01",
                fim="2026-11-30",
            ),
            tmp_path,
        )
        assert arquivos(tmp_path) == [ORIGINAL, "c-1_CC-X_2026-11.json"]


class TestMesclarDespesas:
    def test_funcao_pura(self):
        existentes = sol([desp("d-1")]).despesas
        novas = sol([desp("d-1"), desp("d-2", "20")]).despesas
        despesas, adicionadas, ignoradas = service.mesclar_despesas(existentes, novas)
        assert [d.id for d in despesas] == ["d-1", "d-2"]
        assert (adicionadas, ignoradas) == (1, 1)
        assert [d.id for d in existentes] == ["d-1"]  # entrada intacta

    def test_listas_vazias(self):
        assert service.mesclar_despesas([], []) == ([], 0, 0)


# --------------------------------------------------------------------------
# T-014 — arquivos corrompidos e erros de I/O
# --------------------------------------------------------------------------


@pytest.mark.req("RN-009")
def test_json_corrompido_tratamento(tmp_path):
    (tmp_path / ORIGINAL).write_text("{nao e json", "utf-8")
    antes = (tmp_path / ORIGINAL).read_bytes()

    with pytest.raises(ArquivoCorrompidoError):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
    with pytest.raises(RepositorioError):  # um único tipo para a interface capturar
        service.validar_competencia(*CHAVE, diretorio=tmp_path)

    assert (tmp_path / ORIGINAL).read_bytes() == antes  # não é sobrescrito
    assert arquivos(tmp_path) == [ORIGINAL]  # sem resultado nem temporários


class TestArquivosCorrompidos:
    @pytest.mark.parametrize(
        "conteudo",
        [b"", b"{", b"[1, 2", b"\xff\xfe\x00lixo", b"null", b"[]", b"{}"],
    )
    def test_existente_malformado_ou_incompleto(self, tmp_path, conteudo):
        (tmp_path / ORIGINAL).write_bytes(conteudo)
        with pytest.raises(ArquivoCorrompidoError):
            service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert (tmp_path / ORIGINAL).read_bytes() == conteudo

    def test_existente_com_despesa_incompleta(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        dados = json.loads((tmp_path / ORIGINAL).read_text("utf-8"))
        del dados["despesas"][0]["valor"]
        (tmp_path / ORIGINAL).write_text(json.dumps(dados), "utf-8")
        with pytest.raises(ArquivoCorrompidoError, match="schema inválido"):
            service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)

    def test_corrompido_nao_impede_outras_competencias(self, tmp_path):
        (tmp_path / ORIGINAL).write_text("{", "utf-8")
        service.consolidar_solicitacao(
            sol(
                [desp("d-1")],
                competencia="2026-11",
                inicio="2026-11-01",
                fim="2026-11-30",
            ),
            tmp_path,
        )
        assert "c-1_CC-X_2026-11.json" in arquivos(tmp_path)

    def test_validar_com_schema_incompleto(self, tmp_path):
        (tmp_path / ORIGINAL).write_text('{"colaborador": {"id": "c-1"}}', "utf-8")
        with pytest.raises(ArquivoCorrompidoError):
            service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert arquivos(tmp_path) == [ORIGINAL]


class TestErrosDeDisco:
    def test_falha_de_escrita_ao_criar(self, tmp_path, falha_ao_trocar_arquivo):
        with pytest.raises(FalhaDePersistenciaError, match="disco cheio"):
            service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert arquivos(tmp_path) == []  # sem arquivo parcial nem temporário

    def test_falha_de_escrita_ao_atualizar_preserva_o_arquivo(
        self, tmp_path, monkeypatch
    ):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        antes = (tmp_path / ORIGINAL).read_bytes()
        monkeypatch.setattr(
            os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("x"))
        )
        with pytest.raises(FalhaDePersistenciaError):
            service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)
        assert (tmp_path / ORIGINAL).read_bytes() == antes
        assert arquivos(tmp_path) == [ORIGINAL]

    def test_falha_de_disco_e_repositorio_error_e_preserva_a_causa(
        self, tmp_path, falha_ao_trocar_arquivo
    ):
        with pytest.raises(RepositorioError) as erro:
            service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert isinstance(erro.value.__cause__, OSError)

    def test_destino_que_e_diretorio(self, tmp_path):
        (tmp_path / ORIGINAL).mkdir()
        with pytest.raises(FalhaDePersistenciaError):
            service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        assert [p.suffix for p in tmp_path.iterdir()] == [".json"]  # só o diretório

    def test_arquivo_ilegivel(self, tmp_path, monkeypatch):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)

        def nega(self, *args, **kwargs):
            raise PermissionError("acesso negado")

        monkeypatch.setattr(Path, "read_text", nega)
        with pytest.raises(FalhaDePersistenciaError, match="acesso negado"):
            service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)


class TestCarregarArquivo:
    def test_carrega_o_exemplo_do_desafio(self, tmp_path):
        pasta = tmp_path / "colaborador"
        resultado = service.carregar_arquivo(EXEMPLO, pasta)
        assert resultado.criado and resultado.novas == 14
        assert arquivos(pasta) == ["c-0417_CC-ENG-PLATAFORMA_2026-07.json"]
        assert EXEMPLO.exists()  # a origem não é movida

    def test_carregar_duas_vezes_e_idempotente(self, tmp_path):
        service.carregar_arquivo(EXEMPLO, tmp_path / "c")
        segundo = service.carregar_arquivo(EXEMPLO, tmp_path / "c")
        assert (segundo.criado, segundo.novas, segundo.ignoradas) == (False, 0, 14)

    def test_origem_inexistente(self, tmp_path):
        with pytest.raises(ArquivoNaoEncontradoError):
            service.carregar_arquivo(tmp_path / "nada.json", tmp_path / "c")
        assert not (tmp_path / "c").exists()

    @pytest.mark.parametrize(
        "conteudo", ["{malformado", "", '{"colaborador": {}}', "[]"]
    )
    def test_origem_malformada_ou_incompleta(self, tmp_path, conteudo):
        origem = tmp_path / "envio.json"
        origem.write_text(conteudo, "utf-8")
        with pytest.raises(ArquivoCorrompidoError):
            service.carregar_arquivo(origem, tmp_path / "c")
        assert not (tmp_path / "c").exists()

    def test_origem_com_competencia_invalida(self, tmp_path):
        dados = json.loads(EXEMPLO.read_text("utf-8"))
        dados["periodo"]["competencia"] = "07/2026"
        origem = tmp_path / "envio.json"
        origem.write_text(json.dumps(dados), "utf-8")
        with pytest.raises(engine.CompetenciaInvalidaError):
            service.carregar_arquivo(origem, tmp_path / "c")

    def test_origem_sem_permissao_de_leitura(self, tmp_path, monkeypatch):
        origem = tmp_path / "envio.json"
        shutil.copy(EXEMPLO, origem)

        def nega(self, *args, **kwargs):
            raise PermissionError("acesso negado")

        monkeypatch.setattr(Path, "read_text", nega)
        with pytest.raises(FalhaDePersistenciaError):
            service.carregar_arquivo(origem, tmp_path / "c")


# --------------------------------------------------------------------------
# T-022 — validação e transição de estado
# --------------------------------------------------------------------------


@pytest.mark.req("RN-001")
@pytest.mark.req("RN-004")
def test_validacao_gera_resultado_e_renomeia(tmp_path):
    service.carregar_arquivo(EXEMPLO, tmp_path)
    original = tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07.json"
    conteudo = original.read_bytes()

    validacao = service.validar_competencia(
        "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
    )

    # renomeação física: o original some, o _validado guarda o mesmo conteúdo
    assert not original.exists()
    assert validacao.caminho_validado.read_bytes() == conteudo
    assert arquivos(tmp_path) == [
        "c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json",
        "c-0417_CC-ENG-PLATAFORMA_2026-07_validado.json",
    ]
    assert (
        validacao.caminho_resultado.name
        == "c-0417_CC-ENG-PLATAFORMA_2026-07_resultado.json"
    )

    # o arquivo de resultado é a auditoria do motor, com números de duas casas
    texto = validacao.caminho_resultado.read_text("utf-8")
    assert '"valor_reembolsado": 60.00' in texto
    gravado = ResultadoAuditoria.model_validate(
        repository.ler_json(validacao.caminho_resultado)
    )
    assert gravado == validacao.resultado
    por_id = {i.id: i for i in gravado.historico_despesas[0].despesas}
    assert por_id["d-001"].status_item == "parcial"
    assert por_id["d-006"].status_item == "rejeitado - duplicidade"
    assert str(por_id["d-011"].valor_reembolsado) == "33.33"


class TestValidacao:
    def test_ciclo_carregar_consolidar_validar(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1", "85")]), tmp_path)
        service.consolidar_solicitacao(sol([desp("d-2", "20")]), tmp_path)
        validacao = service.validar_competencia(*CHAVE, diretorio=tmp_path)
        itens = validacao.resultado.historico_despesas[0].despesas
        assert [(i.id, i.status_item, str(i.valor_reembolsado)) for i in itens] == [
            ("d-1", "parcial", "60.00"),
            ("d-2", "rejeitado", "0.00"),
        ]
        assert arquivos(tmp_path) == [RESULTADO, VALIDADO]

    def test_validado_continua_legivel_pelo_repositorio(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert repository.existe_solicitacao(*CHAVE, diretorio=tmp_path)
        assert (
            repository.ler_solicitacao(*CHAVE, diretorio=tmp_path).despesas[0].id
            == "d-1"
        )

    def test_validar_duas_vezes_e_recusado(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        service.validar_competencia(*CHAVE, diretorio=tmp_path)
        resultado_antes = (tmp_path / RESULTADO).read_bytes()
        with pytest.raises(CompetenciaJaValidadaError):
            service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert (tmp_path / RESULTADO).read_bytes() == resultado_antes
        assert arquivos(tmp_path) == [RESULTADO, VALIDADO]

    def test_sem_arquivo_carregado(self, tmp_path):
        with pytest.raises(ArquivoNaoEncontradoError):
            service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert arquivos(tmp_path) == []

    def test_diretorio_inexistente(self, tmp_path):
        with pytest.raises(ArquivoNaoEncontradoError):
            service.validar_competencia(*CHAVE, diretorio=tmp_path / "nada")

    def test_chave_invalida(self, tmp_path):
        with pytest.raises(NomeArquivoInvalidoError):
            service.validar_competencia("c_1", "CC-X", "2026-10", diretorio=tmp_path)

    @pytest.mark.req("RN-009")
    def test_competencia_invalida_gravada_no_disco_nao_e_validada(self, tmp_path):
        dados = sol([desp("d-1")]).model_dump()
        dados["periodo"]["competencia"] = "2026-13"
        repository.salvar_json(tmp_path / "c-1_CC-X_2026-13.json", dados)
        with pytest.raises(engine.CompetenciaInvalidaError):
            service.validar_competencia("c-1", "CC-X", "2026-13", diretorio=tmp_path)
        assert arquivos(tmp_path) == ["c-1_CC-X_2026-13.json"]

    def test_resultado_antigo_e_sobrescrito(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        (tmp_path / RESULTADO).write_text("lixo", "utf-8")
        service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert (
            json.loads((tmp_path / RESULTADO).read_text("utf-8"))["colaborador"]["id"]
            == "c-1"
        )

    def test_usa_pasta_colaborador_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path)
        service.consolidar_solicitacao(sol([desp("d-1")]))
        service.validar_competencia(*CHAVE)
        assert arquivos(tmp_path) == [RESULTADO, VALIDADO]

    def test_motor_nao_e_afetado_pela_persistencia(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1", "85")]), tmp_path)
        esperado = engine.avaliar(
            repository.ler_solicitacao(*CHAVE, diretorio=tmp_path)
        )
        validacao = service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert validacao.resultado == esperado


class TestFalhasNaValidacao:
    def test_falha_ao_gravar_resultado_nao_renomeia(
        self, tmp_path, falha_ao_trocar_arquivo
    ):
        # cria o original sem passar pela troca atômica (que está falhando)
        shutil.copy(EXEMPLO, tmp_path / "c-0417_CC-ENG-PLATAFORMA_2026-07.json")
        with pytest.raises(FalhaDePersistenciaError):
            service.validar_competencia(
                "c-0417", "CC-ENG-PLATAFORMA", "2026-07", diretorio=tmp_path
            )
        assert arquivos(tmp_path) == ["c-0417_CC-ENG-PLATAFORMA_2026-07.json"]

    def test_renomear_tenta_de_novo_e_conclui(self, tmp_path, monkeypatch):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        original_rename = Path.rename
        chamadas = []
        esperas = []

        def instavel(self, destino):
            chamadas.append(1)
            if len(chamadas) < 3:
                raise PermissionError("arquivo em uso")
            return original_rename(self, destino)

        monkeypatch.setattr(Path, "rename", instavel)
        monkeypatch.setattr(service.time, "sleep", esperas.append)

        service.validar_competencia(*CHAVE, diretorio=tmp_path)

        assert len(chamadas) == 3
        assert esperas == [service.ESPERA_ENTRE_TENTATIVAS] * 2
        assert arquivos(tmp_path) == [RESULTADO, VALIDADO]

    def test_renomear_falha_sempre_desfaz_o_resultado(self, tmp_path, monkeypatch):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        original = (tmp_path / ORIGINAL).read_bytes()
        chamadas = []

        def bloqueado(self, destino):
            chamadas.append(1)
            raise PermissionError("arquivo em uso")

        monkeypatch.setattr(Path, "rename", bloqueado)
        monkeypatch.setattr(service.time, "sleep", lambda s: None)

        with pytest.raises(FalhaDePersistenciaError, match="arquivo em uso"):
            service.validar_competencia(*CHAVE, diretorio=tmp_path)

        assert len(chamadas) == service.TENTATIVAS_RENOMEAR
        assert arquivos(tmp_path) == [ORIGINAL]  # resultado removido, original intacto
        assert (tmp_path / ORIGINAL).read_bytes() == original

    def test_apos_falha_a_validacao_pode_ser_refeita(self, tmp_path, monkeypatch):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        with monkeypatch.context() as m:
            m.setattr(
                Path,
                "rename",
                lambda self, destino: (_ for _ in ()).throw(OSError("x")),
            )
            m.setattr(service.time, "sleep", lambda s: None)
            with pytest.raises(FalhaDePersistenciaError):
                service.validar_competencia(*CHAVE, diretorio=tmp_path)
        service.validar_competencia(*CHAVE, diretorio=tmp_path)
        assert arquivos(tmp_path) == [RESULTADO, VALIDADO]


# --------------------------------------------------------------------------
# Listagem de competências e consulta do resultado (T-016, T-018)
# --------------------------------------------------------------------------


def sol_de(id_, competencia="2026-10", nome="Ana", cc="CC-X", despesas=()):
    return SolicitacaoReembolso.model_validate(
        {
            "colaborador": {"id": id_, "nome": nome, "centro_custo": cc},
            "periodo": {
                "competencia": competencia,
                "inicio": f"{competencia}-01",
                "fim": f"{competencia}-28",
            },
            "despesas": list(despesas) or [desp("d-1", data=f"{competencia}-10")],
        }
    )


class TestListarCompetencias:
    def test_diretorio_vazio_ou_inexistente(self, tmp_path):
        assert service.listar_competencias(tmp_path) == []
        assert service.listar_competencias(tmp_path / "nada") == []

    def test_competencia_carregada(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1"), desp("d-2", "20")]), tmp_path)
        (entrada,) = service.listar_competencias(tmp_path)
        assert entrada == service.EntradaCompetencia(
            id_colaborador="c-1",
            centro_custo="CC-X",
            competencia="2026-10",
            nome="Ana",
            validado=False,
            tem_resultado=False,
            corrompido=False,
            erro=None,
            total_despesas=2,
        )

    def test_competencia_validada(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        service.validar_competencia(*CHAVE, diretorio=tmp_path)
        (entrada,) = service.listar_competencias(tmp_path)
        assert entrada.validado and entrada.tem_resultado
        assert not entrada.corrompido
        assert (entrada.nome, entrada.total_despesas) == ("Ana", 1)

    def test_ignora_arquivos_fora_da_nomenclatura(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        (tmp_path / ".gitkeep").write_text("", "utf-8")
        (tmp_path / "anotacoes.txt").write_text("x", "utf-8")
        (tmp_path / "solto.json").write_text("{}", "utf-8")
        (tmp_path / "a_b.json").write_text("{}", "utf-8")
        (tmp_path / "__x.json").write_text("{}", "utf-8")
        (tmp_path / "c-1_CC-X_2026-10.json.tmp").write_text("{", "utf-8")
        (tmp_path / "c-9_CC-X_2026-10.json").mkdir()
        assert [e.competencia for e in service.listar_competencias(tmp_path)] == [
            "2026-10"
        ]

    def test_arquivo_corrompido_nao_derruba_a_listagem(self, tmp_path):
        service.consolidar_solicitacao(sol_de("c-1"), tmp_path)
        (tmp_path / "c-2_CC-X_2026-10.json").write_text("{nao e json", "utf-8")
        (tmp_path / "c-3_CC-X_2026-10.json").write_text('{"colaborador": {}}', "utf-8")
        ok, ruim, incompleto = service.listar_competencias(tmp_path)
        assert not ok.corrompido and ok.erro is None
        assert ruim.corrompido and "malformado" in ruim.erro
        assert incompleto.corrompido and "schema inválido" in incompleto.erro
        assert ruim.nome is None and ruim.total_despesas is None

    def test_apenas_resultado_orfao_e_sinalizado(self, tmp_path):
        (tmp_path / RESULTADO).write_text("{}", "utf-8")
        (entrada,) = service.listar_competencias(tmp_path)
        assert entrada.corrompido and entrada.tem_resultado
        assert "solicitação ausente" in entrada.erro

    def test_validado_tem_preferencia_sobre_original(self, tmp_path):
        service.consolidar_solicitacao(sol_de("c-1", nome="Ana"), tmp_path)
        shutil.copy(tmp_path / ORIGINAL, tmp_path / VALIDADO)
        (entrada,) = service.listar_competencias(tmp_path)
        assert entrada.validado

    def test_ordenacao_e_filtro_por_colaborador(self, tmp_path):
        service.consolidar_solicitacao(sol_de("c-2", "2026-10"), tmp_path)
        service.consolidar_solicitacao(sol_de("c-1", "2026-11"), tmp_path)
        service.consolidar_solicitacao(sol_de("c-1", "2026-09"), tmp_path)
        todas = service.listar_competencias(tmp_path)
        assert [(e.id_colaborador, e.competencia) for e in todas] == [
            ("c-1", "2026-09"),
            ("c-1", "2026-11"),
            ("c-2", "2026-10"),
        ]
        so_c2 = service.listar_competencias(tmp_path, id_colaborador="c-2")
        assert [e.id_colaborador for e in so_c2] == ["c-2"]

    def test_centro_de_custo_com_underscore(self, tmp_path):
        service.consolidar_solicitacao(sol_de("c-1", cc="CC_ENG_X"), tmp_path)
        (entrada,) = service.listar_competencias(tmp_path)
        assert entrada.centro_custo == "CC_ENG_X"
        assert entrada.competencia == "2026-10"

    def test_usa_pasta_colaborador_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "COLABORADOR_DIR", tmp_path)
        service.consolidar_solicitacao(sol([desp("d-1")]))
        assert len(service.listar_competencias()) == 1

    def test_pasta_ilegivel(self, tmp_path, monkeypatch):
        def nega(self):
            raise PermissionError("acesso negado")

        monkeypatch.setattr(Path, "iterdir", nega)
        with pytest.raises(FalhaDePersistenciaError, match="acesso negado"):
            service.listar_competencias(tmp_path)


class TestObterResultado:
    def test_devolve_a_auditoria_gravada(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1", "85")]), tmp_path)
        validacao = service.validar_competencia(*CHAVE, diretorio=tmp_path)
        lido = service.obter_resultado(*CHAVE, diretorio=tmp_path)
        assert lido == validacao.resultado
        assert lido.historico_despesas[0].despesas[0].status_item == "parcial"

    def test_sem_validacao_nao_ha_resultado(self, tmp_path):
        service.consolidar_solicitacao(sol([desp("d-1")]), tmp_path)
        with pytest.raises(ArquivoNaoEncontradoError):
            service.obter_resultado(*CHAVE, diretorio=tmp_path)

    @pytest.mark.parametrize("conteudo", ["{malformado", "{}", "[]"])
    def test_resultado_corrompido(self, tmp_path, conteudo):
        (tmp_path / RESULTADO).write_text(conteudo, "utf-8")
        with pytest.raises(ArquivoCorrompidoError):
            service.obter_resultado(*CHAVE, diretorio=tmp_path)

    def test_resultado_ilegivel(self, tmp_path, monkeypatch):
        (tmp_path / RESULTADO).write_text("{}", "utf-8")

        def nega(self, *args, **kwargs):
            raise PermissionError("acesso negado")

        monkeypatch.setattr(Path, "read_text", nega)
        with pytest.raises(FalhaDePersistenciaError):
            service.obter_resultado(*CHAVE, diretorio=tmp_path)
