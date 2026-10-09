"""Leitura: junta dicionário, ligador, restrições, tipo, necessidades e orçamento.

A confiança decide quanto da v1 continua rodando (opção C, Ponto 1):
alta → pula reformulação e tradução por LLM; média → só a tradução;
baixa → v1 completa, com o top-12 de sempre.
"""

from .dicionario import Dicionario, chave_texto
from .ligador import PALAVRAS_COMUNS, ambigua, ligar, refinar_por_restricoes
from .necessidades import gerar
from .orcamento import calcular
from .restricoes import extrair_restricoes
from .tipo import classificar
from .tipos import Leitura, Ligacao

# Aproximada abaixo disso não sustenta confiança alta (Ponto 1).
SCORE_CONFIANCA_ALTA = 0.85
LLM_POR_CONFIANCA = {"alta": "nenhum", "media": "traducao", "baixa": "completo"}


def _confianca(tipo: str, ligacoes: tuple[Ligacao, ...]) -> tuple[str, tuple[str, ...]]:
    if tipo in ("sem_nome", "fora_de_escopo"):
        return "baixa", (f"tipo {tipo}",)
    comuns = [lig.trecho for lig in ligacoes if chave_texto(lig.trecho) in PALAVRAS_COMUNS]
    if comuns:
        return "baixa", ("ligado só por palavra comum: " + ", ".join(comuns),)

    motivos = []
    # Empate sem desempate não derruba a leitura: a política traz todas as
    # alternativas como necessidades (cada uma com vaga), só tira a confiança alta.
    empates = [lig.trecho for lig in ligacoes if ambigua(lig)]
    if empates:
        motivos.append("empate sem desempate (traz todas): " + ", ".join(empates))
    fracas = [lig for lig in ligacoes
              if lig.tipo == "aproximada" and lig.score < SCORE_CONFIANCA_ALTA]
    if fracas:
        motivos.append("aproximada abaixo de 0,85: " + ", ".join(
            f"{lig.trecho} ({lig.score:.2f})" for lig in fracas))
    if not any(lig.tipo in ("exata", "apelido") for lig in ligacoes):
        motivos.append("só ligações aproximadas")
    if motivos:
        return "media", tuple(motivos)
    return "alta", ("todas as ligações exatas e sem empate",)


def ler(texto: str, dicionario: Dicionario) -> Leitura:
    ligacoes = ligar(texto, dicionario)
    restricoes = extrair_restricoes(texto, ligacoes)
    ligacoes = refinar_por_restricoes(ligacoes, restricoes)
    tipo = classificar(texto, ligacoes, restricoes)
    necessidades = gerar(ligacoes, restricoes, tipo, dicionario.tabelas)
    confianca, motivos = _confianca(tipo, ligacoes)
    return Leitura(
        texto_original=texto,
        ligacoes=ligacoes,
        restricoes=restricoes,
        tipo=tipo,
        necessidades=necessidades,
        k=calcular(tipo, necessidades, confianca),
        confianca=confianca,
        motivos=motivos,
        usar_llm=LLM_POR_CONFIANCA[confianca],
    )
