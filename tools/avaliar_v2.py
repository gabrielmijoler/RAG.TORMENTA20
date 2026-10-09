"""Avalia a recuperação da v2 em termos absolutos (sem LLM, sem comparar com a v1).

Uso (da raiz):
  .venv/bin/python tools/avaliar_v2.py --etapa dev1                    # só dev
  .venv/bin/python tools/avaliar_v2.py --etapa marco1 --conjunto teste --confirmar-teste

- RERANK é fixado em flashrank (local): sem Cohere, resultado reproduzível.
- Aborta se a conexão não for o servidor Qdrant ou se a coleção não tiver o nº
  de pontos esperado (evita medir contra o índice local antigo, que já
  contaminou uma rodada).
- Pergunta com confiança baixa segue o caminho de fallback: o mesmo pipeline
  de recuperação sem necessidades, k=12 (aproxima a v1 sem decomposição).
- Sequências (`mensagens`) rodam em uma Sessao compartilhada: o foco e a ficha
  de um turno valem no seguinte.
Grava avaliacao_v2_<etapa>.json (ignorado pelo git).
"""

import argparse
import dataclasses
import json
import os
import sys
import time

os.environ.setdefault("RERANK", "flashrank")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client import QdrantClient

import rag_core
from rag_v2 import avaliacao
from rag_v2.dicionario import do_corpus
from rag_v2.leitura import ler
from rag_v2.recuperacao import indexar_registros, recuperar_v2
from rag_v2.sessao import Sessao

ENTRADA_PADRAO = "propostas/goldenset_proposta_12.jsonl"


def _ids_ligados(leitura) -> list[str]:
    ids = []
    for lig in leitura.ligacoes:
        for chave in (lig.chave, *lig.alternativas):
            ids.append(f"{chave.tabela}|{chave.nome}")
    return ids


def rodar_turno(retriever, dicionario, registros, sessao, mensagem: str) -> dict:
    t0 = time.perf_counter()
    leitura = ler(mensagem, dicionario, sessao)
    v2 = leitura.confianca != "baixa"
    efetiva = leitura if v2 else dataclasses.replace(leitura, necessidades=(), k=12)
    consulta = leitura.texto_resolvido or mensagem
    docs, telemetria = recuperar_v2(retriever, efetiva, registros, consulta, consulta)
    sessao.atualizar(leitura)
    return {
        "caminho": "v2" if v2 else "fallback_v1",
        "final": telemetria["rastro"]["final"],
        "rastro": telemetria["rastro"],
        "telemetria": telemetria,
        "leitura": {"tipo": leitura.tipo, "confianca": leitura.confianca, "k": leitura.k,
                    "motivos": list(leitura.motivos), "ligacoes": _ids_ligados(leitura),
                    "necessidades": [n.descricao for n in leitura.necessidades]},
        "n_docs": len(docs),
        "chars": sum(len(d.page_content) for d in docs),
        "tempo_s": time.perf_counter() - t0,
    }


def conectar(pontos_esperados: int):
    conexao = rag_core.escolher_conexao_qdrant()
    if not conexao.get("url"):
        sys.exit("abortado: Qdrant servidor indisponível (caiu no índice local antigo)")
    pontos = QdrantClient(url=conexao["url"]).count(rag_core.COLECAO).count
    if pontos != pontos_esperados:
        sys.exit(f"abortado: coleção com {pontos} pontos (esperado {pontos_esperados})")
    chunks = rag_core.montar_chunks(verbose=False)
    retriever = rag_core.montar_retriever(chunks, conexao=conexao, verbose=False)
    return retriever, chunks, pontos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Avalia a recuperação da v2 (absoluta, sem LLM)")
    ap.add_argument("--etapa", required=True)
    ap.add_argument("--entrada", default=ENTRADA_PADRAO)
    ap.add_argument("--conjunto", choices=avaliacao.CONJUNTOS, default="dev")
    ap.add_argument("--confirmar-teste", action="store_true",
                    help="obrigatório para o conjunto teste (teste fechado)")
    ap.add_argument("--ids", help="prefixos de id separados por vírgula")
    ap.add_argument("--pontos-esperados", type=int, default=5674)
    args = ap.parse_args(argv)

    casos = avaliacao.carregar(args.entrada, args.conjunto, args.confirmar_teste)
    if args.ids:
        prefixos = args.ids.split(",")
        casos = [c for c in casos if any(c["id"].startswith(p) for p in prefixos)]
    if args.conjunto == "teste":
        print("⚠️  TESTE FECHADO: não use este resultado para ajustar nada.")

    retriever, chunks, pontos = conectar(args.pontos_esperados)
    dicionario = do_corpus()
    registros = indexar_registros(chunks)

    resultados = []
    for caso in casos:
        sessao = Sessao()
        mensagens = caso.get("mensagens") or [caso["consulta"]]
        turnos = [rodar_turno(retriever, dicionario, registros, sessao, m) for m in mensagens]
        resultado = avaliacao.avaliar_caso(caso, turnos)
        resultado["consulta"] = caso["consulta"]
        resultado["turnos_detalhe"] = turnos
        resultados.append(resultado)
        cob = resultado["cobertura_entidades"]
        print(f"[{caso['id']}] {resultado['caminho']} cobertura="
              f"{'n/a' if cob is None else f'{cob:.0%}'} docs={resultado['n_docs']} "
              f"{resultado['tempo_s']}s", flush=True)

    agregado = avaliacao.agregar(resultados)
    saida = f"avaliacao_v2_{args.etapa}.json"
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"etapa": args.etapa, "conjunto": args.conjunto, "pontos": pontos,
                   "reranker": rag_core.reranker_ativo(), "agregado": agregado,
                   "resultados": resultados}, f, ensure_ascii=False, indent=1, default=float)
    print("\n" + avaliacao.renderizar(agregado, resultados))
    print(f"\nResultado salvo em {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
