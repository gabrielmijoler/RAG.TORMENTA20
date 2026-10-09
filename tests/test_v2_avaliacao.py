"""Avaliador da v2: cobertura por entidade/necessidade, rastreio por etapa, dev x teste."""

import json

import pytest

from rag_v2 import avaliacao as av

JA = "Tormenta20 - Jogo do Ano"


def _caso(id_="c1", conjunto="dev", nivel="facil", **kw):
    base = {"id": id_, "nivel": nivel, "conjunto": conjunto, "consulta": "q",
            "mensagens": None, "premissa_falsa": False,
            "entidades_esperadas": [{"nome": "Voo", "tabela": "Magias", "fonte": JA, "sub": None}],
            "fatos_esperados": ["f"], "verificacao": "ok"}
    base.update(kw)
    return base


def _jsonl(tmp_path, casos):
    arq = tmp_path / "casos.jsonl"
    arq.write_text("\n".join(json.dumps(c) for c in casos), encoding="utf-8")
    return arq


# --- carga e conjuntos -------------------------------------------------------

def test_carregar_filtra_por_conjunto(tmp_path):
    arq = _jsonl(tmp_path, [_caso("a"), _caso("b", conjunto="teste"),
                            _caso("c", conjunto="sem_resposta")])
    assert [c["id"] for c in av.carregar(arq, "dev")] == ["a"]
    assert [c["id"] for c in av.carregar(arq, "teste", confirmar_teste=True)] == ["b"]


def test_carregar_recusa_caso_com_entidade_nao_verificada(tmp_path):
    arq = _jsonl(tmp_path, [_caso("a", verificacao="entidade_nao_encontrada")])
    with pytest.raises(ValueError, match="não verificad"):
        av.carregar(arq, "dev")


def test_teste_fechado_exige_confirmacao(tmp_path):
    arq = _jsonl(tmp_path, [_caso("b", conjunto="teste")])
    with pytest.raises(PermissionError, match="teste fechado"):
        av.carregar(arq, "teste", confirmar_teste=False)
    assert av.carregar(arq, "teste", confirmar_teste=True)


# --- rastreio -----------------------------------------------------------------

RASTRO = {
    "candidatos": ["Magias|Voo", "Condições|Caído", "Magias|X", "Armas|Y"],
    "rerank": ["Magias|X", "Magias|Voo", "Condições|Caído", "Armas|Y"],
    "limiar": ["Magias|X", "Magias|Voo", "Armas|Y"],
    "garantidos": ["Magias|Voo"],
    "final": ["Magias|Voo", "Magias|X"],
}


def test_entidade_no_final_nao_foi_perdida():
    r = av.rastrear("Magias|Voo", RASTRO)
    assert r["perdida_em"] is None and r["rank_final"] == 1 and r["rank_rerank"] == 2


def test_perdida_no_limiar():
    assert av.rastrear("Condições|Caído", RASTRO)["perdida_em"] == "limiar"


def test_perdida_no_orcamento_quando_passou_o_limiar_mas_nao_coube():
    assert av.rastrear("Armas|Y", RASTRO)["perdida_em"] == "orcamento"


def test_perdida_nos_candidatos_quando_a_busca_nao_trouxe():
    assert av.rastrear("Magias|Z", RASTRO)["perdida_em"] == "candidatos"


def test_sem_rerank_nao_ha_etapa_limiar():
    rastro = dict(RASTRO, rerank=[], limiar=[], final=["Magias|X"])
    assert av.rastrear("Armas|Y", rastro)["perdida_em"] == "orcamento"


# --- avaliar um caso -----------------------------------------------------------

def _saida(final, rastro=None, necessidades=(), caminho="v2", chars=1000):
    return {"caminho": caminho, "final": final, "rastro": dict(rastro or RASTRO, final=final),
            "leitura": {"tipo": "direta", "confianca": "alta", "k": 8,
                        "ligacoes": ["Magias|Voo"], "necessidades": list(necessidades)},
            "n_docs": len(final), "chars": chars, "tempo_s": 1.5}


def test_cobertura_por_entidade_e_por_pergunta():
    caso = _caso(entidades_esperadas=[
        {"nome": "Voo", "tabela": "Magias", "fonte": JA, "sub": None},
        {"nome": "Caído", "tabela": "Condições", "fonte": JA, "sub": None}])
    res = av.avaliar_caso(caso, [_saida(["Magias|Voo", "Magias|X"])])
    assert res["cobertura_entidades"] == 0.5
    por = {e["registro"]: e for e in res["entidades"]}
    assert por["Magias|Voo"]["achada"] and not por["Condições|Caído"]["achada"]
    assert por["Condições|Caído"]["perdida_em"] == "limiar"
    assert por["Magias|Voo"]["ligada_pelo_analisador"] is True
    assert por["Condições|Caído"]["ligada_pelo_analisador"] is False


def test_cobertura_por_necessidade():
    nec = [{"descricao": "a", "obrigatoria": True, "atendida": True},
           {"descricao": "b", "obrigatoria": True, "atendida": False},
           {"descricao": "c", "obrigatoria": False, "atendida": False}]
    saida = _saida(["Magias|Voo"])
    saida["telemetria"] = {"necessidades": nec}
    res = av.avaliar_caso(_caso(), [saida])
    assert res["cobertura_necessidades"] == 0.5  # só as obrigatórias contam


def test_sequencia_cobre_a_entidade_no_ultimo_turno_e_registra_todos():
    caso = _caso(mensagens=["a", "b", "c"])
    turnos = [_saida(["Magias|X"]), _saida(["Magias|Voo"]), _saida(["Magias|Voo"])]
    res = av.avaliar_caso(caso, turnos)
    assert res["cobertura_entidades"] == 1.0
    assert [t["achou_todas"] for t in res["turnos"]] == [False, True, True]


def test_caso_sem_entidades_esperadas_tem_cobertura_none():
    res = av.avaliar_caso(_caso(entidades_esperadas=[], id_="x"), [_saida(["Magias|X"])])
    assert res["cobertura_entidades"] is None


def test_chars_e_n_docs_vem_do_ultimo_turno():
    res = av.avaliar_caso(_caso(), [_saida(["Magias|Voo"], chars=4321)])
    assert res["chars"] == 4321 and res["n_docs"] == 1


# --- agregação -----------------------------------------------------------------

def _res(nivel, cob, perdida=None, conjunto="dev", caminho="v2", falsa=False):
    ents = [{"registro": "A|B", "achada": cob == 1.0, "perdida_em": perdida,
             "ligada_pelo_analisador": True, "rank_final": 1, "rank_rerank": 1}]
    return {"id": nivel + str(cob), "nivel": nivel, "conjunto": conjunto,
            "cobertura_entidades": cob, "cobertura_necessidades": 1.0, "entidades": ents,
            "chars": 1000, "n_docs": 8, "tempo_s": 2.0, "caminho": caminho,
            "premissa_falsa": falsa, "leitura": {"tipo": "direta", "confianca": "alta"}}


def test_agregar_por_nivel_e_conjunto_sem_misturar():
    res = [_res("facil", 1.0), _res("facil", 0.5, "limiar"), _res("dificil", 1.0),
           _res("dificil", 1.0, conjunto="teste")]
    ag = av.agregar(res)
    assert ag["dev"]["facil"]["n"] == 2
    assert ag["dev"]["facil"]["cobertura_media"] == 0.75
    assert ag["teste"]["dificil"]["n"] == 1
    assert "teste" in ag and "dev" in ag


def test_agregar_conta_onde_as_entidades_se_perdem():
    res = [_res("facil", 0.0, "limiar"), _res("facil", 0.0, "candidatos"),
           _res("facil", 0.0, "limiar")]
    perdas = av.agregar(res)["dev"]["_perdas_por_etapa"]
    assert perdas == {"limiar": 2, "candidatos": 1}


def test_agregar_ignora_cobertura_none():
    ag = av.agregar([_res("sem_resposta", None)])
    assert ag["dev"]["sem_resposta"]["cobertura_media"] is None


def test_renderizar_relatorio_mostra_cada_nivel_e_nao_diz_nada_de_v1():
    res = [_res("facil", 1.0), _res("complexa", 0.5, "orcamento")]
    texto = av.renderizar(av.agregar(res), res)
    assert "facil" in texto and "complexa" in texto and "orcamento" in texto
    assert "v1" not in texto.lower().replace("fallback_v1", "")
