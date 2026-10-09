"""Tipo da pergunta por sinais contáveis: nomes, tabelas, interrogações, conectivos."""

import re

from .dicionario import chave_texto, singular
from .tipos import Ligacao, Restricoes

# Palavras que só aparecem em pergunta de regra de RPG; sem nenhuma delas e
# sem nome ligado, a pergunta não é sobre o jogo.
VOCABULARIO_DO_JOGO = frozenset([
    "teste", "pm", "pv", "dano", "ataque", "defesa", "magia", "pericia", "classe",
    "raca", "nivel", "acao", "rodada", "turno", "cd", "bonus", "penalidade",
    "regra", "personagem", "mestre", "t20", "tormenta", "arton", "deus", "item",
    "arma", "armadura", "condicao", "poder", "habilidade", "critico", "resistencia",
    "atributo", "ficha", "build", "combate", "iniciativa", "deslocamento",
])
PALAVRAS_DE_BUILD = frozenset([
    "combam", "combar", "combo", "combina", "combinar", "combinam", "build", "melhor",
    "otimizar", "maximizar", "sinergia", "montar", "construcao",
])
_RE_CONECTIVO = re.compile(r"\be (?:qual|quais|como|quanto|quantos|quantas|onde)\b"
                           r"|\btambem\b|\balem disso\b")


def classificar(texto: str, ligacoes: tuple[Ligacao, ...], restricoes: Restricoes) -> str:
    """direta | multiparte | build | sem_nome | fora_de_escopo."""
    norma = chave_texto(texto)
    palavras = {singular(p) for p in norma.split()} | set(norma.split())
    if not ligacoes:
        return "sem_nome" if palavras & VOCABULARIO_DO_JOGO else "fora_de_escopo"

    tem_build = bool(palavras & PALAVRAS_DE_BUILD)
    personagem = bool(restricoes.classes or restricoes.racas)
    if personagem and (restricoes.nivel is not None or tem_build):
        return "build"
    if tem_build and len(ligacoes) >= 2:
        return "build"

    tabelas = {lig.chave.tabela for lig in ligacoes}
    registros = {(lig.chave.tabela, lig.chave.nome) for lig in ligacoes}
    # 2+ registros distintos (mesmo da mesma tabela, ex.: "A e B") são 2 necessidades
    if (texto.count("?") >= 2 or _RE_CONECTIVO.search(norma) or len(tabelas) >= 2
            or len(registros) >= 2):
        return "multiparte"
    return "direta"
