"""Roda o chat REAL (index.py) com perguntas do goldenset — uma pergunta por sessão.

Uso:
    .venv/bin/python chat_usuario.py --saida chat_usuario_antes.json
    .venv/bin/python chat_usuario.py --saida chat_usuario_depois.json --continuar

Fidelidade: chama `index.processar()` (a MESMA função do main()) com histórico e
filtros limpos antes de cada pergunta (= usuário abrindo o chat do zero) e
captura o STDOUT — nenhuma linha do chat é alterada. O que sai é o rodapé
`ground: ...` que o usuário veria, mais a reformulação ao vivo do [2/4].

Amostra dirigida: as 28 queries da auditoria (23 com grd 0% + 11 com cobertura
< 50% em avaliacao_baseline_fr_l12_ground.json), pelo PREFIXO NUMÉRICO do id —
sobrevive ao reescopo do 42 (`42_cd_heroica` -> `42_cd_escapar`).
"""
import argparse
import contextlib
import io
import json
import os
import re
import time

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

# 23 queries com grd 0% + 11 com cobertura < 50% (deduplicadas = 28).
AMOSTRA = ["02", "06", "07", "08", "10", "11", "14", "15", "16", "21",
           "23", "24", "26", "27", "30", "32", "34", "38", "40", "42",
           "43", "44", "49", "52", "53", "54", "57", "59"]

_RE_GROUND = re.compile(r"^ground: (.+)$", re.MULTILINE)
_RE_REFORM = re.compile(r"\[2/4\][^\n]*\n\s*-> (.+)$", re.MULTILINE)


def parsear_ground(texto: str) -> float | None:
    """0.89 / None (n/a: resposta sem citações, ou sem resposta nenhuma)."""
    m = _RE_GROUND.search(texto or "")
    if not m:
        return None
    p = re.match(r"(\d+)%", m.group(1).strip())
    return int(p.group(1)) / 100 if p else None


def resolver_caso(casos: list, chave: str) -> dict | None:
    """Id exato, senão prefixo numérico (`42` -> `42_cd_escapar`)."""
    exato = [c for c in casos if c["id"] == chave]
    if exato:
        return exato[0]
    pref = [c for c in casos if c["id"].startswith(chave + "_")]
    return pref[0] if pref else None


def _registrar(saida: dict, caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(saida, arquivo, ensure_ascii=False, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Chat real com o goldenset")
    ap.add_argument("--saida", required=True, help="JSON de saída")
    ap.add_argument("--continuar", action="store_true",
                    help="pula ids já gravados no --saida")
    ap.add_argument("--pausa", type=float, default=10.0,
                    help="segundos entre perguntas (cota dos LLMs gratuitos)")
    ap.add_argument("--apenas", default=None,
                    help="prefixo único (smoke): ex. --apenas 05")
    args = ap.parse_args()

    import index  # monta chunks/retriever/chain igual ao chat
    from avaliar import carregar_goldenset

    casos = carregar_goldenset()
    chaves = [args.apenas] if args.apenas else list(AMOSTRA)
    feitos: dict = {}
    if args.continuar and os.path.exists(args.saida):
        with open(args.saida, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        feitos = {r["id"]: r for r in dados.get("respostas", []) if r.get("id")}

    saida = {"etapa": os.path.basename(args.saida), "amostra": list(chaves),
             "pausa_s": args.pausa,
             "data_inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "respostas": []}
    for n, chave in enumerate(chaves, 1):
        caso = resolver_caso(casos, chave)
        if caso is None:
            raise SystemExit(f"prefixo {chave} não achado no goldenset")
        if caso["id"] in feitos:
            continue
        index.chat_history.clear()          # sessão nova = usuário abrindo o chat
        index.filtros_ativos.clear()
        buf = io.StringIO()
        t0 = time.time()
        erro = None
        try:
            with contextlib.redirect_stdout(buf):   # única "instrumentação"
                index.processar(caso["consulta"])
        except Exception as e:                       # noqa: BLE001 — registra e segue
            erro = f"{type(e).__name__}: {str(e)[:300]}"
        texto = buf.getvalue()
        m_reform = _RE_REFORM.search(texto)
        registro = {
            "id": caso["id"],
            "consulta": caso["consulta"],
            "reformulacao": m_reform.group(1).strip() if m_reform else None,
            "ground": parsear_ground(texto),
            "sem_resposta": "ground:" not in texto,
            "erro": erro,
            "duracao_s": round(time.time() - t0, 1),
            "log": texto,
        }
        feitos[caso["id"]] = registro
        print(f"{n:>2}/{len(chaves)} {caso['id']:<26} "
              f"ground={registro['ground']} "
              f"{'ERRO ' if erro else ''}"
              f"{'sem_resposta ' if registro['sem_resposta'] else ''}"
              f"({registro['duracao_s']}s)", flush=True)
        saida["respostas"] = list(feitos.values())
        _registrar(saida, args.saida)
        time.sleep(args.pausa)

    regs = saida["respostas"]
    grds = [r["ground"] for r in regs if r["ground"] is not None]
    print("\nRESUMO")
    if grds:
        print(f"  n={len(regs)}  grd_media={sum(grds) / len(grds):.1%}  "
              f"zeros={sum(1 for g in grds if g == 0)}")
    else:
        print(f"  n={len(regs)}  sem ground nenhum")
    print(f"  n/a={sum(1 for r in regs if r['ground'] is None)}  "
          f"erros={sum(1 for r in regs if r['erro'])}  "
          f"sem_resposta={sum(1 for r in regs if r['sem_resposta'])}")


if __name__ == "__main__":
    main()
