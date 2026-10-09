"""TDD do VoyageRerank (flag experimental RERANK=voyage) — T3.

Tabela A/B/C/D da T3: A=FlashRank (atual), B=Cohere, C=Voyage (novo),
D=cascata auto. A flag é experimental — o default continua `auto` e o
FlashRank não é removido.

A API do Voyage não aceita `top_n` no corpo (HTTP 400): o corte para
`top_n` é local, após ordenar por `relevance_score` decrescente.
"""

import pytest

import rag_core
from rag_core import Document


def _doc(texto):
    return Document(
        page_content=texto,
        metadata={"Tabela": "Criaturas", "Fonte": "Tormenta20 - Jogo do Ano"},
    )


# --- Montagem -------------------------------------------------------------

def test_criar_reranker_voyage_monta_o_compressor_experimental():
    # Construir VoyageRerank não bate em rede (a chamada é em compress_documents)
    cascata = rag_core.criar_reranker("voyage")

    assert isinstance(cascata, rag_core.CascataReranker)
    assert isinstance(cascata.primario, rag_core.VoyageRerank)
    assert cascata.secundario is None
    assert cascata.nome_primario == "voyage"
    assert cascata.top_n == 12


def test_default_continua_auto_sem_voyage(monkeypatch):
    """Regressão: sem RERANK no ambiente, nada muda (FlashRank segue)."""
    monkeypatch.delenv("RERANK", raising=False)

    cascata = rag_core.criar_reranker()

    assert not isinstance(cascata.primario, rag_core.VoyageRerank)
    assert cascata.nome_primario == "flashrank"
    assert cascata.secundario is not None


def test_flag_desconhecida_menciona_voyage_nas_opcoes():
    with pytest.raises(ValueError, match="voyage"):
        rag_core.criar_reranker("banana")


# --- compress_documents ---------------------------------------------------

def test_compress_ordena_por_score_decrescente_e_corta_top_n(monkeypatch):
    capturado = {}

    def falso_api(query, documentos, model, api_key, timeout):
        capturado.update(
            query=query, documentos=documentos, model=model,
            api_key=api_key, timeout=timeout,
        )
        # Resposta fora de ordem (a API devolve ranqueada; não confiamos nisso)
        return [
            {"index": 2, "relevance_score": 0.91},
            {"index": 0, "relevance_score": 0.44},
            {"index": 1, "relevance_score": 0.17},
        ]

    monkeypatch.setattr(rag_core, "_voyage_rerank_api", falso_api)
    monkeypatch.setenv("VOYAGE_API_KEY", "chave-teste")
    docs = [_doc("primeiro"), _doc("segundo"), _doc("terceiro")]

    saida = list(rag_core.VoyageRerank(top_n=2).compress_documents(docs, "pergunta pt-BR"))

    assert [d.page_content for d in saida] == ["terceiro", "primeiro"]
    assert saida[0].metadata["relevance_score"] == pytest.approx(0.91)
    assert saida[0].metadata["Tabela"] == "Criaturas"  # metadata preservada
    assert capturado["documentos"] == ["primeiro", "segundo", "terceiro"]
    assert capturado["model"] == rag_core.MODELO_VOYAGE
    assert capturado["api_key"] == "chave-teste"


def test_compress_sem_chave_de_api_levanta(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        rag_core.VoyageRerank().compress_documents([_doc("a")], "q")


def test_compress_lista_vazia_nao_chama_a_api(monkeypatch):
    def explodir(*args, **kwargs):
        raise AssertionError("não deveria chamar a API sem candidatos")

    monkeypatch.setattr(rag_core, "_voyage_rerank_api", explodir)

    assert list(rag_core.VoyageRerank().compress_documents([], "q")) == []


def test_compress_erro_de_api_propaga_para_o_fallback(monkeypatch):
    """Erro sobe para recuperar(), que degrada (ensemble_fallback)."""
    def falso_api(*args, **kwargs):
        raise RuntimeError("429 rate limit do Voyage")

    monkeypatch.setattr(rag_core, "_voyage_rerank_api", falso_api)
    monkeypatch.setenv("VOYAGE_API_KEY", "chave-teste")

    with pytest.raises(RuntimeError, match="429"):
        rag_core.VoyageRerank().compress_documents([_doc("a")], "q")


def test_cascata_voyage_registra_ultimo_modo_e_limiar(monkeypatch):
    monkeypatch.setattr(
        rag_core, "_voyage_rerank_api",
        lambda *args, **kwargs: [{"index": 0, "relevance_score": 0.8}],
    )
    monkeypatch.setenv("VOYAGE_API_KEY", "chave-teste")
    cascata = rag_core.criar_reranker("voyage")

    cascata.compress_documents([_doc("a"), _doc("b")], "q")

    assert cascata.ultimo_modo == "voyage"
    assert rag_core.limiar_padrao(cascata.ultimo_modo) == 0.60
