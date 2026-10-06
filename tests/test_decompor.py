import rag_core
from tests.fakes import FakeChat


def test_modo_estrategia_padrao_e_baseline(monkeypatch):
    monkeypatch.delenv("ESTRATEGIA", raising=False)
    assert rag_core.modo_estrategia() == "baseline"


def test_modo_estrategia_lê_env_valida(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    assert rag_core.modo_estrategia() == "decompor"


def test_modo_estrategia_ignora_lixo(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "banana")
    assert rag_core.modo_estrategia() == "baseline"


def test_decompor_limpa_marcadores_e_limita_a_3():
    llm = FakeChat(respostas=[(
        "1. como funciona armadura pesada\n"
        "- qual a penalidade de armadura\n"
        "* armadura pesada\n"
        "penalidade de armadura; vestir armadura pesada\n"
        "uma linha a mais para estourar o limite\n"
    )])
    var = rag_core.decompor_consultas("como funciona armadura pesada", llm=llm)
    assert var == [
        "qual a penalidade de armadura",
        "armadura pesada",
        "penalidade de armadura; vestir armadura pesada",
    ]


def test_decompor_falha_devolve_vazio():
    llm = FakeChat(respostas=[RuntimeError("cota")])
    var = rag_core.decompor_consultas("x" * 40, llm=llm)
    assert var == []


def test_decompor_cacheia_por_query():
    llm = FakeChat(respostas=["uma outra forma de perguntar\ndois termos aqui\ntres sub questoes"])
    q = "quantos pv tem um ogro"
    rag_core.decompor_consultas(q, llm=llm)
    rag_core.decompor_consultas(q, llm=llm)
    assert llm.chamadas == 1
