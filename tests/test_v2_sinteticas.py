"""Perguntas sintéticas sem LLM: gabarito por construção, ruído controlado, semente fixa."""

import random
from collections import Counter

import pytest

from rag_v2 import sinteticas as sn

JA = "Tormenta20 - Jogo do Ano"


def _dados():
    return {"tabelas": [
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Bola de Fogo", "origin": JA, "circle": 2, "school": "Evocação",
             "execution": "Padrão", "range": "Médio", "duration": "Instantânea",
             "resistance": "Reflexos reduz à metade", "target": "Esfera com 6m de raio"},
            {"name": "Voo", "origin": JA, "circle": 3, "school": "Transmutação",
             "execution": "Padrão", "range": "Pessoal", "duration": "Cena",
             "resistance": "Nenhuma", "target": "Você"},
            {"name": "Teia", "origin": JA, "circle": 2, "school": "Conjuração",
             "execution": "Padrão", "range": "Curto", "duration": "Cena",
             "resistance": "Reflexos anula", "target": "Esfera com 6m de raio"},
            {"name": "Voo Reserva", "origin": "Dragão Brasil", "circle": 3,
             "school": "Transmutação", "execution": "Padrão", "range": "Pessoal",
             "duration": "Cena", "resistance": "Nenhuma", "target": "Você"}]},
        {"arquivo": "weapons.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA, "damage": "2d8", "critical": "x3",
             "grip": "Duas Mãos", "price": "T$ 50"}]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Caído", "origin": JA, "description": "–5 na Defesa contra corpo a corpo."}]},
        {"arquivo": "regreiro.ts", "export": "regreiroQAs", "elementos": [
            {"name": "> pergunta de leitor", "origin": "DB - 228"}]},
    ]}


def test_mesma_semente_gera_exatamente_as_mesmas_perguntas():
    a = sn.gerar(_dados(), n=8, semente=7)
    b = sn.gerar(_dados(), n=8, semente=7)
    assert [c["consulta"] for c in a] == [c["consulta"] for c in b]


def test_semente_diferente_muda_a_amostra():
    a = sn.gerar(_dados(), n=8, semente=1)
    b = sn.gerar(_dados(), n=8, semente=2)
    assert [c["consulta"] for c in a] != [c["consulta"] for c in b]


def test_cada_caso_traz_gabarito_do_registro_e_fato_do_campo():
    for caso in sn.gerar(_dados(), n=12, semente=3, ruido=0.0):
        ent = caso["entidades_esperadas"][0]
        assert ent["tabela"] and ent["nome"] and ent["fonte"] == JA
        assert caso["fatos_esperados"] and caso["verificacao"] == "ok"
        assert caso["conjunto"] == "sintetico" and caso["origem"].startswith("sintetica:semente=3")


def test_sem_ruido_o_nome_aparece_inteiro_na_pergunta():
    for caso in sn.gerar(_dados(), n=12, semente=4, ruido=0.0):
        if caso["tipo_pergunta"] != "descritiva":
            assert caso["entidades_esperadas"][0]["nome"].lower() in caso["consulta"].lower()


def test_nome_repetido_em_duas_fontes_nao_vira_pergunta():
    nomes = {c["entidades_esperadas"][0]["nome"] for c in sn.gerar(_dados(), n=40, semente=5)}
    assert "Voo Reserva" not in nomes   # outra fonte: fora do núcleo de regras


def test_regreiro_nunca_e_usado():
    for caso in sn.gerar(_dados(), n=40, semente=6):
        assert "leitor" not in caso["consulta"]


def test_descritiva_sem_o_nome_so_para_assinatura_unica():
    casos = sn.gerar(_dados(), n=60, semente=9, ruido=0.0)
    descritivas = [c for c in casos if c["tipo_pergunta"] == "descritiva"]
    assert descritivas, "esperava ao menos uma descritiva"
    for c in descritivas:
        assert c["entidades_esperadas"][0]["nome"] not in ("Voo",), \
            "Voo tem gêmeo (Voo Reserva) com a mesma assinatura: ambígua"
        assert c["entidades_esperadas"][0]["nome"].lower() not in c["consulta"].lower()


def test_ruido_edita_so_o_nome_e_uma_vez():
    rng = random.Random(1)
    ruidoso = sn.com_erro_de_digitacao("Machado Táurico", rng)
    assert ruidoso != "Machado Táurico"
    assert ruidoso.lower().startswith("m")  # a primeira letra preservada
    assert sn.similaridade("Machado Táurico", ruidoso) >= 0.85


def test_nome_curto_nao_recebe_erro_de_digitacao():
    assert sn.com_erro_de_digitacao("Voo", random.Random(1)) == "Voo"


def test_abreviacao_e_sem_acento_informais():
    texto = sn.informalizar("Qual o nível de Voo? Quanto custa?", random.Random(2))
    assert texto == texto.lower() and "í" not in texto and "?" not in texto


def test_amostra_nunca_passa_do_numero_pedido_e_nao_repete_registro_com_o_mesmo_modelo():
    casos = sn.gerar(_dados(), n=5, semente=11)
    assert len(casos) <= 5
    chaves = [(c["tipo_pergunta"], c["entidades_esperadas"][0]["nome"], c["modelo"])
              for c in casos]
    assert len(chaves) == len(set(chaves))


def test_estimativa_de_gabarito_errado_conta_itens_marcados():
    assert sn.taxa_gabarito_errado(30, 3) == pytest.approx(0.10)
    assert sn.taxa_gabarito_errado(0, 0) is None


def test_amostra_intercala_tabelas_em_vez_de_deixar_a_maior_dominar():
    casos = sn.gerar(_dados(), n=6, semente=3, ruido=0.0)
    tabelas = {c["entidades_esperadas"][0]["tabela"] for c in casos}
    assert len(tabelas) >= 3   # Magias, Armas e Condições têm candidatos


def test_nenhuma_tabela_passa_de_metade_da_amostra_quando_ha_outras():
    casos = sn.gerar(_dados(), n=8, semente=5, ruido=0.0)
    por_tabela = Counter(c["entidades_esperadas"][0]["tabela"] for c in casos)
    assert max(por_tabela.values()) <= 4
