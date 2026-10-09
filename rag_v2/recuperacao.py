"""Recuperação por necessidade (v2).

Mesma pilha da v1 (ensemble Qdrant+BM25, CascataReranker, `_diversificar`),
com três diferenças guiadas pela leitura:
1. candidatos extras por necessidade: o registro ligado entra DIRETO (sem
   depender da busca — o caso 53 tinha o Grifo no corpus e o rerank o
   enterrava) e a necessidade de tabela busca pela própria descrição;
2. um ÚNICO rerank da união, com a pergunta ORIGINAL (o FlashRank em inglês
   piora com a query combinada; reranquear por necessidade multiplicaria o
   custo, que já é ~11 s por chamada);
3. vagas garantidas: cada necessidade obrigatória ganha vaga antes do
   preenchimento por score, mesmo abaixo do limiar; o preenchimento segue o
   limiar e o 1-chunk-por-registro da v1, até o orçamento `leitura.k`.
"""

from collections import defaultdict

from langchain_core.documents import Document

import rag_core

from .tipos import Leitura, Necessidade

# Vagas de uma necessidade de tabela ("poderes de Bárbaro"): valor inicial.
VAGAS_POR_TABELA = 3


def indexar_registros(chunks: list[Document]) -> dict[tuple[str, str], list[Document]]:
    """(Tabela, Nome) -> chunks do registro: a busca direta do registro ligado."""
    indice: dict[tuple[str, str], list[Document]] = defaultdict(list)
    for doc in chunks:
        indice[(doc.metadata.get("Tabela"), doc.metadata.get("Nome"))].append(doc)
    return dict(indice)


def _registro(doc: Document) -> tuple:
    return (doc.metadata.get("Tabela"), doc.metadata.get("Nome"))


def _atende(doc: Document, necessidade: Necessidade) -> bool:
    if doc.metadata.get("Tabela") != necessidade.tabela_alvo:
        return False
    return necessidade.registro is None or doc.metadata.get("Nome") == necessidade.registro


def _limiar_efetivo(limiar: float | None, compressor) -> float | None:
    """Mesma precedência da v1: argumento > LIMIAR_RELEVANCIA > padrão do reranker."""
    if limiar is not None:
        return limiar
    efeito = rag_core.limiar_relevancia()
    if efeito is None:
        efeito = rag_core.limiar_padrao(getattr(compressor, "ultimo_modo", None))
    return efeito


def recuperar_v2(retriever, leitura: Leitura, registros: dict, consulta_busca: str,
                 consulta_original: str, limiar: float | None = None
                 ) -> tuple[list[Document], dict]:
    """Devolve (documentos do contexto, telemetria para /entendi e sinais)."""
    busca = retriever.base_retriever
    compressor = retriever.base_compressor
    candidatos: list[Document] = []
    vistos: set[str] = set()

    def juntar(docs):
        for doc in docs:
            if doc.page_content not in vistos:
                vistos.add(doc.page_content)
                candidatos.append(doc)

    juntar(busca.invoke(consulta_busca))
    if consulta_original and consulta_original != consulta_busca:
        juntar(busca.invoke(consulta_original))
    for nec in leitura.necessidades:
        if nec.registro is not None:
            juntar(registros.get((nec.tabela_alvo, nec.registro), []))
        else:
            juntar(d for d in busca.invoke(nec.descricao)
                   if d.metadata.get("Tabela") == nec.tabela_alvo)

    top_n = compressor.top_n
    compressor.top_n = len(candidatos)
    try:
        ranked = list(compressor.compress_documents(candidatos, consulta_original))
        com_rerank = True
    except Exception as erro:  # noqa: BLE001 — como na v1: rerank fora não derruba a busca
        print(f"⚠️  rerank indisponível ({type(erro).__name__}) — seguindo na ordem da busca")
        ranked, com_rerank = list(candidatos), False
        compressor.ultimo_modo = "ensemble_fallback"
    finally:
        compressor.top_n = top_n
    ranked = rag_core._expandir_pais(rag_core._filtrar_fragmentos_preco(ranked))

    garantidos: list[Document] = []
    escolhidos: set = set()
    for nec in (n for n in leitura.necessidades if n.obrigatoria):
        vagas = 1 if nec.registro is not None else VAGAS_POR_TABELA
        vagas -= sum(1 for d in garantidos if _atende(d, nec))
        for doc in ranked:
            if vagas <= 0:
                break
            if _atende(doc, nec) and _registro(doc) not in escolhidos:
                garantidos.append(doc)
                escolhidos.add(_registro(doc))
                vagas -= 1

    efeito = _limiar_efetivo(limiar, compressor) if com_rerank else None
    preenchimento = [d for d in rag_core._aplicar_limiar(ranked, efeito)
                     if _registro(d) not in escolhidos]
    k = max(leitura.k, len(garantidos))
    final = garantidos + rag_core._diversificar(preenchimento, k - len(garantidos))
    final.sort(key=lambda d: d.metadata.get("relevance_score") or 0, reverse=True)

    telemetria = {
        "candidatos": len(candidatos),
        "garantidos": len(garantidos),
        "k": k,
        "reranker": getattr(compressor, "ultimo_modo", None),
        "necessidades": [{"descricao": n.descricao, "obrigatoria": n.obrigatoria,
                          "atendida": any(_atende(d, n) for d in final)}
                         for n in leitura.necessidades],
    }
    return final, telemetria
