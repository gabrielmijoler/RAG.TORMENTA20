"""Revalidação do reparo no avaliar.responder: teto de 3 passadas.

Espelha a lógica de exigir_citacoes: a 2ª passada é revalidada;
se ainda sem citação, faz uma 3ª chamada com AVISO_CITACAO.
Telemetria: `passadas` registra cada passada com motivo.
"""

from tests.test_ground_zero import _llm_falso, _SinteseFalsa, _top_falso


def test_responder_c_2a_sem_citacao_dispara_3a():
    """1ª sem citação, 2ª ainda sem, 3ª com -> 3 invocações."""
    from avaliar import responder

    sintese = _SinteseFalsa([
        "resposta sem fonte nenhuma",              # 1ª: sem citação
        "ainda sem fonte na segunda",              # 2ª: AVISO_CITACAO, ainda sem
        "agora com [Classes > Tormenta20 - Jogo do Ano].",  # 3ª: válida
    ])

    resposta, guarda = responder(_llm_falso(), _top_falso(), sintese,
                                 "pergunta")

    assert len(sintese.entradas) == 3
    assert resposta.startswith("agora com [Classes >")
    assert guarda["guard_sem_citacao_disparado"] is True
    assert guarda["guard_reparo_disparado"] is False


def test_responder_d_tres_sem_citacao_devolve_ultima():
    """3 passadas sem citação -> devolve a última; estado detectável."""
    from avaliar import responder
    from rag_core import resposta_sem_citacoes

    sintese = _SinteseFalsa([
        "sem fonte nenhuma",
        "ainda sem fonte",
        "nem na terceira",
    ])

    resposta, guarda = responder(_llm_falso(), _top_falso(), sintese,
                                 "pergunta")

    assert len(sintese.entradas) == 3
    assert resposta == "nem na terceira"
    assert resposta_sem_citacoes(resposta) is True
    assert guarda["guard_sem_citacao_disparado"] is True


def test_responder_e_1a_com_fora_2a_sem_dispara_3a():
    """Caso da query 13: 1ª com citação fora, 2ª reescreve em prosa sem
    citação -> 3ª com AVISO_CITACAO. Nunca devolver a 1ª (que tinha fora)."""
    from avaliar import responder

    sintese = _SinteseFalsa([
        "Inventor é bom [Classes > Fonte Errada].",  # 1ª: fora
        "reescrita em prosa sem nenhum colchete",     # 2ª: aviso_reparo, sem citação
        "Inventor é bom [Classes > Tormenta20 - Jogo do Ano].",  # 3ª: válida
    ])

    resposta, guarda = responder(_llm_falso(), _top_falso(), sintese,
                                 "pergunta")

    assert len(sintese.entradas) == 3
    assert resposta.startswith("Inventor é bom [Classes > Tormenta20")
    assert "Fonte Errada" not in resposta  # nunca devolve a 1ª com fora
    assert guarda["guard_reparo_disparado"] is True


def test_responder_registra_passadas_na_telemetria():
    """Cada passada é registrada em `passadas` com motivo e
    presença/ausência de citação — a 1ª nunca mais some do log."""
    from avaliar import responder

    sintese = _SinteseFalsa([
        "Inventor é bom [Classes > Fonte Errada].",  # 1ª: fora
        "reescrita em prosa sem colchete",            # 2ª: sem citação
        "Inventor é bom [Classes > Tormenta20 - Jogo do Ano].",  # 3ª: válida
    ])

    _, guarda = responder(_llm_falso(), _top_falso(), sintese, "pergunta")

    passadas = guarda["passadas"]
    assert len(passadas) == 3
    # 1ª: inicial, tinha citação (fora)
    assert passadas[0]["n"] == 1
    assert passadas[0]["motivo"] == "inicial"
    assert passadas[0]["citacoes"] == ["classes > fonte errada"]
    assert passadas[0]["fora"] == ["classes > fonte errada"]
    # 2ª: reparo, sem citação
    assert passadas[1]["n"] == 2
    assert passadas[1]["motivo"] == "fora"
    assert passadas[1]["citacoes"] == []
    assert passadas[1]["fora"] == []
    # 3ª: revalidação, com citação válida
    assert passadas[2]["n"] == 3
    assert passadas[2]["motivo"] == "revalidacao"
    assert passadas[2]["citacoes"] == ["classes > tormenta20 - jogo do ano"]
    assert passadas[2]["fora"] == []


def test_responder_1a_valida_uma_chamada_com_passada():
    """1ª válida -> 1 invocação, `passadas` com 1 entrada."""
    from avaliar import responder

    sintese = _SinteseFalsa([
        "Inventor é bom [Classes > Tormenta20 - Jogo do Ano].",
    ])

    _, guarda = responder(_llm_falso(), _top_falso(), sintese, "pergunta")

    assert len(sintese.entradas) == 1
    passadas = guarda["passadas"]
    assert len(passadas) == 1
    assert passadas[0]["n"] == 1
    assert passadas[0]["motivo"] == "inicial"
    assert passadas[0]["citacoes"] == ["classes > tormenta20 - jogo do ano"]
