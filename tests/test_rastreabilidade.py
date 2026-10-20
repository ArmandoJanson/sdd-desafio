"""Verifica a matriz de rastreabilidade (T-020).

Garante que spec, plan, tasks e testes continuam descrevendo a mesma coisa:
marcadores ``@pytest.mark.req`` válidos, toda regra com teste e a tabela de
cobertura do ``tasks.md`` sem referências quebradas.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SPECS = RAIZ / "specs" / "001-motor-reembolso"
TESTES = Path(__file__).resolve().parent


def ler(caminho):
    return caminho.read_text(encoding="utf-8")


SPEC = ler(SPECS / "spec.md")
PLAN = ler(SPECS / "plan.md")
TASKS = ler(SPECS / "tasks.md")
COBERTURA = TASKS[TASKS.index("## Cobertura") :]

REGRAS = set(re.findall(r"^### (RN-\d{3})", SPEC, re.M))
AMBIGUIDADES = set(re.findall(r"^### (AMB-\d{3})", SPEC, re.M))
DECISOES_TECNICAS = set(re.findall(r"^### (DT-\d{3})", PLAN, re.M))


def arquivos_de_teste():
    return sorted(TESTES.glob("test_*.py"))


def marcadores_req():
    """``{id: [teste, ...]}`` lido dos decoradores ``@pytest.mark.req("ID")``."""
    usados = defaultdict(list)
    for arquivo in arquivos_de_teste():
        for no in ast.walk(ast.parse(ler(arquivo))):
            if not isinstance(no, (ast.FunctionDef, ast.ClassDef)):
                continue
            for decorador in no.decorator_list:
                if (
                    isinstance(decorador, ast.Call)
                    and ast.unparse(decorador.func) == "pytest.mark.req"
                ):
                    usados[decorador.args[0].value].append(f"{arquivo.name}::{no.name}")
    return usados


def nomes_definidos(arquivo):
    return {
        no.name
        for no in ast.walk(ast.parse(ler(TESTES / arquivo)))
        if isinstance(no, (ast.FunctionDef, ast.ClassDef))
    }


def test_a_spec_define_as_regras_esperadas():
    assert REGRAS == {f"RN-{n:03d}" for n in range(1, 13)}
    assert AMBIGUIDADES == {f"AMB-{n:03d}" for n in range(1, 10)}
    assert DECISOES_TECNICAS == {"DT-001", "DT-002"}


def test_marcadores_correspondem_as_regras_da_spec():
    """Todo ``req`` aponta para uma regra da spec (RN) ou decisão do plan (DT)."""
    validos = REGRAS | DECISOES_TECNICAS
    invalidos = set(marcadores_req()) - validos
    assert not invalidos, f"marcadores sem regra correspondente: {sorted(invalidos)}"


def test_toda_regra_da_spec_tem_teste_marcado():
    sem_teste = REGRAS - set(marcadores_req())
    assert not sem_teste, f"regras sem teste marcado: {sorted(sem_teste)}"


def test_tabela_cobre_todas_as_regras_e_ambiguidades():
    for identificador in sorted(REGRAS | AMBIGUIDADES):
        assert f"| **{identificador}** |" in COBERTURA, identificador


def test_testes_citados_na_tabela_existem():
    citados = re.findall(r"`(test_\w+\.py)::(\w+)`", COBERTURA)
    assert len(citados) > 30
    for arquivo, nome in citados:
        assert (TESTES / arquivo).is_file(), f"{arquivo} não existe"
        assert nome in nomes_definidos(arquivo), f"{arquivo}::{nome} não existe"


def test_testes_da_tabela_de_regras_carregam_o_marcador_da_regra():
    marcados = marcadores_req()
    for linha in COBERTURA.splitlines():
        achou = re.match(r"\| \*\*(RN-\d{3})\*\* \|", linha)
        if not achou:
            continue
        regra = achou.group(1)
        citados = {
            f"{a}::{n}" for a, n in re.findall(r"`(test_\w+\.py)::(\w+)`", linha)
        }
        assert citados & set(marcados[regra]), f"{regra}: nenhum teste citado é marcado"


def test_tasks_citadas_existem_e_estao_concluidas():
    concluidas = set(re.findall(r"^- \[x\] \*\*(T-\d{3})\*\*", TASKS, re.M))
    citadas = set(re.findall(r"\bT-\d{3}\b", COBERTURA))
    assert citadas
    assert citadas <= concluidas, f"não concluídas: {sorted(citadas - concluidas)}"


def test_ambiguidade_aponta_para_a_regra_afetada_da_spec():
    afetadas = dict(
        re.findall(
            r"^### (AMB-\d{3}).*?\*\*Regra afetada:\*\*\s*(RN-\d{3})",
            SPEC,
            re.M | re.S,
        )
    )
    assert set(afetadas) == AMBIGUIDADES
    linhas = {
        m.group(1): m.group(2)
        for m in re.finditer(r"\| \*\*(AMB-\d{3})\*\* \| (RN-\d{3}) \|", COBERTURA)
    }
    assert linhas == afetadas


def test_regras_da_tabela_listam_as_ambiguidades_da_spec():
    afetadas = defaultdict(set)
    for amb, regra in re.findall(
        r"^### (AMB-\d{3}).*?\*\*Regra afetada:\*\*\s*(RN-\d{3})",
        SPEC,
        re.M | re.S,
    ):
        afetadas[regra].add(amb)
    for linha in COBERTURA.splitlines():
        achou = re.match(r"\| \*\*(RN-\d{3})\*\* \| ([^|]*)\|", linha)
        if achou:
            listadas = set(re.findall(r"AMB-\d{3}", achou.group(2)))
            assert listadas == afetadas[achou.group(1)], achou.group(1)
