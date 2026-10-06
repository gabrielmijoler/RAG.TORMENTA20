import json

import pytest

from avaliar import CONSULTAS, carregar_goldenset

_CAMPOS = ("id", "consulta", "entidades", "resposta_esperada")


def _linha(caso: dict) -> str:
    return json.dumps(caso, ensure_ascii=False) + "\n"


def _caso(**extra) -> dict:
    caso = {
        "id": "01_exemplo",
        "consulta": "Quais as penalidades da condição Caído?",
        "entidades": ["caído", "defesa"],
        "resposta_esperada": "Reduz Defesa e deslocamento pela metade.",
    }
    caso.update(extra)
    return caso


def test_carrega_jsonl_com_todos_os_campos(tmp_path):
    arquivo = tmp_path / "goldenset.jsonl"
    arquivo.write_text(_linha(_caso()), encoding="utf-8")

    casos = carregar_goldenset(str(arquivo))

    assert len(casos) == 1
    assert casos[0]["id"] == "01_exemplo"
    assert casos[0]["resposta_esperada"].startswith("Reduz Defesa")
    assert casos[0]["entidades"] == ["caído", "defesa"]


def test_erro_quando_falta_campo_obrigatorio(tmp_path):
    arquivo = tmp_path / "goldenset.jsonl"
    caso = _caso()
    del caso["resposta_esperada"]
    arquivo.write_text(_linha(caso), encoding="utf-8")

    with pytest.raises(ValueError, match="resposta_esperada"):
        carregar_goldenset(str(arquivo))


def test_erro_quando_id_duplicado(tmp_path):
    arquivo = tmp_path / "goldenset.jsonl"
    arquivo.write_text(_linha(_caso()) + _linha(_caso(consulta="outra?")),
                       encoding="utf-8")

    with pytest.raises(ValueError, match="duplicado"):
        carregar_goldenset(str(arquivo))


def test_erro_quando_linha_nao_e_json(tmp_path):
    arquivo = tmp_path / "goldenset.jsonl"
    arquivo.write_text("nao eh json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="linha 1"):
        carregar_goldenset(str(arquivo))


def test_arquivo_ausente_cai_nas_consultas_embutidas(tmp_path):
    casos = carregar_goldenset(str(tmp_path / "nao_existe.jsonl"))
    assert casos == CONSULTAS


def test_repositorio_tem_goldenset_valido():
    """O goldenset.jsonl do projeto carrega e cobre o dataset embarcado."""
    casos = carregar_goldenset()
    ids = [c["id"] for c in casos]
    assert len(casos) >= len(CONSULTAS)
    assert len(ids) == len(set(ids))
    for caso in casos:
        for campo in _CAMPOS:
            assert caso.get(campo), f"{caso.get('id')}: campo {campo} vazio"
