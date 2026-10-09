"""Orçamento de chunks: quantos documentos vão para o contexto final.

Valores iniciais conservadores (Ponto 1), a calibrar pelos percentis do k
necessário por tipo de pergunta. Confiança baixa sempre devolve o top-12 da v1.
"""

from .tipos import Necessidade

K_FALLBACK = 12
K_DIRETA = 8
K_MIN_MULTIPARTE = 8
K_POR_NECESSIDADE = 4
K_BUILD = 15
K_MAX = 15


def calcular(tipo: str, necessidades: tuple[Necessidade, ...], confianca: str) -> int:
    if confianca == "baixa" or tipo in ("sem_nome", "fora_de_escopo"):
        return K_FALLBACK
    if tipo == "build":
        return K_BUILD
    obrigatorias = sum(1 for n in necessidades if n.obrigatoria)
    minimo = K_DIRETA if tipo == "direta" else K_MIN_MULTIPARTE
    return max(minimo, min(K_MAX, K_POR_NECESSIDADE * obrigatorias))
