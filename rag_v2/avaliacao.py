"""Avaliação da v2 em termos absolutos: por pergunta, por entidade e por necessidade.

Sem linha de base da v1: a v1 foi ajustada nas perguntas fixas, então uma
comparação seria enviesada. Cada entidade esperada é rastreada pelas etapas
da recuperação (candidatos -> rerank -> limiar -> vagas -> orçamento) para
dizer ONDE ela se perdeu, e o relatório separa dev de teste fechado.

Este módulo é lógica pura (sem Qdrant): `tools/avaliar_v2.py` liga o retriever
real e entrega aqui a saída de cada turno.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

CONJUNTOS = ("dev", "teste", "sintetico")
ETAPAS_PERDA = ("candidatos", "limiar", "orcamento")


def carregar(caminho, conjunto: str, confirmar_teste: bool = False) -> list[dict]:
    """Casos de um conjunto. O teste fechado exige confirmação explícita."""
    if conjunto == "teste" and not confirmar_teste:
        raise PermissionError(
            "teste fechado: rode só ao fim de cada marco e nunca para ajustar "
            "(use --confirmar-teste)")
    casos = [json.loads(linha) for linha in Path(caminho).read_text(encoding="utf-8").splitlines()
             if linha.strip()]
    selecionados = [c for c in casos if c["conjunto"] == conjunto]
    nao_verificados = [c["id"] for c in selecionados if c.get("verificacao") != "ok"]
    if nao_verificados:
        raise ValueError(f"casos com entidade não verificada no corpus: {nao_verificados}")
    return selecionados


def _posicao(lista: list[str], registro: str) -> int | None:
    return lista.index(registro) + 1 if registro in lista else None


def rastrear(registro: str, rastro: dict) -> dict:
    """Onde um registro esperado se perdeu: candidatos, limiar ou orçamento.

    `limiar` só existe se houve rerank; sem ele (rerank fora do ar) o que não
    entrou no top-k foi cortado pelo orçamento.
    """
    final = rastro["final"]
    saida = {
        "registro": registro,
        "rank_rerank": _posicao(rastro["rerank"], registro),
        "rank_final": _posicao(final, registro),
        "garantido": registro in rastro["garantidos"],
        "perdida_em": None,
    }
    if registro in final:
        return saida
    if registro not in rastro["candidatos"]:
        saida["perdida_em"] = "candidatos"
    elif rastro["rerank"] and registro not in rastro["limiar"]:
        saida["perdida_em"] = "limiar"
    else:
        saida["perdida_em"] = "orcamento"
    return saida


def _registro(ent: dict) -> str:
    return f"{ent['tabela']}|{ent['nome']}"


def avaliar_caso(caso: dict, turnos: list[dict]) -> dict:
    """`turnos`: uma saída por mensagem (um só item numa pergunta simples).

    A cobertura é medida no ÚLTIMO turno (é o que a sequência quer responder);
    todos os turnos ficam registrados.
    """
    ultimo = turnos[-1]
    esperados = [_registro(e) for e in caso["entidades_esperadas"]]
    ligadas = set(ultimo["leitura"].get("ligacoes", []))
    entidades = []
    for reg in dict.fromkeys(esperados):  # sem repetir (sub-habilidades do mesmo registro)
        item = rastrear(reg, ultimo["rastro"])
        item["achada"] = item["perdida_em"] is None
        item["ligada_pelo_analisador"] = reg in ligadas
        entidades.append(item)

    obrigatorias = [n for n in (ultimo.get("telemetria") or {}).get("necessidades", [])
                    if n["obrigatoria"]]
    return {
        "id": caso["id"], "nivel": caso["nivel"], "conjunto": caso["conjunto"],
        "premissa_falsa": caso.get("premissa_falsa", False),
        "caminho": ultimo["caminho"],
        "leitura": ultimo["leitura"],
        "cobertura_entidades": (sum(e["achada"] for e in entidades) / len(entidades)
                                if entidades else None),
        "cobertura_necessidades": (sum(n["atendida"] for n in obrigatorias) / len(obrigatorias)
                                   if obrigatorias else None),
        "entidades": entidades,
        "n_docs": ultimo["n_docs"], "chars": ultimo["chars"],
        "tempo_s": round(sum(t["tempo_s"] for t in turnos), 2),
        "turnos": [{"achou_todas": all(
            rastrear(r, t["rastro"])["perdida_em"] is None for r in dict.fromkeys(esperados)),
            "caminho": t["caminho"], "n_docs": t["n_docs"]} for t in turnos],
    }


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 3) if valores else None


def agregar(resultados: list[dict]) -> dict:
    """{conjunto: {nivel: {...}, '_perdas_por_etapa': {...}}} — dev e teste separados."""
    por_conjunto: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in resultados:
        por_conjunto[r["conjunto"]][r["nivel"]].append(r)

    saida: dict = {}
    for conjunto, niveis in por_conjunto.items():
        saida[conjunto] = {}
        perdas: Counter = Counter()
        for nivel, rs in niveis.items():
            saida[conjunto][nivel] = {
                "n": len(rs),
                "cobertura_media": _media(r["cobertura_entidades"] for r in rs),
                "cobertura_necessidades_media": _media(r["cobertura_necessidades"] for r in rs),
                "completas": sum(1 for r in rs if r["cobertura_entidades"] == 1.0),
                "chars_medio": round(sum(r["chars"] for r in rs) / len(rs)),
                "docs_medio": round(sum(r["n_docs"] for r in rs) / len(rs), 1),
                "tempo_medio_s": round(sum(r["tempo_s"] for r in rs) / len(rs), 2),
                "caminho_v2": sum(1 for r in rs if r["caminho"] == "v2"),
            }
            for r in rs:
                for e in r["entidades"]:
                    if e["perdida_em"]:
                        perdas[e["perdida_em"]] += 1
        saida[conjunto]["_perdas_por_etapa"] = dict(perdas)
    return saida


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def renderizar(agregado: dict, resultados: list[dict]) -> str:
    """Relatório em texto: números absolutos da v2, sem coluna de outra arquitetura."""
    linhas = []
    for conjunto, niveis in agregado.items():
        linhas += [f"== {conjunto} ==",
                   (f"{'nivel':13}{'n':>3} {'cob.entid.':>11} {'cob.nec.':>9} {'completas':>10} "
                    f"{'docs':>5} {'chars':>7} {'tempo_s':>8} {'via v2':>7}")]
        for nivel, v in niveis.items():
            if nivel.startswith("_"):
                continue
            linhas.append(
                f"{nivel:13}{v['n']:>3} {_pct(v['cobertura_media']):>11} "
                f"{_pct(v['cobertura_necessidades_media']):>9} "
                f"{v['completas']:>4}/{v['n']:<5} {v['docs_medio']:>5} {v['chars_medio']:>7} "
                f"{v['tempo_medio_s']:>8} {v['caminho_v2']:>4}/{v['n']}")
        perdas = niveis["_perdas_por_etapa"]
        linhas.append("entidades perdidas por etapa: "
                      + (", ".join(f"{k}={perdas[k]}" for k in ETAPAS_PERDA if k in perdas)
                         or "nenhuma"))
        linhas.append("")
    linhas.append("Perdas por pergunta (entidade -> etapa):")
    achou_perda = False
    for r in resultados:
        for e in r["entidades"]:
            if e["perdida_em"]:
                achou_perda = True
                ligada = "ligada" if e["ligada_pelo_analisador"] else "NÃO ligada"
                linhas.append(f"  {r['id']}: {e['registro']} -> {e['perdida_em']} ({ligada})")
    if not achou_perda:
        linhas.append("  nenhuma")
    return "\n".join(linhas)
