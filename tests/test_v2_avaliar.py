"""Plugue da v2 no avaliador: ARQUITETURA=v2 troca recuperação e síntese; v1 intacta."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import avaliar
import rag_v2.recuperacao
from rag_v2.dicionario import construir

DOCS = [Document(page_content="[Magias > Tormenta20 - Jogo do Ano]\n# Voo\nconteudo",
                 metadata={"Tabela": "Magias", "Nome": "Voo", "relevance_score": 0.9})]
TELEMETRIA = {"candidatos": 3, "garantidos": 1, "k": 8, "reranker": "flashrank",
              "necessidades": [{"descricao": "registro de Voo (Magias)",
                                "obrigatoria": True, "atendida": True}]}


@pytest.fixture
def ambiente(monkeypatch):
    chamadas = {"buscar": 0, "recuperar_v2": 0, "reformular": 0, "perguntas": []}

    def fake_buscar(retriever, consulta, consulta_real=None, limiar=None, decompor=False):
        chamadas["buscar"] += 1
        return list(DOCS)

    def fake_recuperar_v2(retriever, leitura, registros, busca, original, limiar=None):
        chamadas["recuperar_v2"] += 1
        return list(DOCS), dict(TELEMETRIA)

    def fake_reformular(llm, consulta, cache):
        chamadas["reformular"] += 1
        return consulta + " (traduzida)"

    def fake_responder(llm, top, sintese, pergunta):
        chamadas["perguntas"].append(pergunta)
        return "Voo [Magias > Tormenta20 - Jogo do Ano]", {
            "guard_reparo_disparado": False, "guard_sem_citacao_disparado": False}

    dicionario = construir({"tabelas": [{"arquivo": "spells.ts", "export": "spells",
                                         "elementos": [{"name": "Voo", "origin": "X"}]}]})
    monkeypatch.setattr(avaliar, "buscar", fake_buscar)
    # avaliar importa a v2 dentro da função: o alvo do patch é o módulo de origem
    monkeypatch.setattr(rag_v2.recuperacao, "recuperar_v2", fake_recuperar_v2)
    monkeypatch.setattr(avaliar, "reformular", fake_reformular)
    monkeypatch.setattr(avaliar, "responder", fake_responder)
    monkeypatch.setattr(avaliar, "_montar_v2",
                        lambda chunks: (dicionario, {}) if avaliar._arquitetura() == "v2"
                        else (None, None))
    monkeypatch.setattr(avaliar.rag_core, "montar_chunks", lambda verbose=True: [])
    monkeypatch.setattr(avaliar.rag_core, "montar_retriever",
                        lambda chunks, estrategia="hibrida", llm=None: SimpleNamespace())
    monkeypatch.setattr(avaliar.rag_core, "montar_cadeia_resposta",
                        lambda system_prompt, llm, com_historico=False: None)
    monkeypatch.setattr(avaliar.rag_core, "reranker_ativo", lambda: "flashrank")
    monkeypatch.setattr(avaliar, "carregar_cache", dict)
    monkeypatch.setattr(avaliar, "_pontos_colecao", lambda: 0)
    monkeypatch.setattr(avaliar, "INTERVALO_QUERY", 0)
    return chamadas


def _rodar(monkeypatch, consulta):
    monkeypatch.setattr(avaliar, "carregar_goldenset",
                        lambda: [{"id": "01", "consulta": consulta, "entidades": ["voo"]}])
    return avaliar.avaliar(None, saida=None)


def test_sem_flag_o_avaliador_continua_v1(monkeypatch, ambiente):
    monkeypatch.delenv("ARQUITETURA", raising=False)
    resultado = _rodar(monkeypatch, "o que faz a magia Voo?")
    assert ambiente["buscar"] == 1 and ambiente["recuperar_v2"] == 0
    assert ambiente["perguntas"] == ["o que faz a magia Voo? (traduzida)"]
    assert "v2" not in resultado["registros"][0]
    assert resultado["arquitetura"] == "v1"


def test_v2_com_confianca_alta_pula_traducao_e_manda_a_lista_ao_llm(monkeypatch, ambiente):
    monkeypatch.setenv("ARQUITETURA", "v2")
    resultado = _rodar(monkeypatch, "o que faz a magia Voo?")
    assert ambiente["reformular"] == 0 and ambiente["buscar"] == 0
    assert ambiente["recuperar_v2"] == 1
    assert "LISTA DE VERIFICAÇÃO" in ambiente["perguntas"][0]
    reg = resultado["registros"][0]
    assert reg["v2"]["confianca"] == "alta"
    assert reg["v2"]["recuperacao"]["garantidos"] == 1
    assert resultado["arquitetura"] == "v2"


def test_v2_com_confianca_baixa_cai_na_v1_e_registra_a_leitura(monkeypatch, ambiente):
    monkeypatch.setenv("ARQUITETURA", "v2")
    resultado = _rodar(monkeypatch, "quanto dano causa um ataque critico?")
    assert ambiente["buscar"] == 1 and ambiente["recuperar_v2"] == 0
    assert "LISTA DE VERIFICAÇÃO" not in ambiente["perguntas"][0]
    reg = resultado["registros"][0]
    assert reg["v2"]["confianca"] == "baixa" and reg["v2"]["recuperacao"] is None
