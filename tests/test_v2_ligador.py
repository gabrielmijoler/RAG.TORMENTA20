"""Ligador da v2: nomes do jogo dentro da pergunta (exato, apelido, aproximado)."""

import pytest

from rag_v2.dicionario import construir
from rag_v2.ligador import ambigua, ligar, refinar_por_restricoes
from rag_v2.tipos import Chave, Restricoes

JA = "Tormenta20 - Jogo do Ano"
SEMENTE = ("Sou um barbaro, bugbear, nv4, quero usar intimidacao e machado toureo "
           "para causar dano. Quais habilidades combam com isso.")


def _dados():
    return {"tabelas": [
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA},
            {"name": "Machado de Batalha", "origin": JA},
            {"name": "Adaga", "origin": JA}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": JA,
             "abilities": [{"name": "Fúria"}]}]},
        {"arquivo": "races.ts", "export": "races", "elementos": [
            {"name": "Bugbear", "origin": "Ameaças de Arton"}]},
        {"arquivo": "skills.ts", "export": "skills", "elementos": [
            {"name": "Intimidação", "origin": "Compendio T20"},
            {"name": "Cura", "origin": "Compendio T20"}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Cura", "origin": JA}]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Abençoado", "origin": JA}]},
        {"arquivo": "magicarmor.ts", "export": "enchantments", "elementos": [
            {"name": "Abençoado", "origin": JA}]},
        {"arquivo": "dangers.ts", "export": "dangers", "elementos": [
            {"name": "Doenças", "origin": "Ameaças de Arton"},
            {"name": "Doenças", "origin": JA}]},
        {"arquivo": "powers-barbaro.ts", "export": "powersBarbaro", "elementos": [
            {"name": "Esmagador", "origin": JA}]},
        {"arquivo": "powers-guerreiro.ts", "export": "powersGuerreiro", "elementos": [
            {"name": "Esmagador", "origin": JA}]},
    ]}


def _d(apelidos=None):
    return construir(_dados(), apelidos=apelidos)


def _por_trecho(ligacoes):
    return {lig.trecho.lower(): lig for lig in ligacoes}


def test_caso_semente_liga_os_quatro_nomes_e_nada_mais():
    ligs = ligar(SEMENTE, _d())
    nomes = {(lig.chave.tabela, lig.chave.nome) for lig in ligs}
    assert nomes == {("Classes", "Bárbaro"), ("Raças", "Bugbear"),
                     ("Perícias", "Intimidação"), ("Armas", "Machado Táurico")}


def test_caso_semente_machado_toureo_e_aproximada_acima_do_limiar():
    lig = _por_trecho(ligar(SEMENTE, _d()))["machado toureo"]
    assert lig.tipo == "aproximada"
    assert 0.80 <= lig.score < 1.0
    assert lig.chave.nome == "Machado Táurico"


def test_ligacoes_exatas_tem_score_1_e_offsets_corretos():
    for lig in ligar(SEMENTE, _d()):
        assert SEMENTE[lig.inicio:lig.fim] == lig.trecho
        if lig.tipo == "exata":
            assert lig.score == 1.0


def test_cada_palavra_so_e_ligada_uma_vez():
    ligs = ligar("Qual o dano do machado taurico?", _d())
    assert [lig.chave.nome for lig in ligs] == ["Machado Táurico"]


def test_plural_acha_o_nome():
    ligs = ligar("o que as adagas fazem", _d())
    assert [lig.chave.nome for lig in ligs] == ["Adaga"]


def test_palavra_de_uma_letra_so_nao_liga_aproximada_curta():
    assert ligar("preciso de uma adga", _d()) == ()


def test_uma_palavra_com_6_letras_ou_mais_liga_aproximada():
    ligs = ligar("o que e um bugber", _d())
    assert ligs and ligs[0].chave.nome == "Bugbear" and ligs[0].tipo == "aproximada"


def test_sem_nome_do_jogo_nao_liga_nada():
    assert ligar("Qual a capital da França?", _d()) == ()
    assert ligar("", _d()) == ()


def test_palavra_comum_sem_pista_de_tabela_nao_liga():
    assert ligar("preciso de cura urgente", _d()) == ()


def test_palavra_comum_com_pista_liga_na_tabela_da_pista():
    ligs = ligar("como funciona a pericia cura", _d())
    assert [(lig.chave.tabela, lig.chave.nome) for lig in ligs] == [("Perícias", "Cura")]
    assert not ambigua(ligs[0])


def test_mesmo_nome_em_duas_tabelas_e_ambiguo_e_guarda_alternativas():
    lig = ligar("o que e abençoado", _d())[0]
    assert ambigua(lig)
    assert {lig.chave.tabela, *(a.tabela for a in lig.alternativas)} == {
        "Condições", "Encantamentos de Armaduras"}


def test_pista_de_tabela_desfaz_o_empate():
    lig = ligar("qual a condição abençoado", _d())[0]
    assert lig.chave.tabela == "Condições"
    assert not ambigua(lig)


def test_mesma_tabela_fontes_diferentes_escolhe_a_fonte_prioritaria():
    lig = ligar("o que sao doencas", _d())[0]
    assert lig.chave.fonte == JA
    assert not ambigua(lig)


def test_apelido_aprovado_liga_com_tipo_apelido():
    alvo = Chave("Armas", "Machado Táurico", JA)
    d = _d(apelidos={"machado do minotauro": alvo})
    lig = ligar("quanto dano causa o machado do minotauro", d)[0]
    assert lig.tipo == "apelido" and lig.chave == alvo


def test_refinar_por_restricao_de_classe_resolve_empate_de_poderes():
    lig = ligar("qual o poder esmagador", _d())[0]
    assert ambigua(lig) or lig.chave.tabela.startswith("Poderes")
    sem_pista = ligar("o esmagador", _d())[0]
    assert ambigua(sem_pista)
    refinada = refinar_por_restricoes((sem_pista,), Restricoes(classes=("Bárbaro",)))[0]
    assert refinada.chave.tabela == "Poderes (Bárbaro)"
    assert not ambigua(refinada)


def test_refinar_sem_restricao_util_mantem_a_ambiguidade():
    sem_pista = ligar("o esmagador", _d())[0]
    mantida = refinar_por_restricoes((sem_pista,), Restricoes())[0]
    assert mantida == sem_pista


# --- classes de falha vistas no corpus real (checagem do caso semente) ---

def _dados_reais_minimos():
    return {"tabelas": [
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": JA},
            {"name": "Arcanista", "origin": JA, "abilities": [{"name": "Magias"}]},
            {"name": "Miragem (Caçador)", "origin": "Dragão Brasil - 211",
             "abilities": [{"name": "Dança da Areia"}]}]},
        {"arquivo": "powerCategories.ts", "export": "powerCategories", "elementos": [
            {"name": "Bárbaro", "origin": "Compendio T20"}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Condição", "origin": JA},
            {"name": "Bola de Fogo", "origin": JA}]},
        {"arquivo": "rules.tsx", "export": "ruleSections", "elementos": [
            {"name": "Habilidades", "origin": "Compendio T20"}]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Caído", "origin": JA}]},
    ]}


def test_palavra_de_categoria_sozinha_nao_vira_nome():
    d = construir(_dados_reais_minimos())
    ligs = ligar("quais as penalidades da condição Caído e quais habilidades e magias", d)
    assert [lig.chave.nome for lig in ligs] == ["Caído"]


def test_aproximada_nao_atravessa_pontuacao_nem_usa_palavra_comum():
    d = construir(_dados_reais_minimos())
    ligs = ligar("Qual o dano, a área e a resistência da magia Bola de Fogo?", d)
    assert [lig.chave.nome for lig in ligs] == ["Bola de Fogo"]


def test_tabela_de_categorias_perde_o_empate_para_a_entidade():
    d = construir(_dados_reais_minimos())
    lig = ligar("sou barbaro", d)[0]
    assert lig.chave.tabela == "Classes"
    assert not ambigua(lig)


# --- pronomes não fazem parte de nome (achado na avaliação: 'resistência dela') ---

def _d_resistencia():
    return construir({"tabelas": [{"arquivo": "races.ts", "export": "races", "elementos": [
        {"name": "Qareen", "origin": JA,
         "abilities": [{"name": "Resistência Elemental"}]}]}]})


@pytest.mark.parametrize("texto", [
    "e qual a CD de resistência dela?",
    "qual a resistência dele?",
    "e a resistência deles?",
    "a resistência disso",
    "a resistência dessa",
])
def test_pronome_no_fim_da_janela_nao_forma_nome_aproximado(texto):
    assert ligar(texto, _d_resistencia()) == ()


def test_nome_real_com_a_mesma_palavra_continua_ligando():
    ligs = ligar("o que faz a resistência elemental do qareen?", _d_resistencia())
    assert {lig.chave.sub for lig in ligs} >= {"Resistência Elemental"}
