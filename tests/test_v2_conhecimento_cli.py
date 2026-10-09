"""CLI tools/conhecimento.py: listar, propor, aprovar, recusar, verificar, gerar-md."""

import importlib.util
import json
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


# --- gerar-propostas (Fase 6) ---------------------------------------------------------

def _sinais(pasta, eventos):
    arq = pasta / "sinais.jsonl"
    arq.write_text("\n".join(json.dumps(e) for e in eventos), encoding="utf-8")
    return arq


def _eventos_do_machado():
    saida = []
    for ref, valor in (("e1", "errado"), ("e2", "parcial")):
        saida.append({"tipo": "pergunta", "id": ref, "leitura": {"ligacoes": []},
                      "necessidades_nao_atendidas": ["registro da arma Machado Táurico"]})
        saida.append({"tipo": "feedback", "id": f"f{ref}", "ref": ref, "valor": valor,
                      "faltou": "faltou o machado toureo",
                      "necessidades_nao_atendidas": ["registro da arma Machado Táurico"]})
    return saida


def test_gerar_propostas_grava_pendente_e_regenera_o_md(pasta, capsys):
    arq = _sinais(pasta, _eventos_do_machado())
    assert _rodar(pasta, "gerar-propostas", "--sinais", str(arq)) == 0
    saida = capsys.readouterr().out
    assert "1 proposta" in saida and "machado toureo" in saida and "aprovar" in saida
    assert [e["status"] for e in cli.k.carregar(pasta / "propostas.yaml")] == ["proposta"]
    assert not (pasta / "apelidos.yaml").exists()           # nada aprovado sozinho
    assert "machado toureo" in (pasta / "APRENDIZADOS.md").read_text(encoding="utf-8")


def test_gerar_propostas_simular_nao_grava(pasta, capsys):
    arq = _sinais(pasta, _eventos_do_machado())
    assert _rodar(pasta, "gerar-propostas", "--sinais", str(arq), "--simular") == 0
    assert "SIMULAÇÃO" in capsys.readouterr().out
    assert not (pasta / "propostas.yaml").exists()


def test_gerar_propostas_sem_arquivo_de_sinais_diz_que_nao_ha_nada(pasta, capsys):
    assert _rodar(pasta, "gerar-propostas", "--sinais", str(pasta / "nao_existe.jsonl")) == 0
    assert "Nenhuma proposta nova" in capsys.readouterr().out


def test_gerar_propostas_depois_de_aprovar_nao_repete(pasta, capsys):
    arq = _sinais(pasta, _eventos_do_machado())
    _rodar(pasta, "gerar-propostas", "--sinais", str(arq))
    assert _rodar(pasta, "aprovar", "a0001", "--por", "gabriel") == 0
    capsys.readouterr()
    _rodar(pasta, "gerar-propostas", "--sinais", str(arq))
    assert "Nenhuma proposta nova" in capsys.readouterr().out
