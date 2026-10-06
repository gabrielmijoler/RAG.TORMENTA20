import os
from types import SimpleNamespace

from rag_core import (
    LIMIARES_PADRAO,
    Document,
    _aplicar_limiar,
    limiar_confianca_flashrank,
    limiar_padrao,
    limiar_relevancia,
    recuperar,
)


def _doc(nome, score, tabela="Magias", fonte="Tormenta20 - Jogo do Ano"):
    meta = {"Tabela": tabela, "Fonte": fonte, "Nome": nome}
    if score is not None:
        meta["relevance_score"] = score
    return Document(page_content=f"regra de {nome} sem preco", metadata=meta)


def test_limiar_corta_docs_abaixo_do_corte():
    docs = [_doc("a", 0.95), _doc("b", 0.50), _doc("c", 0.70)]
    sel = _aplicar_limiar(docs, 0.70)
    assert [d.metadata["Nome"] for d in sel] == ["a", "c"]


def test_limiar_desligado_devolve_tudo():
    docs = [_doc("a", 0.10), _doc("b", None)]
    assert _aplicar_limiar(docs, None) == docs
    assert _aplicar_limiar(docs, 0.0) == docs


def test_limiar_corta_doc_sem_score():
    docs = [_doc("sem", None), _doc("com", 0.9)]
    sel = _aplicar_limiar(docs, 0.7)
    assert [d.metadata["Nome"] for d in sel] == ["com"]


def test_limiar_que_corta_tudo_devolve_vazio():
    docs = [_doc("a", 0.30), _doc("b", 0.45)]
    assert _aplicar_limiar(docs, 0.70) == []


def test_ler_limiar_da_variavel_de_ambiente(monkeypatch):
    monkeypatch.delenv("LIMIAR_RELEVANCIA", raising=False)
    assert limiar_relevancia() is None
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "")
    assert limiar_relevancia() is None
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0")
    assert limiar_relevancia() is None
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0.75")
    assert limiar_relevancia() == 0.75
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "lixo")
    assert limiar_relevancia() is None


def _fake_retriever(docs, modo=None):
    class Compressor:
        top_n = 8

        def compress_documents(self, candidatos, query):
            return candidatos

    compressor = Compressor()
    if modo is not None:
        compressor.ultimo_modo = modo
    return SimpleNamespace(
        base_retriever=SimpleNamespace(invoke=lambda q: list(docs)),
        base_compressor=compressor,
    )


def test_recuperar_aplica_limiar_e_respeita_top_n():
    docs = [_doc("alto", 0.92), _doc("baixo", 0.40), _doc("medio", 0.75)]
    top = recuperar(_fake_retriever(docs), "consulta", limiar=0.70)
    assert [d.metadata["Nome"] for d in top] == ["alto", "medio"]


def test_recuperar_sem_limiar_comporta_como_antes():
    docs = [_doc("alto", 0.92), _doc("baixo", 0.40)]
    top = recuperar(_fake_retriever(docs), "consulta")
    assert len(top) == 2


def test_recuperar_com_limiar_agressivo_devolve_vazio():
    docs = [_doc("a", 0.30), _doc("b", 0.20)]
    top = recuperar(_fake_retriever(docs), "consulta", limiar=0.70)
    assert top == []


def test_ler_limiar_de_ambiente_no_processo(monkeypatch):
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0.8")
    docs = [_doc("alto", 0.92), _doc("baixo", 0.72)]
    top = recuperar(_fake_retriever(docs), "consulta")
    assert [d.metadata["Nome"] for d in top] == ["alto"]
    assert os.environ["LIMIAR_RELEVANCIA"] == "0.8"


# --- LIMIARES_PADRAO -------------------------------------------------------


def test_limiares_padrao_valores():
    assert LIMIARES_PADRAO == {"voyage": 0.60, "cohere": 0.70, "flashrank": 0.35}


def test_limiar_padrao_por_modo():
    assert limiar_padrao("flashrank") == 0.35
    assert limiar_padrao("cohere") == 0.70
    assert limiar_padrao("cohere_escalado") == 0.70
    assert limiar_padrao("voyage") == 0.60
    assert limiar_padrao("FLASHRANK") == 0.35  # caixa livre
    assert limiar_padrao("desligado") is None
    assert limiar_padrao("ensemble_fallback") is None
    assert limiar_padrao(None) is None
    assert limiar_padrao("modo-inventado") is None


def test_default_do_flashrank_confianca_vem_do_dict(monkeypatch):
    monkeypatch.delenv("LIMIAR_CONFIANCA_FLASHRANK", raising=False)
    assert limiar_confianca_flashrank() == LIMIARES_PADRAO["flashrank"]


def test_recuperar_corta_no_default_do_modo_flashrank(monkeypatch):
    monkeypatch.delenv("LIMIAR_RELEVANCIA", raising=False)
    docs = [_doc("alto", 0.92), _doc("baixo", 0.20)]
    top = recuperar(_fake_retriever(docs, modo="flashrank"), "consulta")
    assert [d.metadata["Nome"] for d in top] == ["alto"]


def test_recuperar_corta_no_70_quando_scores_sao_do_cohere(monkeypatch):
    monkeypatch.delenv("LIMIAR_RELEVANCIA", raising=False)
    docs = [_doc("alto", 0.92), _doc("medio", 0.60)]
    top = recuperar(_fake_retriever(docs, modo="cohere_escalado"), "consulta")
    assert [d.metadata["Nome"] for d in top] == ["alto"]


def test_recuperar_argo_explicito_vence_o_default_do_modo(monkeypatch):
    monkeypatch.delenv("LIMIAR_RELEVANCIA", raising=False)
    docs = [_doc("alto", 0.92), _doc("medio", 0.50)]
    top = recuperar(_fake_retriever(docs, modo="flashrank"), "consulta",
                    limiar=0.70)
    assert [d.metadata["Nome"] for d in top] == ["alto"]


def test_recuperar_env_vence_o_default_do_modo(monkeypatch):
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0.95")
    docs = [_doc("alto", 0.99), _doc("medio", 0.92)]
    top = recuperar(_fake_retriever(docs, modo="flashrank"), "consulta")
    assert [d.metadata["Nome"] for d in top] == ["alto"]


def test_recuperar_modo_sem_score_nao_corta(monkeypatch):
    monkeypatch.delenv("LIMIAR_RELEVANCIA", raising=False)
    docs = [_doc("lixo", 0.10), _doc("ok", 0.90)]
    top = recuperar(_fake_retriever(docs, modo="ensemble_fallback"), "consulta")
    assert len(top) == 2
