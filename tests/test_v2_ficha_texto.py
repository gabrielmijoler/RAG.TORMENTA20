"""Ficha do personagem lida do texto livre do jogador (atributos, perícias, ofícios, devoção)."""

import pytest

from rag_v2.ficha_texto import extrair


def test_atributo_com_igual_ou_dois_pontos_ou_maiuscula():
    assert extrair("meu atributo principal é INT = 6")["atributos"] == {"int": 6}
    assert extrair("For: 3, Des: 2")["atributos"] == {"for": 3, "des": 2}
    assert extrair("tenho Sab 2 e Car -1")["atributos"] == {"sab": 2, "car": -1}


def test_palavra_comum_for_nao_vira_atributo():
    assert extrair("se for 3 dias de viagem")["atributos"] == {}
    assert extrair("quando eu for 5 vezes")["atributos"] == {}


def test_todos_os_oficios():
    assert extrair("sou armeiro e tenho todos os oficios")["todos_oficios"] is True
    assert extrair("tenho todos os ofícios")["todos_oficios"] is True
    assert extrair("tenho um oficio")["todos_oficios"] is False


def test_oficio_especifico_so_com_verbo_de_posse():
    assert extrair("sou armeiro")["oficios"] == {"armeiro"}
    assert extrair("tenho Ofício (alquimista)")["oficios"] == {"alquimista"}
    assert extrair("o armeiro da vila vendeu uma espada")["oficios"] == set()


def test_treinado_em_varias_pericias():
    assert extrair("sou treinado em Luta e Pontaria")["pericias"] == {"luta", "pontaria"}
    assert extrair("treinado em Intimidação, Atletismo")["pericias"] == {"intimidacao", "atletismo"}


def test_devoto():
    assert extrair("sou devoto de Azgher")["devoto"] == "azgher"
    assert extrair("sou devota de Lena")["devoto"] == "lena"


@pytest.mark.parametrize("texto", ["", "qual o dano da bola de fogo?", "o que faz a magia Teia"])
def test_texto_sem_ficha_nao_inventa_nada(texto):
    r = extrair(texto)
    assert r == {"atributos": {}, "oficios": set(), "todos_oficios": False,
                 "pericias": set(), "devoto": None}
