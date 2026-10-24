"""Listar e filtrar os poderes de uma classe para um personagem (sem busca por semelhança)."""

from rag_v2.catalogo import construir_catalogo
from rag_v2.poderes import escolher_para_contexto, listar, tema_da_pergunta
from rag_v2.requisitos import Ficha

JA = "Tormenta20 - Jogo do Ano"


def _cat():
    return construir_catalogo({"tabelas": [
        {"arquivo": "powers-inventor.ts", "export": "powersInventor", "elementos": [
            {"name": "Armeiro", "origin": JA, "prerequisite": "treinado em Luta e Ofício (armeiro).",
             "description": "Proficiência com armas marciais e fabricar armas."},
            {"name": "Ferreiro", "origin": JA, "prerequisite": "Armeiro, 5º nível de inventor.",
             "description": "Arma corpo a corpo fabricada por você causa mais dano."},
            {"name": "Gênio Inovador", "origin": JA, "prerequisite": "17º nível de inventor",
             "description": "Poder de nível alto."},
            {"name": "Invenção Potente", "origin": JA, "prerequisite": "",
             "description": "Aumenta o dano de uma engenhoca."},
            {"name": "Mestre Alquimista", "origin": JA,
             "prerequisite": "Int 9, Alquimista Iniciado, 10º nível de inventor",
             "description": "Alquimia avançada."},
            {"name": "Resistente", "origin": JA, "prerequisite": "treinado em Vontade",
             "description": "Defesa."},
            {"name": "Alquimista Iniciado", "origin": JA,
             "prerequisite": "Int 1, treinado em Ofício (alquimista).",
             "description": "Fabricar poções e itens alquímicos."}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Inventor", "origin": JA, "skills": {
                "mandatory": ["Ofício (Int)", "Vontade (Sab)"],
                "optional": {"skills": ["Luta (For)"], "count": 4}}}]},
    ]})


def _ficha(**kw):
    return Ficha(**{"classe": "Inventor", "nivel": 7, "atributos": {"int": 6},
                    "todos_oficios": True, **kw})


def _por_nome(lista):
    return {p.nome: p for p in lista}


def test_lista_todos_os_poderes_da_tabela_da_classe_com_status():
    r = _por_nome(listar(_cat(), "Inventor", _ficha()))
    assert set(r) == {"Armeiro", "Ferreiro", "Gênio Inovador", "Invenção Potente",
                      "Mestre Alquimista", "Resistente", "Alquimista Iniciado"}
    assert r["Invenção Potente"].status == "disponivel"


def test_poder_sem_pre_requisito_e_poder_de_pericia_obrigatoria_da_classe_estao_disponiveis():
    r = _por_nome(listar(_cat(), "Inventor", _ficha()))
    assert r["Resistente"].status == "disponivel"       # Vontade é obrigatória do Inventor
    assert r["Alquimista Iniciado"].status == "disponivel"  # Int 1 ok + Ofício (todos)


def test_pericia_opcional_da_classe_fica_indeterminada_com_nota():
    r = _por_nome(listar(_cat(), "Inventor", _ficha()))["Armeiro"]
    assert r.status == "indeterminado"
    assert any("Luta" in p for p in r.pendencias)
    assert any("Luta" in n and "opcionais" in n for n in r.notas)


def test_poder_que_depende_de_outro_poder_e_encadeado():
    r = _por_nome(listar(_cat(), "Inventor", _ficha()))["Ferreiro"]
    assert r.status == "encadeado" and r.encadeados == ("armeiro",)


def test_nivel_ou_atributo_insuficiente_e_indisponivel():
    r = _por_nome(listar(_cat(), "Inventor", _ficha()))
    assert r["Gênio Inovador"].status == "indisponivel"
    assert r["Mestre Alquimista"].status == "indisponivel"


def test_nivel_baixo_derruba_o_encadeado_para_indisponivel():
    r = _por_nome(listar(_cat(), "Inventor", _ficha(nivel=4)))["Ferreiro"]
    assert r.status == "indisponivel"


def test_poder_ja_possuido_libera_o_encadeado():
    r = _por_nome(listar(_cat(), "Inventor", _ficha(poderes={"armeiro"})))["Ferreiro"]
    assert r.status == "disponivel"


def test_classe_sem_tabela_de_poderes_devolve_lista_vazia():
    assert listar(_cat(), "Bardo", _ficha(classe="Bardo")) == []


def test_ordem_status_depois_relevancia_depois_nome():
    tema = tema_da_pergunta("quero fabricar armas", "Inventor")
    nomes = [p.nome for p in listar(_cat(), "Inventor", _ficha(), tema)]
    assert nomes.index("Invenção Potente") < nomes.index("Armeiro") < nomes.index("Gênio Inovador")
    assert nomes[-1] in {"Gênio Inovador", "Mestre Alquimista"}


def test_tema_ignora_palavras_vazias_e_o_nome_da_classe_e_usa_sinonimos():
    tema = tema_da_pergunta("Sou inventor e quero craftar armaduras", "Inventor")
    assert "inven" not in tema and "quero" not in tema
    assert "fabri" in tema                          # craftar -> fabricar
    assert "armad" in tema


def test_relevancia_conta_palavras_do_tema_no_nome_e_na_descricao():
    tema = tema_da_pergunta("fabricar armas", "Inventor")
    r = _por_nome(listar(_cat(), "Inventor", _ficha(), tema))
    assert r["Armeiro"].relevancia > r["Resistente"].relevancia == 0


def test_escolha_para_o_contexto_respeita_o_maximo_e_exclui_indisponiveis():
    tema = tema_da_pergunta("fabricar armas", "Inventor")
    lista = listar(_cat(), "Inventor", _ficha(), tema)
    escolhidos = escolher_para_contexto(lista, maximo=3)
    assert len(escolhidos) == 3
    assert all(p.status != "indisponivel" for p in escolhidos)
    assert escolhidos[0].nome in {"Armeiro", "Alquimista Iniciado"}   # relevantes primeiro


def test_escolha_so_inclui_irrelevantes_quando_ha_poucos_relevantes():
    lista = listar(_cat(), "Inventor", _ficha(), tema_da_pergunta("fabricar armas", "Inventor"))
    nomes = [p.nome for p in escolher_para_contexto(lista)]
    assert "Resistente" not in nomes and "Invenção Potente" not in nomes   # 3 relevantes bastam


def test_sem_tema_a_escolha_cai_nos_primeiros_pegaveis():
    lista = listar(_cat(), "Inventor", _ficha(), frozenset())
    nomes = [p.nome for p in escolher_para_contexto(lista)]
    assert 1 <= len(nomes) <= 4 and all(p.status != "indisponivel"
                                        for p in escolher_para_contexto(lista))


def test_relevancia_ao_tema_vence_a_situacao_na_escolha_do_contexto():
    # Ferreiro (encadeado) é mais relevante a "fabricar armas" que Invenção Potente (disponível)
    lista = listar(_cat(), "Inventor", _ficha(), tema_da_pergunta("fabricar armas corpo", "Inventor"))
    nomes = [p.nome for p in escolher_para_contexto(lista, maximo=3)]
    assert "Ferreiro" in nomes


def test_oficio_nao_gera_nota_de_pericia_opcional():
    cat = construir_catalogo({"tabelas": [
        {"arquivo": "powers-inventor.ts", "export": "powersInventor", "elementos": [
            {"name": "Couraceiro", "origin": JA, "prerequisite": "treinado em Ofício (armeiro).",
             "description": "x"}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Inventor", "origin": JA, "skills": {
                "mandatory": ["Ofício (Int)"], "optional": {"skills": ["Ofício (Int)"], "count": 1}}}]},
    ]})
    r = listar(cat, "Inventor", _ficha(todos_oficios=False))[0]
    assert r.status == "indeterminado" and r.notas == ()
