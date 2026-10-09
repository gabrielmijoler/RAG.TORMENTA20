"""Ponte entre a v2 e o chat/avaliador: flag, dicas ao LLM e o texto do /entendi."""

import os

from .tipos import Leitura

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


def bloco_dicas(leitura: Leitura) -> str:
    """Lista de verificação anexada à entrada da síntese (o SYSTEM_PROMPT não muda).

    Pede cobertura item a item OU a declaração de que a base não cobre — nunca
    preenchimento com conhecimento externo.
    """
    if leitura.confianca == "baixa" or not leitura.necessidades:
        return ""
    itens = "\n".join(f"{i}) {n.descricao}" + ("" if n.obrigatoria else " (se houver)")
                      for i, n in enumerate(leitura.necessidades, 1))
    ficha = _ficha(leitura)
    linha_ficha = f"Personagem/contexto da pergunta: {ficha}.\n" if ficha else ""
    return (
        "\n\n[LISTA DE VERIFICAÇÃO DA PERGUNTA — gerada pelo sistema, não pelo usuário]\n"
        f"{linha_ficha}A resposta deve cobrir:\n{itens}\n"
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
