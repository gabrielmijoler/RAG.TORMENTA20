"""Mapa do corpus: o que existe em cada Tabela, com que campos e de que Fonte.

Somente leitura (não toca o Qdrant). Lê os registros crus pelo mesmo
extrator da ingestão (`rag_core._extrair_fonte_ts`) e usa os mesmos rótulos
de Tabela, Fonte e Nome da metadata dos chunks, para que o mapa descreva
exatamente o que a busca enxerga.

Uso (da raiz):  .venv/bin/python tools/mapa_corpus.py
Saída: docs/MAPA_CORPUS.md (para ler) e docs/mapa_corpus.json (para código).
"""

import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rag_core

# Campos que podem virar restrição ou necessidade na v2 (nomes reais dos
# dados, em inglês ou português conforme o .ts de origem).
CAMPOS_UTEIS = (
    "level", "levelProgression", "prerequisite", "requirement", "price",
    "preco", "pm", "size", "tamanho", "type", "tipo", "circle", "school",
    "nd", "category", "proficiency", "damage", "critical", "grip",
    "attributeModifiers", "skills",
)
EXEMPLOS_POR_CAMPO = 3


def _preenchido(valor) -> bool:
    return valor not in (None, "", [], {})


def _curto(valor, limite: int = 70) -> str:
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def mapear(dados: dict) -> dict:
    """Contagens por Tabela e Fonte, % de preenchimento e nomes repetidos."""
    tabelas: dict = defaultdict(lambda: {
        "registros": 0, "exports": set(), "fontes": Counter(),
        "_campos": Counter(), "_exemplos": defaultdict(list)})
    fontes: Counter = Counter()
    locais_por_nome: dict = defaultdict(set)

    for bloco in dados["tabelas"]:
        tabela = rag_core._rotulo_tabela(bloco["arquivo"], bloco["export"])
        info = tabelas[tabela]
        info["exports"].add(f'{bloco["arquivo"]}:{bloco["export"]}')
        for reg in bloco["elementos"]:
            fonte = rag_core._fonte_do_registro(reg)
            info["registros"] += 1
            info["fontes"][fonte] += 1
            fontes[fonte] += 1
            for campo, valor in reg.items():
                if campo.startswith("__") or not _preenchido(valor):
                    continue
                info["_campos"][campo] += 1
                exemplos = info["_exemplos"][campo]
                if campo in CAMPOS_UTEIS and len(exemplos) < EXEMPLOS_POR_CAMPO:
                    curto = _curto(valor)
                    if curto not in exemplos:
                        exemplos.append(curto)
            nome = rag_core._nome_do_registro(reg)
            if nome:
                locais_por_nome[rag_core.normalizar(nome)].add((tabela, fonte, nome))

    saida_tabelas = {}
    for tabela, info in sorted(tabelas.items()):
        total = info["registros"]
        saida_tabelas[tabela] = {
            "registros": total,
            "exports": sorted(info["exports"]),
            "fontes": dict(info["fontes"].most_common()),
            "campos": {c: round(100 * n / total) for c, n in info["_campos"].most_common()},
            "exemplos": {c: v for c, v in info["_exemplos"].items() if v},
        }

    repetidos = {}
    for nome, locais in sorted(locais_por_nome.items()):
        if len({(t, f) for t, f, _ in locais}) > 1:
            # repetição que some ao normalizar a grafia da Fonte não é
            # ambiguidade real ("Livro A" x "livro a" é o mesmo livro)
            so_grafia = len({(t, rag_core.normalizar(f)) for t, f, _ in locais}) == 1
            repetidos[nome] = [{"tabela": t, "fonte": f, "nome": n,
                                "so_grafia_de_fonte": so_grafia}
                               for t, f, n in sorted(locais)]

    grafias: dict = defaultdict(set)
    for fonte in fontes:
        grafias[rag_core.normalizar(fonte)].add(fonte)
    variantes = {k: sorted(v) for k, v in sorted(grafias.items()) if len(v) > 1}

    return {"tabelas": saida_tabelas, "fontes": dict(fontes.most_common()),
            "variantes_de_fonte": variantes, "nomes_repetidos": repetidos}


def renderizar_md(mapa: dict) -> str:
    """Versão legível do mapa (o JSON é a fonte; este texto é só para ler)."""
    total = sum(t["registros"] for t in mapa["tabelas"].values())
    so_grafia = sum(1 for locais in mapa["nomes_repetidos"].values()
                    if locais[0]["so_grafia_de_fonte"])
    linhas = [
        "# Mapa do corpus",
        "",
        ("Gerado por `tools/mapa_corpus.py` a partir dos `.ts` do aTormenta "
         "(mesmos rótulos de Tabela/Fonte/Nome da metadata dos chunks). "
         "Não edite à mão: rode o script de novo."),
        "",
        f"- Registros: {total} em {len(mapa['tabelas'])} tabelas",
        f"- Fontes: {len(mapa['fontes'])}",
        (f"- Nomes em mais de uma Tabela ou Fonte: {len(mapa['nomes_repetidos'])}"
         f" (dos quais {so_grafia} só por grafia diferente da mesma Fonte)"),
        "",
        "## Fontes",
        "",
        "| Fonte | Registros |",
        "|---|---:|",
    ]
    linhas += [f"| {f} | {n} |" for f, n in mapa["fontes"].items()]
    linhas += ["", "### Mesma Fonte com grafias diferentes", "",
               ("Agrupadas por minúsculas e sem acento; abreviações e palavras "
                "diferentes (ex.: `DB` x `Dragão Brasil`, `de` x `dos`) não são "
                "detectadas aqui."), ""]
    linhas += [f"- `{k}`: " + " · ".join(v) for k, v in mapa["variantes_de_fonte"].items()]
    linhas += ["", "## Tabelas", ""]
    for tabela, info in mapa["tabelas"].items():
        linhas += [f"## {tabela}", "",
                   f"{info['registros']} registros · exports: "
                   + ", ".join(f"`{e}`" for e in info["exports"]), "",
                   "Fontes: " + " · ".join(f"{f} ({n})" for f, n in info["fontes"].items()),
                   "",
                   "Campos (% preenchido): "
                   + ", ".join(f"`{c}` {p}%" for c, p in info["campos"].items()), ""]
        for campo, exemplos in info["exemplos"].items():
            linhas.append(f"- `{campo}`: " + " | ".join(exemplos))
        linhas.append("")
    linhas += ["## Nomes em mais de uma Tabela ou Fonte", "",
               "`só grafia` = a repetição some ao normalizar a Fonte.", "",
               "| Nome normalizado | Só grafia? | Onde aparece (Tabela > Fonte) |",
               "|---|---|---|"]
    for nome, locais in mapa["nomes_repetidos"].items():
        onde = "; ".join(f"{loc['tabela']} > {loc['fonte']}" for loc in locais)
        marca = "só grafia" if locais[0]["so_grafia_de_fonte"] else ""
        linhas.append(f"| {nome} | {marca} | {onde} |")
    return "\n".join(linhas) + "\n"


def main() -> None:
    mapa = mapear(rag_core._extrair_fonte_ts(verbose=False))
    raiz = os.path.join(os.path.dirname(__file__), "..", "docs")
    with open(os.path.join(raiz, "mapa_corpus.json"), "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=1)
    with open(os.path.join(raiz, "MAPA_CORPUS.md"), "w", encoding="utf-8") as f:
        f.write(renderizar_md(mapa))
    print(f"{sum(t['registros'] for t in mapa['tabelas'].values())} registros, "
          f"{len(mapa['tabelas'])} tabelas, {len(mapa['nomes_repetidos'])} nomes repetidos")


if __name__ == "__main__":
    main()
