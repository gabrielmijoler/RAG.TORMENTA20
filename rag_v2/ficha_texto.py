"""Ficha do personagem lida do texto livre do jogador.

Só extrai o que está EXPLÍCITO. Atributo exige separador ('INT = 6', 'For: 3') ou a
forma de sigla ('Int 6', 'CAR 1'): a palavra comum 'for' ('se for 3 dias') não conta.
Ofício específico só com verbo de posse ('sou armeiro', 'tenho Ofício (alquimista)').
O que o jogador não disse fica DESCONHECIDO (campo vazio), nunca 'não tem'.
"""

import re

import rag_core

_ATRIBUTOS = {"for": "for", "forca": "for", "des": "des", "destreza": "des", "con": "con",
              "constituicao": "con", "int": "int", "inteligencia": "int", "sab": "sab",
              "sabedoria": "sab", "car": "car", "carisma": "car"}
_RE_ATRIBUTO = re.compile(
    r"\b(for(?:ça|ca)?|des(?:treza)?|con(?:stituição|stituicao)?|int(?:eligência|eligencia)?|"
    r"sab(?:edoria)?|car(?:isma)?)\b(\s*[=:]\s*|\s+)(-?\d{1,2})\b", re.IGNORECASE)
_OFICIOS = ("armeiro", "artesao", "alquimista", "cozinheiro", "alfaiate", "engenhoqueiro")
_RE_TODOS_OFICIOS = re.compile(r"\btodos os oficios\b")
_RE_POSSE = re.compile(r"\b(?:sou|tenho|treinad[oa] em|oficio)\b")
_RE_TREINADO = re.compile(r"treinad[oa]s? em ([^.;?!]+)")
_RE_DEVOTO = re.compile(r"\bdevot[oa] d[eao] (\w+)")


def _atributos(texto: str) -> dict[str, int]:
    saida: dict[str, int] = {}
    for m in _RE_ATRIBUTO.finditer(texto):
        palavra, separador, valor = m.groups()
        tem_separador = "=" in separador or ":" in separador
        forma_sigla = len(palavra) == 3 and (palavra.isupper() or palavra.istitle())
        forma_extenso = len(palavra) > 3
        if tem_separador or forma_extenso or forma_sigla:
            saida[_ATRIBUTOS[rag_core.normalizar(palavra)]] = int(valor)
    return saida


def extrair(texto: str) -> dict:
    norma = " ".join(rag_core.normalizar(texto or "").split())
    oficios = {o for o in _OFICIOS if re.search(rf"\b{o}\b", norma) and _RE_POSSE.search(norma)
               and re.search(rf"(?:\bsou|\btenho|oficio\s*\(?){'.{0,12}'}\b{o}\b", norma)}
    pericias: set[str] = set()
    for trecho in _RE_TREINADO.findall(norma):
        for nome in re.split(r",|\be\b|\bou\b", trecho):
            nome = re.sub(r"\(.*?\)", "", nome).strip()
            if nome and not nome.startswith("oficio"):
                pericias.add(nome)
    devoto = _RE_DEVOTO.search(norma)
    return {
        "atributos": _atributos(texto or ""),
        "oficios": oficios,
        "todos_oficios": bool(_RE_TODOS_OFICIOS.search(norma)),
        "pericias": pericias,
        "devoto": devoto.group(1) if devoto else None,
    }
