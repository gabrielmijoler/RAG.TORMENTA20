"""Orçamento de chunks da v2: função determinística da leitura."""

import pytest

from rag_v2.orcamento import K_FALLBACK, K_MAX, calcular
from rag_v2.tipos import Necessidade


def _nec(n, obrigatoria=True):
    return tuple(Necessidade(f"n{i}", "T", f"e{i}", obrigatoria) for i in range(n))


def test_confianca_baixa_usa_o_top12_da_v1():
    assert calcular("direta", _nec(1), "baixa") == K_FALLBACK == 12


@pytest.mark.parametrize("tipo", ["sem_nome", "fora_de_escopo"])
def test_sem_nome_e_fora_de_escopo_usam_o_fallback(tipo):
    assert calcular(tipo, (), "alta") == K_FALLBACK


def test_direta_com_uma_necessidade_usa_8():
    assert calcular("direta", _nec(1), "alta") == 8


def test_multiparte_cresce_4_por_necessidade_obrigatoria_entre_8_e_15():
    assert calcular("multiparte", _nec(2), "alta") == 8
    assert calcular("multiparte", _nec(3), "alta") == 12
    assert calcular("multiparte", _nec(9), "alta") == K_MAX == 15


def test_necessidade_opcional_nao_aumenta_o_orcamento():
    assert calcular("multiparte", _nec(2) + _nec(3, obrigatoria=False), "media") == 8


def test_build_usa_o_maximo():
    assert calcular("build", _nec(1), "media") == 15
