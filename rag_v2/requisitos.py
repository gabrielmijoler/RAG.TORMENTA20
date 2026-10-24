"""Pré-requisitos de poderes: lê o texto livre do livro e confere contra uma ficha.

O corpus guarda o pré-requisito como frase ("treinado em Luta e Ofício (armeiro)",
"Armeiro, 5º nível de inventor", "Int 3, Sab 3"). Aqui a frase vira requisitos
tipados e cada um é conferido contra o que SE SABE do personagem. Regra central:
o que a ficha não diz nunca é presumido. Só um impedimento DEFINITIVO (nível ou
atributo menor, raça ou devoção diferente) torna o poder indisponível; o resto fica
`indeterminado` (falta informação) ou `encadeado` (falta escolher outro poder antes).

Sem LLM: é um leitor de padrões sobre o texto do próprio corpus.
"""

import re
from dataclasses import dataclass, field

import rag_core

_SIGLAS = {"for": "for", "des": "des", "con": "con", "int": "int", "sab": "sab", "car": "car"}
_RE_ATRIBUTO = re.compile(r"(for|des|con|int|sab|car)[a-z]*\s*(\d+)")
_RE_NIVEL = re.compile(r"(\d+)\s*[o°º]?\s*nivel de (.+)")
_RE_CIRCULO = re.compile(r"lancar magias de (\d+)\s*[o°º]?\s*circulo")
_RE_DEVOTO = re.compile(r"devot[oa] d[eao]s? (.+)")
_RE_TREINADO = re.compile(r"treinad[oa] em (.+)")
_RE_PERICIA = re.compile(r"(.+?)\s*(?:\((.+)\))?")


@dataclass(frozen=True)
class Requisito:
    tipo: str          # atributo | nivel | treinado | poder | raca | devoto | circulo | desconhecido
    texto: str         # trecho original (para mensagens)
    a: str | None = None     # sigla / classe / perícia / poder / raça / deus (normalizado)
    sub: str | None = None   # subtipo (ex.: Ofício (armeiro) -> "armeiro")
    n: int | None = None


@dataclass
class Ficha:
    """O que se sabe do personagem. Campo vazio = DESCONHECIDO, não 'não tem'."""

    classe: str | None = None
    nivel: int | None = None
    atributos: dict[str, int] = field(default_factory=dict)
    oficios: set[str] = field(default_factory=set)
    todos_oficios: bool = False
    pericias: set[str] = field(default_factory=set)
    poderes: set[str] = field(default_factory=set)
    raca: str | None = None
    devoto: str | None = None


@dataclass
class Resultado:
    status: str                       # disponivel | encadeado | indeterminado | indisponivel
    pendencias: list[str] = field(default_factory=list)
    encadeados: list[str] = field(default_factory=list)


def _n(texto: str) -> str:
    """Minúsculas, sem acento, espaços colapsados, sem ponto final (mantém parênteses)."""
    return " ".join(rag_core.normalizar(texto or "").split()).strip(" .")


def _fora_dos_parenteses(texto: str, separador: str) -> list[str]:
    """Divide em `separador` ignorando o que está entre parênteses."""
    partes, atual, nivel, i = [], "", 0, 0
    while i < len(texto):
        c = texto[i]
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel = max(0, nivel - 1)
        if nivel == 0 and texto.startswith(separador, i):
            partes.append(atual)
            atual, i = "", i + len(separador)
            continue
        atual += c
        i += 1
    partes.append(atual)
    return [p.strip() for p in partes if p.strip()]


def _pericia(trecho: str) -> Requisito:
    m = _RE_PERICIA.fullmatch(_n(trecho))
    nome, sub = (m.group(1), m.group(2)) if m else (_n(trecho), None)
    return Requisito("treinado", trecho.strip(), a=nome.strip(), sub=sub)


def _alternativas(trecho: str, poderes: frozenset[str], racas: frozenset[str]) -> list[Requisito]:
    """Um item do pré-requisito: uma lista de alternativas (qualquer uma serve)."""
    norma = _n(trecho)
    if norma in poderes:
        return [Requisito("poder", trecho.strip(), a=norma)]
    saida = []
    for pedaco in _fora_dos_parenteses(trecho, " ou "):
        p = _n(pedaco)
        if p in poderes:
            saida.append(Requisito("poder", pedaco, a=p))
        elif p in racas:
            saida.append(Requisito("raca", pedaco, a=p))
        else:
            saida.append(Requisito("desconhecido", pedaco))
    return saida


def interpretar(texto: str | None, poderes: frozenset[str],
                racas: frozenset[str]) -> list[list[Requisito]]:
    """Lista de itens (todos exigidos); cada item é uma lista de alternativas (qualquer uma)."""
    texto = (texto or "").strip().strip(".")
    if not texto or texto in {"—", "-", "–"}:
        return []
    poderes = frozenset(_n(p) for p in poderes)
    racas = frozenset(_n(r) for r in racas)
    itens: list[list[Requisito]] = []
    for parte in _fora_dos_parenteses(texto, ","):
        p = _n(parte)
        if (m := _RE_ATRIBUTO.fullmatch(p)):
            itens.append([Requisito("atributo", parte, a=_SIGLAS[m.group(1)], n=int(m.group(2)))])
        elif (m := _RE_NIVEL.fullmatch(p)):
            itens.append([Requisito("nivel", parte, a=m.group(2).strip(), n=int(m.group(1)))])
        elif (m := _RE_CIRCULO.fullmatch(p)):
            itens.append([Requisito("circulo", parte, n=int(m.group(1)))])
        elif (m := _RE_DEVOTO.fullmatch(p)):
            itens.append([Requisito("devoto", parte, a=m.group(1).strip())])
        elif _RE_TREINADO.fullmatch(p):
            resto = parte.split(None, 2)[2]               # depois de "treinado em"
            for pedaco in _fora_dos_parenteses(resto, " e "):
                itens.append([_pericia(alt) for alt in _fora_dos_parenteses(pedaco, " ou ")])
        else:
            itens.append(_alternativas(parte, poderes, racas))
    return itens


# --- avaliação -----------------------------------------------------------------------------

def _um(req: Requisito, ficha: Ficha) -> tuple[str, str | None]:
    """(estado, mensagem): estado em ok | falta | ? | encadeado."""
    if req.tipo == "atributo":
        tem = ficha.atributos.get(req.a)
        if tem is None:
            return "?", f"informar {req.a.capitalize()} (exige {req.texto})"
        return ("ok", None) if tem >= req.n else (
            "falta", f"{req.texto} (você tem {tem})")
    if req.tipo == "nivel":
        if ficha.nivel is None or ficha.classe is None:
            return "?", f"informar classe e nível (exige {req.texto})"
        if _n(ficha.classe) != req.a:
            return "falta", f"{req.texto} (você é {ficha.classe})"
        return ("ok", None) if ficha.nivel >= req.n else (
            "falta", f"{req.texto} (você é nível {ficha.nivel})")
    if req.tipo == "treinado":
        if req.a == "oficio":
            if ficha.todos_oficios or (req.sub and req.sub in ficha.oficios):
                return "ok", None
        elif req.a in ficha.pericias:
            return "ok", None
        return "?", f"confirmar treinamento: {req.texto}"
    if req.tipo == "poder":
        return ("ok", None) if req.a in ficha.poderes else ("encadeado", req.texto)
    if req.tipo == "raca":
        if ficha.raca is None:
            return "?", f"informar a raça (exige {req.texto})"
        return ("ok", None) if _n(ficha.raca) == req.a else (
            "falta", f"raça {req.texto} (você é {ficha.raca})")
    if req.tipo == "devoto":
        if ficha.devoto is None:
            return "?", f"informar a divindade ({req.texto})"
        return ("ok", None) if _n(ficha.devoto) == req.a else (
            "falta", f"{req.texto} (você é devoto de {ficha.devoto})")
    return "?", f"conferir no livro: {req.texto}"      # circulo e desconhecido


_PRIORIDADE = {"ok": 0, "?": 1, "encadeado": 2, "falta": 3}


def avaliar(itens: list[list[Requisito]], ficha: Ficha) -> Resultado:
    estados: list[str] = []
    pendencias: list[str] = []
    encadeados: list[str] = []
    for alternativas in itens:
        avaliados = [_um(r, ficha) for r in alternativas]
        melhor = min(range(len(avaliados)), key=lambda i: _PRIORIDADE[avaliados[i][0]])
        estado, mensagem = avaliados[melhor]
        estados.append(estado)
        if estado == "encadeado":
            encadeados.append(alternativas[melhor].a)
        elif estado in ("?", "falta") and mensagem:
            pendencias.append(mensagem)
    if "falta" in estados:
        status = "indisponivel"
    elif "?" in estados:
        status = "indeterminado"
    elif "encadeado" in estados:
        status = "encadeado"
    else:
        status = "disponivel"
    return Resultado(status, pendencias, encadeados)
