"""Suite de avaliação do RAG de Tormenta 20.

Mede 3 dimensões sobre as MESMAS queries, usando o mesmo pipeline que
`meu_primeiro_rag.py` (chunks, retriever e prompts vêm do rag_core):

  1. Cobertura de entidades — as entidades esperadas aparecem no top-8?
  2. Fidelidade à base      — % das citações da resposta que estão no
                              contexto realmente recuperado (alucinação).
  3. Qualidade do rerank    — faixa de relevância do top-8.

Uso:
    ./.venv/bin/python avaliar.py --etapa baseline
    ./.venv/bin/python avaliar.py --etapa depois
    ./.venv/bin/python avaliar.py --so-recuperacao      # sem chamar o LLM final

A reformulação da pergunta é cacheada em traducoes_cache.json para que a
rodada "antes" e "depois" use EXATAMENTE as mesmas queries (sem variação do LLM).
"""

import argparse
import json
import os
import re
import time
import unicodedata
from datetime import datetime

from langchain_community.callbacks.manager import get_openai_callback
from qdrant_client import QdrantClient

import rag_core
from rag_core import (
    MODELOS_GRATUITOS,
    PROMPT_TRADUCAO,
    SYSTEM_PROMPT,
    e_cota_esgotada,
    e_modelo_indisponivel,
    e_transitorio,
    trocar_modelo,
)

ARQUIVO_CACHE = "traducoes_cache.json"

# O pacing protege o rerank Cohere (chave Trial: 10 chamadas por minuto; cada
# query gasta 1) e também a cota diária dos LLMs gratuitos.
INTERVALO_QUERY = 13
ESPERA_429 = 61

# ---------------------------------------------------------------------------
# Dataset: 18 perguntas de usuario reais, cobrindo as frentes que o compendio
# indexado responde (regras, magias, pericias, classes, racas, itens, ameacas,
# deuses, distincoes...). As `entidades` sao trechos que PRECISAM aparecer no
# top-8 (corpo do chunk ou metadados) — todas verificadas contra o corpus.
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
     "consulta": "Quanto custa em PM conjurar uma magia de 3º círculo?",
     "entidades": ["pontos de mana", "círculo", "magia"]},
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

# Citações no formato exigido pelo SYSTEM_PROMPT: Nome [Fonte] — ex.:
# "Fogueirada [Magias > Arcanas]". A fonte entre colchetes é o que liga a
# resposta ao contexto (formato genérico de domínio, sem siglas fixas).
PADRAO_CITACAO = re.compile(r"\[([^\]]{3,60})\]")


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para casar 'Caído' == 'caido' == 'Caido'."""
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def citacoes_em(texto: str) -> set[str]:
    """Fontes citadas no formato Nome [Fonte] (normalizadas)."""
    return {normalizar(c) for c in PADRAO_CITACAO.findall(texto)}


def carregar_cache() -> dict:
    if os.path.exists(ARQUIVO_CACHE):
        with open(ARQUIVO_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_cache(cache: dict) -> None:
    with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def reformular(llm, consulta: str, cache: dict) -> str:
    """Reformula para termos do sistema, cacheando para manter o A/B estável."""
    if consulta in cache:
        return cache[consulta]

    chain = PROMPT_TRADUCAO | llm
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                texto = chain.invoke({"queixa": consulta}).content.strip()
                if rag_core.e_recusa(texto):
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


def buscar(retriever, consulta: str):
    for i in range(4):
        try:
            return retriever.invoke(consulta)
        except Exception as e:
            if e_transitorio(e) and i < 3:
                print(f"  429 no rerank, aguardando {ESPERA_429}s...")
                time.sleep(ESPERA_429)
            else:
                raise
    return []


def avaliar(llm, so_recuperacao: bool = False, saida: str | None = None) -> dict:
    """Roda as CONSULTAS e devolve o resultado.

    Quando `saida` é informado, grava o JSON a cada query: uma falha de rede na
    última consulta não joga fora o trabalho das anteriores.
    """
    chunks = rag_core.montar_chunks()
    retriever = rag_core.montar_retriever(chunks)

    rag_chain = None
    if not so_recuperacao:
        rag_chain = rag_core.montar_rag_chain(retriever, SYSTEM_PROMPT, llm)

    cache = carregar_cache()
    registros = []

    for caso in CONSULTAS:
        print(f"\n[{caso['id']}] {caso['consulta'][:70]}...")
        reformulada = reformular(llm, caso["consulta"], cache)
        print(f"  reformulação: {reformulada[:95]}")

        top = buscar(retriever, reformulada)

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

        registro = {
            "id": caso["id"],
            "consulta": caso["consulta"],
            "reformulacao": reformulada,
            "entidades_esperadas": sorted(esperadas),
            "entidades_no_metadata": sorted(encontrados_meta),
            "entidades_no_texto": sorted(encontrados_texto),
            "cobertura_entidades": round(hit, 3),
            "scores_rerank": [round(s, 4) for s in scores],
            "top8": [{
                "score": round(d.metadata.get("relevance_score", 0), 4),
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
            grounding = (len(c_resp & c_ctx) / len(c_resp)) if c_resp else None
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
        "n_consultas": len(registros),
        "registros": registros,
    }


def gravar(saida: str, resultado: dict) -> None:
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


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
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(description="Avalia o RAG de Tormenta 20")
    ap.add_argument("--etapa", default="baseline", help="nome do arquivo de saída")
    ap.add_argument("--so-recuperacao", action="store_true",
                    help="não chama o LLM final (só métricas de recuperação)")
    args = ap.parse_args()

    llm = rag_core.criar_llm()
    saida = f"avaliacao_{args.etapa}.json"
    resultado = avaliar(llm, so_recuperacao=args.so_recuperacao, saida=saida)
    resultado["etapa"] = args.etapa
    gravar(saida, resultado)
    print(f"\nResultado salvo em {saida}")

    resumir(resultado)


if __name__ == "__main__":
    main()
