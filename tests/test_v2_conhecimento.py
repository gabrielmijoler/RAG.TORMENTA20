"""Conhecimento da v2: apelidos aprendidos, só valem depois de aprovados."""

import datetime as dt

import pytest

from rag_v2 import conhecimento as k
from rag_v2.dicionario import construir
from rag_v2.ligador import ligar
from rag_v2.tipos import Chave

JA = "Tormenta20 - Jogo do Ano"
MACHADO = Chave("Armas", "Machado Táurico", JA)
HOJE = dt.date(2026, 10, 9)


def _d(apelidos=None):
    return construir({"tabelas": [
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}, {"name": "Adaga", "origin": JA}]},
    ]}, apelidos=apelidos)


@pytest.fixture
def caminhos(tmp_path):
    return {"propostas": tmp_path / "propostas.yaml", "apelidos": tmp_path / "apelidos.yaml"}


def _propor(caminhos, apelido="machado do minotauro", chave=MACHADO):
    return k.propor(apelido, chave, observado="usuário escreveu 'machado do minotauro'",
                    onde_confirmar="Armas, Tormenta20 - Jogo do Ano",
                    caminho=caminhos["propostas"], hoje=HOJE)


def test_proposta_nasce_pendente_e_nao_vale_no_ligador(caminhos):
    entrada = _propor(caminhos)
    assert entrada["status"] == "proposta" and entrada["id"] == "a0001"
    assert k.carregar(caminhos["propostas"])[0]["apelido"] == "machado do minotauro"
    assert k.apelidos_ativos(caminhos["apelidos"]) == {}


def test_aprovar_move_para_apelidos_e_passa_a_valer(caminhos):
    _propor(caminhos)
    erros = k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"],
                      caminhos["apelidos"], hoje=HOJE)
    assert erros == []
    aprovadas = k.carregar(caminhos["apelidos"])
    assert aprovadas[0]["status"] == "aprovada" and aprovadas[0]["aprovado_por"] == "gabriel"
    assert k.carregar(caminhos["propostas"]) == []
    ativos = k.apelidos_ativos(caminhos["apelidos"])
    assert ativos == {"machado do minotauro": MACHADO}
    lig = ligar("o machado do minotauro é bom?", _d(ativos))[0]
    assert lig.tipo == "apelido" and lig.chave == MACHADO


def test_aprovar_recusa_registro_inexistente(caminhos):
    _propor(caminhos, chave=Chave("Armas", "Machado Inexistente", JA))
    erros = k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    assert any("não existe" in e for e in erros)
    assert k.carregar(caminhos["apelidos"]) == []
    assert k.carregar(caminhos["propostas"])[0]["status"] == "proposta"


def test_aprovar_recusa_apelido_que_e_nome_real(caminhos):
    _propor(caminhos, apelido="adaga")
    erros = k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    assert any("nome real" in e for e in erros)


def test_aprovar_recusa_colisao_com_apelido_aprovado(caminhos):
    _propor(caminhos)
    k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    _propor(caminhos, chave=Chave("Armas", "Adaga", JA))
    erros = k.aprovar("a0002", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    assert any("já existe" in e for e in erros)


def test_aprovar_id_desconhecido(caminhos):
    assert k.aprovar("a9999", "x", _d(), caminhos["propostas"], caminhos["apelidos"]) != []


def test_recusada_fica_registrada_e_nunca_vale(caminhos):
    _propor(caminhos)
    assert k.recusar("a0001", "apelido ambíguo", caminhos["propostas"]) is True
    entrada = k.carregar(caminhos["propostas"])[0]
    assert entrada["status"] == "recusada" and entrada["motivo"] == "apelido ambíguo"
    assert k.apelidos_ativos(caminhos["apelidos"]) == {}
    assert k.aprovar("a0001", "x", _d(), caminhos["propostas"], caminhos["apelidos"]) != []


def test_verificar_suspende_apelido_orfao_sem_apagar(caminhos):
    _propor(caminhos)
    k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    corpus_sem_machado = construir({"tabelas": [{"arquivo": "armas.ts", "export": "weapons",
                                                 "elementos": [{"name": "Adaga", "origin": JA}]}]})
    suspensos = k.verificar(corpus_sem_machado, caminhos["apelidos"])
    assert [s["id"] for s in suspensos] == ["a0001"]
    entrada = k.carregar(caminhos["apelidos"])[0]
    assert entrada["status"] == "suspensa" and "não existe" in entrada["motivo"]
    assert k.apelidos_ativos(caminhos["apelidos"]) == {}


def test_ids_sao_unicos_entre_os_dois_arquivos(caminhos):
    _propor(caminhos)
    k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    nova = _propor(caminhos, apelido="machadao")
    assert nova["id"] == "a0002"


def test_md_gerado_traz_os_campos_de_cada_entrada(caminhos):
    _propor(caminhos)
    k.aprovar("a0001", "gabriel", _d(), caminhos["propostas"], caminhos["apelidos"])
    _propor(caminhos, apelido="machadao")
    md = k.gerar_md(caminhos["propostas"], caminhos["apelidos"])
    for trecho in ("machado do minotauro", "Machado Táurico", "Armas", "aprovada",
                   "gabriel", "proposta", "machadao", "2026-10-09", "não edite"):
        assert trecho in md


def test_arquivo_ausente_e_lista_vazia(tmp_path):
    assert k.carregar(tmp_path / "nao_existe.yaml") == []
