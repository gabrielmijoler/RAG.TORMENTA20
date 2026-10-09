"""Revalidação do reparo de citação: teto de 3 passadas.

A 2ª passada (AVISO_CITACAO ou aviso_reparo) agora é REVALIDADA:
se ainda sem citação, faz uma 3ª chamada. Teto total = 3.
A 1ª passada com citação FORA nunca é devolvida como fallback.

Casos de teste (especificação):
(b) 1ª sem citação -> 2ª válida (sem 3ª)        [já coberto em test_ground_zero]
(c) 2ª sem citação -> 3ª válida                 [NOVO]
(d) 3 passadas sem -> última devolvida           [NOVO - teto]
(e) 1ª com fora -> 2ª válida (sem 3ª)            [já coberto em test_ground_zero]
"""


def test_c_2a_sem_citacao_dispara_3a():
    """(c) 1ª sem citação, 2ª ainda sem, 3ª com -> válida. Total 3 chamadas."""
    from rag_core import exigir_citacoes

    chamadas = []
    tentativas = iter([
        "resposta sem fonte nenhuma",          # 1ª: sem citação
        "ainda sem fonte na segunda",          # 2ª: AVISO_CITACAO, ainda sem
        "agora com [Magias > Tormenta20].",    # 3ª: AVISO_CITACAO, válida
    ])

    def gerar(entrada):
        chamadas.append(entrada)
        return next(tentativas)

    final = exigir_citacoes(gerar, "pergunta")
    assert final == "agora com [Magias > Tormenta20]."
    assert len(chamadas) == 3
    from rag_core import AVISO_CITACAO
    assert AVISO_CITACAO in chamadas[1]
    assert AVISO_CITACAO in chamadas[2]


def test_d_tres_sem_citacao_devolve_ultima():
    """(d) 3 passadas sem citação -> devolve a última; chamador detecta
    o estado sem_citacao via resposta_sem_citacoes()."""
    from rag_core import exigir_citacoes, resposta_sem_citacoes

    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "sem fonte nenhuma"

    final = exigir_citacoes(gerar, "p")
    assert final == "sem fonte nenhuma"
    assert len(chamadas) == 3
    assert resposta_sem_citacoes(final) is True


def test_d2_tres_sem_com_contexto_devolve_ultima():
    """(d2) Mesmo com contexto: 1ª sem, 2ª sem, 3ª sem -> última."""
    from rag_core import exigir_citacoes, resposta_sem_citacoes

    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "sem fonte"

    contexto = "[Classes > Tormenta20 - Jogo do Ano]\n# Inventor"
    final = exigir_citacoes(gerar, "p", contexto=contexto)
    assert final == "sem fonte"
    assert len(chamadas) == 3
    assert resposta_sem_citacoes(final) is True


def test_e_1a_com_fora_2a_valida_nao_dispara_3a():
    """(e) 1ª com citação fora, 2ª conserta -> retorna 2ª. Teto 2 chamadas."""
    from rag_core import exigir_citacoes

    chamadas = []
    tentativas = iter([
        "Inventor é bom [Classes > Fonte Errada].",  # 1ª: fora
        "Inventor é bom [Classes > Tormenta20].",    # 2ª: aviso_reparo, válida
    ])

    def gerar(entrada):
        chamadas.append(entrada)
        return next(tentativas)

    contexto = "[Classes > Tormenta20 - Jogo do Ano]\n# Inventor"
    final = exigir_citacoes(gerar, "p", contexto=contexto)
    assert final == "Inventor é bom [Classes > Tormenta20]."
    assert len(chamadas) == 2  # não dispara 3ª quando 2ª conserta


def test_1a_valida_sem_reparo_uma_chamada():
    """(a) 1ª válida -> 1 chamada, sem reparo."""
    from rag_core import exigir_citacoes

    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "regra [Magias > Tormenta20] aplicada."

    final = exigir_citacoes(gerar, "p")
    assert final == "regra [Magias > Tormenta20] aplicada."
    assert len(chamadas) == 1
