"""Testes do mapa do corpus (tools/mapa_corpus.py): contagens, campos e nomes repetidos."""

import importlib.util
import os

_CAMINHO = os.path.join(os.path.dirname(__file__), "..", "tools", "mapa_corpus.py")
_spec = importlib.util.spec_from_file_location("mapa_corpus", _CAMINHO)
mapa_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mapa_corpus)


def _dados():
    return {"tabelas": [
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Espada Longa", "origin": "Livro A", "price": "T$ 15", "damage": "1d8"},
            {"name": "Machado", "origin": "Livro A", "price": "", "damage": "1d6"},
        ]},
        {"arquivo": "magias.ts", "export": "spells", "elementos": [
            {"name": "Espada longa", "origin": "Livro B", "circle": "1º"},
        ]},
    ]}


def test_conta_registros_e_fontes_por_tabela():
    mapa = mapa_corpus.mapear(_dados())
    armas = mapa["tabelas"]["Armas"]
    assert armas["registros"] == 2
    assert armas["fontes"] == {"Livro A": 2}
    assert mapa["fontes"] == {"Livro A": 2, "Livro B": 1}


def test_preenchimento_ignora_valor_vazio():
    campos = mapa_corpus.mapear(_dados())["tabelas"]["Armas"]["campos"]
    assert campos["damage"] == 100
    assert campos["price"] == 50


def test_nome_repetido_em_outra_tabela_e_detectado_sem_acento_nem_caixa():
    repetidos = mapa_corpus.mapear(_dados())["nomes_repetidos"]
    assert set(repetidos) == {"espada longa"}
    locais = repetidos["espada longa"]
    assert {(loc["tabela"], loc["fonte"]) for loc in locais} == {
        ("Armas", "Livro A"), ("Magias", "Livro B")}


def test_markdown_tem_secao_por_tabela_e_lista_de_repetidos():
    md = mapa_corpus.renderizar_md(mapa_corpus.mapear(_dados()))
    assert "## Armas" in md
    assert "espada longa" in md.lower()


def test_fontes_com_mesma_grafia_normalizada_sao_agrupadas():
    dados = {"tabelas": [{"arquivo": "armas.ts", "export": "weapons", "elementos": [
        {"name": "Adaga", "origin": "Livro A"},
        {"name": "Adaga", "origin": "livro a"},
    ]}]}
    mapa = mapa_corpus.mapear(dados)
    assert mapa["variantes_de_fonte"] == {"livro a": ["Livro A", "livro a"]}
    assert mapa["nomes_repetidos"]["adaga"][0]["so_grafia_de_fonte"] is True
