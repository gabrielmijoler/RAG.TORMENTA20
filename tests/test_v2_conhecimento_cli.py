"""CLI tools/conhecimento.py: listar, propor, aprovar, recusar, verificar, gerar-md."""

import importlib.util
import os

import pytest

from rag_v2.dicionario import construir

_CAMINHO = os.path.join(os.path.dirname(__file__), "..", "tools", "conhecimento.py")
_spec = importlib.util.spec_from_file_location("cli_conhecimento", _CAMINHO)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

JA = "Tormenta20 - Jogo do Ano"


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    dicionario = construir({"tabelas": [{"arquivo": "armas.ts", "export": "weapons",
                                         "elementos": [{"name": "Machado Táurico",
                                                        "origin": JA}]}]})
    monkeypatch.setattr(cli, "carregar_dicionario", lambda: dicionario)
    return tmp_path


def _rodar(pasta, *args):
    return cli.main(["--pasta", str(pasta), *args])


def test_fluxo_propor_aprovar_gera_md(pasta, capsys):
    assert _rodar(pasta, "propor", "machado do minotauro", "--tabela", "Armas",
                  "--nome", "Machado Táurico", "--fonte", JA,
                  "--observado", "usuário escreveu", "--onde", "Armas, JdA") == 0
    assert _rodar(pasta, "aprovar", "a0001", "--por", "gabriel") == 0
    saida = capsys.readouterr().out
    assert "aprovada" in saida and "teste fechado" in saida
    md = (pasta / "APRENDIZADOS.md").read_text(encoding="utf-8")
    assert "machado do minotauro" in md
    assert _rodar(pasta, "listar") == 0
    assert "a0001" in capsys.readouterr().out


def test_aprovar_invalido_devolve_erro_e_nao_aplica(pasta, capsys):
    _rodar(pasta, "propor", "machado taurico", "--tabela", "Armas",
           "--nome", "Machado Táurico", "--fonte", JA, "--observado", "x", "--onde", "y")
    assert _rodar(pasta, "aprovar", "a0001", "--por", "gabriel") == 1
    assert "nome real" in capsys.readouterr().out
    assert not (pasta / "apelidos.yaml").exists()


def test_recusar_e_verificar(pasta, capsys):
    _rodar(pasta, "propor", "machadao", "--tabela", "Armas", "--nome", "Machado Táurico",
           "--fonte", JA, "--observado", "x", "--onde", "y")
    assert _rodar(pasta, "recusar", "a0001", "--motivo", "ambíguo") == 0
    assert _rodar(pasta, "verificar") == 0
    assert "nenhum apelido órfão" in capsys.readouterr().out
