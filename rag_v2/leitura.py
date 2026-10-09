"""Leitura: junta dicionário, ligador, restrições, tipo, necessidades e orçamento.

A confiança decide quanto da v1 continua rodando (opção C, Ponto 1):
alta → pula reformulação e tradução por LLM; média → só a tradução;
baixa → v1 completa, com o top-12 de sempre.

Com a `Sessao` do chat, a leitura também resolve referências pelo foco
("e a CD dela?" → a última entidade discutida) e herda a ficha em perguntas
em primeira pessoa ("isso combina comigo?").
"""

from dataclasses import replace

from .dicionario import Dicionario, chave_texto
from .ligador import PALAVRAS_COMUNS, ambigua, ligar, refinar_por_restricoes
from .necessidades import gerar
from .orcamento import calcular
from .restricoes import extrair_restricoes
from .sessao import Sessao, precisa_de_foco, primeira_pessoa
from .tipo import classificar
from .tipos import Leitura, Ligacao, Restricoes

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
    foco = [lig.trecho for lig in ligacoes if lig.tipo == "foco"]
    if foco:
        motivos.append("referência resolvida pelo foco da sessão: " + ", ".join(foco))
    fracas = [lig for lig in ligacoes
              if lig.tipo == "aproximada" and lig.score < SCORE_CONFIANCA_ALTA]
    if fracas:
        motivos.append("aproximada abaixo de 0,85: " + ", ".join(
            f"{lig.trecho} ({lig.score:.2f})" for lig in fracas))
    if not any(lig.tipo in ("exata", "apelido", "foco") for lig in ligacoes):
        motivos.append("só ligações aproximadas")
    if motivos:
        return "media", tuple(motivos)
    return "alta", ("todas as ligações exatas e sem empate",)


def _resolver_foco(texto: str, sessao: Sessao) -> tuple[str, Ligacao]:
    """'e a CD dela?' + foco Teia -> ('e a CD dela? (Teia)', ligação tipo foco)."""
    nome = sessao.foco.sub or sessao.foco.nome
    resolvido = f"{texto.rstrip()} ({nome})"
    inicio = len(resolvido) - len(nome) - 1
    return resolvido, Ligacao(nome, inicio, inicio + len(nome), sessao.foco, 1.0, "foco")


def _herdar_ficha(restricoes: Restricoes, sessao: Sessao) -> Restricoes:
    ficha = sessao.ficha
    return replace(
        restricoes,
        classes=restricoes.classes or ((ficha.classe,) if ficha.classe else ()),
        racas=restricoes.racas or ((ficha.raca,) if ficha.raca else ()),
        nivel=restricoes.nivel if restricoes.nivel is not None else ficha.nivel,
    )


def ler(texto: str, dicionario: Dicionario, sessao: Sessao | None = None) -> Leitura:
    ligacoes = ligar(texto, dicionario)
    texto_lido, resolvido = texto, None
    if sessao is not None and not ligacoes and sessao.foco and precisa_de_foco(texto):
        resolvido, ligacao_foco = _resolver_foco(texto, sessao)
        texto_lido, ligacoes = resolvido, (ligacao_foco,)

    restricoes = extrair_restricoes(texto_lido, ligacoes)
    extras = []
    if sessao is not None and not sessao.ficha.vazia() and primeira_pessoa(texto):
        restricoes = _herdar_ficha(restricoes, sessao)
        extras.append(f"ficha da sessão herdada: {sessao.ficha.resumo()}")
    ligacoes = refinar_por_restricoes(ligacoes, restricoes)
    tipo = classificar(texto_lido, ligacoes, restricoes)
    necessidades = gerar(ligacoes, restricoes, tipo, dicionario.tabelas)
    confianca, motivos = _confianca(tipo, ligacoes)
    motivos = motivos + tuple(extras)
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
        texto_resolvido=resolvido,
    )
