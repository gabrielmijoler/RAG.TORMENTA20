"""Prefixos do e5 (`query: ` / `passage: `), atrás da flag EMBEDDING_PREFIXOS=e5.

O multilingual-e5 foi treinado com esses prefixos; sem eles a similaridade
densa piora. A flag liga o embrulho e troca a coleção, deixando a atual intacta.
"""

import pytest
from langchain_core.embeddings import Embeddings

import rag_core


class BaseFalsa(Embeddings):
    def __init__(self):
        self.documentos, self.consultas = [], []

    def embed_documents(self, textos):
        self.documentos.extend(textos)
        return [[float(len(t))] for t in textos]

    def embed_query(self, texto):
        self.consultas.append(texto)
        return [float(len(texto))]


def test_embrulho_poe_passage_nos_documentos_e_query_nas_perguntas():
    base = BaseFalsa()
    emb = rag_core.EmbeddingsComPrefixo(base)
    emb.embed_documents(["Voo causa 6d6", "Caído"])
    emb.embed_query("o que é Caído?")
    assert base.documentos == ["passage: Voo causa 6d6", "passage: Caído"]
    assert base.consultas == ["query: o que é Caído?"]


def test_embrulho_nao_prefixa_duas_vezes():
    base = BaseFalsa()
    emb = rag_core.EmbeddingsComPrefixo(base)
    emb.embed_query("query: já veio com prefixo")
    assert base.consultas == ["query: já veio com prefixo"]


@pytest.mark.parametrize("valor,esperado", [
    (None, False), ("", False), ("0", False), ("e5", True), ("E5", True)])
def test_flag_desligada_por_padrao(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("EMBEDDING_PREFIXOS", raising=False)
    else:
        monkeypatch.setenv("EMBEDDING_PREFIXOS", valor)
    assert rag_core.embedding_prefixos_ativo() is esperado


def test_nome_da_colecao_e_o_atual_sem_a_flag(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PREFIXOS", raising=False)
    assert rag_core.nome_da_colecao() == "tormenta20"


def test_nome_da_colecao_muda_com_a_flag_para_nao_misturar_vetores(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PREFIXOS", "e5")
    assert rag_core.nome_da_colecao() == "tormenta20_e5p"


def test_obter_embeddings_devolve_o_embrulho_com_a_flag(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PREFIXOS", "e5")
    monkeypatch.setattr(rag_core, "_EMBEDDINGS_CACHE", None)
    monkeypatch.setattr(rag_core, "HuggingFaceEmbeddings", lambda **kw: BaseFalsa())
    emb = rag_core.obter_embeddings()
    assert isinstance(emb, rag_core.EmbeddingsComPrefixo)


def test_obter_embeddings_sem_flag_e_o_modelo_puro(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PREFIXOS", raising=False)
    monkeypatch.setattr(rag_core, "_EMBEDDINGS_CACHE", None)
    monkeypatch.setattr(rag_core, "HuggingFaceEmbeddings", lambda **kw: BaseFalsa())
    assert isinstance(rag_core.obter_embeddings(), BaseFalsa)
