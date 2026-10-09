"""Sinais de uso (v2): JSONL local, atrás de flag, sem chaves nem dados pessoais."""

import json

import pytest
from langchain_core.documents import Document

from rag_v2 import sinais
from rag_v2.tipos import Chave, Leitura, Ligacao, Necessidade

JA = "Tormenta20 - Jogo do Ano"
DOC = Document(page_content="[Magias > Tormenta20 - Jogo do Ano]\n# Teia\nconteudo",
               metadata={"Tabela": "Magias", "Nome": "Teia", "Fonte": JA,
                         "relevance_score": 0.91})


def _leitura():
    return Leitura(texto_original="o que faz a Teia?",
                   ligacoes=(Ligacao("Teia", 12, 16, Chave("Magias", "Teia", JA), 1.0, "exata"),),
                   tipo="direta", confianca="alta", k=8, usar_llm="nenhum",
                   necessidades=(Necessidade("registro de Teia (Magias)", "Magias", "Teia",
                                             registro="Teia"),))


TELE = {"candidatos": 30, "garantidos": 1, "k": 8, "reranker": "flashrank",
        "necessidades": [{"descricao": "registro de Teia (Magias)", "obrigatoria": True,
                          "atendida": True}]}


@pytest.mark.parametrize("valor,esperado", [
    (None, False), ("0", False), ("1", True), ("sim", True), ("true", True)])
def test_flag_desligada_por_padrao(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("SINAIS", raising=False)
    else:
        monkeypatch.setenv("SINAIS", valor)
    assert sinais.ativo() is esperado


@pytest.mark.parametrize("resposta,estado", [
    ("A Teia prende. [Magias > Tormenta20 - Jogo do Ano]", "ok"),
    ("A Teia prende.", "sem_citacao"),
    ("A Teia prende. [Magias > Livro Inventado]", "fora"),
    ("", "vazia")])
def test_estado_da_citacao(resposta, estado):
    assert sinais.estado_citacao(resposta, DOC.page_content) == estado


@pytest.mark.parametrize("resposta,esperado", [
    ("A base consultada não cobre esse ponto.", True),
    ("Não há informação sobre isso no contexto.", True),
    ("A Teia prende o alvo. [Magias > Tormenta20 - Jogo do Ano]", False)])
def test_detecta_resposta_nao_ha(resposta, esperado):
    assert sinais.disse_nao_ha(resposta) is esperado


def test_evento_traz_leitura_docs_estado_e_tempos_sem_chaves():
    evento = sinais.montar_evento(_leitura(), [DOC], "A Teia. [Magias > Tormenta20 - Jogo do Ano]",
                                  {"recuperacao": 1.2, "geracao": 3.4}, TELE, "v2")
    assert evento["tipo"] == "pergunta" and len(evento["id"]) == 12
    assert evento["pergunta"] == "o que faz a Teia?"
    assert evento["leitura"]["confianca"] == "alta"
    assert evento["leitura"]["ligacoes"][0]["nome"] == "Teia"
    assert evento["docs"] == [{"tabela": "Magias", "nome": "Teia", "fonte": JA, "score": 0.91}]
    assert evento["estado_citacao"] == "ok" and evento["nao_ha"] is False
    assert evento["tempos_s"] == {"recuperacao": 1.2, "geracao": 3.4}
    assert evento["necessidades_nao_atendidas"] == []
    texto = json.dumps(evento)
    assert "KEY" not in texto.upper().replace("CHAVE", "")


def test_evento_sem_leitura_v1():
    evento = sinais.montar_evento(None, [DOC], "x", {}, None, "v1", pergunta="oi?")
    assert evento["leitura"] is None and evento["pergunta"] == "oi?"


def test_registrar_acrescenta_jsonl_e_feedback_aponta_a_pergunta(tmp_path):
    caminho = tmp_path / "sinais" / "sinais.jsonl"
    evento = sinais.montar_evento(_leitura(), [DOC], "x", {}, TELE, "v2")
    assert sinais.registrar(evento, caminho) is True
    fb = sinais.feedback(evento, "parcial", "faltou a CD")
    assert sinais.registrar(fb, caminho) is True
    linhas = [json.loads(linha) for linha in caminho.read_text().splitlines()]
    assert [linha["tipo"] for linha in linhas] == ["pergunta", "feedback"]
    assert linhas[1]["ref"] == evento["id"] and linhas[1]["valor"] == "parcial"
    assert linhas[1]["faltou"] == "faltou a CD" and linhas[1]["forca"] == "forte"


def test_registrar_nunca_derruba_o_chat(tmp_path):
    bloqueado = tmp_path / "arquivo"
    bloqueado.write_text("x")
    assert sinais.registrar({"tipo": "x"}, bloqueado / "sinais.jsonl") is False
