"""Gera perguntas sintéticas (sem LLM) a partir do corpus, com gabarito por construção.

Uso (da raiz):
  .venv/bin/python tools/gerar_sinteticas.py --semente 7 --n 30
Grava propostas/sinteticas_semente<N>.jsonl (mesmo esquema da suíte de 12, conjunto
"sintetico"), que o tools/avaliar_v2.py roda com --conjunto sintetico.
Use uma semente NOVA a cada rodada: a amostra deve ser de perguntas que o sistema
ainda não viu.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rag_core
from rag_v2 import sinteticas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gera perguntas sintéticas sem LLM")
    ap.add_argument("--semente", type=int, required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--ruido", type=float, default=0.35,
                    help="chance de erro de digitação/informalidade (0 a 1)")
    args = ap.parse_args(argv)

    casos = sinteticas.gerar(rag_core._extrair_fonte_ts(verbose=False), args.n,
                             args.semente, args.ruido)
    os.makedirs("propostas", exist_ok=True)
    saida = f"propostas/sinteticas_semente{args.semente}.jsonl"
    with open(saida, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(caso, ensure_ascii=False) + "\n" for caso in casos)
    tipos = {}
    for c in casos:
        tipos[c["tipo_pergunta"]] = tipos.get(c["tipo_pergunta"], 0) + 1
    print(f"{len(casos)} perguntas em {saida} | tipos: {tipos} | "
          f"com erro de digitação: {sum(c['com_erro_de_digitacao'] for c in casos)} | "
          f"informais: {sum(c['informal'] for c in casos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
