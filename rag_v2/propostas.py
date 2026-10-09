"""Fase 6: propostas de apelido geradas a partir dos sinais de uso.

Lê `sinais/sinais.jsonl` (gravado com SINAIS=1) e procura um padrão simples e
verificável: o usuário marcou a resposta como errada/parcial (/errado, /parcial) e,
no texto livre `faltou`, escreveu um nome parecido com um registro do corpus que o
ligador NÃO tinha ligado na pergunta original. Se o mesmo apelido aparece em pelo
menos `MIN_OCORRENCIAS` eventos distintos, vira uma PROPOSTA em
`conhecimento/propostas.yaml` (via `conhecimento.propor`).

Sem LLM, como o resto do analisador: o texto de `faltou` é lido pelo próprio
`rag_v2.ligador`, com os mesmos limiares (0,80 / 0,90) e as mesmas proteções
(palavra real do corpus, âncora). Este módulo SÓ propõe: nada vale no ligador sem
`tools/conhecimento.py aprovar`, feito por uma pessoa.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import conhecimento
from .dicionario import Dicionario, chave_texto
from .ligador import ligar
from .tipos import Chave

CAMINHO_SINAIS = Path("sinais") / "sinais.jsonl"
# Eventos DISTINTOS que precisam repetir o mesmo apelido antes de virar proposta.
MIN_OCORRENCIAS = 2
FEEDBACK_NEGATIVO = ("errado", "parcial")
ONDE_CONFIRMAR = "a confirmar"


@dataclass
class Relatorio:
    caminho: str
    eventos_lidos: int = 0
    feedbacks_negativos: int = 0
    linhas_invalidas: int = 0
    falhas_por_necessidade: list[tuple[str, int]] = field(default_factory=list)
    propostas: list[dict] = field(default_factory=list)
    # motivos por feedback (sem_correspondencia, nome_exato, ja_ligada_na_pergunta) ou por
    # apelido candidato (abaixo_do_minimo, ja_existe, colide_com_nome_real)
    ignoradas: Counter = field(default_factory=Counter)
    simulado: bool = False


def ler_sinais(caminho) -> tuple[dict[str, dict], list[dict], int]:
    """(perguntas por id, feedbacks, linhas inválidas). Arquivo ausente = tudo vazio."""
    caminho = Path(caminho)
    perguntas: dict[str, dict] = {}
    feedbacks: list[dict] = []
    invalidas = 0
    if not caminho.exists():
        return perguntas, feedbacks, invalidas
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            invalidas += 1
            continue
        if not isinstance(evento, dict):
            invalidas += 1
        elif evento.get("tipo") == "pergunta" and evento.get("id"):
            perguntas[evento["id"]] = evento
        elif evento.get("tipo") == "feedback":
            feedbacks.append(evento)
    return perguntas, feedbacks, invalidas


def _ligados_na_pergunta(evento: dict | None) -> set[tuple[str, str]]:
    leitura = (evento or {}).get("leitura") or {}
    return {(lig.get("tabela"), lig.get("nome")) for lig in leitura.get("ligacoes", [])}


def _falhas_por_necessidade(negativos: dict[str, dict], perguntas: dict) -> list[tuple[str, int]]:
    """Quantas perguntas DIFERENTES deixaram a mesma necessidade sem atender."""
    contagem: Counter = Counter()
    for ref, feedback in negativos.items():
        descricoes = (feedback.get("necessidades_nao_atendidas")
                      or (perguntas.get(ref) or {}).get("necessidades_nao_atendidas") or [])
        contagem.update(set(descricoes))
    return sorted(contagem.items(), key=lambda item: (-item[1], item[0]))


def gerar(caminho_sinais, dicionario: Dicionario,
          caminho_propostas=conhecimento.CAMINHO_PROPOSTAS,
          caminho_apelidos=conhecimento.CAMINHO_APELIDOS,
          minimo: int = MIN_OCORRENCIAS, simular: bool = False) -> Relatorio:
    perguntas, feedbacks, invalidas = ler_sinais(caminho_sinais)
    rel = Relatorio(caminho=str(caminho_sinais), eventos_lidos=len(perguntas) + len(feedbacks),
                    linhas_invalidas=invalidas, simulado=simular)

    # um feedback negativo por pergunta (a mesma pergunta avaliada 2x conta 1 vez)
    negativos: dict[str, dict] = {}
    for feedback in feedbacks:
        if feedback.get("valor") in FEEDBACK_NEGATIVO and feedback.get("ref"):
            negativos.setdefault(feedback["ref"], feedback)
    rel.feedbacks_negativos = len(negativos)
    rel.falhas_por_necessidade = _falhas_por_necessidade(negativos, perguntas)

    candidatos: dict[tuple, dict] = defaultdict(lambda: {"refs": set(), "scores": [],
                                                         "necessidades": set()})
    for ref, feedback in negativos.items():
        faltou = (feedback.get("faltou") or "").strip()
        if not faltou:
            continue
        ligacoes = ligar(faltou, dicionario)
        if not ligacoes:
            rel.ignoradas["sem_correspondencia"] += 1
            continue
        ja_ligados = _ligados_na_pergunta(perguntas.get(ref))
        for lig in ligacoes:
            if lig.tipo != "aproximada":
                rel.ignoradas["nome_exato"] += 1   # nome certo: não é apelido
                continue
            if (lig.chave.tabela, lig.chave.nome) in ja_ligados:
                rel.ignoradas["ja_ligada_na_pergunta"] += 1   # a falha não foi de interpretação
                continue
            chave = (chave_texto(lig.trecho), lig.chave.tabela, lig.chave.nome, lig.chave.fonte)
            candidato = candidatos[chave]
            candidato["refs"].add(ref)
            candidato["scores"].append(lig.score)
            candidato["necessidades"].update(
                feedback.get("necessidades_nao_atendidas")
                or (perguntas.get(ref) or {}).get("necessidades_nao_atendidas") or [])

    existentes = {chave_texto(e["apelido"])
                  for e in conhecimento.carregar(caminho_propostas)
                  + conhecimento.carregar(caminho_apelidos)}
    ordenados = sorted(candidatos.items(), key=lambda item: (-len(item[1]["refs"]), item[0]))
    for (apelido, tabela, nome, fonte), info in ordenados:
        refs = sorted(info["refs"])
        if len(refs) < minimo:
            rel.ignoradas["abaixo_do_minimo"] += 1
            continue
        if apelido in existentes:
            rel.ignoradas["ja_existe"] += 1
            continue
        if dicionario.exato(apelido):
            rel.ignoradas["colide_com_nome_real"] += 1
            continue
        media = sum(info["scores"]) / len(info["scores"])
        observado = (
            f"{len(refs)} feedbacks negativos (eventos {', '.join(refs)}): no 'faltou' o "
            f"usuário escreveu algo parecido com {nome} ('{apelido}', ligação aproximada, "
            f"score médio {media:.2f}) e a pergunta original não ligou esse registro. "
            f"Necessidades não atendidas: {'; '.join(sorted(info['necessidades'])) or 'n/d'}. "
            "Gerado de sinais/sinais.jsonl; só vale depois de aprovado.")
        if simular:
            entrada = {"id": "(simulado)", "apelido": apelido, "tabela": tabela, "nome": nome,
                       "fonte": fonte, "observado": observado, "onde_confirmar": ONDE_CONFIRMAR,
                       "status": "proposta", "aprovado_por": None}
        else:
            entrada = conhecimento.propor(
                apelido, Chave(tabela, nome, fonte), observado, ONDE_CONFIRMAR,
                caminho=caminho_propostas, caminho_apelidos=caminho_apelidos)
        existentes.add(apelido)
        rel.propostas.append(entrada)
    return rel


def renderizar(rel: Relatorio) -> str:
    """Resumo para quem roda a CLI de vez em quando."""
    n = len(rel.propostas)
    linhas = [
        f"Sinais lidos de {rel.caminho}: {rel.eventos_lidos} eventos, "
        f"{rel.feedbacks_negativos} perguntas avaliadas como erradas/parciais"
        + (f", {rel.linhas_invalidas} linha(s) inválida(s) ignorada(s)" if rel.linhas_invalidas else ""),
        "",
        (f"{n} proposta{'s' if n != 1 else ''} "
         + ("(SIMULAÇÃO: nada foi gravado)" if rel.simulado else "gravada(s) em conhecimento/propostas.yaml")
         + ":" if n else "Nenhuma proposta nova."),
    ]
    for p in rel.propostas:
        linhas.append(f"  {p['id']}  '{p['apelido']}' -> {p['tabela']} > {p['nome']} [{p['fonte']}]")
        linhas.append(f"      {p['observado']}")
    if n and not rel.simulado:
        linhas += ["", ("Nada disso vale ainda. Para aceitar: "
                        "tools/conhecimento.py aprovar <id> --por <você>; para descartar: recusar.")]
    if rel.falhas_por_necessidade:
        linhas += ["", "Necessidades que mais ficaram sem atender (perguntas distintas):"]
        linhas += [f"  {quantas}x  {descricao}" for descricao, quantas in rel.falhas_por_necessidade[:10]]
    if rel.ignoradas:
        linhas += ["", "Ignorados: " + ", ".join(f"{motivo}={quantas}"
                                                  for motivo, quantas in sorted(rel.ignoradas.items()))]
    return "\n".join(linhas)
