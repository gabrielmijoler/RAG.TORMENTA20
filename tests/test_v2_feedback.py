"""Leitura de feedback em linguagem natural (Fase 6, item 3): sinal FRACO, sem LLM.

Reconhece só o que é claro. O que não reconhece é ignorado, e o silêncio nunca
conta como acerto. O comando (/errado, /parcial) continua sendo o sinal forte.
"""

import pytest

from rag_v2 import feedback as fb


def _valor(texto):
    resultado = fb.interpretar(texto)
    return resultado.valor if resultado else None


@pytest.mark.parametrize("texto", [
    "deu certo", "funcionou", "Funcionou, valeu!", "perfeito", "era isso mesmo", "correto",
    "isso resolveu", "exatamente",
])
def test_reconhece_feedback_positivo(texto):
    assert _valor(texto) == "certo"


@pytest.mark.parametrize("texto", [
    "errado", "Não era isso", "nao funcionou", "não deu certo", "resposta errada",
    "isso não ajudou", "nunca deu certo", "incorreto",
])
def test_reconhece_feedback_negativo(texto):
    assert _valor(texto) == "errado"


@pytest.mark.parametrize("texto", [
    "em partes", "mais ou menos", "só em parte", "parcialmente", "faltou a duração",
    "funcionou mais ou menos", "deu certo mas faltou a CD",
])
def test_reconhece_feedback_parcial(texto):
    assert _valor(texto) == "parcial"


def test_negacao_vira_o_oposto_e_nao_o_positivo():
    assert _valor("não funcionou") == "errado"
    assert _valor("não deu certo") == "errado"
    assert _valor("isso não está errado") == "certo"


@pytest.mark.parametrize("texto", [
    "", "   ", "obrigado", "ok", "hum", "e a duração dela?", "o que faz a magia Teia?",
    "como funciona a perícia Cura", "quais as regras para desfazer o errado de uma magia",
    "funcionou? não sei", "qual a CD para ver se deu certo",
])
def test_nao_reconhecido_e_ignorado(texto):
    assert fb.interpretar(texto) is None


def test_frase_longa_demais_nao_e_feedback():
    texto = ("hoje na mesa o mestre disse que a regra da condição caído funcionou "
             "do jeito que a gente esperava e todo mundo gostou")
    assert fb.interpretar(texto) is None


def test_polaridades_em_conflito_sao_ignoradas():
    assert fb.interpretar("funcionou mas está errado") is None


def test_negativo_com_parcial_prevalece_o_errado():
    assert _valor("errado, faltou a duração") == "errado"


def test_confianca_alta_para_frase_curta_e_media_para_frase_mais_longa_ou_mista():
    assert fb.interpretar("deu certo").confianca == "alta"
    assert fb.interpretar("funcionou direitinho pra mim ontem na mesa").confianca == "media"
    assert fb.interpretar("deu certo mas faltou a CD").confianca == "media"


def test_extrai_o_que_faltou_quando_o_usuario_diz():
    r = fb.interpretar("em partes, faltou a duração")
    assert r.valor == "parcial" and r.faltou == "a duração"
    assert fb.interpretar("em partes").faltou is None


def test_faltou_sem_complemento_nao_inventa_texto():
    r = fb.interpretar("faltou")
    assert r.valor == "parcial" and r.faltou is None


def test_resultado_guarda_o_texto_original_para_auditoria():
    assert fb.interpretar("Deu certo!").texto == "Deu certo!"


def test_exclamacao_que_comeca_com_que_nao_e_confundida_com_pergunta():
    assert _valor("que bom, funcionou") == "certo"
    assert _valor("que droga, não era isso") == "errado"
