import json

import pytest
from fakes import FakeChat
from langchain_core.documents import Document

from avaliar import (
    juizar,
    parsear_veredito,
    resumo_juiz,
)


def _doc(texto, nome="registro"):
    return Document(page_content=texto, metadata={"Nome": nome, "Tabela": "T"})


def _veredito_json(score=8, aprovado=True, justificativa="contexto cobre a pergunta"):
    return json.dumps({"score": score, "aprovado": aprovado,
                       "justificativa": justificativa}, ensure_ascii=False)


def test_parse_veredito_json_puro():
    v = parsear_veredito(_veredito_json(score=9))
    assert v["score"] == 9.0
    assert v["aprovado"] is True
    assert "contexto" in v["justificativa"]


def test_parse_veredito_com_cerca_de_codigo_e_texto_ao_redor():
    texto = (f"Claro! Aqui está:\n```json\n{_veredito_json(score=6, aprovado=False)}\n```\n"
             "Espero que ajude.")
    v = parsear_veredito(texto)
    assert v["score"] == 6.0
    assert v["aprovado"] is False


def test_parse_veredito_rejeita_json_invalido():
    with pytest.raises(ValueError):
        parsear_veredito("o contexto esta bom demais")
    with pytest.raises(ValueError):
        parsear_veredito('{"score": 11, "aprovado": true, "justificativa": "x"}')
    with pytest.raises(ValueError):
        parsear_veredito('{"score": 8, "justificativa": "faltou o booleano"}')
    with pytest.raises(ValueError):
        parsear_veredito('{"aprovado": true, "justificativa": "sem score"}')


def test_juizar_retorna_veredito_e_cacheia():
    llm = FakeChat(respostas=[_veredito_json(score=8)])
    cache: dict = {}

    v = juizar(llm, "Qual o ND do Basilisco?",
               [_doc("Basilisco ND 4, Defesa 23.")], cache=cache)

    assert v["score"] == 8.0
    assert llm.chamadas == 1
    assert len(cache) == 1

    de_novo = juizar(llm, "Qual o ND do Basilisco?",
                     [_doc("Basilisco ND 4, Defesa 23.")], cache=cache)
    assert de_novo == v
    assert llm.chamadas == 1


def test_juizar_resposta_diferente_nao_usa_cache_de_outro_contexto():
    llm = FakeChat(respostas=[_veredito_json(score=3, aprovado=False)])
    cache: dict = {}

    juizar(llm, "pergunta", [_doc("contexto ruim")], cache=cache)
    v2 = juizar(llm, "pergunta", [_doc("contexto excelente")], cache=cache)

    assert llm.chamadas == 2
    assert v2["score"] == 3.0


def test_juizar_inclui_resposta_na_chave_de_cache():
    llm = FakeChat(respostas=[_veredito_json(score=7)])
    cache: dict = {}
    docs = [_doc("ctx")]

    juizar(llm, "pergunta", docs, cache=cache)
    juizar(llm, "pergunta", docs, resposta="uma resposta", cache=cache)

    assert llm.chamadas == 2
    assert len(cache) == 2


def test_juizar_pula_resposta_invalida_e_usa_a_seguinte():
    llm = FakeChat(respostas=["não consigo avaliar", _veredito_json(score=5)])
    v = juizar(llm, "pergunta", [_doc("ctx")], cache={})
    assert v["score"] == 5.0
    assert llm.chamadas == 2


def test_juizar_falha_total_devolve_none():
    llm = FakeChat(respostas=RuntimeError("rede fora"))
    assert juizar(llm, "pergunta", [_doc("ctx")], cache={}) is None


def test_juizar_contexto_composta_entra_no_prompt():
    llm = FakeChat(respostas=[_veredito_json()])
    juizar(llm, "Qual a Defesa do Basilisco?",
           [_doc("Basilisco: Defesa 23."), _doc("Basilisco: ND 4.")],
           resposta="Defesa 23.", cache={})
    assert llm.chamadas == 1  # só prova que rodou; o prompt é validado no integrate


def test_resumo_juiz_agrega_score_e_aprovacao():
    registros = [
        {"juiz": {"score": 8, "aprovado": True, "justificativa": ""}},
        {"juiz": {"score": 4, "aprovado": False, "justificativa": ""}},
        {"juiz": None},
        {"sem juiz": True},
    ]
    r = resumo_juiz(registros)
    assert r["n"] == 2
    assert r["score_medio"] == 6.0
    assert r["taxa_aprovacao"] == 0.5


def test_resumo_juiz_sem_vereditos():
    r = resumo_juiz([{"juiz": None}, {}])
    assert r == {"n": 0, "score_medio": None, "taxa_aprovacao": None}


def test_cache_do_juiz_persiste_em_arquivo(tmp_path):
    from avaliar import carregar_cache_juiz, salvar_cache_juiz

    caminho = str(tmp_path / "juiz.json")
    assert carregar_cache_juiz(caminho) == {}
    veredito = {"score": 7.0, "aprovado": True, "justificativa": "ok"}
    salvar_cache_juiz({"chave": veredito}, caminho)
    assert carregar_cache_juiz(caminho) == {"chave": veredito}
