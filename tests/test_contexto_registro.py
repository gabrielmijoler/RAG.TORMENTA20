"""Contexto completo gravado por query no JSON de avaliação.

A partir desta mudança o registro guarda a lista de `page_content` (cada
item com o cabeçalho de procedência `[Tabela > Fonte]`) entregue ao
gerador — permite re-julgar uma rodada (régua juiz_v2) sem regerar
recuperação nem respostas.
"""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import avaliar


@pytest.fixture
def docs_do_top():
    return [
        Document(page_content="[Magias > Tormenta20 - Jogo do Ano]\n# Voo\nconteudo",
                 metadata={"Fonte": "Tormenta20 - Jogo do Ano",
                           "relevance_score": 0.5}),
        Document(page_content="[Condicoes > Tormenta20 - Jogo do Ano]\n# Caido\nconteudo",
                 metadata={"Fonte": "Tormenta20 - Jogo do Ano",
                           "relevance_score": 0.4}),
    ]


def test_avaliar_grava_contexto_completo_no_registro(monkeypatch, docs_do_top):
    def fake_buscar(retriever, consulta, consulta_real=None, limiar=None,
                    decompor=False):
        return list(docs_do_top)

    monkeypatch.setattr(avaliar, "buscar", fake_buscar)
    monkeypatch.setattr(avaliar, "responder",
                        lambda llm, top, sintese, pergunta: (
                            "resposta sintetizada",
                            {"guard_reparo_disparado": False,
                             "guard_sem_citacao_disparado": False}))
    monkeypatch.setattr(avaliar, "reformular",
                        lambda llm, consulta, cache: consulta)
    monkeypatch.setattr(avaliar.rag_core, "montar_chunks", lambda verbose=True: [])
    monkeypatch.setattr(avaliar.rag_core, "montar_retriever",
                        lambda chunks, estrategia="hibrida", llm=None:
                        SimpleNamespace())
    monkeypatch.setattr(avaliar.rag_core, "montar_cadeia_resposta",
                        lambda system_prompt, llm, com_historico=False: None)
    monkeypatch.setattr(avaliar.rag_core, "reranker_ativo", lambda: "flashrank")
    monkeypatch.setattr(avaliar, "carregar_goldenset",
                        lambda: [{"id": "01_teste", "consulta": "pergunta",
                                  "entidades": ["Voo"]}])
    monkeypatch.setattr(avaliar, "carregar_cache", dict)
    monkeypatch.setattr(avaliar, "_pontos_colecao", lambda: 0)
    monkeypatch.setattr(avaliar, "INTERVALO_QUERY", 0)

    resultado = avaliar.avaliar(None, saida=None)

    reg = resultado["registros"][0]
    # é EXATAMENTE a lista que o gerador consumiu, na ordem do rank
    assert reg["contexto"] == [d.page_content for d in docs_do_top]
    # cada item carrega o cabeçalho de procedência
    assert reg["contexto"][0].startswith("[Magias > Tormenta20 - Jogo do Ano]")
    assert reg["contexto"][1].startswith("[Condicoes > Tormenta20 - Jogo do Ano]")
    # e o contexto em string (métricas) é a junção da mesma lista
    assert "\n".join(reg["contexto"]).splitlines()[0] == "[Magias > Tormenta20 - Jogo do Ano]"
