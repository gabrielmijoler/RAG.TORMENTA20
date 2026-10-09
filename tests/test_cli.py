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


def test_parser_aceita_ids():
    args = criar_parser().parse_args(["--ids", "13,28,49,53,64"])
    assert args.ids == "13,28,49,53,64"


def test_parser_ids_default_none():
    args = criar_parser().parse_args([])
    assert args.ids is None


def test_avaliar_filtra_por_ids(monkeypatch):
    """--ids filtra o goldenset por prefixo de id."""
    casos = [
        {"id": "13_tamanho_criaturas", "consulta": "q13", "entidades": []},
        {"id": "28_deusa_lena", "consulta": "q28", "entidades": []},
        {"id": "49_condicao_exausto", "consulta": "q49", "entidades": []},
        {"id": "50_condicao_sangrando", "consulta": "q50", "entidades": []},
    ]
    monkeypatch.setattr(avaliar, "carregar_goldenset", lambda: casos)
    # filtra por prefixo: "13" pega 13_*, "5" pegaria 50_* e 5_*
    filtrados = [c for c in casos
                 if any(c["id"].startswith(p) for p in ["13", "28", "49"])]
    assert len(filtrados) == 3
    assert all(not c["id"].startswith("50") for c in filtrados)


def test_avaliar_buscar_nao_decompoe_sem_flag(monkeypatch):
    import rag_core
    from tests.test_decompor import _BuscaFalsa, _RerankFalso

    def _explode(q, llm=None):
        raise AssertionError("avaliar baseline não pode decompôr")

    monkeypatch.setattr(rag_core, "decompor_consultas", _explode)
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    buscar(_RerankFalso(_BuscaFalsa()), "consulta reformulada", "consulta real")
