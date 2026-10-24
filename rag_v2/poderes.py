"""Listar e filtrar os poderes de uma classe para um personagem.

A busca por semelhança devolve os poderes mais parecidos com a pergunta (3 de 52, no
caso do Inventor). "Qual poder pegar?" pede o contrário: TODOS os poderes da classe,
cada um conferido contra a ficha, e só então os mais relevantes ao tema. Este módulo
faz essa conta em Python, a partir do texto do próprio livro (pré-requisitos).
"""

import re

import rag_core

from .catalogo import Catalogo
from .requisitos import Ficha, avaliar, interpretar
from .tipos import PoderAvaliado

MAX_NO_CONTEXTO = 8
MIN_NO_CONTEXTO = 3
_ORDEM = {"disponivel": 0, "encadeado": 1, "indeterminado": 2, "indisponivel": 3}
_PALAVRAS_VAZIAS = frozenset(["para", "qual", "quais", "como", "quero", "queria", "gostaria", "comecar", "sobre", "minha", "meu", "seus", "suas", "isso", "esse", "essa", "todos", "todas", "tenho", "sendo", "ainda", "melhor", "melhores", "pegar", "escolher", "poder", "poderes", "habilidade", "habilidades", "atributo", "principal", "nivel", "pode", "posso", "devo", "uma", "umas", "uns", "com", "por", "que", "mais", "menos"])
# Gíria de jogador -> radical que o livro usa. Pequeno de propósito: cresce com os sinais.
_SINONIMOS = {"craft": "fabri", "craftar": "fabri", "criar": "fabri", "construir": "fabri",
              "forjar": "ferre", "consertar": "repar"}
_RE_PALAVRA = re.compile(r"[a-z]{4,}")


def _radicais(texto: str) -> set[str]:
    palavras = _RE_PALAVRA.findall(rag_core.normalizar(texto or ""))
    return {_SINONIMOS.get(p, p)[:5] for p in palavras if p not in _PALAVRAS_VAZIAS}


def tema_da_pergunta(texto: str, classe: str) -> frozenset[str]:
    """Radicais (5 letras) das palavras que dizem O QUE o jogador quer (sem o nome da classe)."""
    return frozenset(_radicais(texto) - _radicais(classe))


def _ficha_efetiva(ficha: Ficha, pericias_classe: dict[str, set[str]]) -> Ficha:
    """Perícias obrigatórias da classe já vêm treinadas (Ofício não: exige escolher qual)."""
    obrigatorias = pericias_classe.get("obrigatorias", set()) - {"oficio"}
    return Ficha(classe=ficha.classe, nivel=ficha.nivel, atributos=ficha.atributos,
                 oficios=ficha.oficios, todos_oficios=ficha.todos_oficios,
                 pericias=ficha.pericias | obrigatorias, poderes=ficha.poderes,
                 raca=ficha.raca, devoto=ficha.devoto)


def listar(catalogo: Catalogo, classe: str, ficha: Ficha,
           tema: frozenset[str] = frozenset()) -> list[PoderAvaliado]:
    """Todos os poderes da classe, ordenados: situação, relevância ao tema, nome."""
    tabela = catalogo.tabela_de_poderes(classe)
    if tabela is None:
        return []
    pericias = catalogo.pericias_classe.get(rag_core.normalizar(classe).strip(), {})
    efetiva = _ficha_efetiva(ficha, pericias)
    opcionais = pericias.get("opcionais", set())
    saida = []
    for poder in catalogo.poderes[tabela]:
        itens = interpretar(poder.prerequisito, catalogo.nomes_poderes, catalogo.racas)
        resultado = avaliar(itens, efetiva)
        notas = tuple(
            f"{r.a.capitalize()} está entre as perícias opcionais de {classe}"
            for alternativas in itens for r in alternativas
            if r.tipo == "treinado" and r.a != "oficio" and r.a in opcionais
            and r.a not in efetiva.pericias)
        relevancia = len(tema & _radicais(f"{poder.nome} {poder.descricao}"))
        saida.append(PoderAvaliado(
            nome=poder.nome, tabela=poder.tabela, fonte=poder.fonte, status=resultado.status,
            prerequisito=poder.prerequisito, pendencias=tuple(resultado.pendencias),
            encadeados=tuple(resultado.encadeados), notas=notas, relevancia=relevancia))
    return sorted(saida, key=lambda p: (_ORDEM[p.status], -p.relevancia, p.nome))


def escolher_para_contexto(poderes: list[PoderAvaliado],
                           maximo: int = MAX_NO_CONTEXTO) -> list[PoderAvaliado]:
    """Os poderes que merecem texto completo no contexto: pegáveis (não indisponíveis) e
    relevantes ao tema da pergunta. Com poucos relevantes, completa com os primeiros
    pegáveis (até MIN_NO_CONTEXTO) para a resposta não ficar vazia."""
    pegaveis = [p for p in poderes if p.status != "indisponivel"]
    pegaveis.sort(key=lambda p: (-p.relevancia, _ORDEM[p.status], p.nome))
    relevantes = [p for p in pegaveis if p.relevancia > 0]
    if len(relevantes) >= MIN_NO_CONTEXTO:
        return relevantes[:maximo]
    resto = [p for p in pegaveis if p.relevancia == 0]
    return (relevantes + resto)[:max(MIN_NO_CONTEXTO + 1, len(relevantes))]
