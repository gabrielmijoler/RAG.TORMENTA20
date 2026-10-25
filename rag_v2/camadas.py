"""Pergunta em camadas: "me liste 5 comidas que ajudam com mana" = tabela x efeito.

Uma busca só dilui as duas camadas, e o livro escreve "PM temporários" onde o
jogador diz "mana". O código escreve uma sub-consulta por variação do efeito,
no vocabulário do livro, e o `recuperar_v2` busca cada uma na tabela pedida.
"""

from .dicionario import chave_texto, singular
from .tipos import Camadas

# palavra (singular, sem acento) -> (rótulo da tabela, como a sub-consulta chama o item)
CATEGORIAS = {
    "comida": ("Alimentos", "alimento"), "alimento": ("Alimentos", "alimento"),
    "bebida": ("Alimentos", "alimento"), "refeicao": ("Alimentos", "alimento"),
    "prato": ("Alimentos", "alimento"),
    "pocao": ("Poções", "poção"), "alquimico": ("Alquímicos", "item alquímico"),
}
# efeito pedido -> variações do trecho que o livro usa
EFEITOS = {
    frozenset({"mana", "pm"}): ("que concede PM temporários", "que recupera PM",
                                "com pontos de mana"),
}
_NUMEROS = {"dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
            "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}


def _quantidade(palavras: list[str]) -> int | None:
    for p in palavras:
        if p.isdigit() and len(p) <= 2:
            return int(p)
    return next((_NUMEROS[p] for p in palavras if p in _NUMEROS), None)


def camadas(texto: str, tabelas: frozenset[str]) -> Camadas | None:
    palavras = chave_texto(texto).split()
    item = next((CATEGORIAS[singular(p)] for p in palavras if singular(p) in CATEGORIAS), None)
    variacoes = next((v for chaves, v in EFEITOS.items() if chaves & set(palavras)), None)
    if item is None or variacoes is None or item[0] not in tabelas:
        return None
    tabela, nome = item
    return Camadas(tabela, tuple(f"{nome} {v}" for v in variacoes), _quantidade(palavras))
