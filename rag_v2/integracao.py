"""Ponte entre a v2 e o chat/avaliador: flag, dicas ao LLM e o texto do /entendi."""

import os
from collections import Counter

import rag_core

from .tipos import Leitura

MAX_INDISPONIVEIS = 8
# Em pergunta de "qual poder pegar" o LLM tende a despejar todos os registros: pede-se
# uma resposta curta, com recomendação, e a admissão do que a base não cobre.
FORMATO_PODERES = (
    "Formato da resposta (curta, sem repetir o texto dos registros): explique em uma linha por "
    "poder da RECOMENDAÇÃO, usando o registro dele no contexto. PROIBIDO citar, recomendar ou "
    "listar qualquer poder que não esteja na RECOMENDAÇÃO, ou mudar a situação de algum; depois responda os demais pontos da pergunta e diga o que a "
    "base não cobre.")

ARQUITETURAS = ("v1", "v2")


def arquitetura() -> str:
    """ARQUITETURA do ambiente; qualquer valor fora de v1/v2 vale v1 (padrão)."""
    valor = os.environ.get("ARQUITETURA", "").strip().lower()
    return valor if valor in ARQUITETURAS else "v1"


def usar_v2(leitura: Leitura | None) -> bool:
    """A v2 só assume com a flag ligada e confiança acima de baixa (fallback total)."""
    return arquitetura() == "v2" and leitura is not None and leitura.confianca != "baixa"


def _ficha(leitura: Leitura) -> str:
    r = leitura.restricoes
    partes = [*r.classes, *r.racas]
    if r.nivel is not None:
        partes.append(f"nível {r.nivel}")
    partes += [*r.pericias, *r.itens]
    return ", ".join(partes)


def _exibicao(normalizado: str, poderes) -> str:
    return next((p.nome for p in poderes if rag_core.normalizar(p.nome).strip() == normalizado),
                normalizado.capitalize())


def secao_poderes(leitura: Leitura) -> str:
    """Todos os poderes da classe e a situação de cada um (calculado, não buscado)."""
    if not leitura.poderes:
        return ""
    classe = leitura.restricoes.classes[0]
    por_status = {s: [p for p in leitura.poderes if p.status == s]
                  for s in ("disponivel", "encadeado", "indeterminado", "indisponivel")}
    linhas = [(f"PODERES DE {classe.upper()} (nível {leitura.restricoes.nivel}) — calculado pelo "
               "sistema a partir dos pré-requisitos do livro, para a ficha informada. Use esta lista "
               "para dizer QUAIS poderes existem e quais o personagem pode pegar; o efeito de um poder "
               "só pode ser descrito se o texto dele estiver no contexto.")]
    if por_status["disponivel"]:
        linhas.append("Pode pegar agora: " + ", ".join(p.nome for p in por_status["disponivel"]))
    if por_status["encadeado"]:
        linhas.append("Pode pegar depois de escolher outro poder: " + "; ".join(
            f"{p.nome} (precisa de {', '.join(_exibicao(e, leitura.poderes) for e in p.encadeados)})"
            for p in por_status["encadeado"]))
    if por_status["indeterminado"]:
        linhas.append("Depende de confirmar a ficha: " + "; ".join(
            f"{p.nome} ({'; '.join(p.pendencias + p.notas)})" for p in por_status["indeterminado"]))
    if por_status["indisponivel"]:
        mostrados = por_status["indisponivel"][:MAX_INDISPONIVEIS]
        resto = len(por_status["indisponivel"]) - len(mostrados)
        linhas.append("Não pode pegar ainda: " + "; ".join(
            f"{p.nome} ({'; '.join(p.pendencias)})" for p in mostrados)
            + (f"; e mais {resto}" if resto else ""))
    return "\n".join(linhas)


def _dicas_da_lista(leitura: Leitura) -> str:
    """Pergunta em camadas: lista só o que o contexto prova e diz quantos achou."""
    c = leitura.camadas
    pedido = f"{c.quantidade} " if c.quantidade else ""
    buscas = "; ".join(c.subconsultas)
    return (
        "\n\n[LISTA DE VERIFICAÇÃO DA PERGUNTA — gerada pelo sistema, não pelo usuário]\n"
        f"O jogador pediu {pedido}itens de {c.tabela} com um efeito. O sistema buscou: {buscas}.\n"
        "Liste SOMENTE os itens do contexto cujo texto traz esse efeito (ex.: \"PM temporários\", "
        "recuperação de PM), cada um com o efeito e a citação [Tabela > Fonte] copiada dele. "
        "Se achar menos do que o pedido, diga quantos achou — não complete a lista com itens "
        "sem esse efeito nem com conhecimento externo.]"
    )


def bloco_dicas(leitura: Leitura) -> str:
    """Lista de verificação anexada à entrada da síntese (o SYSTEM_PROMPT não muda).

    Pede cobertura item a item OU a declaração de que a base não cobre — nunca
    preenchimento com conhecimento externo.
    """
    if leitura.confianca == "baixa" or not leitura.necessidades:
        return ""
    necessidades = leitura.necessidades
    if leitura.poderes:   # os poderes já estão na seção própria; sem despejar um item por poder
        necessidades = tuple(n for n in necessidades
                             if not n.descricao.startswith("poder ")
                             and "poderes gerais" not in n.descricao.lower()
                             and not (n.registro is None and n.tabela_alvo.startswith("Poderes (")))
    if leitura.camadas:
        return _dicas_da_lista(leitura)
    itens = "\n".join(f"{i}) {n.descricao}" + ("" if n.obrigatoria else " (se houver)")
                      for i, n in enumerate(necessidades, 1))
    ficha = _ficha(leitura)
    linha_ficha = f"Personagem/contexto da pergunta: {ficha}.\n" if ficha else ""
    poderes = secao_poderes(leitura)
    linha_poderes = (f"{poderes}\n{leitura.recomendacao}\n{FORMATO_PODERES}\n"
                     if poderes else "")
    return (
        "\n\n[LISTA DE VERIFICAÇÃO DA PERGUNTA — gerada pelo sistema, não pelo usuário]\n"
        f"{linha_ficha}{linha_poderes}A resposta deve cobrir:\n{itens}\n"
        "Para cada item, use SOMENTE o contexto, com a citação [Tabela > Fonte] "
        "copiada dele; se o contexto não trouxer o item, diga explicitamente que "
        "a base consultada não cobre esse ponto. Nunca complete com conhecimento externo.]"
    )


def descrever(leitura: Leitura | None, telemetria: dict | None) -> str:
    """Texto do /entendi: o que o analisador leu e o que a recuperação garantiu."""
    if leitura is None:
        return "Nenhuma pergunta lida ainda (faça uma pergunta de regra primeiro)."
    linhas = [f"Pergunta: {leitura.texto_original}",
              (f"Tipo: {leitura.tipo} | confiança: {leitura.confianca} | "
               f"LLM de reformulação/tradução: {leitura.usar_llm} | orçamento: k={leitura.k}")]
    if leitura.motivos:
        linhas.append("Motivos: " + "; ".join(leitura.motivos))
    linhas.append("Nomes reconhecidos:" if leitura.ligacoes else "Nomes reconhecidos: nenhum")
    for lig in leitura.ligacoes:
        sub = f" > {lig.chave.sub}" if lig.chave.sub else ""
        linhas.append(f"  '{lig.trecho}' -> {lig.chave.tabela} > {lig.chave.nome}{sub} "
                      f"[{lig.chave.fonte}] ({lig.tipo}, {lig.score:.2f})")
        for alt in lig.alternativas:
            linhas.append(f"      alternativa: {alt.tabela} > {alt.nome} [{alt.fonte}]")
    ficha = _ficha(leitura)
    linhas.append(f"Restrições: {ficha or 'nenhuma'}")
    atendidas = {}
    if telemetria:
        atendidas = {n["descricao"]: n["atendida"] for n in telemetria["necessidades"]}
    if leitura.poderes:
        contagem = Counter(p.status for p in leitura.poderes)
        linhas.append(
            f"Poderes de {leitura.restricoes.classes[0]}: {len(leitura.poderes)} avaliados — "
            f"{contagem['disponivel']} disponíveis, {contagem['encadeado']} encadeados, "
            f"{contagem['indeterminado']} a confirmar, {contagem['indisponivel']} indisponíveis")
    if leitura.necessidades:
        linhas.append("Necessidades:")
    for n in leitura.necessidades:
        marca = "" if not telemetria else (
            " — atendida" if atendidas.get(n.descricao) else " — NÃO atendida")
        opcional = "" if n.obrigatoria else " (opcional)"
        linhas.append(f"  - {n.descricao} [{n.tabela_alvo}]{opcional}{marca}")
    if telemetria:
        linhas.append(f"Recuperação v2: {telemetria['candidatos']} candidatos, "
                      f"{telemetria['garantidos']} vagas garantidas, k={telemetria['k']}, "
                      f"reranker={telemetria['reranker']}")
    elif arquitetura() == "v2":
        linhas.append("Recuperação: v1 (confiança baixa → fallback total)")
    else:
        linhas.append("Recuperação: v1 (ARQUITETURA=v1; a leitura é só informativa)")
    return "\n".join(linhas)
