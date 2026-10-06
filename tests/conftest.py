"""Fixtures globais da suíte.

`montar_retriever()` constrói os compressores de verdade: sem este patch,
`tests/test_hyde.py` dispararia o download do modelo FlashRank (~150 MB) na
1ª execução do pytest. Testes que precisam de comportamento específico dão
override com `monkeypatch.setattr(rag_core, ...)` no corpo do teste.
"""

import pytest
from langchain_core.documents import BaseDocumentCompressor

import rag_core


class CompressorFalso(BaseDocumentCompressor):
    """Stand-in do FlashrankRerank/CohereRerank: devolve os candidatos intactos."""

    top_n: int = 12
    model: str | None = None

    def compress_documents(self, documents, query, callbacks=None):
        return list(documents)[: self.top_n]


@pytest.fixture(autouse=True)
def construtores_de_reranker_falsos(monkeypatch):
    monkeypatch.setattr(rag_core, "FlashrankRerank", CompressorFalso, raising=False)
    monkeypatch.setattr(rag_core, "CohereRerank", CompressorFalso, raising=False)
