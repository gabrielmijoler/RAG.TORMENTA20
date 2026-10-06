"""Sonda read-only: rerank com query combinada vs original vs reformulada.

RERANK=flashrank (sem Cohere) e zero LLM (reformulações do traducoes_cache.json).
Roda exatamente `rag_core.recuperar()` — só a query entregue ao compressor muda;
candidatos (ensemble das duas formulações), limiar 0.35 e `_diversificar` são
idênticos nas três variantes.

Uso:
    .venv/bin/python probe_rerank_ab.py 2>&1 | tee log_probe_rerank_ab.txt
"""
import os

os.environ["RERANK"] = "flashrank"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

import json
import logging
from types import SimpleNamespace

import rag_core
from avaliar import carregar_goldenset

# Qdrant (httpx) loga cada busca em INFO — polui 1/3 do log da sonda.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class _BuscaCacheada:
    """`invoke` memoizado: os candidatos ficam idênticos entre as 3 variantes.

    O ensemble (denso + BM25) é determinístico para a mesma query; cachear
    corta 4 das 6 buscas Qdrant por query SEM mudar o que `recuperar()` vê.
    """

    def __init__(self, real):
        self._real, self._cache = real, {}

    def invoke(self, consulta: str):
        if consulta not in self._cache:
            self._cache[consulta] = self._real.invoke(consulta)
        return self._cache[consulta]


class _ForcarQuery:
    """Delega ao compressor real, mas entrega SEMPRE `query_fixa` ao rerank."""

    def __init__(self, real, query_fixa):
        self._real, self._q = real, query_fixa

    @property
    def top_n(self):
        return self._real.top_n

    @top_n.setter
    def top_n(self, valor):
        self._real.top_n = valor

    @property
    def ultimo_modo(self):
        return self._real.ultimo_modo

    @ultimo_modo.setter
    def ultimo_modo(self, valor):
        self._real.ultimo_modo = valor

    def compress_documents(self, docs, query, callbacks=None):
        return self._real.compress_documents(docs, self._q, callbacks=callbacks)


def _bloco(doc) -> str:
    return rag_core.normalizar(
        doc.page_content + " "
        + " ".join(str(v) for v in doc.metadata.values() if isinstance(v, str))
    )


def cobertura(top, esperadas) -> float:
    """Mesma fórmula de avaliar.py:437-451."""
    if not esperadas:
        return 0.0
    textos = [_bloco(d) for d in top]
    achados = {e for e in esperadas if any(e in t for t in textos)}
    return len(achados) / len(esperadas)


def pos_todas(top, esperadas):
    """1-based da primeira posição com TODAS as entidades; None fora do top-8."""
    for i, d in enumerate(top, 1):
        t = _bloco(d)
        if all(e in t for e in esperadas):
            return i
    return None


def main() -> None:
    with open("traducoes_cache.json", encoding="utf-8") as arquivo:
        cache = json.load(arquivo)
    casos = carregar_goldenset()
    retriever = rag_core.montar_retriever(
        rag_core.montar_chunks(verbose=False), verbose=False
    )
    real = retriever.base_compressor
    busca = _BuscaCacheada(retriever.base_retriever)

    linhas = []
    resumo = {v: {"soma": 0.0, "cheias": 0, "pos": []}
              for v in ("combinada", "original", "reformulada")}

    for n, caso in enumerate(casos, 1):
        consulta = caso["consulta"]
        reformulada = cache.get(consulta, consulta)
        sem_cache = consulta not in cache
        esperadas = [rag_core.normalizar(e) for e in caso["entidades"]]
        variantes = {
            "combinada": f"{reformulada} {consulta}",
            "original": consulta,
            "reformulada": reformulada,
        }
        linha = {"id": caso["id"], "sem_reformulacao_cache": sem_cache}
        for nome, q in variantes.items():
            falso = SimpleNamespace(
                base_retriever=busca,
                base_compressor=_ForcarQuery(real, q),
            )
            top = rag_core.recuperar(falso, reformulada, consulta)
            assert real.ultimo_modo == "flashrank", (caso["id"], real.ultimo_modo)
            cob = cobertura(top, esperadas)
            linha[nome] = round(cob, 3)
            linha[f"{nome}_pos"] = pos_todas(top, esperadas)
            resumo[nome]["soma"] += cob
            resumo[nome]["cheias"] += cob == 1.0
            if linha[f"{nome}_pos"]:
                resumo[nome]["pos"].append(linha[f"{nome}_pos"])
        linhas.append(linha)
        marca = " (sem cache de reformulação)" if sem_cache else ""
        print(f"{n:>2}/{len(casos)} {caso['id']:<26} comb={linha['combinada']:.0%} "
              f"orig={linha['original']:.0%} refor={linha['reformulada']:.0%}{marca}",
              flush=True)

    print("\nRESUMO (61 queries)")
    for nome, s in resumo.items():
        pos = sorted(s["pos"])
        print(f"  {nome:<12} cob_media={s['soma'] / len(linhas):.1%} "
              f"cob_100%={s['cheias']}/{len(linhas)} "
              f"pos_alvo_mediana={pos[len(pos) // 2] if pos else '-'}")

    regr = [l for l in linhas if l["original"] < l["combinada"]]
    print("\nREGRESSÕES (original < combinada): "
          + (", ".join(f"{l['id']} {l['combinada']:.0%}->{l['original']:.0%}"
                       for l in regr) or "nenhuma"))
    ganhos = sum(1 for l in linhas if l["original"] > l["combinada"])
    print(f"GANHOS (original > combinada): {ganhos}")

    with open("probe_rerank_ab.json", "w", encoding="utf-8") as arquivo:
        json.dump(linhas, arquivo, ensure_ascii=False, indent=1)
    print("detalhe: probe_rerank_ab.json")


if __name__ == "__main__":
    main()
