"""Tipo da pergunta na v2: sinais contáveis, sem LLM."""

from rag_v2.restricoes import extrair_restricoes
from rag_v2.tipo import classificar
from rag_v2.tipos import Chave, Ligacao

JA = "Tormenta20 - Jogo do Ano"


def _lig(tabela, nome):
    return Ligacao(nome, 0, len(nome), Chave(tabela, nome, JA), 1.0, "exata")


def _tipo(texto, *ligs):
    return classificar(texto, ligs, extrair_restricoes(texto, ligs))


def test_sem_ligacao_com_vocabulario_do_jogo_e_sem_nome():
    assert _tipo("quanto de dano causa um ataque critico?") == "sem_nome"


def test_sem_ligacao_e_sem_vocabulario_do_jogo_e_fora_de_escopo():
    assert _tipo("qual a capital da França?") == "fora_de_escopo"
    assert _tipo("oi, tudo bem?") == "fora_de_escopo"


def test_um_nome_e_uma_pergunta_e_direta():
    assert _tipo("o que faz a magia Bola de Fogo?", _lig("Magias", "Bola de Fogo")) == "direta"


def test_duas_interrogacoes_e_multiparte():
    texto = "Qual o dano da Bola de Fogo? E a área?"
    assert _tipo(texto, _lig("Magias", "Bola de Fogo")) == "multiparte"


def test_conectivo_e_quais_e_multiparte():
    texto = "o que faz a Teia e quais as regras de Caído"
    assert _tipo(texto, _lig("Magias", "Teia"), _lig("Condições", "Caído")) == "multiparte"


def test_duas_tabelas_distintas_e_multiparte():
    texto = "a Teia deixa o alvo Caído"
    assert _tipo(texto, _lig("Magias", "Teia"), _lig("Condições", "Caído")) == "multiparte"


def test_classe_mais_nivel_e_build():
    assert _tipo("sou barbaro nv4, o que pego?", _lig("Classes", "Bárbaro")) == "build"


def test_caso_semente_e_build():
    texto = ("Sou um barbaro, bugbear, nv4, quero usar intimidacao e machado toureo "
             "para causar dano. Quais habilidades combam com isso.")
    ligs = (_lig("Classes", "Bárbaro"), _lig("Raças", "Bugbear"),
            _lig("Perícias", "Intimidação"), _lig("Armas", "Machado Táurico"))
    assert _tipo(texto, *ligs) == "build"


def test_palavra_de_build_com_dois_nomes_e_build_mesmo_sem_classe():
    texto = "machado taurico combina com intimidacao?"
    assert _tipo(texto, _lig("Armas", "Machado Táurico"),
                 _lig("Perícias", "Intimidação")) == "build"


def test_melhor_com_um_nome_so_nao_e_build():
    assert _tipo("qual a melhor adaga?", _lig("Armas", "Adaga")) == "direta"
