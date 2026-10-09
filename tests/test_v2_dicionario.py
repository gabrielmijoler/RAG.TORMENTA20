"""Dicionário de nomes da v2: construído de registros fake (sem Qdrant, sem LLM)."""

from rag_v2.dicionario import (
    PRIORIDADE_FONTES,
    chave_texto,
    construir,
    normalizar_fonte,
    prioridade_fonte,
)
from rag_v2.tipos import Chave

JA = "Tormenta20 - Jogo do Ano"


def _dados():
    return {"tabelas": [
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA},
            {"name": "Adaga", "origin": JA},
        ]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": "tormenta20 - jogo do ano",
             "abilities": [{"name": "Fúria", "description": "x"},
                           {"name": "Instinto Selvagem", "description": "y"}]},
        ]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Abençoado", "origin": JA},
        ]},
        {"arquivo": "magicarmor.ts", "export": "enchantments", "elementos": [
            {"name": "Abençoado", "origin": JA},
        ]},
        {"arquivo": "dangers.ts", "export": "dangers", "elementos": [
            {"name": "Doenças", "origin": "Ameaças de Arton"},
            {"name": "Doenças", "origin": JA},
        ]},
        {"arquivo": "regreiro.ts", "export": "regreiroQAs", "elementos": [
            {"name": "> Saudações, caros membros!", "origin": "DB - 228"},
        ]},
    ]}


def test_chave_texto_tira_acento_caixa_e_pontuacao():
    assert chave_texto("Machado   Táurico!") == "machado taurico"
    assert chave_texto("Ceret’th, Fúria") == "ceret th furia"


def test_nome_exato_acha_a_chave_com_tabela_e_fonte():
    d = construir(_dados())
    assert d.exato("machado taurico") == (Chave("Armas", "Machado Táurico", JA),)


def test_plural_simples_acha_o_singular_e_vice_versa():
    d = construir(_dados())
    assert d.exato("barbaros") == d.exato("barbaro")
    assert d.exato("adagas") == d.exato("adaga")
    assert d.exato("doenca") == d.exato("doencas")


def test_subnome_aponta_para_o_registro_pai_com_sub():
    d = construir(_dados())
    chaves = d.exato("furia")
    assert len(chaves) == 1
    assert chaves[0].tabela == "Classes" and chaves[0].nome == "Bárbaro"
    assert chaves[0].sub == "Fúria"


def test_mesmo_nome_em_duas_tabelas_devolve_as_duas():
    d = construir(_dados())
    assert {c.tabela for c in d.exato("abencoado")} == {
        "Condições", "Encantamentos de Armaduras"}


def test_mesma_tabela_fontes_diferentes_ordena_pela_prioridade_de_fonte():
    d = construir(_dados())
    fontes = [c.fonte for c in d.exato("doencas")]
    assert fontes == [JA, "Ameaças de Arton"]


def test_regreiro_fica_fora_do_dicionario():
    d = construir(_dados())
    assert d.exato("saudacoes caros membros") == ()
    assert all(c.tabela != "Regreiro (Perguntas e Respostas)"
               for chaves in d.exatos.values() for c in chaves)


def test_apelido_aprovado_e_separado_do_nome_real():
    chave = Chave("Armas", "Machado Táurico", JA)
    d = construir(_dados(), apelidos={"machado do minotauro": chave})
    assert d.apelido("machado do minotauro") == (chave,)
    assert d.exato("machado do minotauro") == ()


def test_max_palavras_limita_a_janela_do_ligador():
    d = construir(_dados())
    assert 1 <= d.max_palavras <= 5


def test_nome_com_parentese_tambem_entra_sem_o_parentese():
    dados = {"tabelas": [{"arquivo": "poderes.ts", "export": "godPowers", "elementos": [
        {"name": "Fúria Divina (Thwor)", "origin": JA}]}]}
    d = construir(dados)
    assert d.exato("furia divina")


def test_normalizar_fonte_junta_grafias():
    assert normalizar_fonte("tormenta20 - jogo do ano") == normalizar_fonte(
        "Tormenta20 - Jogo do Ano")
    assert normalizar_fonte("Guia dos Deuses Menores") == normalizar_fonte(
        "Guia de Deuses Menores")
    assert normalizar_fonte("DB - 228") == normalizar_fonte("Dragão Brasil - 228")


def test_prioridade_segue_a_ordem_fixada():
    assert prioridade_fonte("tormenta20 - jogo do ano") == 0
    assert prioridade_fonte("Herois de Arton") < prioridade_fonte("Ameaças de Arton")
    assert prioridade_fonte("Deuses de Arton") < prioridade_fonte("Compendio T20")
    assert prioridade_fonte("Dragão Brasil - 212") == len(PRIORIDADE_FONTES)
