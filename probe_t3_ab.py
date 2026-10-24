"""Sonda T3: tabela A/B/C/D do rerank — flashrank vs cohere vs voyage vs auto.

Roda exatamente `rag_core.recuperar(decompor=True)` (mesmo caminho do mq8);
candidatos idênticos entre variantes (busca memoizada), reformulações do
traducoes_cache.json (53 corrigida) e latência medida SÓ no estágio de rerank
(`compress_documents`), com o pacing do rate limit FORA do cronômetro.

  A = flashrank (atual, 1 run — local, determinístico)
  B = cohere rerank-v3.5 (3 runs — BLOQUEADA nesta sessão: cota trial
      esgotada, "1000 API calls / month"; documentada como indisponível)
  C = voyage rerank-2 (3 runs — serviço externo)
  D = auto/cascata (3 runs — escala p/ Cohere se top-1 < 0.35; sem cota,
      a escalada falha e a cascata mantém FlashRank, como em produção)

Uso:
    PROBE_LIMITE=2 .venv/bin/python probe_t3_ab.py   # smoke (2 queries)
    .venv/bin/python probe_t3_ab.py 2>&1 | tee log_probe_t3_ab.txt
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
# Montagem do retriever; o compressor de cada variante vem de criar_reranker().
os.environ.setdefault("RERANK", "flashrank")

import json
import logging
import time
from collections import Counter
from types import SimpleNamespace

import rag_core
from avaliar import carregar_goldenset

# Qdrant (httpx) loga cada busca em INFO — polui o log da sonda.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ESPERA_429 = 61  # igual a avaliar.buscar
INTERVALO_COHERE = 6.1  # trial: 10 chamadas/min
INTERVALO_VOYAGE = 0.6  # corte conservador; 429 cai no retry
VARIANTES = [
    ("A_flashrank", "flashrank", 1),
    ("B_cohere", "cohere", 3),
    ("C_voyage", "voyage", 3),
    ("D_auto", "auto", 3),
]
MODOS_ESPERADOS = {
    "flashrank": {"flashrank"},
    "cohere": {"cohere"},
    "voyage": {"voyage"},
    "auto": {"flashrank", "cohere_escalado"},
}


class _Pacing:
    """Garante intervalo mínimo entre chamadas ao serviço externo.

    O sono acontece ANTES do cronômetro do rerank — latência reportada é só
    o tempo real da chamada, não a espera do rate limit.
    """

    def __init__(self, intervalo):
        self._intervalo, self._ultima = intervalo, 0.0

    def esperar(self):
        espera = self._intervalo - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        self._ultima = time.monotonic()


class _BuscaCacheada:
    """`invoke` memoizado: os candidatos ficam idênticos entre as variantes.

    Devolve cópia rasa da lista — `recuperar()` pode anexar a `consulta_real`
    sem poluir o cache das próximas queries/variantes.
    """

    def __init__(self, real):
        self._real, self._cache = real, {}

    def invoke(self, consulta: str):
        if consulta not in self._cache:
            self._cache[consulta] = self._real.invoke(consulta)
        return list(self._cache[consulta])


class _ComRelogio:
    """Delega ao cascata real e cronometra só `compress_documents`.

    Pacing do rate limit fora do cronômetro; expõe `top_n`/`ultimo_modo`
    (recuperar() muta e lê os dois).
    """

    def __init__(self, real, pacing=None):
        self._real, self._pacing = real, pacing
        self.ms, self.chamadas = 0.0, 0

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
        if self._pacing is not None:
            self._pacing.esperar()
        inicio = time.perf_counter()
        saida = self._real.compress_documents(docs, query, callbacks=callbacks)
        self.ms += (time.perf_counter() - inicio) * 1000
        self.chamadas += 1
        return saida


class _BuscaComRetry:
    """Conta retentativas de fallback (429/cota) para o resumo."""

    tentativas = 0


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
    """1-based da primeira posição com TODAS as entidades; None fora do top."""
    for i, d in enumerate(top, 1):
        t = _bloco(d)
        if all(e in t for e in esperadas):
            return i
    return None


def pos_ent(top, esperadas):
    """1-based da primeira posição de CADA entidade; None se ausente."""
    saida = {}
    for e in esperadas:
        saida[e] = next(
            (i for i, d in enumerate(top, 1) if e in _bloco(d)), None
        )
    return saida


def _detalhe_alvo(top, esperadas):
    """Ranking nomeado dos top-12 (tabela + entidades) p/ os casos 53 e 64."""
    return [
        {"pos": i, "tabela": d.metadata.get("Tabela"),
         "tem": [e for e in esperadas if e in _bloco(d)]}
        for i, d in enumerate(top, 1)
    ]


def _recuperar_com_retry(falso, comp, reformulada, consulta, esperados):
    """`recuperar()` com retentativa quando o rerank cai (429/cota).

    `recuperar()` captura a exceção do compressor e devolve
    `ensemble_fallback`; repetimos (igual a avaliar.buscar) até o modo
    esperado da variante — fallback persistente aborta o probe.
    """
    ultimo_modo = None
    for tentativa in range(1, 4):
        comp.ms, comp.chamadas = 0.0, 0
        top = rag_core.recuperar(falso, reformulada, consulta, decompor=True)
        ultimo_modo = comp.ultimo_modo
        if ultimo_modo in esperados:
            return top, ultimo_modo
        _BuscaComRetry.tentativas += 1
        print(f"    ⚠ modo {ultimo_modo!r} inesperado (tentativa "
              f"{tentativa}/3) — dormindo {ESPERA_429}s", flush=True)
        time.sleep(ESPERA_429)
    raise RuntimeError(
        f"fallback persistente: {consulta[:60]!r} -> {ultimo_modo!r}"
    )


def _p95(valores):
    if not valores:
        return 0.0
    ordenado = sorted(valores)
    return ordenado[min(len(ordenado) - 1, int(len(ordenado) * 0.95))]


def _resumo(linhas, cob_mq8):
    """Tabela A/B/C/D + regressões vs A + deltas vs A e vs mq8."""
    por_var = {}
    for nome, _tipo, _runs in VARIANTES:
        por_var[nome] = [l for l in linhas if l["variante"] == nome]
    # média por query (B/C/D têm 3 runs) — comparável com o 1 run de A
    medias = {}
    for nome, linhas_var in por_var.items():
        medias[nome] = {}
        for l in linhas_var:
            medias[nome].setdefault(l["id"], []).append(l["cob"])
        medias[nome] = {
            k: sum(v) / len(v) for k, v in medias[nome].items()
        }
    base = medias["A_flashrank"]
    print(f"\nTABELA A/B/C/D ({len(base)} queries; B/C/D = média de 3 runs)")
    print(f"  {'variante':<12} {'runs':>4} {'cob_media':>9} {'cob_100%':>8} "
          f"{'reg_vs_A':>8} {'pior_100%':>9} {'lat_med':>8} {'lat_p95':>8} "
          f"{'retries':>7}  modos")
    resumo = {}
    for nome, _tipo, runs in VARIANTES:
        linhas_var = por_var[nome]
        m = medias[nome]
        cob_media = sum(m.values()) / len(m)
        cheias = sum(1 for v in m.values() if v >= 1.0)
        regressoes = [k for k in m if m[k] < base[k]]
        pioraram = [k for k in m if base[k] >= 1.0 and m[k] < 1.0]
        lats = [l["lat_ms"] for l in linhas_var]
        modos = dict(Counter(l["modo"] for l in linhas_var))
        print(f"  {nome:<12} {runs:>4} {cob_media:>8.1%} {f'{cheias}/{len(m)}':>8} "
              f"{len(regressoes):>8} {len(pioraram):>9} "
              f"{sum(lats) / len(lats):>7.0f}ms {_p95(lats):>7.0f}ms "
              f"{_BuscaComRetry.tentativas:>7}  {modos}")
        # ganho vs A: geral, sem a 53 (ganho real) e só na 53 (efeito do cache)
        exc53 = [k for k in m if not k.startswith("53_")]
        resumo[nome] = {
            "runs": runs,
            "cob_media": round(cob_media, 4),
            "cob_100": cheias,
            "regressoes_vs_A": sorted(regressoes),
            "pioraram_de_100": sorted(pioraram),
            "delta_vs_A": round(cob_media - sum(base.values()) / len(base), 4),
            "delta_vs_A_sem_53": round(
                sum(m[k] for k in exc53) / len(exc53)
                - sum(base[k] for k in exc53) / len(exc53), 4),
            "delta_vs_A_somente_53": round(
                m["53_parceiro_grifo"] - base["53_parceiro_grifo"], 4),
            "lat_ms_media": round(sum(lats) / len(lats), 1),
            "lat_ms_p95": round(_p95(lats), 1),
            "modos": modos,
        }
    print("\nDELTA vs mq8 (produção; 53 corrigida aqui, corrompida lá)")
    for nome, _tipo, _runs in VARIANTES:
        m = medias[nome]
        exc53 = [k for k in m if not k.startswith("53_")]
        geral = sum(m[k] - cob_mq8[k] for k in m) / len(m)
        real = (sum(m[k] - cob_mq8[k] for k in exc53) / len(exc53)
                if cob_mq8 else 0.0)
        so53 = m["53_parceiro_grifo"] - cob_mq8.get(
            "53_parceiro_grifo", m["53_parceiro_grifo"])
        print(f"  {nome:<12} geral={geral:+.1%}  só-53={so53:+.1%}  "
              f"sem-53(=real)={real:+.1%}")
    if pioramos := {
        n: [f'{k} {base[k]:.0%}->{medias[n][k]:.0%}'
            for k in medias[n] if base[k] >= 1.0 and medias[n][k] < 1.0]
        for n in medias
    }:
        print("\nPIORARAM DE 100% (vs A):")
        for n, itens in pioramos.items():
            if itens:
                print(f"  {n:<12} " + ", ".join(itens))
    return resumo


def _casos_obrigatorios(linhas, medias):
    """Rank do alvo nos casos 53 (Grifo) e 64 (Condições#Caído)."""
    print("\nCASOS OBRIGATÓRIOS (rank 1-based; entidade no bloco do doc)")
    for caso in ("53_parceiro_grifo", "64_magia_voo_area_caido"):
        print(f"  {caso}")
        for nome, _tipo, _runs in VARIANTES:
            rodadas = [l for l in linhas
                       if l["variante"] == nome and l["id"] == caso]
            r0 = rodadas[0]
            print(f"    {nome:<12} cob={medias[nome][caso]:.0%} "
                  f"pos_ent={r0['pos_ent']} pos_todas={r0['pos']}")
            for item in (r0.get("top") or [])[:8]:
                marca = " <-" if item["tem"] else ""
                print(f"      [{item['pos']}] {item['tabela']!s:<22}"
                      f"{item['tem']}{marca}")


def main() -> None:
    limite = int(os.environ.get("PROBE_LIMITE", "0"))
    with open("traducoes_cache.json", encoding="utf-8") as arquivo:
        cache = json.load(arquivo)
    casos = carregar_goldenset()
    if limite:
        casos = casos[:limite]
        print(f"⚠️  SMOKE: só {limite} queries")
    cob_mq8 = {}
    try:
        with open("avaliacao_fr_l12_multiquery8.json", encoding="utf-8") as f:
            cob_mq8 = {r["id"]: r["cobertura_entidades"]
                       for r in json.load(f)["registros"]}
    except (OSError, KeyError):
        pass  # comparação com mq8 é opcional (smoke)

    chunks = rag_core.montar_chunks(verbose=False)
    retriever = rag_core.montar_retriever(chunks, verbose=False)
    busca = _BuscaCacheada(retriever.base_retriever)

    linhas = []
    for nome, tipo, runs in VARIANTES:
        cascata = rag_core.criar_reranker(tipo)
        intervalo = (INTERVALO_COHERE if tipo == "cohere"
                     else INTERVALO_VOYAGE if tipo == "voyage" else 0.0)
        # auto: escaladas são raras (0 no mq8) — sem pacing proativo; se um
        # 429 derrubar a escalada, a cascata mantém flashrank (comportamento
        # de produção) e o modo segue "flashrank".
        pacing = _Pacing(intervalo) if tipo in ("cohere", "voyage") else None
        for run in range(1, runs + 1):
            for caso in casos:
                consulta = caso["consulta"]
                reformulada = cache.get(consulta, consulta)
                esperadas = [rag_core.normalizar(e)
                             for e in caso["entidades"]]
                comp = _ComRelogio(cascata, pacing)
                falso = SimpleNamespace(
                    base_retriever=busca, base_compressor=comp)
                top, modo = _recuperar_com_retry(
                    falso, comp, reformulada, consulta, MODOS_ESPERADOS[tipo])
                cob = cobertura(top, esperadas)
                linha = {
                    "variante": nome, "run": run, "id": caso["id"],
                    "cob": round(cob, 3), "modo": modo,
                    "lat_ms": round(comp.ms, 1),
                    "pos": pos_todas(top, esperadas),
                    "pos_ent": pos_ent(top, esperadas),
                }
                if caso["id"].startswith(("53_", "64_")):
                    linha["top"] = _detalhe_alvo(top, esperadas)
                linhas.append(linha)
                print(f"{nome} r{run} {caso['id']:<26} cob={cob:.0%} "
                      f"modo={modo} lat={comp.ms:.0f}ms", flush=True)

    resumo = _resumo(linhas, cob_mq8)
    medias = {}
    for linha in linhas:
        medias.setdefault(linha["variante"], {}).setdefault(
            linha["id"], []).append(linha["cob"])
    medias = {v: {k: sum(x) / len(x) for k, x in d.items()}
              for v, d in medias.items()}
    if not limite:
        _casos_obrigatorios(linhas, medias)
    with open("probe_t3_ab.json", "w", encoding="utf-8") as arquivo:
        json.dump({"resumo": resumo, "linhas": linhas}, arquivo,
                  ensure_ascii=False, indent=1)
    print("\ndetalhe: probe_t3_ab.json")


if __name__ == "__main__":
    main()
