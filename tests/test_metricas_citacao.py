"""Separação de métricas: sem_citacao ≠ citacoes_fora ≠ citacoes_ok.

Cada query recebe um `estado_citacao` explícito:
- `vazia`: resposta vazia (falha de geração — n/a)
- `sem_citacao`: resposta não vazia mas SEM nenhuma citação
- `fora`: tem citação mas alguma fora do contexto
- `ok`: tem citação e nenhuma fora

Uma resposta sem citação NÃO conta como "zero citações fora".
"""

from types import SimpleNamespace

import avaliar


def _doc(texto):
    return SimpleNamespace(page_content=texto)


def _reg(resposta, fora, citacoes):
    """Registro sintético como o avaliar monta após partir_citacoes."""
    return {
        "id": "test",
        "resposta": resposta,
        "citacoes_na_resposta": citacoes,
        "citacoes_fora_do_contexto": fora,
    }


def test_estado_citacao_vazia():
    r = _reg("", [], [])
    assert avaliar.estado_citacao(r) == "vazia"


def test_estado_citacao_sem_citacao():
    """Resposta não vazia mas sem citação -> sem_citacao (não 'ok')."""
    r = _reg("resposta sem fonte nenhuma", [], [])
    assert avaliar.estado_citacao(r) == "sem_citacao"


def test_estado_citacao_fora():
    r = _reg("regra [Classes > Fonte Errada]",
             ["classes > fonte errada"], ["classes > fonte errada"])
    assert avaliar.estado_citacao(r) == "fora"


def test_estado_citacao_ok():
    r = _reg("regra [Classes > Tormenta20 - Jogo do Ano]", [],
             ["classes > tormenta20 - jogo do ano"])
    assert avaliar.estado_citacao(r) == "ok"


def test_resumo_conta_estados_separados():
    """O resumo conta sem_citacao, citacoes_fora e citacoes_ok separados."""
    registros = [
        _reg("ok [Classes > Tormenta20]", [],
             ["classes > tormenta20"]),                        # ok
        _reg("sem fonte nenhuma", [], []),                     # sem_citacao
        _reg("fora [Classes > Errada]", ["classes > errada"],
             ["classes > errada"]),                            # fora
        _reg("ok2 [Magias > Tormenta20]", [],
             ["magias > tormenta20"]),                         # ok
        _reg("", [], []),                                      # vazia
    ]
    for i, r in enumerate(registros):
        r["id"] = f"q{i}"
    contagem = avaliar.contar_estados(registros)
    assert contagem == {"ok": 2, "sem_citacao": 1, "fora": 1, "vazia": 1}
