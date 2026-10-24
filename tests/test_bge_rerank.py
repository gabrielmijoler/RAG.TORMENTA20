"""Reranker multilíngue local (cross-encoder bge-reranker-v2-m3), flag RERANK=bge.

O modelo (2,3 GB, Apache-2.0 segundo o Hugging Face) é carregado só na primeira
pergunta; os testes usam um cross-encoder falso para nunca baixar nada.
"""

import pytest

import rag_core
from rag_core import Document


class CrossEncoderFalso:
    criados = 0

    def __init__(self, *a, **k):
        type(self).criados += 1
        self.chamadas = []

    def predict(self, pares, **k):
        self.chamadas.append(len(pares))
        # score = quantas palavras da pergunta aparecem no texto
        return [float(sum(w in texto.lower() for w in consulta.lower().split()))
                for consulta, texto in pares]


@pytest.fixture(autouse=True)
def modelo_falso(monkeypatch):
    CrossEncoderFalso.criados = 0
    monkeypatch.setattr(rag_core, "_carregar_cross_encoder",
                        lambda nome, max_length, threads: CrossEncoderFalso())


def _doc(texto):
    return Document(page_content=texto, metadata={"Tabela": "T", "Fonte": "F"})


def test_criar_reranker_bge_nao_carrega_o_modelo_ao_montar():
    cascata = rag_core.criar_reranker("bge")
    assert isinstance(cascata, rag_core.CascataReranker)
    assert isinstance(cascata.primario, rag_core.CrossEncoderRerank)
    assert cascata.secundario is None and cascata.nome_primario == "bge"
    assert CrossEncoderFalso.criados == 0


def test_ordena_por_score_decrescente_e_grava_relevance_score():
    rr = rag_core.CrossEncoderRerank(top_n=3)
    docs = [_doc("nada a ver"), _doc("grifo voa"), _doc("o grifo parceiro voa alto")]
    saida = rr.compress_documents(docs, "grifo parceiro voa")
    assert [d.page_content for d in saida] == ["o grifo parceiro voa alto", "grifo voa",
                                               "nada a ver"]
    assert saida[0].metadata["relevance_score"] == 3.0
    assert saida[0].metadata["Tabela"] == "T"          # metadata original preservada


def test_corta_em_top_n():
    rr = rag_core.CrossEncoderRerank(top_n=2)
    docs = [_doc(f"grifo {i}") for i in range(5)]
    assert len(rr.compress_documents(docs, "grifo")) == 2


def test_empate_mantem_a_ordem_de_entrada():
    rr = rag_core.CrossEncoderRerank(top_n=5)
    docs = [_doc("a grifo"), _doc("b grifo"), _doc("c grifo")]
    assert [d.page_content for d in rr.compress_documents(docs, "grifo")] == [
        "a grifo", "b grifo", "c grifo"]


def test_lista_vazia_nao_carrega_nem_quebra():
    assert rag_core.CrossEncoderRerank().compress_documents([], "q") == []
    assert CrossEncoderFalso.criados == 0


def test_modelo_e_carregado_uma_unica_vez_entre_perguntas():
    rr = rag_core.CrossEncoderRerank()
    rr.compress_documents([_doc("grifo")], "grifo")
    rr.compress_documents([_doc("grifo")], "outra pergunta")
    assert CrossEncoderFalso.criados == 1


def test_default_continua_sendo_o_flashrank(monkeypatch):
    monkeypatch.delenv("RERANK", raising=False)
    assert rag_core.criar_reranker().nome_primario == "flashrank"


def test_modo_bge_e_aceito_pela_flag_de_ambiente(monkeypatch):
    monkeypatch.setenv("RERANK", "bge")
    assert rag_core.criar_reranker().nome_primario == "bge"


def test_sem_limiar_padrao_para_bge_pois_a_escala_do_score_nao_foi_calibrada():
    assert rag_core.limiar_padrao("bge") is None


# --- o reranker padrão da v2 é o bge; o da v1 continua o FlashRank ---------------------------

def test_na_v2_o_reranker_padrao_e_o_bge(monkeypatch):
    monkeypatch.delenv("RERANK", raising=False)
    monkeypatch.setenv("ARQUITETURA", "v2")
    assert rag_core.reranker_ativo() == "bge"
    assert rag_core.criar_reranker().nome_primario == "bge"


def test_na_v2_a_variavel_rerank_explicita_continua_valendo(monkeypatch):
    monkeypatch.setenv("ARQUITETURA", "v2")
    monkeypatch.setenv("RERANK", "flashrank")
    assert rag_core.reranker_ativo() == "flashrank"


def test_na_v1_o_reranker_padrao_continua_auto(monkeypatch):
    monkeypatch.delenv("RERANK", raising=False)
    monkeypatch.delenv("ARQUITETURA", raising=False)
    assert rag_core.reranker_ativo() == "auto"
    monkeypatch.setenv("ARQUITETURA", "v1")
    assert rag_core.reranker_ativo() == "auto"
