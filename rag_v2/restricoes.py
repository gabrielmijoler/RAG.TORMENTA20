"""Restrições da pergunta: nível por padrões de texto; o resto pelas ligações."""

import re

from .dicionario import chave_texto
from .tipos import Ligacao, Restricoes

NIVEL_MIN, NIVEL_MAX = 1, 20

# Sobre o texto já normalizado por `chave_texto` ("4º nível" vira "4o nivel").
_PADROES_NIVEL = (
    re.compile(r"\b(?:nv|nivel|lvl|lv|level)\s?(\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})o?\s+nivel\b"),
)

_PREFIXOS_ITEM = ("Armas", "Armaduras", "Acessórios", "Esotéricos", "Itens",
                  "Escudos")
_TABELAS_ITEM = frozenset({
    "Alquímicos", "Poções", "Equipamentos", "Ferramentas", "Vestuário",
    "Instrumentos Musicais", "Artefatos", "Alimentos", "Itens Diversos",
})


def extrair_nivel(texto: str) -> int | None:
    norma = chave_texto(texto)
    for padrao in _PADROES_NIVEL:
        for m in padrao.finditer(norma):
            nivel = int(m.group(1))
            if NIVEL_MIN <= nivel <= NIVEL_MAX:
                return nivel
    return None


def _e_item(tabela: str) -> bool:
    return tabela in _TABELAS_ITEM or tabela.startswith(_PREFIXOS_ITEM)


def extrair_restricoes(texto: str, ligacoes: tuple[Ligacao, ...]) -> Restricoes:
    """Uma habilidade aninhada (chave.sub) não diz qual é a classe do personagem."""
    grupos: dict[str, list[str]] = {"classes": [], "racas": [], "pericias": [], "itens": []}
    for lig in ligacoes:
        chave = lig.chave
        if chave.sub is not None:
            continue
        if chave.tabela == "Classes":
            destino = "classes"
        elif chave.tabela == "Raças":
            destino = "racas"
        elif chave.tabela == "Perícias":
            destino = "pericias"
        elif _e_item(chave.tabela):
            destino = "itens"
        else:
            continue
        if chave.nome not in grupos[destino]:
            grupos[destino].append(chave.nome)
    return Restricoes(nivel=extrair_nivel(texto),
                      **{k: tuple(v) for k, v in grupos.items()})
