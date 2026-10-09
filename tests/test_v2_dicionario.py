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


def test_dicionario_conhece_as_tabelas_do_corpus():
    d = construir(_dados())
    assert {"Armas", "Classes", "Condições"} <= d.tabelas


def test_subhabilidade_de_dois_niveis_aponta_para_a_classe():
    dados = {"tabelas": [{"arquivo": "classes.ts", "export": "classes", "elementos": [
        {"name": "Arcanista", "origin": JA, "abilities": [
            {"name": "Caminho do Arcanista", "description": "x", "subAbilities": [
                {"name": "Feiticeiro", "description": "poder inato"},
                {"name": "Bruxo", "description": "foco"}]}]}]}]}
    d = construir(dados)
    chave = d.exato("feiticeiro")[0]
    assert (chave.tabela, chave.nome, chave.sub) == ("Classes", "Arcanista", "Feiticeiro")
    assert d.exato("bruxo")[0].sub == "Bruxo"
    assert d.exato("caminho do arcanista")[0].sub == "Caminho do Arcanista"


def test_subhabilidade_nao_vence_o_registro_de_mesmo_nome_em_fonte_prioritaria():
    dados = {"tabelas": [{"arquivo": "classes.ts", "export": "classes", "elementos": [
        {"name": "Mago (A Lenda de Ghanor)", "origin": "A Lenda de Ghanor"},
        {"name": "Arcanista", "origin": JA, "abilities": [
            {"name": "Caminho", "subAbilities": [{"name": "Mago"}]}]}]}]}
    chaves = construir(dados).exato("mago")
    assert chaves[0].nome == "Arcanista" and chaves[0].sub == "Mago"


def test_vocabulario_guarda_palavras_frequentes_do_texto_do_corpus():
    dados = {"tabelas": [{"arquivo": "conditions.ts", "export": "conditions", "elementos": [
        {"name": f"Cond {i}", "origin": JA,
         "description": "Você sempre precisa gastar uma ação rara"} for i in range(3)]}]}
    d = construir(dados)
    assert {"precisa", "gastar", "acao"} <= d.vocabulario     # 3 ocorrências cada
    assert "rara" in d.vocabulario
    assert "zzzraro" not in d.vocabulario


def test_palavra_rara_nao_entra_no_vocabulario():
    dados = {"tabelas": [{"arquivo": "conditions.ts", "export": "conditions", "elementos": [
        {"name": "A", "origin": JA, "description": "palavra unica"}]}]}
    assert "unica" not in construir(dados).vocabulario


def test_vocabulario_ignora_a_tabela_do_regreiro():
    dados = {"tabelas": [{"arquivo": "regreiro.ts", "export": "regreiroQAs", "elementos": [
        {"name": f"p{i}", "origin": "DB", "description": "xablau xablau"} for i in range(5)]}]}
    assert "xablau" not in construir(dados).vocabulario
