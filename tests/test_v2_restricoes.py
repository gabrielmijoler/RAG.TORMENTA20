"""Restrições da v2: nível por padrões; classe, raça, perícia e item pelas ligações."""

import pytest

from rag_v2.restricoes import extrair_nivel, extrair_restricoes
from rag_v2.tipos import Chave, Ligacao

JA = "Tormenta20 - Jogo do Ano"


def _lig(tabela, nome, sub=None):
    return Ligacao(nome, 0, len(nome), Chave(tabela, nome, JA, sub), 1.0, "exata")


@pytest.mark.parametrize("texto", [
    "sou nv4", "sou nv 4", "nível 4", "nivel 4", "lvl 4", "4º nível", "4o nivel",
    "no 4 nível", "level 4",
])
def test_nivel_reconhece_as_formas_comuns(texto):
    assert extrair_nivel(texto) == 4


@pytest.mark.parametrize("texto", [
    "magia de 3º círculo", "custa 4 PM", "nível 0", "nível 25", "sem nada",
])
def test_nivel_ignora_numero_que_nao_e_nivel_ou_fora_de_1_a_20(texto):
    assert extrair_nivel(texto) is None


def test_restricoes_vem_das_tabelas_das_ligacoes():
    ligs = (_lig("Classes", "Bárbaro"), _lig("Raças", "Bugbear"),
            _lig("Perícias", "Intimidação"), _lig("Armas", "Machado Táurico"),
            _lig("Magias", "Bola de Fogo"))
    r = extrair_restricoes("barbaro bugbear nv4", ligs)
    assert r.nivel == 4
    assert r.classes == ("Bárbaro",)
    assert r.racas == ("Bugbear",)
    assert r.pericias == ("Intimidação",)
    assert r.itens == ("Machado Táurico",)


def test_habilidade_aninhada_nao_vira_classe_do_personagem():
    r = extrair_restricoes("como funciona a furia", (_lig("Classes", "Bárbaro", sub="Fúria"),))
    assert r.classes == ()


def test_sem_repeticao_e_na_ordem_do_texto():
    ligs = (_lig("Armaduras", "Cota de Malha"), _lig("Armas", "Adaga"),
            _lig("Armas", "Adaga"))
    assert extrair_restricoes("", ligs).itens == ("Cota de Malha", "Adaga")
