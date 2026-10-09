"""Fase 6: propostas de apelido geradas a partir dos sinais de uso.

O gerador só PROPÕE. Nada vale no ligador sem `tools/conhecimento.py aprovar`.
"""

import json

import pytest

from rag_v2 import conhecimento as k
from rag_v2 import propostas as pr
from rag_v2.dicionario import chave_texto, construir
from rag_v2.tipos import Chave

JA = "Tormenta20 - Jogo do Ano"
MACHADO = Chave("Armas", "Machado Táurico", JA)


def _d():
    return construir({"tabelas": [
        {"arquivo": "weapons.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}, {"name": "Adaga", "origin": JA}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Teia", "origin": JA}]},
    ]})


def _pergunta(id_, ligados=(), nao_atendidas=("registro da arma Machado Táurico",)):
    return {"tipo": "pergunta", "id": id_, "pergunta": f"pergunta {id_}",
            "leitura": {"ligacoes": [{"trecho": t, "tabela": tab, "nome": n, "sub": None,
                                      "tipo": "exata", "score": 1.0, "ambigua": False}
                                     for tab, n, t in ligados]},
            "necessidades_nao_atendidas": list(nao_atendidas)}


def _feedback(ref, faltou, valor="errado", nao_atendidas=("registro da arma Machado Táurico",),
              id_=None):
    return {"tipo": "feedback", "id": id_ or f"f_{ref}_{valor}", "ref": ref, "valor": valor,
            "faltou": faltou, "forca": "forte",
            "necessidades_nao_atendidas": list(nao_atendidas)}


@pytest.fixture
def pastas(tmp_path):
    return {"sinais": tmp_path / "sinais.jsonl", "propostas": tmp_path / "propostas.yaml",
            "apelidos": tmp_path / "apelidos.yaml"}


def _gravar(caminho, eventos, extra=""):
    caminho.write_text("\n".join(json.dumps(e) for e in eventos) + extra, encoding="utf-8")


def _gerar(pastas, **kw):
    return pr.gerar(pastas["sinais"], _d(), pastas["propostas"], pastas["apelidos"], **kw)


DOIS_FEEDBACKS = [
    _pergunta("e1"), _feedback("e1", "faltou citar o machado toureo"),
    _pergunta("e2"), _feedback("e2", "o machado toureo não apareceu", valor="parcial"),
]


# --- sem sinais ou sem padrão: nenhuma proposta ----------------------------------

def test_arquivo_inexistente_nao_quebra_e_nao_propoe(pastas):
    rel = _gerar(pastas)
    assert rel.propostas == [] and rel.feedbacks_negativos == 0
    assert not pastas["propostas"].exists()


def test_arquivo_vazio_nao_propoe(pastas):
    pastas["sinais"].write_text("")
    assert _gerar(pastas).propostas == []


def test_linha_corrompida_e_ignorada_e_contada(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS, extra="\n{isto nao e json\n")
    rel = _gerar(pastas)
    assert rel.linhas_invalidas == 1 and len(rel.propostas) == 1


def test_um_so_feedback_negativo_nao_gera_proposta(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS[:2])
    rel = _gerar(pastas)
    assert rel.propostas == []
    assert rel.ignoradas["abaixo_do_minimo"] == 1


def test_o_mesmo_evento_avaliado_duas_vezes_conta_uma_vez(pastas):
    _gravar(pastas["sinais"], [_pergunta("e1"),
                               _feedback("e1", "faltou o machado toureo", "errado"),
                               _feedback("e1", "faltou o machado toureo", "parcial")])
    assert _gerar(pastas).propostas == []


def test_feedback_positivo_nao_conta(pastas):
    eventos = [_pergunta("e1"), _feedback("e1", "faltou o machado toureo", valor="certo"),
               _pergunta("e2"), _feedback("e2", "faltou o machado toureo", valor="certo")]
    _gravar(pastas["sinais"], eventos)
    assert _gerar(pastas).propostas == []


# --- o caso que deve propor ------------------------------------------------------------

def test_n_feedbacks_com_o_mesmo_texto_aproximado_geram_uma_proposta_pendente(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    rel = _gerar(pastas)
    assert len(rel.propostas) == 1
    p = rel.propostas[0]
    assert p["status"] == "proposta" and p["aprovado_por"] is None
    assert (p["tabela"], p["nome"], p["fonte"]) == ("Armas", "Machado Táurico", JA)
    assert chave_texto(p["apelido"]) == "machado toureo"
    assert p["onde_confirmar"] == "a confirmar"
    assert "e1" in p["observado"] and "e2" in p["observado"]
    assert "registro da arma Machado Táurico" in p["observado"]


def test_proposta_fica_no_arquivo_de_propostas_e_nunca_no_de_apelidos(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    _gerar(pastas)
    assert [e["status"] for e in k.carregar(pastas["propostas"])] == ["proposta"]
    assert k.carregar(pastas["apelidos"]) == []
    assert k.apelidos_ativos(pastas["apelidos"]) == {}


def test_minimo_e_configuravel(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS[:2])
    assert len(_gerar(pastas, minimo=1).propostas) == 1


def test_textos_diferentes_nao_se_somam(pastas):
    eventos = [_pergunta("e1"), _feedback("e1", "faltou o machado toureo"),
               _pergunta("e2"), _feedback("e2", "faltou o machado taurico")]  # esse é exato
    _gravar(pastas["sinais"], eventos)
    assert _gerar(pastas).propostas == []


# --- não duplica / não propõe o que não faz sentido ----------------------------------------

def test_proposta_ja_existente_para_o_mesmo_apelido_nao_duplica(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    _gerar(pastas)
    rel = _gerar(pastas)
    assert rel.propostas == [] and rel.ignoradas["ja_existe"] == 1
    assert len(k.carregar(pastas["propostas"])) == 1


def test_apelido_recusado_antes_nao_volta_a_ser_proposto(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    _gerar(pastas)
    k.recusar("a0001", "ambíguo", pastas["propostas"])
    assert _gerar(pastas).propostas == []


def test_apelido_ja_aprovado_nao_e_proposto_de_novo(pastas):
    k.propor("machado toureo", MACHADO, "x", "y", caminho=pastas["propostas"],
             caminho_apelidos=pastas["apelidos"])
    assert k.aprovar("a0001", "gabriel", _d(), pastas["propostas"], pastas["apelidos"]) == []
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    assert _gerar(pastas).propostas == []


def test_faltou_sem_correspondencia_plausivel_nao_gera_proposta(pastas):
    eventos = [_pergunta("e1"), _feedback("e1", "faltou falar de marmota roxa"),
               _pergunta("e2"), _feedback("e2", "faltou falar de marmota roxa")]
    _gravar(pastas["sinais"], eventos)
    rel = _gerar(pastas)
    assert rel.propostas == [] and rel.ignoradas["sem_correspondencia"] == 2
    assert not pastas["propostas"].exists()


def test_registro_que_ja_tinha_sido_ligado_na_pergunta_nao_e_problema_de_apelido(pastas):
    ligado = [("Armas", "Machado Táurico", "machado toureo")]
    eventos = [_pergunta("e1", ligados=ligado), _feedback("e1", "faltou o machado toureo"),
               _pergunta("e2", ligados=ligado), _feedback("e2", "faltou o machado toureo")]
    _gravar(pastas["sinais"], eventos)
    rel = _gerar(pastas)
    assert rel.propostas == [] and rel.ignoradas["ja_ligada_na_pergunta"] == 2


def test_feedback_sem_faltou_ou_sem_pergunta_de_origem_nao_quebra(pastas):
    eventos = [_feedback("sumiu", "faltou o machado toureo"), _pergunta("e2"),
               _feedback("e2", None), _feedback("e2", "   ")]
    _gravar(pastas["sinais"], eventos)
    assert _gerar(pastas).propostas == []


# --- falhas repetidas por necessidade (sem proposta) ------------------------------------------

def test_agrupa_falhas_por_necessidade_em_comum_entre_perguntas_diferentes(pastas):
    eventos = [_pergunta("e1"), _feedback("e1", None),
               _pergunta("e2"), _feedback("e2", None, valor="parcial"),
               _pergunta("e3", nao_atendidas=("registro de Teia (Magias)",)),
               _feedback("e3", None, nao_atendidas=("registro de Teia (Magias)",))]
    _gravar(pastas["sinais"], eventos)
    rel = _gerar(pastas)
    assert rel.falhas_por_necessidade[0] == ("registro da arma Machado Táurico", 2)
    assert ("registro de Teia (Magias)", 1) in rel.falhas_por_necessidade
    assert rel.propostas == []


# --- simulação e relatório -----------------------------------------------------------------------------

def test_simular_nao_escreve_nada(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    rel = _gerar(pastas, simular=True)
    assert len(rel.propostas) == 1 and rel.simulado
    assert not pastas["propostas"].exists()


def test_relatorio_em_texto_resume_o_que_foi_proposto_e_o_que_foi_ignorado(pastas):
    _gravar(pastas["sinais"], DOIS_FEEDBACKS)
    texto = pr.renderizar(_gerar(pastas))
    for trecho in ("1 proposta", "machado toureo", "Machado Táurico", "tools/conhecimento.py aprovar"):
        assert trecho in texto
