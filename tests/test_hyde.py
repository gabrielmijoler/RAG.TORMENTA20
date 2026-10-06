import pytest
from fakes import FakeChat
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

import rag_core
from rag_core import (
    PROMPT_HYDE,
    RecuperadorDensoHyDE,
    gerar_documento_hipotetico,
)


def test_prompt_hyde_pece_documento_respondendo_a_pergunta():
    msgs = PROMPT_HYDE.format_messages(consulta="Qual o ND de um Basilisco?")
    assert "Qual o ND de um Basilisco?" in msgs[-1].content
    texto = " ".join(m.content for m in msgs)
    assert "pt-BR" in texto or "portugu" in texto.lower()
    assert "pergunta" in texto.lower()  # deve instruir a NÃO devolver pergunta


def test_gerar_documento_chama_llm_e_cacheia():
    llm = FakeChat(respostas=["Basilisco é uma ameaça ND 4 com Defesa 23."])
    cache: dict = {}

    doc = gerar_documento_hipotetico(llm, "Qual o ND do Basilisco?", cache)

    assert "ND 4" in doc
    assert llm.chamadas == 1
    assert cache["Qual o ND do Basilisco?"] == doc

    de_novo = gerar_documento_hipotetico(llm, "Qual o ND do Basilisco?", cache)
    assert de_novo == doc
    assert llm.chamadas == 1  # cacheado: zero chamadas novas


def test_gerar_documento_cache_invalido_e_regenerado():
    llm = FakeChat(respostas=["Resposta hipotética válida sobre a regra em questão."])
    cache = {"consulta": "?"}  # lixo antigo: o usuario mandou uma pergunta

    doc = gerar_documento_hipotetico(llm, "consulta", cache)
    assert llm.chamadas == 1
    assert doc != "?"


def test_gerar_documento_falha_total_devolve_vazio():
    llm = FakeChat(respostas=RuntimeError("rede fora"))
    doc = gerar_documento_hipotetico(llm, "Qual o ND do Basilisco?", {})
    assert doc == ""


def test_gerar_documento_recusa_e_tenta_outro_modelo():
    llm = FakeChat(respostas=["Desculpe, não posso ajudar com isso."])
    doc = gerar_documento_hipotetico(llm, "Qual o ND do Basilisco?", {})
    # recusa nao entra: esgota os modelos e devolve vazio
    assert doc == ""
    assert llm.chamadas >= 1


class FakeStore:
    def __init__(self, docs=None):
        self.visto = None
        self.docs = docs or [Document(page_content="Basilisco ND 4",
                                      metadata={"Nome": "Basilisco"})]

    def similarity_search(self, query, k=4):
        self.visto = (query, k)
        return list(self.docs)

    def as_retriever(self, search_kwargs=None):
        store = self
        k_padrao = (search_kwargs or {}).get("k", 4)

        class _Densa(BaseRetriever):
            def _get_relevant_documents(self, query, *, run_manager=None):
                return store.similarity_search(query, k=k_padrao)

        return _Densa()


def test_retriever_hyde_busca_pelo_documento_gerado():
    store = FakeStore()
    llm = FakeChat(respostas=["Documento hipotético sobre ameaças ND 4."])
    ret = RecuperadorDensoHyDE(vectorstore=store, llm=llm, k=50)

    docs = ret.invoke("Qual o ND do Basilisco?")

    assert store.visto == ("Documento hipotético sobre ameaças ND 4.", 50)
    assert docs[0].metadata["Nome"] == "Basilisco"


def test_retriever_hyde_sem_llm_utilizavel_busca_pela_pergunta():
    store = FakeStore()
    llm = FakeChat(respostas=RuntimeError("rede fora"))
    ret = RecuperadorDensoHyDE(vectorstore=store, llm=llm, k=50)

    ret.invoke("Qual o ND do Basilisco?")

    assert store.visto[0] == "Qual o ND do Basilisco?"


def test_montar_retriever_rejeita_estrategia_desconhecida(monkeypatch):
    monkeypatch.setattr(rag_core, "preparar_colecao", lambda *a, **k: FakeStore())
    docs = [Document(page_content="x", metadata={"Tabela": "T", "Nome": "n"})]
    with pytest.raises(ValueError, match="estrategia"):
        rag_core.montar_retriever(docs, estrategia="banana", verbose=False, conexao={})


def test_montar_retriever_hyde_usa_lego_densa_hyde(monkeypatch):
    monkeypatch.setattr(rag_core, "preparar_colecao", lambda *a, **k: FakeStore())
    docs = [Document(page_content="x", metadata={"Tabela": "T", "Nome": "n"})]
    ret = rag_core.montar_retriever(docs, estrategia="hyde", verbose=False, conexao={})

    ensemble = ret.base_retriever
    assert isinstance(ensemble.retrievers[0], RecuperadorDensoHyDE)


def test_montar_retriever_baseline_continua_densa_pura(monkeypatch):
    monkeypatch.setattr(rag_core, "preparar_colecao", lambda *a, **k: FakeStore())
    docs = [Document(page_content="x", metadata={"Tabela": "T", "Nome": "n"})]
    ret = rag_core.montar_retriever(docs, verbose=False, conexao={})

    ensemble = ret.base_retriever
    assert not isinstance(ensemble.retrievers[0], RecuperadorDensoHyDE)
