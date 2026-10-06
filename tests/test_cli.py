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
                       limiar=None):
        capturado["consulta"] = consulta
        capturado["limiar"] = limiar
        return []

    monkeypatch.setattr(avaliar.rag_core, "recuperar", fake_recuperar)
    buscar(None, "q tecnica", "q original", limiar=0.7)
    assert capturado == {"consulta": "q tecnica", "limiar": 0.7}


def test_buscar_sem_limiar_passa_none(monkeypatch):
    capturado = {}

    def fake_recuperar(retriever, consulta, consulta_real=None, filtros=None,
                       limiar=None):
        capturado["limiar"] = limiar
        return []

    monkeypatch.setattr(avaliar.rag_core, "recuperar", fake_recuperar)
    buscar(None, "q")
    assert capturado["limiar"] is None
