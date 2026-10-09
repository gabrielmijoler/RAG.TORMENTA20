"""Leitura de feedback em linguagem natural: sinal FRACO, em Python, sem LLM.

Na mensagem seguinte a uma resposta, o usuário pode dizer "deu certo", "funcionou",
"em partes", "não era isso". Este módulo reconhece só frases CLARAS e curtas:
- reconhecido -> `FeedbackNatural` (vira um sinal fraco, com a confiança registrada);
- não reconhecido -> `None`: a mensagem segue o fluxo normal e nada é registrado;
- o silêncio NUNCA conta como acerto (sem mensagem, sem sinal).
O comando (/errado, /parcial) continua sendo o sinal forte.

Cuidados contra falso positivo: pergunta (com '?' ou começando por palavra
interrogativa) nunca é feedback, frases longas também não, e polaridades em conflito
("funcionou mas está errado") são ignoradas em vez de adivinhadas.
"""

import re
from dataclasses import dataclass

from .dicionario import chave_texto

MAX_PALAVRAS = 12            # acima disso a mensagem provavelmente é outra coisa
MAX_PALAVRAS_ALTA = 6        # frase curta e direta -> confiança alta

# Padrões sobre o texto normalizado (minúsculas, sem acento, sem pontuação).
_NAO_FOI_ERRADO = re.compile(r"\bnao (?:esta|e|foi|ta) (?:errad[oa]|incorret[oa])\b")
_ERRADO = re.compile(
    r"\b(?:errad[oa]s?|incorret[oa]s?|nao era isso|nao e isso|nao e bem isso|nao funcionou|"
    r"nao deu certo|nunca deu certo|nao ajudou|nao resolveu|nao serve)\b")
_PARCIAL = re.compile(
    r"\b(?:em partes?|so em partes?|mais ou menos|parcialmente|incomplet[oa]|faltou)\b")
_CERTO = re.compile(
    r"\b(?:deu certo|funcionou|correto|correta|perfeit[oa]|era isso(?: mesmo)?|"
    r"exatamente|resolveu|ajudou)\b")
_INTERROGATIVAS = ("qual", "quais", "como", "quanto", "quantos", "quantas", "quem", "onde",
                   "quando", "porque", "por que", "o que", "existe", "tem", "pode")
_RE_FALTOU = re.compile(r"\bfaltou\b(.*)", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class FeedbackNatural:
    valor: str                  # "certo" | "parcial" | "errado"
    confianca: str              # "alta" | "media"
    faltou: str | None          # o que o usuário disse que faltou, se disse
    texto: str                  # mensagem original, para auditoria


def _faltou(texto: str) -> str | None:
    achado = _RE_FALTOU.search(texto)
    complemento = achado.group(1).strip(" .,:;!-—") if achado else ""
    return complemento or None


def interpretar(texto: str) -> FeedbackNatural | None:
    """O feedback da mensagem, ou None se não for um feedback claro."""
    original = (texto or "").strip()
    if not original or "?" in original:
        return None
    norma = chave_texto(original)
    palavras = norma.split()
    if not palavras or len(palavras) > MAX_PALAVRAS:
        return None
    if any(norma == i or norma.startswith(i + " ") for i in _INTERROGATIVAS):
        return None

    # "isso não está errado" é positivo: tira a negação antes de olhar o resto
    nao_errado = bool(_NAO_FOI_ERRADO.search(norma))
    restante = _NAO_FOI_ERRADO.sub(" ", norma)
    errado = bool(_ERRADO.search(restante))
    # frases negativas ("nao funcionou") contêm termos positivos: remove-as antes de
    # procurar o positivo, senão "não funcionou" viraria "funcionou"
    sem_negativos = _ERRADO.sub(" ", restante)
    parcial = bool(_PARCIAL.search(sem_negativos))
    certo = bool(_CERTO.search(sem_negativos)) or nao_errado

    if certo and errado:
        return None                       # conflito: não adivinha
    if errado:
        valor = "errado"
    elif parcial:
        valor = "parcial"
    elif certo:
        valor = "certo"
    else:
        return None

    misto = sum((errado, parcial, certo)) > 1 or nao_errado
    alta = len(palavras) <= MAX_PALAVRAS_ALTA and not misto
    return FeedbackNatural(valor=valor, confianca="alta" if alta else "media",
                           faltou=_faltou(original) if valor != "certo" else None,
                           texto=original)
