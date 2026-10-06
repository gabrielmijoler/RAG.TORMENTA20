from types import SimpleNamespace

from rag_core import Document, recuperar


def _doc(nome, score=None):
    meta = {"Tabela": "Magias", "Fonte": "Tormenta20 - Jogo do Ano",
            "Nome": nome}
    if score is not None:
        meta["relevance_score"] = score
    return Document(page_content=f"regra de {nome} sem preco", metadata=meta)


def _retriever_com_rerank_quebrado(docs, top_n_original=8):
    class Compressor:
        top_n = top_n_original

        def compress_documents(self, candidatos, query):
            raise RuntimeError(
                "429 Client Error: Too Many Requests — "
                "x-trial-endpoint-call-limit: 10"
            )

    return SimpleNamespace(
        base_retriever=SimpleNamespace(invoke=lambda q: list(docs)),
        base_compressor=Compressor(),
    )


def test_recuperar_sem_rerank_devolve_docs_na_ordem_do_ensemble(capsys):
    docs = [_doc("a"), _doc("b"), _doc("c")]
    top = recuperar(_retriever_com_rerank_quebrado(docs), "consulta")
    assert [d.metadata["Nome"] for d in top] == ["a", "b", "c"]
    assert "rerank" in capsys.readouterr().out.lower()


def test_recuperar_sem_rerank_ignora_o_limiar():
    docs = [_doc("a", 0.95), _doc("b", 0.10)]
    top = recuperar(_retriever_com_rerank_quebrado(docs), "consulta",
                    limiar=0.70)
    assert len(top) == 2


def test_recuperar_restaura_top_n_apos_falha_do_rerank():
    retriever = _retriever_com_rerank_quebrado([_doc("a")], top_n_original=8)
    recuperar(retriever, "consulta")
    assert retriever.base_compressor.top_n == 8
