"""Suite de avaliação do RAG de Tormenta 20.

Mede 3 dimensões sobre as MESMAS queries, usando o mesmo pipeline que
`index.py` (chunks, retriever e prompts vêm do rag_core):

  1. Cobertura de entidades — as entidades esperadas aparecem no top-8?
  2. Fidelidade à base      — % das citações da resposta que estão no
                              contexto realmente recuperado (alucinação).
  3. Qualidade do rerank    — faixa de relevância do top-8.

Uso:
    ./.venv/bin/python avaliar.py --etapa baseline
    ./.venv/bin/python avaliar.py --etapa depois
    ./.venv/bin/python avaliar.py --etapa baseline --continuar   # retoma o parcial
    ./.venv/bin/python avaliar.py --so-recuperacao      # sem chamar o LLM final
    ./.venv/bin/python avaliar.py --etapa hyde --estrategia hyde --juiz
    ./.venv/bin/python avaliar.py --etapa base_lim07 --limiar 0.70 --juiz

Dataset ativo em goldenset.jsonl (61 casos com resposta_esperada); as 18
perguntas originais ficam em CONSULTAS como fallback. A reformulação da
pergunta é cacheada em traducoes_cache.json para que rodadas A/B usem
EXATAMENTE as mesmas queries (sem variação do LLM).
"""

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime

# Proteção de CPU (igual rag_core): numpy (via langchain_community) carrega
# ANTES do rag_core aqui — as variáveis precisam valer desde o primeiro import.
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.prompts import ChatPromptTemplate
from qdrant_client import QdrantClient

import rag_core
from rag_core import (
    MODELOS_GRATUITOS,
    PROMPT_TRADUCAO,
    SYSTEM_PROMPT,
    citacoes_em,
    e_cota_esgotada,
    e_modelo_indisponivel,
    e_transitorio,
    groundedness,
    normalizar,
    trocar_modelo,
)

ARQUIVO_CACHE = "traducoes_cache.json"

# Golden dataset em JSONL (uma pergunta por linha): id, consulta, entidades e
# resposta_esperada (validada contra o corpus). Arquivo ausente cai no
# CONSULTAS embarcado abaixo — compatibilidade com o pipeline antigo.
GOLDENSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goldenset.jsonl")
CAMPOS_OBRIGATORIOS = ("id", "consulta", "entidades", "resposta_esperada")

# Cache do LLM-as-Judge: mesma (pergunta, contexto, resposta) => mesmo
# veredito pago uma única vez, independente de quantas estratégias rodarem.
ARQUIVO_CACHE_JUIZ = "juiz_cache.json"

# O pacing protege o rerank Cohere (chave Trial: 10 chamadas por minuto; cada
# query gasta 1) e também a cota diária dos LLMs gratuitos.
INTERVALO_QUERY = 13
ESPERA_429 = 61

# ---------------------------------------------------------------------------
# Dataset reserva: as 18 perguntas originais, mantidas embarcadas como
# fallback quando goldenset.jsonl nao existir. O dataset ativo (61 casos,
# com resposta_esperada) vive em goldenset.jsonl (ver carregar_goldenset).
# As `entidades` sao trechos que PRECISAM aparecer no top-8 (corpo do chunk
# ou metadados) — todas verificadas contra o corpus.
# ---------------------------------------------------------------------------
CONSULTAS = [
    {"id": "01_condicao_caido",
     "consulta": "Quais as penalidades da condição Caído em Tormenta 20?",
     "entidades": ["caído", "defesa", "deslocamento"]},
    {"id": "02_condicao_agarrado",
     "consulta": "Como funciona a condição Agarrado durante o combate?",
     "entidades": ["agarrado", "desprevenido", "ataque"]},
    {"id": "03_pericia_furtividade",
     "consulta": "O que a perícia Furtividade faz e quando é usada?",
     "entidades": ["furtividade", "perícia"]},
    {"id": "04_custo_circulo",
     "consulta": "Quanto custa aprender uma magia de 3º círculo pelo método do Escriba Arcano?",
     "entidades": ["escriba arcano", "círculo", "magia"]},
    {"id": "05_curar_ferimentos",
     "consulta": "O que faz a magia Curar Ferimentos?",
     "entidades": ["curar ferimentos", "cura"]},
    {"id": "06_cavaleiro_proficiencias",
     "consulta": "Quais perícias e proficiências a classe Cavaleiro possui?",
     "entidades": ["cavaleiro", "proficiência"]},
    {"id": "07_espada_longa",
     "consulta": "Qual o preço e o dano de uma Espada Longa?",
     "entidades": ["espada longa", "dano", "preço"]},
    {"id": "08_basilisco",
     "consulta": "Qual o ND, a defesa e o deslocamento de um Basilisco?",
     "entidades": ["basilisco", "defesa"]},
    {"id": "09_hyninn",
     "consulta": "Quem é o deus Hyninn e qual é seu símbolo sagrado?",
     "entidades": ["hyninn", "símbolo sagrado"]},
    {"id": "10_ladrao_de_tumulos",
     "consulta": "O que a origem Ladrão de Túmulos oferece como benefício?",
     "entidades": ["ladrão de túmulos", "benefício"]},
    {"id": "11_ataque_vs_defesa",
     "consulta": "Como é resolvido um teste de ataque contra a Defesa do alvo?",
     "entidades": ["defesa", "ataque", "d20"]},
    {"id": "12_dificuldade_teste",
     "consulta": "Como funcionam os graus de dificuldade de um teste?",
     "entidades": ["dificuldade", "sucesso"]},
    {"id": "13_tamanho_criaturas",
     "consulta": "Quais são os tamanhos de criatura e qual espaço cada um ocupa?",
     "entidades": ["tamanho", "espaço", "enorme"]},
    {"id": "14_poder_psicopompo",
     "consulta": "O que concede o poder Dom do Psicopompo?",
     "entidades": ["psicopompo", "morte"]},
    {"id": "15_xerife_azgher",
     "consulta": "Como obtenho a distinção Xerife de Azgher?",
     "entidades": ["xerife de azgher", "azgher"]},
    {"id": "16_anao_habilidades",
     "consulta": "Quais as habilidades raciais do Anão e qual seu deslocamento?",
     "entidades": ["anão", "visão no escuro", "deslocamento"]},
    {"id": "17_cavalo_deslocamento",
     "consulta": "Qual o deslocamento de um Cavalo e quanto ele custa?",
     "entidades": ["cavalo", "deslocamento"]},
    {"id": "18_bomba_alquimica",
     "consulta": "Quais os efeitos e o preço de uma Bomba alquímica?",
     "entidades": ["bomba", "impacto", "preço"]},
]


def carregar_cache() -> dict:
    if os.path.exists(ARQUIVO_CACHE):
        with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_cache(cache: dict) -> None:
    with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def carregar_goldenset(caminho: str | None = None) -> list[dict]:
    """Le o golden dataset em JSONL e valida estrutura antes de usar.

    Campos obrigatorios por linha: id, consulta, entidades, resposta_esperada.
    Linha invalida (JSON quebrado, campo faltando, id repetido) derruba a
    carga com o numero da linha — dataset corrompido silenciosamente geraria
    metricas de mentira. Sem arquivo, devolve o CONSULTAS embarcado.
    """
    caminho = caminho or GOLDENSET
    if not os.path.exists(caminho):
        return CONSULTAS
    casos: list[dict] = []
    vistos: set[str] = set()
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if not linha.strip():
                continue
            try:
                caso = json.loads(linha)
            except ValueError as e:
                raise ValueError(f"{caminho}: linha {n} nao e JSON valido") from e
            faltando = [c for c in CAMPOS_OBRIGATORIOS if not caso.get(c)]
            if faltando:
                raise ValueError(f"{caminho}: linha {n} sem campo obrigatorio {faltando}")
            if caso["id"] in vistos:
                raise ValueError(f"{caminho}: id duplicado {caso['id']!r} (linha {n})")
            vistos.add(caso["id"])
            casos.append(caso)
    return casos


# ---------------------------------------------------------------------------
# LLM-as-Judge (Passo 2): um LLM externo avalia retrieval/resposta com
# score numerico + diagnostico True/False, substituindo validacao manual.
# ---------------------------------------------------------------------------
PROMPT_JUIZ = ChatPromptTemplate.from_messages([
    ("system",
     ("Você é um JUIZ DE QUALIDADE de sistemas RAG especializado em Tormenta 20. "
     "Avalie se o CONTEXTO recuperado pelo sistema é suficiente e pertinente para "
     "responder à PERGUNTA do usuário (e, quando houver, se a RESPOSTA respeita o "
     "contexto sem alucinar).\n\n"
     "Critérios:\n"
     "- score 9-10: contexto responde integralmente, entidades certas na base;\n"
     "- score 6-8: contexto cobre o essencial, com lacunas menores;\n"
     "- score 3-5: contexto só tangencia a pergunta;\n"
     "- score 0-2: contexto não serve ou é de outro assunto.\n"
     "- aprovado = true somente se score >= 6.\n\n"
     "Responda APENAS com JSON válido, sem cercas de código:\n"
     '{{"score": <0-10>, "aprovado": <true|false>, "justificativa": "<1 frase em pt-BR>"}}')),
    ("human",
     ("PERGUNTA:\n{pergunta}\n\nCONTEXTO RECUPERADO:\n{contexto}\n\n"
      "RESPOSTA DO SISTEMA (se houver):\n{resposta}")),
])


def parsear_veredito(texto: str) -> dict:
    """Extrai e valida o JSON do juiz, tolerando cerca de código e preâmbulo.

    Saída fora do contrato (sem JSON, score fora de 0-10, campo `aprovado`
    ausente) levanta ValueError; `aprovado` de tipo errado levanta TypeError.
    O chamador tenta outro modelo em vez de registrar métrica fabricada.
    """
    t = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(),
               flags=re.MULTILINE).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("sem JSON no veredito do juiz")
    obj = json.loads(t[i:j + 1])
    score = obj.get("score")
    aprovado = obj.get("aprovado")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 10:
        raise ValueError(f"score invalido: {score!r}")
    if "aprovado" not in obj:
        raise ValueError("veredito sem campo 'aprovado'")
    if not isinstance(aprovado, bool):
        raise TypeError(f"aprovado invalido: {aprovado!r}")
    return {
        "score": float(score),
        "aprovado": aprovado,
        "justificativa": str(obj.get("justificativa", ""))[:300],
    }


def carregar_cache_juiz(caminho: str | None = None) -> dict:
    caminho = caminho or ARQUIVO_CACHE_JUIZ
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}
    return {}


def salvar_cache_juiz(cache: dict, caminho: str | None = None) -> None:
    caminho = caminho or ARQUIVO_CACHE_JUIZ
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _chave_juiz(pergunta: str, top: list, resposta: str | None) -> str:
    """Chave de conteúdo: contexto identico => veredito identico (cache seguro)."""
    base = json.dumps({
        "pergunta": pergunta,
        "contexto": [d.page_content for d in top],
        "resposta": resposta or "",
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def juizar(llm, pergunta: str, top: list, resposta: str | None = None,
           cache: dict | None = None) -> dict | None:
    """LLM-as-Judge: score 0-10 + True/False sobre o `top` recuperado.

    Cacheia por conteúdo (pergunta+contexto+resposta). Resposta inválida do
    juiz (JSON fora do contrato) pula direto para o próximo modelo; falha
    total devolve None (o registro fica sem juiz em vez de abortar a rodada).
    """
    cache = cache if cache is not None else {}
    chave = _chave_juiz(pergunta, top, resposta)
    cached = cache.get(chave)
    if isinstance(cached, dict) and "score" in cached and "aprovado" in cached:
        return cached

    contexto = "\n---\n".join(d.page_content for d in top)[:6000]
    cadeia = PROMPT_JUIZ | llm
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                texto = cadeia.invoke({
                    "pergunta": pergunta,
                    "contexto": contexto,
                    "resposta": resposta or "(avaliação só de recuperação)",
                }).content
                veredito = parsear_veredito(texto)
            except Exception as e:  # noqa: BLE001 — cascata de LLM: qualquer erro cai no próximo modelo
                if e_transitorio(e):
                    time.sleep(5)
                    continue
                break  # JSON inválido/cota/modelo: próximo modelo
            cache[chave] = veredito
            return veredito
    return None


def resumo_juiz(registros: list) -> dict:
    """Média de score e taxa de aprovação dos vereditos presentes."""
    vereditos = [r["juiz"] for r in registros if r.get("juiz")]
    if not vereditos:
        return {"n": 0, "score_medio": None, "taxa_aprovacao": None}
    return {
        "n": len(vereditos),
        "score_medio": round(sum(v["score"] for v in vereditos) / len(vereditos), 2),
        "taxa_aprovacao": round(
            sum(1 for v in vereditos if v["aprovado"]) / len(vereditos), 3),
    }


def reformular(llm, consulta: str, cache: dict) -> str:
    """Reformula para termos do sistema, cacheando para manter o A/B estável.

    Entrada inválida (preâmbulo/cotação do LLM) nunca entra no cache: lida
    antiga ruim é regenerada na hora; se todos os modelos falharem, a busca
    recebe a pergunta original.
    """
    if consulta in cache and rag_core.reformulacao_valida(cache[consulta]):
        return cache[consulta]

    chain = PROMPT_TRADUCAO | llm
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                texto = chain.invoke({"queixa": consulta}).content.strip()
                if rag_core.e_recusa(texto) or not rag_core.reformulacao_valida(texto):
                    raise rag_core.RecusaTraducao(texto[:60])
                cache[consulta] = texto
                salvar_cache(cache)
                return texto
            except Exception as e:
                if e_cota_esgotada(e):
                    break
                elif e_transitorio(e):
                    time.sleep(ESPERA_429)
                else:
                    break
    cache[consulta] = consulta
    salvar_cache(cache)
    return consulta


def responder(llm, rag_chain, pergunta: str) -> str:
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                with get_openai_callback():
                    return rag_chain.invoke({"input": pergunta})["answer"]
            except Exception as e:
                if e_cota_esgotada(e):
                    break
                elif e_transitorio(e):
                    time.sleep(ESPERA_429)
                elif e_modelo_indisponivel(e):
                    break
                else:
                    raise
    return ""


def buscar(retriever, consulta: str, consulta_real: str | None = None,
           limiar: float | None = None):
    """Top-8: candidatos das duas formulações, rerank com a query original."""
    for i in range(4):
        try:
            return rag_core.recuperar(retriever, consulta, consulta_real,
                                      limiar=limiar)
        except Exception as e:
            if e_transitorio(e) and i < 3:
                print(f"  429 no rerank, aguardando {ESPERA_429}s...")
                time.sleep(ESPERA_429)
            else:
                raise
    return []


def _hyde_doc_do(retriever, consulta: str) -> str | None:
    """Documento hipotético gerado para `consulta` (observabilidade do HyDE)."""
    try:
        densa = retriever.base_retriever.retrievers[0]
    except AttributeError:
        return None
    if isinstance(densa, rag_core.RecuperadorDensoHyDE):
        return densa.cache.get(consulta)
    return None


def avaliar(
    llm,
    so_recuperacao: bool = False,
    saida: str | None = None,
    continuar: bool = False,
    estrategia: str = "baseline",
    limiar: float | None = None,
    juiz: bool = False,
) -> dict:
    """Roda as CONSULTAS e devolve o resultado.

    Quando `saida` é informado, grava o JSON a cada query: uma falha de rede na
    última consulta não joga fora o trabalho das anteriores. `continuar` relê o
    `saida` parcial e pula as queries ja registradas (retomada em vez de zero).

    Estratégias (Passo 2): `estrategia="hyde"` usa busca densa por documento
    hipotético; `limiar` corta pelo score do rerank (None = como antes);
    `juiz=True` roda o LLM-as-Judge sobre cada recuperação (cacheado em
    juiz_cache.json).
    """
    chunks = rag_core.montar_chunks()
    retriever = rag_core.montar_retriever(
        chunks,
        estrategia="hyde" if estrategia == "hyde" else "hibrida",
        llm=llm,
    )

    rag_chain = None
    if not so_recuperacao:
        rag_chain = rag_core.montar_rag_chain(retriever, SYSTEM_PROMPT, llm)

    cache = carregar_cache()
    cache_juiz = carregar_cache_juiz() if juiz else {}
    casos = carregar_goldenset()
    registros = carregar_parcial(saida) if continuar else []
    feitos = {r.get("id") for r in registros}
    pendentes = [c for c in casos if c["id"] not in feitos]
    if feitos:
        print(f"↻ retomando {saida}: {len(registros)} queries prontas, {len(pendentes)} restantes")

    for caso in pendentes:
        print(f"\n[{caso['id']}] {caso['consulta'][:70]}...")
        reformulada = reformular(llm, caso["consulta"], cache)
        print(f"  reformulação: {reformulada[:95]}")

        top = buscar(retriever, reformulada, caso["consulta"], limiar=limiar)

        # --- 1. cobertura de entidades ---
        esperadas = {normalizar(e) for e in caso["entidades"]}
        encontrados_meta, encontrados_texto = set(), set()
        for doc in top:
            meta = normalizar(" ".join(
                str(v) for v in doc.metadata.values() if isinstance(v, str)
            ))
            corpo = normalizar(doc.page_content)
            for ent in esperadas:
                if ent in meta:
                    encontrados_meta.add(ent)
                if ent in corpo:
                    encontrados_texto.add(ent)
            unidos = encontrados_meta | encontrados_texto
        hit = len(unidos & esperadas) / len(esperadas) if esperadas else 0.0

        scores = [d.metadata.get("relevance_score") for d in top
                  if d.metadata.get("relevance_score") is not None]

        # O que o CascataReranker fez NESTA query (flashrank, cohere_escalado,
        # cohere, desligado ou ensemble_fallback) — recuperar() garante que o
        # atributo esteja atualizado (inclusive no caminho de exceção).
        compressor = getattr(retriever, "base_compressor", None)

        registro = {
            "id": caso["id"],
            "consulta": caso["consulta"],
            "reformulacao": reformulada,
            "entidades_esperadas": sorted(esperadas),
            "entidades_no_metadata": sorted(encontrados_meta),
            "entidades_no_texto": sorted(encontrados_texto),
            "cobertura_entidades": round(hit, 3),
            "reranker_usado": (getattr(compressor, "ultimo_modo", None)
                               or "ensemble_fallback"),
            # float(): FlashRank devolve numpy.float32 (JSON não serializa)
            "scores_rerank": [round(float(s), 4) for s in scores],
            "top8": [{
                "score": round(float(d.metadata.get("relevance_score", 0)), 4),
                "fonte": d.metadata.get("Fonte") or d.metadata.get("Tabela", ""),
                "tipo": d.metadata.get("Tipo", ""),
                "trecho": d.page_content[:220],
            } for d in top],
        }

        # --- 2. fidelidade à base (citações Nome [Fonte]) ---
        contexto = "\n".join(d.page_content for d in top)
        if not so_recuperacao:
            resposta = responder(llm, rag_chain, reformulada)
            c_resp = citacoes_em(resposta)
            c_ctx = citacoes_em(contexto)
            grounding = groundedness(resposta, contexto)
            registro.update({
                "resposta": resposta,
                "citacoes_na_resposta": sorted(c_resp),
                "citacoes_no_contexto": sorted(c_ctx),
                "citacoes_fundamentadas": sorted(c_resp & c_ctx),
                "citacoes_fora_do_contexto": sorted(c_resp - c_ctx),
                "groundedness": round(grounding, 3) if grounding is not None else None,
            })
            print(f"  cobertura entidades: {hit:.0%} | groundedness: "
                  f"{'n/a' if grounding is None else f'{grounding:.0%}'} "
                  f"| citações fora: {len(c_resp - c_ctx)}")

        if estrategia == "hyde":
            registro["hyde_doc"] = _hyde_doc_do(retriever, reformulada)

        if juiz:
            registro["juiz"] = juizar(
                llm, caso["consulta"], top,
                resposta=registro.get("resposta"),
                cache=cache_juiz,
            )
            salvar_cache_juiz(cache_juiz)
            veredito = registro["juiz"]
            if veredito is None:
                print("  juiz: indisponível (todos os modelos falharam)")
            else:
                estado = "aprovado" if veredito["aprovado"] else "reprovado"
                print(f"  juiz: {veredito['score']:.0f}/10 {estado}")

        registros.append(registro)
        if saida:
            # rascunho parcial — main() regrava completo no final
            gravar(saida, {"registros": registros})
        time.sleep(INTERVALO_QUERY)

    return {
        "etapa": None,
        "data": datetime.now().isoformat(timespec="seconds"),
        "colecao": rag_core.COLECAO,
        "pontos_colecao": _pontos_colecao(),
        "estrategia": estrategia,
        "reranker": rag_core.reranker_ativo(),
        "limiar": limiar,
        "n_consultas": len(registros),
        "resumo_juiz": resumo_juiz(registros) if juiz else None,
        "registros": registros,
    }


def gravar(saida: str, resultado: dict) -> None:
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


def carregar_parcial(saida: str | None) -> list:
    """Registros ja gravados no `saida` (base para --continuar)."""
    if not saida or not os.path.exists(saida):
        return []
    try:
        with open(saida, encoding="utf-8") as f:
            dados = json.load(f)
    except (ValueError, OSError):
        return []
    registros = dados.get("registros", [])
    return [r for r in registros if r.get("id")]


def _pontos_colecao() -> int:
    conexao = rag_core.escolher_conexao_qdrant()
    cliente = QdrantClient(**conexao)
    try:
        return cliente.get_collection(rag_core.COLECAO).points_count
    finally:
        if hasattr(cliente, "close"):
            cliente.close()


def resumir(resultado: dict) -> None:
    regs = resultado["registros"]
    print("\n" + "=" * 78)
    print(f"RESUMO — {resultado['etapa']} — {resultado['data']}")
    print("=" * 78)
    print(f"{'id':<22} {'cob.Ent':>8} {'ground':>8} {'score max':>10} {'cit fora':>9}")
    print("-" * 78)
    for r in regs:
        g = r.get("groundedness")
        fora = len(r.get("citacoes_fora_do_contexto", []))
        print(f"{r['id']:<22} {r['cobertura_entidades']:>7.0%} "
              f"{'n/a' if g is None else f'{g:>7.0%}'} "
              f"{max(r['scores_rerank'], default=0):>10.4f} {fora:>9}")

    cob = sum(r["cobertura_entidades"] for r in regs) / len(regs)
    print("-" * 78)
    print(f"{'MÉDIA':<22} {cob:>7.0%}", end="")
    gs = [r["groundedness"] for r in regs if r.get("groundedness") is not None]
    print(f" {'n/a' if not gs else format(sum(gs) / len(gs), '>7.0%')}", end="")
    todos = [s for r in regs for s in r["scores_rerank"]]
    print(f" {max(todos, default=0):>10.4f}")

    rj = resultado.get("resumo_juiz")
    if rj:
        if rj["n"]:
            print(f"JUIZ: {rj['score_medio']:.2f}/10 de média | "
                  f"{rj['taxa_aprovacao']:.0%} aprovado | {rj['n']} vereditos")
        else:
            print("JUIZ: nenhum veredito registrado")
    modos = Counter(r.get("reranker_usado") or "?" for r in regs)
    print("RERANK (modo por query): "
          + " | ".join(f"{m} {n}" for m, n in modos.most_common()))
    print("=" * 78)


def criar_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Avalia o RAG de Tormenta 20")
    ap.add_argument("--etapa", default="baseline", help="nome do arquivo de saída")
    ap.add_argument("--so-recuperacao", action="store_true",
                    help="não chama o LLM final (só métricas de recuperação)")
    ap.add_argument("--continuar", action="store_true",
                    help="retoma o arquivo de saída em vez de começar do zero")
    ap.add_argument("--estrategia", choices=("baseline", "hyde"),
                    default="baseline",
                    help="estratégia de recuperação (Passo 2): baseline ou hyde")
    ap.add_argument("--limiar", type=float, default=None,
                    help="corta candidatos com score de rerank abaixo deste "
                         "valor (ex.: 0.70); sem flag = sem corte")
    ap.add_argument("--juiz", action="store_true",
                    help="LLM-as-Judge por query: score 0-10 + aprovação "
                         "(cache em juiz_cache.json)")
    return ap


def main():
    args = criar_parser().parse_args()

    llm = rag_core.criar_llm()
    saida = f"avaliacao_{args.etapa}.json"
    resultado = avaliar(llm, so_recuperacao=args.so_recuperacao, saida=saida,
                        continuar=args.continuar, estrategia=args.estrategia,
                        limiar=args.limiar, juiz=args.juiz)
    resultado["etapa"] = args.etapa
    gravar(saida, resultado)
    print(f"\nResultado salvo em {saida}")

    resumir(resultado)


if __name__ == "__main__":
    main()
