"""Telemetria da expansão parent-child no avaliar (ULTIMA_EXPANSAO).

Por pergunta, o avaliar congela:
- `expansao`: cópia de `rag_core.ULTIMA_EXPANSAO` (baldes da última chamada
  de `_expandir_pais` — escrita por buscar → recuperar, UMA vez por query);
- `contexto_chars`: tamanho em chars do `top` consumido por geração,
  métricas e juiz.

No fim da rodada, `resumo_expansao` agrega totais, lista as 5 queries com
maior contexto e sinaliza `registro == 0` (expansão desativada: o processo
não passou por montar_chunks) para o `resumir` emitir o aviso visível.
"""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import avaliar
import rag_core


@pytest.fixture
def ultima_expansao():
    """`ULTIMA_EXPANSAO` zerada durante o teste; restaura ao terminar."""
    original = dict(rag_core.ULTIMA_EXPANSAO)
    rag_core.ULTIMA_EXPANSAO.clear()
    yield rag_core.ULTIMA_EXPANSAO
    rag_core.ULTIMA_EXPANSAO.clear()
    rag_core.ULTIMA_EXPANSAO.update(original)


# ---------- anotar_expansao ----------

def test_anotar_expansao_grava_estatisticas_e_contexto_chars(ultima_expansao):
    ultima_expansao.update({"entrada": 4, "expandidos": 3, "sem_pai": 0,
                            "chave_divergente": 1, "truncados": 1,
                            "duplicados": 0, "registro": 493})
    top = [Document(page_content="abcde", metadata={}),
           Document(page_content="1234567", metadata={})]
    registro = {}

    avaliar.anotar_expansao(registro, top)

    assert registro["expansao"] == {"entrada": 4, "expandidos": 3,
                                    "sem_pai": 0, "chave_divergente": 1,
                                    "truncados": 1, "duplicados": 0,
                                    "registro": 493}
    assert registro["contexto_chars"] == len("abcde") + len("1234567")


def test_anotar_expansao_copia_dict_sem_referencia(ultima_expansao):
    """Cópia, não referência: a próxima query sobrescreve o dict global sem
    corromper o registro da anterior (e o registro não retroalimenta)."""
    ultima_expansao.update({"entrada": 2, "registro": 10})
    registro = {}

    avaliar.anotar_expansao(registro, [])

    rag_core.ULTIMA_EXPANSAO["entrada"] = 999  # próxima chamada reescreve
    assert registro["expansao"]["entrada"] == 2
    registro["expansao"]["entrada"] = 555  # o registro não mexe no global
    assert rag_core.ULTIMA_EXPANSAO["entrada"] == 999


def test_avaliar_anota_expansao_logo_apos_buscar(monkeypatch):
    """Loop fino: o `expansao` congelado é o que `buscar` produziu, mesmo
    `responder` sobrescrevendo ULTIMA_EXPANSAO depois — prova de que a
    captura acontece entre buscar e a geração (sem outra busca no meio)."""
    doc = Document(page_content="[Magias > T20]\nconteudo do contexto",
                   metadata={"Fonte": "T20", "relevance_score": 0.5})
    da_buscar = {"entrada": 3, "expandidos": 3, "sem_pai": 0,
                 "chave_divergente": 0, "truncados": 1, "duplicados": 0,
                 "registro": 493}

    def fake_buscar(retriever, consulta, consulta_real=None, limiar=None,
                    decompor=False):
        rag_core.ULTIMA_EXPANSAO.clear()
        rag_core.ULTIMA_EXPANSAO.update(da_buscar)
        return [doc]

    def fake_responder(llm, top, sintese, pergunta):
        rag_core.ULTIMA_EXPANSAO.clear()
        rag_core.ULTIMA_EXPANSAO.update({"entrada": 999, "registro": 0})
        return ("resposta sintetizada",
                {"guard_reparo_disparado": False,
                 "guard_sem_citacao_disparado": False})

    monkeypatch.setattr(avaliar, "buscar", fake_buscar)
    monkeypatch.setattr(avaliar, "responder", fake_responder)
    monkeypatch.setattr(avaliar, "reformular",
                        lambda llm, consulta, cache: consulta)
    monkeypatch.setattr(avaliar.rag_core, "montar_chunks",
                        lambda verbose=True: [])
    monkeypatch.setattr(avaliar.rag_core, "montar_retriever",
                        lambda chunks, estrategia="hibrida", llm=None:
                        SimpleNamespace())
    monkeypatch.setattr(avaliar.rag_core, "montar_cadeia_resposta",
                        lambda system_prompt, llm, com_historico=False: None)
    monkeypatch.setattr(avaliar.rag_core, "reranker_ativo",
                        lambda: "flashrank")
    monkeypatch.setattr(avaliar, "carregar_goldenset",
                        lambda: [{"id": "01_teste", "consulta": "pergunta",
                                  "entidades": ["Bola"]}])
    monkeypatch.setattr(avaliar, "carregar_cache", dict)
    monkeypatch.setattr(avaliar, "_pontos_colecao", lambda: 0)
    monkeypatch.setattr(avaliar, "INTERVALO_QUERY", 0)

    resultado = avaliar.avaliar(None, saida=None)

    reg = resultado["registros"][0]
    # o dicionário gravado é o da BUSCAR (3), não o do responder (999)
    assert reg["expansao"] == da_buscar
    assert reg["contexto_chars"] == len(doc.page_content)
    assert resultado["resumo_expansao"]["n"] == 1


# ---------- resumo_expansao + aviso no resumir ----------

def test_resumo_expansao_agrega_totais_e_maior_contexto():
    registros = [
        {"id": "a", "contexto_chars": 100,
         "expansao": {"entrada": 3, "expandidos": 2, "sem_pai": 0,
                      "chave_divergente": 1, "truncados": 1,
                      "duplicados": 0, "registro": 493}},
        {"id": "b", "contexto_chars": 900,
         "expansao": {"entrada": 2, "expandidos": 2, "sem_pai": 0,
                      "chave_divergente": 0, "truncados": 0,
                      "duplicados": 0, "registro": 493}},
        {"id": "velho"},  # JSON de --continuar anterior ao campo: ignorado
    ]

    r = avaliar.resumo_expansao(registros)

    assert r["n"] == 2
    assert r["expandidos"] == 4
    assert r["chave_divergente"] == 1
    assert r["truncados"] == 1
    assert r["duplicados"] == 0
    assert r["sem_pai"] == 0
    assert r["sem_registro"] == 0
    assert r["maiores"] == [("b", 900), ("a", 100)]


def test_resumir_avisa_quando_registro_zero(capsys):
    """Aviso BEM visível quando a expansão ficou desativada na rodada —
    sem derrubar a avaliação (só imprime)."""
    registros = [{"id": "01_x", "cobertura_entidades": 0.5,
                  "scores_rerank": [0.9], "reranker_usado": "flashrank",
                  "groundedness": None, "contexto_chars": 120,
                  "expansao": {"entrada": 1, "expandidos": 0, "sem_pai": 1,
                               "chave_divergente": 0, "truncados": 0,
                               "duplicados": 0, "registro": 0}}]
    resultado = {"etapa": "etapa_teste", "data": "2026-10-08",
                 "registros": registros,
                 "resumo_expansao": avaliar.resumo_expansao(registros)}

    avaliar.resumir(resultado)

    saida = capsys.readouterr().out
    assert "DESATIVADA" in saida
