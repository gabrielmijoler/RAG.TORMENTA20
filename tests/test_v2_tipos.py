"""Contratos da v2: dataclasses imutáveis, sem lógica."""

import dataclasses

import pytest

from rag_v2.tipos import Chave, Leitura, Ligacao, Necessidade, Restricoes


def test_chave_e_imutavel_e_comparavel():
    a = Chave("Armas", "Machado Táurico", "Tormenta20 - Jogo do Ano")
    b = Chave("Armas", "Machado Táurico", "Tormenta20 - Jogo do Ano")
    assert a == b and hash(a) == hash(b)
    assert a.sub is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.nome = "outro"


def test_ligacao_guarda_alternativas_como_tupla_vazia_por_padrao():
    chave = Chave("Armas", "Adaga", "F")
    lig = Ligacao("adaga", 0, 5, chave, 1.0, "exata")
    assert lig.alternativas == ()


def test_restricoes_padrao_vazio():
    r = Restricoes()
    assert r.nivel is None
    assert r.classes == r.racas == r.pericias == r.itens == ()


def test_leitura_padroes_conservadores_caem_na_v1():
    leitura = Leitura(texto_original="oi")
    assert leitura.tipo == "sem_nome"
    assert leitura.confianca == "baixa"
    assert leitura.usar_llm == "completo"
    assert leitura.ligacoes == () and leitura.necessidades == ()
    assert leitura.k == 12


def test_necessidade_obrigatoria_por_padrao():
    assert Necessidade("registro da classe", "Classes", "Bárbaro").obrigatoria is True
