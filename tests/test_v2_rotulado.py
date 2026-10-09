"""Medição do analisador contra perguntas rotuladas à mão: ligação, restrições, tipo."""

import json

import pytest

from rag_v2 import rotulado as ro
from rag_v2.dicionario import construir

JA = "Tormenta20 - Jogo do Ano"


def _d():
    return construir({"tabelas": [
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Teia", "origin": JA}, {"name": "Voo", "origin": JA}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": JA}]},
        {"arquivo": "weapons.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}]},
    ]})


def _item(id_="r1", texto="o que faz a magia Teia?", ligacoes=("Magias|Teia",),
          nivel=None, classes=(), tipo="direta", mensagens=None, **kw):
    return {"id": id_, "texto": texto, "mensagens": mensagens,
            "ligacoes": list(ligacoes), "restricoes": {"nivel": nivel, "classes": list(classes),
                                                       "racas": []},
            "tipo": tipo, "verificacao": "ok", **kw}


def test_acerto_perfeito():
    r = ro.avaliar_item(_item(), _d())
    assert r["ligacao_recall"] == 1.0 and r["ligacao_precisao"] == 1.0
    assert r["tipo_ok"] and r["restricoes_ok"] and r["erros"] == []


def test_ligacao_faltando_baixa_o_recall_e_aparece_nos_erros():
    r = ro.avaliar_item(_item(ligacoes=("Magias|Teia", "Magias|Voo")), _d())
    assert r["ligacao_recall"] == 0.5 and r["ligacao_precisao"] == 1.0
    assert any("faltou Magias|Voo" in e for e in r["erros"])


def test_ligacao_sobrando_baixa_a_precisao():
    r = ro.avaliar_item(_item(ligacoes=()), _d())
    assert r["ligacao_precisao"] == 0.0 and r["ligacao_recall"] is None
    assert any("sobrou Magias|Teia" in e for e in r["erros"])


def test_item_sem_ligacao_esperada_e_sem_ligacao_lida_acerta():
    r = ro.avaliar_item(_item(texto="qual a capital da França?", ligacoes=(),
                              tipo="fora_de_escopo"), _d())
    assert r["ligacao_precisao"] is None and r["ligacao_recall"] is None
    assert r["tipo_ok"] and r["erros"] == []


def test_restricoes_nivel_e_classe():
    ok = ro.avaliar_item(_item(texto="sou barbaro nv4", ligacoes=("Classes|Bárbaro",),
                               nivel=4, classes=("Bárbaro",), tipo="build"), _d())
    assert ok["restricoes_ok"]
    errado = ro.avaliar_item(_item(texto="sou barbaro nv4", ligacoes=("Classes|Bárbaro",),
                                   nivel=5, classes=("Bárbaro",), tipo="build"), _d())
    assert not errado["restricoes_ok"] and any("nível" in e for e in errado["erros"])


def test_tipo_errado_aparece_nos_erros():
    r = ro.avaliar_item(_item(tipo="multiparte"), _d())
    assert not r["tipo_ok"] and any("tipo" in e for e in r["erros"])


def test_sequencia_avalia_o_ultimo_turno_com_a_sessao():
    item = _item(texto="e a duração dela?", mensagens=["o que faz a magia Teia?",
                                                       "e a duração dela?"])
    r = ro.avaliar_item(item, _d())
    assert r["ligacao_recall"] == 1.0 and r["tipo_ok"]


def test_agregar_calcula_medias_e_taxa_de_fallback():
    itens = [ro.avaliar_item(_item(), _d()),
             ro.avaliar_item(_item(id_="r2", texto="qual a capital da França?", ligacoes=(),
                                   tipo="fora_de_escopo"), _d()),
             ro.avaliar_item(_item(id_="r3", ligacoes=("Magias|Teia", "Magias|Voo")), _d())]
    ag = ro.agregar(itens)
    assert ag["n"] == 3
    assert ag["ligacao_recall_medio"] == pytest.approx(0.75)   # (1.0 + 0.5) / 2 com recall
    assert ag["tipo_acerto"] == 1.0
    assert ag["taxa_fallback"] == pytest.approx(1 / 3, abs=1e-3)   # só a da França
    assert ag["leitura_ms_max"] >= 0


def test_carregar_recusa_item_com_registro_inexistente(tmp_path):
    arq = tmp_path / "r.jsonl"
    arq.write_text(json.dumps(_item(ligacoes=("Magias|Inexistente",))) + "\n")
    with pytest.raises(ValueError, match="não existe"):
        ro.carregar(arq, _d())


def test_carregar_aceita_item_valido(tmp_path):
    arq = tmp_path / "r.jsonl"
    arq.write_text(json.dumps(_item()) + "\n")
    assert [i["id"] for i in ro.carregar(arq, _d())] == ["r1"]


def test_relatorio_lista_os_itens_com_erro():
    itens = [ro.avaliar_item(_item(tipo="multiparte"), _d())]
    texto = ro.renderizar(ro.agregar(itens), itens)
    assert "r1" in texto and "tipo" in texto and "provisório" in texto.lower()
