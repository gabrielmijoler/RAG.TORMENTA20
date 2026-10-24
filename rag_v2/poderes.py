"""Listar e filtrar os poderes de uma classe para um personagem.

A busca por semelhança devolve os poderes mais parecidos com a pergunta (3 de 52, no
caso do Inventor). "Qual poder pegar?" pede o contrário: TODOS os poderes da classe,
cada um conferido contra a ficha, e só então os mais relevantes ao tema. Este módulo
faz essa conta em Python, a partir do texto do próprio livro (pré-requisitos).
"""

import math
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
_RE_FRASE = re.compile(r"(.+?[.!?])(?:\s|$)")
MAX_RESUMO = 220
MAX_RECOMENDADOS = 5


def _radicais(texto: str) -> set[str]:
    palavras = _RE_PALAVRA.findall(rag_core.normalizar(texto or ""))
    return {_SINONIMOS.get(p, p)[:5] for p in palavras if p not in _PALAVRAS_VAZIAS}


def tema_da_pergunta(texto: str, classe: str) -> frozenset[str]:
    """Radicais (5 letras) das palavras que dizem O QUE o jogador quer (sem o nome da classe)."""
    return frozenset(_radicais(texto) - _radicais(classe))


def _resumo(descricao: str) -> str:
    """Primeira frase da descrição (o suficiente para o LLM explicar sem despejar o registro)."""
    m = _RE_FRASE.match(descricao or "")
    frase = m.group(1) if m else (descricao or "")
    return frase if len(frase) <= MAX_RESUMO else frase[:MAX_RESUMO].rstrip() + "…"


def _pesos(catalogo_poderes) -> dict[str, float]:
    """Peso de cada radical = log(N/df) entre os poderes da classe: palavra rara pesa mais."""
    radicais = [_radicais(f"{p.nome} {p.descricao}") for p in catalogo_poderes]
    contagem: dict[str, int] = {}
    for conjunto in radicais:
        for r in conjunto:
            contagem[r] = contagem.get(r, 0) + 1
    return {r: math.log(len(radicais) / n) + 0.1 for r, n in contagem.items()}


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
    pesos = _pesos(catalogo.poderes[tabela])
    for poder in catalogo.poderes[tabela]:
        itens = interpretar(poder.prerequisito, catalogo.nomes_poderes, catalogo.racas)
        resultado = avaliar(itens, efetiva)
        notas = tuple(
            f"{r.a.capitalize()} está entre as perícias opcionais de {classe}"
            for alternativas in itens for r in alternativas
            if r.tipo == "treinado" and r.a != "oficio" and r.a in opcionais
            and r.a not in efetiva.pericias)
        # o nome vale o dobro: um poder chamado "Armeiro" é sobre armeiro
        relevancia = (sum(pesos[r] for r in tema & _radicais(poder.descricao))
                      + 2 * sum(pesos[r] for r in tema & _radicais(poder.nome)))
        saida.append(PoderAvaliado(
            nome=poder.nome, tabela=poder.tabela, fonte=poder.fonte, status=resultado.status,
            prerequisito=poder.prerequisito, pendencias=tuple(resultado.pendencias),
            encadeados=tuple(resultado.encadeados), notas=notas, relevancia=round(relevancia, 3), resumo=_resumo(poder.descricao)))
    return sorted(saida, key=lambda p: (_ORDEM[p.status], -p.relevancia, p.nome))


def escolher_para_contexto(poderes: list[PoderAvaliado],
                           maximo: int = MAX_NO_CONTEXTO) -> list[PoderAvaliado]:
    """Os poderes que merecem texto completo no contexto: pegáveis (não indisponíveis) e
    relevantes ao tema da pergunta. Com poucos relevantes, completa com os primeiros
    pegáveis (até MIN_NO_CONTEXTO) para a resposta não ficar vazia. Cada poder escolhido
    leva junto o texto dos poderes que são seu pré-requisito (a resposta precisa explicar a
    cadeia), por isso o total pode passar de `maximo`."""
    pegaveis = [p for p in poderes if p.status != "indisponivel"]
    pegaveis.sort(key=lambda p: (-p.relevancia, _ORDEM[p.status], p.nome))
    relevantes = [p for p in pegaveis if p.relevancia > 0]
    if len(relevantes) >= MIN_NO_CONTEXTO:
        escolhidos = relevantes[:maximo]
    else:
        resto = [p for p in pegaveis if p.relevancia == 0]
        escolhidos = (relevantes + resto)[:max(MIN_NO_CONTEXTO + 1, len(relevantes))]
    por_nome = {rag_core.normalizar(p.nome).strip(): p for p in poderes}
    nomes = {p.nome for p in escolhidos}
    for poder in list(escolhidos):
        for exigido in poder.encadeados:
            pre = por_nome.get(exigido)
            if pre is not None and pre.nome not in nomes and pre.status != "indisponivel":
                escolhidos.append(pre)
                nomes.add(pre.nome)
    return escolhidos


def recomendar(poderes: list[PoderAvaliado], maximo: int = MAX_RECOMENDADOS) -> list[PoderAvaliado]:
    """Os melhores poderes para o tema: relevantes, não indisponíveis, mais relevante primeiro.
    Sem tema (relevância 0 em todos) não recomenda nada: não chuta."""
    candidatos = [p for p in poderes if p.status != "indisponivel" and p.relevancia > 0]
    candidatos.sort(key=lambda p: (-p.relevancia, _ORDEM[p.status], p.nome))
    return candidatos[:maximo]


def _situacao(p: PoderAvaliado, todos: list[PoderAvaliado]) -> str:
    if p.status == "disponivel":
        return "pode pegar agora"
    if p.status == "encadeado":
        por_nome = {rag_core.normalizar(t.nome).strip(): t.nome for t in todos}
        return "só depois de escolher " + ", ".join(por_nome.get(e, e) for e in p.encadeados)
    return "depende da ficha: " + "; ".join(p.pendencias + p.notas)


def escrever_recomendacao(recomendados: list[PoderAvaliado], todos: list[PoderAvaliado],
                          ficha: Ficha, niveis_com_escolha: list[int] | None) -> str:
    """Texto fechado da recomendação: o código decide QUAIS poderes e a situação de cada um."""
    if not recomendados:
        return ""
    linhas = ["RECOMENDAÇÃO (calculada pelo sistema; explique, não troque os poderes):"]
    if niveis_com_escolha:
        linhas.append(f"Até o nível {ficha.nivel} você escolhe {len(niveis_com_escolha)} poderes "
                      f"de {ficha.classe} (níveis {', '.join(map(str, niveis_com_escolha))}).")
    if ficha.atributos:
        valores = ", ".join(f"{k.upper()} {v}" for k, v in ficha.atributos.items())
        linhas.append(f"Atributo informado: {valores} — no livro esse número já é o modificador "
                      "(teste = 1d20 + atributo), não o valor bruto.")
    for i, p in enumerate(recomendados, 1):
        linhas.append(f"{i}. {p.nome} — {_situacao(p, todos)}. {p.resumo}")
    return "\n".join(linhas)
