"""Sinais de uso real: um evento JSONL por pergunta e por feedback.

Atrás da flag SINAIS=1 (desligado por padrão). Arquivo local, fora do git
(`sinais/sinais.jsonl`), sem chaves de API nem dados pessoais: guarda a
pergunta, a leitura, os registros recuperados com score, o estado da citação,
se a resposta disse "não há", o tempo por etapa e o feedback do usuário.
É a matéria-prima da fila de falhas e das propostas de aprendizado.
"""

import datetime as dt
import json
import os
import re
import uuid
from pathlib import Path

import rag_core

from .dicionario import chave_texto
from .tipos import Leitura

CAMINHO = Path("sinais") / "sinais.jsonl"
_LIGADO = ("1", "true", "sim", "on")
_RE_NAO_HA = re.compile(
    r"\bnao (?:ha|cobre|contem|consta|encontrei|traz)\b|\bbase consultada nao\b")


def ativo() -> bool:
    return os.environ.get("SINAIS", "").strip().lower() in _LIGADO


def estado_citacao(resposta: str, contexto: str) -> str:
    """ok | fora | sem_citacao | vazia — mesma régua do avaliador."""
    if not (resposta or "").strip():
        return "vazia"
    if not rag_core.citacoes_em(resposta):
        return "sem_citacao"
    _, fora = rag_core.partir_citacoes(resposta, contexto)
    return "fora" if fora else "ok"


def disse_nao_ha(resposta: str) -> bool:
    return bool(_RE_NAO_HA.search(chave_texto(resposta or "")))


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def montar_evento(leitura: Leitura | None, docs: list, resposta: str, tempos: dict,
                  telemetria: dict | None, arquitetura: str,
                  pergunta: str | None = None) -> dict:
    contexto = "\n".join(getattr(d, "page_content", str(d)) for d in docs)
    nao_atendidas = [n["descricao"] for n in (telemetria or {}).get("necessidades", [])
                     if n["obrigatoria"] and not n["atendida"]]
    return {
        "tipo": "pergunta",
        "id": uuid.uuid4().hex[:12],
        "ts": _agora(),
        "arquitetura": arquitetura,
        "pergunta": leitura.texto_original if leitura else pergunta,
        "leitura": None if leitura is None else {
            "tipo": leitura.tipo, "confianca": leitura.confianca, "k": leitura.k,
            "usar_llm": leitura.usar_llm, "motivos": list(leitura.motivos),
            "texto_resolvido": leitura.texto_resolvido,
            "ligacoes": [{"trecho": lig.trecho, "tabela": lig.chave.tabela,
                          "nome": lig.chave.nome, "sub": lig.chave.sub,
                          "tipo": lig.tipo, "score": lig.score,
                          "ambigua": bool(lig.alternativas)} for lig in leitura.ligacoes],
            "necessidades": [n.descricao for n in leitura.necessidades],
        },
        "docs": [{"tabela": d.metadata.get("Tabela"), "nome": d.metadata.get("Nome"),
                  "fonte": d.metadata.get("Fonte"),
                  "score": round(float(d.metadata.get("relevance_score") or 0), 4)}
                 for d in docs],
        "recuperacao": telemetria,
        "necessidades_nao_atendidas": nao_atendidas,
        "estado_citacao": estado_citacao(resposta, contexto),
        "nao_ha": disse_nao_ha(resposta),
        "tempos_s": {k: round(v, 2) for k, v in tempos.items()},
    }


def feedback(evento: dict, valor: str, faltou: str | None = None) -> dict:
    """Sinal FORTE (comando /errado ou /parcial) sobre a última pergunta."""
    return {"tipo": "feedback", "id": uuid.uuid4().hex[:12], "ts": _agora(),
            "ref": evento["id"], "valor": valor, "faltou": faltou, "forca": "forte",
            "necessidades_nao_atendidas": evento.get("necessidades_nao_atendidas", [])}


def registrar(evento: dict, caminho=CAMINHO) -> bool:
    """Acrescenta uma linha; falha de disco vira aviso, nunca derruba o chat."""
    try:
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        return True
    except OSError as erro:
        print(f"⚠️  sinal não registrado ({type(erro).__name__})")
        return False
