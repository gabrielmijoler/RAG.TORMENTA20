"""Catálogo do corpus para o construtor de personagem: poderes por tabela, raças, perícias da classe."""

from rag_v2.catalogo import construir_catalogo
from rag_v2.dicionario import construir

JA = "Tormenta20 - Jogo do Ano"


def _dados():
    return {"tabelas": [
        {"arquivo": "powers-inventor.ts", "export": "powersInventor", "elementos": [
            {"name": "Armeiro", "origin": JA, "description": "Proficiência com armas marciais.",
             "prerequisite": "treinado em Luta e Ofício (armeiro)."},
            {"name": "Ferreiro", "origin": JA, "description": "Dano aumenta em um passo.",
             "prerequisite": "Armeiro, 5º nível de inventor."},
            {"name": "Invenção Potente", "origin": JA, "description": "x", "prerequisite": ""}]},
        {"arquivo": "powers-gerais.ts", "export": "powersGerais", "elementos": [
            {"name": "Ataque Pesado", "origin": JA, "description": "y", "prerequisite": "For 1."}]},
        {"arquivo": "races.ts", "export": "races", "elementos": [
            {"name": "Anão", "origin": JA}, {"name": "Goblin", "origin": JA}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Inventor", "origin": JA, "skills": {
                "mandatory": ["Ofício (Int)", "Vontade (Sab)"],
                "optional": {"skills": ["Luta (For)", "Cura (Sab)"], "count": 4}}}]},
        {"arquivo": "items.ts", "export": "items", "elementos": [{"name": "Adaga", "origin": JA}]},
    ]}


def test_poderes_ficam_agrupados_pela_tabela_com_prerequisito_e_fonte():
    cat = construir_catalogo(_dados())
    inventor = cat.poderes["Poderes (Inventor)"]
    assert [p.nome for p in inventor] == ["Armeiro", "Ferreiro", "Invenção Potente"]
    assert inventor[1].prerequisito == "Armeiro, 5º nível de inventor."
    assert inventor[0].fonte == JA and "marciais" in inventor[0].descricao
    assert "Poderes Gerais" in cat.poderes and "Adaga" not in str(cat.poderes)


def test_nomes_de_todos_os_poderes_e_racas_normalizados():
    cat = construir_catalogo(_dados())
    assert {"armeiro", "ferreiro", "ataque pesado", "invencao potente"} <= cat.nomes_poderes
    assert cat.racas == frozenset({"anao", "goblin"})


def test_pericias_da_classe_separam_obrigatorias_de_opcionais_sem_o_atributo():
    cat = construir_catalogo(_dados())
    assert cat.pericias_classe["inventor"]["obrigatorias"] == {"oficio", "vontade"}
    assert cat.pericias_classe["inventor"]["opcionais"] == {"luta", "cura"}


def test_tabela_dos_poderes_de_uma_classe_pelo_nome_da_classe():
    cat = construir_catalogo(_dados())
    assert cat.tabela_de_poderes("Inventor") == "Poderes (Inventor)"
    assert cat.tabela_de_poderes("inventor") == "Poderes (Inventor)"
    assert cat.tabela_de_poderes("Bárbaro") is None


def test_dicionario_expoe_o_catalogo():
    assert construir(_dados()).catalogo.tabela_de_poderes("Inventor") == "Poderes (Inventor)"


# --- quantas escolhas de poder a classe dá até o nível N (pela progressão do livro) ---------

def _dados_progressao():
    return {"tabelas": [{"arquivo": "classes.ts", "export": "classes", "elementos": [
        {"name": "Inventor", "origin": JA, "levelProgression": [
            {"level": 1, "abilities": "Engenhosidade, protótipo"},
            {"level": 2, "abilities": "Fabricar item superior (1 melhoria), poder de inventor"},
            {"level": 3, "abilities": "Comerciante, poder de inventor"},
            {"level": 4, "abilities": "Poder de inventor"},
            {"level": 8, "abilities": "Poder de inventor"}]}]}]}


def test_niveis_com_escolha_de_poder_ate_o_nivel():
    cat = construir_catalogo(_dados_progressao())
    assert cat.niveis_com_poder("Inventor", 4) == [2, 3, 4]
    assert cat.niveis_com_poder("inventor", 7) == [2, 3, 4]
    assert cat.niveis_com_poder("Inventor", 1) == []


def test_classe_sem_progressao_devolve_none():
    assert construir_catalogo(_dados_progressao()).niveis_com_poder("Bardo", 5) is None
