"""Mede o acerto do analisador da v2 contra o conjunto rotulado (sem LLM, sem Qdrant).

Uso (da raiz):
  .venv/bin/python tools/medir_analisador.py [--entrada propostas/rotulado_proposta.jsonl]
Os rótulos de propostas/ são PROVISÓRIOS até o usuário corrigi-los.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag_v2 import rotulado
from rag_v2.dicionario import do_corpus


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Acerto do analisador contra rótulos")
    ap.add_argument("--entrada", default="propostas/rotulado_proposta.jsonl")
    ap.add_argument("--saida", help="grava o resultado em JSON (ex.: avaliacao_analisador_x.json)")
    args = ap.parse_args(argv)

    dicionario = do_corpus()
    itens = [rotulado.avaliar_item(i, dicionario) for i in rotulado.carregar(args.entrada, dicionario)]
    agregado = rotulado.agregar(itens)
    print(rotulado.renderizar(agregado, itens))
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            json.dump({"agregado": agregado, "itens": itens}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
