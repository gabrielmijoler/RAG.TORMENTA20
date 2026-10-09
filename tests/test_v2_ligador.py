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


# --- achados da rodada sintética (semente 7) ---

def _d_sint():
    return construir({"tabelas": [
        {"arquivo": "deuses.ts", "export": "gods", "elementos": [
            {"name": "Valkaria", "origin": JA}, {"name": "Thyatis", "origin": JA}]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Confuso", "origin": JA}, {"name": "Fraco", "origin": JA}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Arma Espiritual", "origin": JA}, {"name": "Santuário", "origin": JA}]},
    ]})


@pytest.mark.parametrize("digitado,esperado", [
    ("vlakaria", "Valkaria"),      # transposição
    ("cofnuso", "Confuso"),        # transposição
    ("valkria", "Valkaria"),       # letra a menos
    ("santario", "Santuário"),     # letra trocada
    ("thyatiss", "Thyatis"),       # letra a mais
])
def test_erro_de_uma_edicao_em_palavra_longa_liga_como_aproximada(digitado, esperado):
    lig = ligar(f"qual o efeito de {digitado}", _d_sint())[0]
    assert lig.chave.nome == esperado and lig.tipo == "aproximada"
    assert 0.80 <= lig.score < 1.0


def test_transposicao_com_ratio_abaixo_de_090_liga_pela_regra_de_uma_edicao():
    # 'vlakaria' x 'valkaria': ratio 0,875 (< 0,90), mas é UMA transposição de letras vizinhas
    from difflib import SequenceMatcher
    assert SequenceMatcher(None, "vlakaria", "valkaria").ratio() < 0.90
    assert ligar("qual o efeito de vlakaria", _d_sint())[0].chave.nome == "Valkaria"


def test_palavra_curta_com_uma_edicao_nao_liga():
    assert ligar("o que e fracp", _d_sint()) == ()   # 5 letras: abaixo do mínimo


def test_nome_que_contem_palavra_comum_pode_ligar_por_aproximacao():
    lig = ligar("qual o alcance da magia arma espiitual", _d_sint())[0]
    assert lig.chave.nome == "Arma Espiritual" and lig.tipo == "aproximada"


def test_janela_so_de_palavras_comuns_ou_de_categoria_continua_barrada():
    d = construir({"tabelas": [{"arquivo": "spells.ts", "export": "spells", "elementos": [
        {"name": "Arma Mágica", "origin": JA}]}]})
    assert ligar("quais as armas e a defesa", d) == ()


# --- erro de digitação não é palavra que existe no corpus (rodada rotulada) ---

def _d_vocab():
    registros = [{"name": "Precisa", "origin": JA}, {"name": "Ataque Acrobático", "origin": JA},
                 {"name": "Teia", "origin": JA}, {"name": "Machado Táurico", "origin": JA}]
    texto = [{"name": f"Regra {i}", "origin": JA,
              "description": "o personagem preciso crítico ataque machado magia"}
             for i in range(4)]
    return construir({"tabelas": [
        {"arquivo": "rules.tsx", "export": "ruleSections", "elementos": registros + texto}]})


@pytest.mark.parametrize("texto", [
    "o que preciso saber?",            # 'preciso' existe no corpus: não é typo de 'Precisa'
    "quanto dano causa um ataque crítico?",   # 'crítico' existe: não é typo de 'Acrobático'
])
def test_palavra_que_existe_no_corpus_nao_vira_aproximada(texto):
    assert [lig for lig in ligar(texto, _d_vocab()) if lig.tipo == "aproximada"] == []


def test_erro_de_digitacao_real_continua_ligando_com_vocabulario_ativo():
    lig = ligar("o machado toureo e bom?", _d_vocab())[0]
    assert lig.chave.nome == "Machado Táurico" and lig.tipo == "aproximada"


def test_plural_de_palavra_do_nome_nao_conta_como_diferente():
    d = construir({"tabelas": [{"arquivo": "weapons.ts", "export": "weapons", "elementos": [
        {"name": "Machado Táurico", "origin": JA, "description": "machados machados machados"},
        {"name": "Espada Curta", "origin": JA, "description": "espadas espadas espadas"}]}]})
    lig = ligar("quanto custam os machados taurico", d)
    assert [l.chave.nome for l in lig] == ["Machado Táurico"]


# --- aproximada precisa de âncora: palavra exata distintiva OU palavra errada longa ---

def _d_ancora():
    return construir({"tabelas": [
        {"arquivo": "races.ts", "export": "races", "elementos": [
            {"name": "Elfo", "origin": JA, "abilities": [{"name": "Magia Antiga"}]}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Teia", "origin": JA}, {"name": "Arma Espiritual", "origin": JA},
            {"name": "Bola de Fogo", "origin": JA}]},
        {"arquivo": "weapons.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}]},
    ]})


def test_palavra_de_categoria_mais_palavra_curta_errada_nao_liga():
    # 'magia' é só pista; 'tiea' (4 letras) não sustenta sozinha uma aproximação
    assert [l for l in ligar("oq faz a magia tiea", _d_ancora()) if l.tipo == "aproximada"] == []


def test_palavra_comum_mais_palavra_errada_longa_liga():
    lig = ligar("qual o alcance da magia arma espiitual", _d_ancora())[0]
    assert lig.chave.nome == "Arma Espiritual"


def test_palavra_exata_distintiva_ancora_a_aproximacao():
    nomes = {l.chave.nome for l in ligar("qto de pm gasta a bola de fgoo", _d_ancora())}
    assert "Bola de Fogo" in nomes
    assert {l.chave.nome for l in ligar("o machado toureo e bom", _d_ancora())} == {"Machado Táurico"}
