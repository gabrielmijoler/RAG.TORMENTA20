"""Mede o PRÓPRIO analisador contra perguntas rotuladas à mão.

Cada item diz o que um humano leria na pergunta: quais registros aparecem
(`Tabela|Nome`), nível e classe/raça, e o tipo. O medidor compara com a
`Leitura`. Rótulos sem revisão do usuário são PROVISÓRIOS: a medição só vale
depois da correção dele.
"""

import json
import time
from pathlib import Path

from .dicionario import Dicionario
from .leitura import ler
from .sessao import Sessao


def _registro(tabela: str, nome: str) -> str:
    return f"{tabela}|{nome.strip()}"


def carregar(caminho, dicionario: Dicionario) -> list[dict]:
    """Itens do JSONL; recusa rótulo que aponta para registro que não existe no corpus."""
    existentes = {_registro(c.tabela, c.nome)
                  for chaves in dicionario.exatos.values() for c in chaves}
    itens = [json.loads(linha) for linha in Path(caminho).read_text(encoding="utf-8").splitlines()
             if linha.strip()]
    for item in itens:
        for ref in item["ligacoes"]:
            if ref not in existentes:
                raise ValueError(f"{item['id']}: registro rotulado não existe no corpus: {ref}")
    return itens


def _ligados(leitura) -> set[str]:
    return {_registro(lig.chave.tabela, lig.chave.nome) for lig in leitura.ligacoes}


def _com_alternativas(leitura) -> set[str]:
    return {_registro(c.tabela, c.nome)
            for lig in leitura.ligacoes for c in (lig.chave, *lig.alternativas)}


def avaliar_item(item: dict, dicionario: Dicionario) -> dict:
    """Lê as mensagens em ordem (com Sessao) e compara o ÚLTIMO turno com o rótulo."""
    sessao = Sessao()
    mensagens = item.get("mensagens") or [item["texto"]]
    t0 = time.perf_counter()
    leitura = None
    for mensagem in mensagens:
        leitura = ler(mensagem, dicionario, sessao)
        sessao.atualizar(leitura)
    ms = (time.perf_counter() - t0) * 1000 / len(mensagens)

    esperado = set(item["ligacoes"])
    achado = _ligados(leitura)
    # o registro esperado vale se foi o escolhido OU está entre as alternativas
    # (empate sem desempate): o recall mede "o analisador viu o registro certo"
    visto = _com_alternativas(leitura)
    erros = [f"faltou {ref}" for ref in sorted(esperado - visto)]
    erros += [f"sobrou {ref}" for ref in sorted(achado - esperado)]

    restr = item.get("restricoes", {})
    nivel_ok = restr.get("nivel") == leitura.restricoes.nivel
    classes_ok = set(restr.get("classes", [])) == set(leitura.restricoes.classes)
    racas_ok = set(restr.get("racas", [])) == set(leitura.restricoes.racas)
    if not nivel_ok:
        erros.append(f"nível: rotulado {restr.get('nivel')}, lido {leitura.restricoes.nivel}")
    if not classes_ok:
        erros.append(f"classes: rotulado {restr.get('classes')}, lido "
                     f"{list(leitura.restricoes.classes)}")
    if not racas_ok:
        erros.append(f"raças: rotulado {restr.get('racas')}, lido "
                     f"{list(leitura.restricoes.racas)}")
    tipo_ok = item["tipo"] == leitura.tipo
    if not tipo_ok:
        erros.append(f"tipo: rotulado {item['tipo']}, lido {leitura.tipo}")

    return {
        "id": item["id"], "texto": item["texto"],
        "ligacao_recall": len(esperado & visto) / len(esperado) if esperado else None,
        "ligacao_precisao": len(esperado & achado) / len(achado) if achado else None,
        "restricoes_ok": nivel_ok and classes_ok and racas_ok,
        "tipo_ok": tipo_ok, "tipo_lido": leitura.tipo,
        "confianca": leitura.confianca, "fallback": leitura.confianca == "baixa",
        "leitura_ms": round(ms, 2), "erros": erros,
    }


def _media(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 3) if valores else None


def agregar(itens: list[dict]) -> dict:
    n = len(itens)
    return {
        "n": n,
        "ligacao_recall_medio": _media(i["ligacao_recall"] for i in itens),
        "ligacao_precisao_media": _media(i["ligacao_precisao"] for i in itens),
        "restricoes_acerto": round(sum(i["restricoes_ok"] for i in itens) / n, 3) if n else None,
        "tipo_acerto": round(sum(i["tipo_ok"] for i in itens) / n, 3) if n else None,
        "taxa_fallback": round(sum(i["fallback"] for i in itens) / n, 3) if n else None,
        "leitura_ms_medio": _media(i["leitura_ms"] for i in itens),
        "leitura_ms_max": max((i["leitura_ms"] for i in itens), default=0),
    }


def renderizar(agregado: dict, itens: list[dict]) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.0%}"
    linhas = [
        "Acerto do analisador contra rótulos PROVISÓRIOS (sem revisão do usuário)",
        f"  itens: {agregado['n']}",
        (f"  ligação — recall {pct(agregado['ligacao_recall_medio'])}, "
         f"precisão {pct(agregado['ligacao_precisao_media'])}"),
        (f"  restrições (nível/classe/raça) {pct(agregado['restricoes_acerto'])} | "
         f"tipo {pct(agregado['tipo_acerto'])} | fallback p/ v1 {pct(agregado['taxa_fallback'])}"),
        (f"  tempo da leitura: médio {agregado['leitura_ms_medio']} ms, "
         f"máx {agregado['leitura_ms_max']} ms"),
        "", "Divergências:",
    ]
    com_erro = [i for i in itens if i["erros"]]
    for i in com_erro:
        linhas.append(f"  {i['id']}  «{i['texto'][:70]}»")
        linhas += [f"      - {e}" for e in i["erros"]]
    if not com_erro:
        linhas.append("  nenhuma")
    return "\n".join(linhas)
