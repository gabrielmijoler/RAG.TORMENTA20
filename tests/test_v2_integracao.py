"""Integração da v2 com o chat e o avaliador: flag, dicas ao LLM e /entendi."""

import pytest

from rag_v2.integracao import arquitetura, bloco_dicas, descrever, usar_v2
from rag_v2.tipos import Chave, Leitura, Ligacao, Necessidade, Restricoes

JA = "Tormenta20 - Jogo do Ano"


def _leitura(confianca="alta"):
    lig = Ligacao("machado toureo", 0, 14, Chave("Armas", "Machado Táurico", JA),
                  0.828, "aproximada", (Chave("Ameaças", "Machado Táurico", "X"),))
    return Leitura(
        texto_original="sou barbaro nv4 com machado toureo",
        ligacoes=(lig,),
        restricoes=Restricoes(nivel=4, classes=("Bárbaro",), racas=("Bugbear",)),
        tipo="build",
        necessidades=(Necessidade("registro da classe Bárbaro", "Classes", "Bárbaro",
                                  registro="Bárbaro"),
                      Necessidade("poderes gerais que usam Intimidação", "Poderes Gerais",
                                  "Intimidação", obrigatoria=False)),
        k=15, confianca=confianca, motivos=("aproximada abaixo de 0,85",),
        usar_llm="traducao")


@pytest.mark.parametrize("valor,esperado", [
    (None, "v1"), ("", "v1"), ("v1", "v1"), ("v2", "v2"), ("V2", "v2"), ("lixo", "v1")])
def test_arquitetura_le_a_flag_com_v1_como_padrao(monkeypatch, valor, esperado):
    if valor is None:
        monkeypatch.delenv("ARQUITETURA", raising=False)
    else:
        monkeypatch.setenv("ARQUITETURA", valor)
    assert arquitetura() == esperado


def test_usar_v2_so_com_flag_e_confianca_acima_de_baixa(monkeypatch):
    monkeypatch.setenv("ARQUITETURA", "v2")
    assert usar_v2(_leitura("media")) is True
    assert usar_v2(_leitura("baixa")) is False
    assert usar_v2(None) is False
    monkeypatch.setenv("ARQUITETURA", "v1")
    assert usar_v2(_leitura("alta")) is False


def test_bloco_de_dicas_lista_necessidades_e_ficha_sem_afrouxar_a_regra():
    dicas = bloco_dicas(_leitura())
    assert "registro da classe Bárbaro" in dicas
    assert "poderes gerais que usam Intimidação" in dicas
    assert "nível 4" in dicas and "Bárbaro" in dicas and "Bugbear" in dicas
    assert "não cobre" in dicas  # pede para declarar o que falta, nunca inventar
    assert "[Tabela > Fonte]" in dicas


def test_bloco_de_dicas_vazio_com_confianca_baixa_ou_sem_necessidade():
    assert bloco_dicas(_leitura("baixa")) == ""
    assert bloco_dicas(Leitura(texto_original="x", confianca="alta")) == ""


def test_descrever_mostra_ligacao_alternativas_restricoes_e_telemetria():
    tele = {"candidatos": 40, "garantidos": 1, "k": 15, "reranker": "flashrank",
            "necessidades": [{"descricao": "registro da classe Bárbaro",
                              "obrigatoria": True, "atendida": True}]}
    texto = descrever(_leitura("media"), tele)
    for trecho in ("machado toureo", "Machado Táurico", "0.83", "aproximada",
                   "Ameaças", "build", "media", "nível 4", "k=15", "atendida"):
        assert trecho in texto


def test_descrever_sem_leitura_explica_o_que_fazer():
    assert "nenhuma" in descrever(None, None).lower()
