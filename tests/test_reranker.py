"""Tiered Reranking — TDD do `CascataReranker` (FlashRank → escalada Cohere).

Casos do spec:
  1. FlashRank confiável (top-1 >= limiar) -> Cohere NÃO é chamado;
  2. baixa confiança -> escalada para o Cohere e resultado do Cohere;
  3. Cohere falha na escalada (429) -> mantém o resultado do FlashRank;
  4. leitura da flag RERANK (auto/cascata, flashrank, cohere, desligado);
  5. `top_n` do wrapper repassa aos compressores filhos.

Os construtores são monkeypatchados em TODOS os testes (também via
`conftest.py`): nada baixa o modelo de 150 MB nem bate na API do Cohere.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.documents import BaseDocumentCompressor
from pydantic import Field

import rag_core
from rag_core import Document


def _doc(nome, score=None):
    meta = {"Tabela": "Magias", "Fonte": "Tormenta20 - Jogo do Ano",
            "Nome": nome}
    if score is not None:
        meta["relevance_score"] = score
    return Document(page_content=f"regra de {nome} sem preco", metadata=meta)


class _Fake(BaseDocumentCompressor):
    """Compressor gravador: devolve `resposta` ou estoura `erro`."""

    top_n: int = 12
    resposta: list = Field(default_factory=list)
    erro: Any = None  # Exception p/ pydantic não gera schema; aceita o que for
    chamadas: int = 0

    def compress_documents(self, documents, query, callbacks=None):
        self.chamadas += 1
        if self.erro is not None:
            raise self.erro
        return list(self.resposta)


class _FlashrankFake(_Fake):
    pass


class _CohereFake(_Fake):
    pass


def _patch_construtores(monkeypatch):
    monkeypatch.setattr(rag_core, "FlashrankRerank", _FlashrankFake, raising=False)
    monkeypatch.setattr(rag_core, "CohereRerank", _CohereFake, raising=False)


def _cascata(primario, secundario=None, limiar=0.35):
    cascata = rag_core.CascataReranker(
        primario=primario,
        secundario=secundario,
        limiar_confianca=limiar,
        nome_primario="flashrank",
    )
    cascata.top_n = 12  # sincroniza wrapper e filhos (como criar_reranker)
    return cascata


def _retriever(candidatos, compressor):
    return SimpleNamespace(
        base_retriever=SimpleNamespace(invoke=lambda q: list(candidatos)),
        base_compressor=compressor,
    )


# --- Caso 1: FlashRank confiável não chama o Cohere -------------------------

def test_cascata_confianca_alta_usa_so_flashrank():
    esperado = [_doc("a", 0.92), _doc("b", 0.40)]
    primario = _Fake(resposta=esperado)
    secundario = _Fake(resposta=[_doc("c", 0.99)])
    cascata = _cascata(primario, secundario)

    saida = cascata.compress_documents([_doc("z")], "consulta")

    assert list(saida) == esperado
    assert secundario.chamadas == 0
    assert cascata.ultimo_modo == "flashrank"


# --- Caso 2: baixa confiança escalona para o Cohere -------------------------

def test_cascata_baixa_confianca_escalona_para_cohere(capsys):
    candidatos = [_doc("a"), _doc("b")]
    primario = _Fake(resposta=[_doc("fr_baixo", 0.12), _doc("fr_pior", 0.05)])
    secundario = _Fake(resposta=[_doc("co_alto", 0.81)])
    cascata = _cascata(primario, secundario)

    saida = cascata.compress_documents(candidatos, "consulta")

    assert secundario.chamadas == 1
    assert next(iter(saida)).metadata["Nome"] == "co_alto"
    assert cascata.ultimo_modo == "cohere_escalado"
    aviso = capsys.readouterr().out
    assert "baixa confiança" in aviso
    assert "Escalando" in aviso


# --- Caso 3: Cohere caído na escalada mantém o FlashRank --------------------

def test_cascata_escalada_com_cohere_caído_mantem_flashrank(capsys):
    esperado = [_doc("fr_baixo", 0.20)]
    primario = _Fake(resposta=esperado)
    secundario = _Fake(erro=RuntimeError("429 Client Error: Too Many Requests"))
    cascata = _cascata(primario, secundario)

    saida = cascata.compress_documents([_doc("z")], "consulta")

    assert list(saida) == esperado
    assert cascata.ultimo_modo == "flashrank"
    assert "mantendo resultado do FlashRank" in capsys.readouterr().out


# --- Caso 4: leitura da flag RERANK -----------------------------------------

def test_auto_monta_cascata_flashrank_para_cohere(monkeypatch):
    _patch_construtores(monkeypatch)
    monkeypatch.delenv("RERANK", raising=False)

    cascata = rag_core.criar_reranker()

    assert isinstance(cascata, rag_core.CascataReranker)
    assert isinstance(cascata.primario, _FlashrankFake)
    assert isinstance(cascata.secundario, _CohereFake)
    assert cascata.limiar_confianca == pytest.approx(0.35)


def test_flag_flashrank_so_usa_o_local(monkeypatch):
    _patch_construtores(monkeypatch)
    cascata = rag_core.criar_reranker("flashrank")
    assert isinstance(cascata.primario, _FlashrankFake)
    assert cascata.secundario is None


def test_flag_cohere_so_usa_a_api(monkeypatch):
    _patch_construtores(monkeypatch)
    cascata = rag_core.criar_reranker("cohere")
    assert isinstance(cascata.primario, _CohereFake)
    assert cascata.secundario is None


def test_flag_desligado_passa_os_docs_intactos(monkeypatch):
    _patch_construtores(monkeypatch)
    cascata = rag_core.criar_reranker("desligado")
    assert cascata.primario is None

    docs = [_doc("a")]
    assert list(cascata.compress_documents(docs, "q")) == docs
    assert cascata.ultimo_modo == "desligado"


def test_flag_desconhecida_levanta_valueerror(monkeypatch):
    _patch_construtores(monkeypatch)
    with pytest.raises(ValueError, match="RERANK"):
        rag_core.criar_reranker("banana")


def test_reranker_ativo_le_a_env(monkeypatch):
    monkeypatch.delenv("RERANK", raising=False)
    assert rag_core.reranker_ativo() == "auto"
    monkeypatch.setenv("RERANK", "flashrank")
    assert rag_core.reranker_ativo() == "flashrank"
    monkeypatch.setenv("RERANK", " Desligado ")
    assert rag_core.reranker_ativo() == "desligado"


# --- Caso 5: top_n repassa aos filhos ---------------------------------------

def test_top_n_do_wrapper_repara_nos_filhos(monkeypatch):
    _patch_construtores(monkeypatch)
    cascata = rag_core.criar_reranker()
    assert cascata.top_n == 12

    cascata.top_n = 30

    assert cascata.top_n == 30
    assert cascata.primario.top_n == 30
    assert cascata.secundario.top_n == 30


# --- Integração com recuperar() ---------------------------------------------

def test_recuperar_com_cascata_escalada_aplica_limiar():
    candidatos = [_doc("cand1"), _doc("cand2")]
    primario = _Fake(resposta=[_doc("fr", 0.20)])
    secundario = _Fake(resposta=[_doc("alto", 0.95), _doc("baixo", 0.20)])
    cascata = _cascata(primario, secundario)

    top = rag_core.recuperar(_retriever(candidatos, cascata), "consulta",
                             limiar=0.70)

    assert secundario.chamadas == 1
    assert [d.metadata["Nome"] for d in top] == ["alto"]
    assert cascata.ultimo_modo == "cohere_escalado"
    assert cascata.top_n == 12  # restaurado após a mutação de recuperar()


def test_recuperar_falha_do_primario_vira_ensemble_fallback(capsys):
    candidatos = [_doc("a"), _doc("b")]
    cascata = _cascata(_Fake(erro=RuntimeError("429 Client Error")))

    top = rag_core.recuperar(_retriever(candidatos, cascata), "consulta",
                             limiar=0.70)

    assert [d.metadata["Nome"] for d in top] == ["a", "b"]
    assert cascata.ultimo_modo == "ensemble_fallback"
    saida = capsys.readouterr().out
    assert "rerank" in saida.lower()
    assert "limiar ignorado" in saida


def test_recuperar_desligado_ignora_o_limiar():
    candidatos = [_doc("a"), _doc("b")]
    cascata = rag_core.criar_reranker("desligado")

    top = rag_core.recuperar(_retriever(candidatos, cascata), "consulta",
                             limiar=0.70)

    assert [d.metadata["Nome"] for d in top] == ["a", "b"]
    assert cascata.ultimo_modo == "desligado"


# --- Rerank só com a query original (2026-10-06) -----------------------------

class _Gravador(_Fake):
    """Registra a query entregue a cada `compress_documents`."""

    queries: list = Field(default_factory=list)

    def compress_documents(self, documents, query, callbacks=None):
        self.queries.append(query)
        return super().compress_documents(documents, query, callbacks)


def _retriever_gravador(candidatos, compressor):
    """Como `_retriever`, mas também grava as queries do ensemble."""
    chamadas: list[str] = []
    retriever = SimpleNamespace(
        base_retriever=SimpleNamespace(invoke=lambda q: (chamadas.append(q),
                                                         list(candidatos))[1]),
        base_compressor=compressor,
    )
    return retriever, chamadas


def test_recuperar_reranka_somente_com_a_query_original():
    """`consulta_real` serve para o RECALL; o rerank vê só ela (pt-BR)."""
    gravador = _Gravador(resposta=[_doc("a", 0.9)])
    retriever, chamadas = _retriever_gravador([_doc("a"), _doc("b")], gravador)

    rag_core.recuperar(retriever, "consulta reformulada", "consulta original")

    assert chamadas == ["consulta reformulada", "consulta original"]
    assert gravador.queries == ["consulta original"]


def test_recuperar_sem_consulta_real_reranka_com_a_propria_query():
    gravador = _Gravador(resposta=[_doc("a", 0.9)])
    retriever, chamadas = _retriever_gravador([_doc("a")], gravador)

    rag_core.recuperar(retriever, "consulta reformulada")

    assert chamadas == ["consulta reformulada"]
    assert gravador.queries == ["consulta reformulada"]
