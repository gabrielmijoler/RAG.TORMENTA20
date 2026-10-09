"""Gerencia o conhecimento aprendido da v2 (apelidos), sempre com aprovação humana.

Uso (da raiz):
  .venv/bin/python tools/conhecimento.py listar [--status proposta]
  .venv/bin/python tools/conhecimento.py propor "machado do minotauro" \\
      --tabela Armas --nome "Machado Táurico" --fonte "Tormenta20 - Jogo do Ano" \\
      --observado "usuário escreveu 'machado do minotauro'" --onde "Armas, JdA"
  .venv/bin/python tools/conhecimento.py aprovar a0001 --por gabriel
  .venv/bin/python tools/conhecimento.py recusar a0001 --motivo "ambíguo"
  .venv/bin/python tools/conhecimento.py verificar      # após reindexar/reingerir
  .venv/bin/python tools/conhecimento.py gerar-md

Toda mudança regenera conhecimento/APRENDIZADOS.md a partir do YAML.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag_v2 import conhecimento as k
from rag_v2.dicionario import do_corpus
from rag_v2.tipos import Chave


def carregar_dicionario():
    """Dicionário do corpus real SEM apelidos (a validação compara com nomes reais)."""
    return do_corpus(apelidos={})


def _caminhos(pasta: Path) -> tuple[Path, Path, Path]:
    return pasta / "propostas.yaml", pasta / "apelidos.yaml", pasta / "APRENDIZADOS.md"


def _regerar_md(pasta: Path) -> None:
    propostas, apelidos, md = _caminhos(pasta)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(k.gerar_md(propostas, apelidos), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Conhecimento aprendido da v2 (apelidos)")
    ap.add_argument("--pasta", default=str(k.PASTA), help="pasta dos YAML (padrão: conhecimento)")
    sub = ap.add_subparsers(dest="comando", required=True)
    listar = sub.add_parser("listar")
    listar.add_argument("--status", choices=("proposta", "aprovada", "recusada", "suspensa"))
    propor = sub.add_parser("propor")
    propor.add_argument("apelido")
    for campo in ("tabela", "nome", "fonte", "observado", "onde"):
        propor.add_argument(f"--{campo}", required=True)
    aprovar = sub.add_parser("aprovar")
    aprovar.add_argument("id")
    aprovar.add_argument("--por", required=True, help="quem aprovou")
    recusar = sub.add_parser("recusar")
    recusar.add_argument("id")
    recusar.add_argument("--motivo", required=True)
    sub.add_parser("verificar")
    sub.add_parser("gerar-md")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pasta = Path(args.pasta)
    propostas, apelidos, md = _caminhos(pasta)

    if args.comando == "listar":
        entradas = k.carregar(apelidos) + k.carregar(propostas)
        if args.status:
            entradas = [e for e in entradas if e["status"] == args.status]
        for e in sorted(entradas, key=lambda e: e["id"]):
            print(f"{e['id']}  {e['status']:9}  {e['apelido']!r} -> "
                  f"{e['tabela']} > {e['nome']} [{e['fonte']}]")
        if not entradas:
            print("(nenhuma entrada)")
        return 0

    if args.comando == "propor":
        entrada = k.propor(args.apelido, Chave(args.tabela, args.nome, args.fonte),
                           args.observado, args.onde, caminho=propostas,
                           caminho_apelidos=apelidos)
        print(f"proposta {entrada['id']} registrada (pendente de aprovação)")
    elif args.comando == "aprovar":
        erros = k.aprovar(args.id, args.por, carregar_dicionario(), propostas, apelidos)
        if erros:
            print("NÃO aprovada:\n  - " + "\n  - ".join(erros))
            return 1
        print(f"{args.id} aprovada: passa a valer no ligador na próxima sessão.")
        print("Próximo passo: rodar o teste fechado e a regressão só-recuperação "
              "(o teste fechado ainda não existe — Fase 2).")
    elif args.comando == "recusar":
        if not k.recusar(args.id, args.motivo, propostas):
            print(f"{args.id} não está pendente")
            return 1
        print(f"{args.id} recusada (fica registrada, nunca é aplicada)")
    elif args.comando == "verificar":
        suspensas = k.verificar(carregar_dicionario(), apelidos)
        if suspensas:
            for e in suspensas:
                print(f"suspenso {e['id']} {e['apelido']!r}: {e['motivo']}")
        else:
            print("nenhum apelido órfão")
    _regerar_md(pasta)
    if args.comando == "gerar-md":
        print(f"{md} regenerado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
