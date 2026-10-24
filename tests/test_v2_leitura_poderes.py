"""'Qual poder pegar?': a leitura lista e filtra os poderes da classe para a ficha."""

from rag_v2.dicionario import construir
from rag_v2.integracao import bloco_dicas, descrever
from rag_v2.leitura import ler
from rag_v2.sessao import Sessao

JA = "Tormenta20 - Jogo do Ano"
PERGUNTA = ("Sou um inventor nivel 7, sou armeiro e tenho todos os oficios. Gostaria de começar a "
            "craftar itens, armaduras, armas e etc. Qual poder pegar? meu atributo principal é "
            "INT = 6")


def _d():
    return construir({"tabelas": [
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Inventor", "origin": JA, "skills": {
                "mandatory": ["Ofício (Int)", "Vontade (Sab)"],
                "optional": {"skills": ["Luta (For)"], "count": 4}}}]},
        {"arquivo": "skills.ts", "export": "skills", "elementos": [
            {"name": "Ofício", "origin": "Compendio T20"}]},
        {"arquivo": "powers-inventor.ts", "export": "powersInventor", "elementos": [
            {"name": "Armeiro", "origin": JA, "prerequisite": "treinado em Luta e Ofício (armeiro).",
             "description": "Proficiência com armas marciais e fabricar armas."},
            {"name": "Ferreiro", "origin": JA, "prerequisite": "Armeiro, 5º nível de inventor.",
             "description": "Arma fabricada por você causa mais dano."},
            {"name": "Couraceiro", "origin": JA, "prerequisite": "treinado em Ofício (armeiro).",
             "description": "Fabricar armaduras."},
            {"name": "Gênio Inovador", "origin": JA, "prerequisite": "17º nível de inventor",
             "description": "Poder de nível alto."},
            {"name": "Mestre Cuca", "origin": JA, "prerequisite": "treinado em Ofício (cozinheiro).",
             "description": "Cozinhar."}]},
    ]})


def _nomes(leitura, status):
    return [p.nome for p in leitura.poderes if p.status == status]


def test_pergunta_de_poder_avalia_todos_os_poderes_da_classe():
    leitura = ler(PERGUNTA, _d())
    assert {p.nome for p in leitura.poderes} == {"Armeiro", "Ferreiro", "Couraceiro",
                                                 "Gênio Inovador", "Mestre Cuca"}
    assert "Couraceiro" in _nomes(leitura, "disponivel")       # todos os ofícios
    assert "Ferreiro" in _nomes(leitura, "encadeado")
    assert "Armeiro" in _nomes(leitura, "indeterminado")        # Luta não informada
    assert "Gênio Inovador" in _nomes(leitura, "indisponivel")  # nível 17


def test_os_poderes_relevantes_ao_tema_viram_necessidades_com_registro():
    leitura = ler(PERGUNTA, _d())
    por_registro = {n.registro: n for n in leitura.necessidades if n.tabela_alvo == "Poderes (Inventor)"}
    assert {"Couraceiro", "Ferreiro", "Armeiro"} <= set(por_registro)
    assert "Gênio Inovador" not in por_registro                 # indisponível: sem espaço
    assert all(n.obrigatoria for n in por_registro.values())


def test_poder_nao_relevante_ao_tema_fica_so_na_lista():
    leitura = ler(PERGUNTA, _d())
    registros = {n.registro for n in leitura.necessidades}
    assert "Mestre Cuca" not in registros                      # cozinha não é craft de armas


def test_sem_a_palavra_poder_nao_avalia_poderes():
    assert ler("Sou inventor nivel 7, o que faz a perícia Ofício?", _d()).poderes == ()


def test_sem_nivel_nao_avalia_poderes():
    assert ler("Sou inventor, qual poder pegar?", _d()).poderes == ()


def test_classe_sem_tabela_de_poderes_nao_quebra():
    assert ler("Sou bárbaro nivel 4, qual poder pegar?", _d()).poderes == ()


def test_ficha_da_sessao_vale_em_pergunta_curta_de_poder():
    d, sessao = _d(), Sessao()
    sessao.atualizar(ler("Sou inventor nivel 7 e tenho todos os oficios, INT = 6", d, sessao))
    leitura = ler("qual poder eu pego?", d, sessao)
    assert "Couraceiro" in _nomes(leitura, "disponivel")


def test_bloco_de_dicas_lista_as_situacoes_e_o_que_falta():
    dicas = bloco_dicas(ler(PERGUNTA, _d()))
    assert "PODERES DE INVENTOR" in dicas and "nível 7" in dicas
    assert "Couraceiro" in dicas
    assert "Ferreiro (precisa de Armeiro)" in dicas
    assert "Armeiro" in dicas and "Luta" in dicas
    assert "Gênio Inovador" in dicas                            # em "não pode"
    assert "calculad" in dicas.lower()


def test_entendi_mostra_o_resumo_dos_poderes():
    texto = descrever(ler(PERGUNTA, _d()), None)
    assert "Poderes de Inventor" in texto and "disponíveis" in texto
