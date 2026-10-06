import pytest

import avaliar
from avaliar import buscar, criar_parser


def test_parser_aceita_estrategia_limiar_e_juiz():
    args = criar_parser().parse_args(
        ["--etapa", "hyde_lim07", "--estrategia", "hyde", "--limiar", "0.7", "--juiz"])
    assert args.etapa == "hyde_lim07"
    assert args.estrategia == "hyde"
    assert args.limiar == 0.7
    assert args.juiz is True


def test_parser_defaults_nao_mudam_o_pipeline_antigo():
    args = criar_parser().parse_args([])
    assert args.estrategia == "baseline"
    assert args.limiar is None
    assert args.juiz is False
    assert args.so_recuperacao is False
    assert args.continuar is False


def test_parser_rejeita_estrategia_invalida():
    with pytest.raises(SystemExit):
        criar_parser().parse_args(["--estrategia", "banana"])


def test_buscar_repassa_limiar_para_recuperar(monkeypatch):
    capturado = {}

    def fake_recuperar(retriever, consulta, consulta_real=None, filtros=None,
                       limiar=None, decompor=False):
        capturado["consulta"] = consulta
        capturado["limiar"] = limiar
        return []

    monkeypatch.setattr(avaliar.rag_core, "recuperar", fake_recuperar)
    buscar(None, "q tecnica", "q original", limiar=0.7)
    assert capturado == {"consulta": "q tecnica", "limiar": 0.7}


def test_buscar_sem_limiar_passa_none(monkeypatch):
    capturado = {}

    def fake_recuperar(retriever, consulta, consulta_real=None, filtros=None,
                       limiar=None, decompor=False):
        capturado["limiar"] = limiar
        return []

    monkeypatch.setattr(avaliar.rag_core, "recuperar", fake_recuperar)
    buscar(None, "q")
    assert capturado["limiar"] is None


def test_parser_aceita_estrategia_decompor():
    args = criar_parser().parse_args(
        ["--etapa", "decompor", "--estrategia", "decompor"]
    )
    assert args.estrategia == "decompor"


def test_avaliar_buscar_nao_decompoe_sem_flag(monkeypatch):
    import rag_core
    from tests.test_decompor import _BuscaFalsa, _RerankFalso

    def _explode(q, llm=None):
        raise AssertionError("avaliar baseline não pode decompôr")

    monkeypatch.setattr(rag_core, "decompor_consultas", _explode)
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    buscar(_RerankFalso(_BuscaFalsa()), "consulta reformulada", "consulta real")
