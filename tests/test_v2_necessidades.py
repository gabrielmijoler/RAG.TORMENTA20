"""Necessidades da v2: o que a resposta precisa conter, por tipo de entidade."""

from rag_v2.necessidades import gerar
from rag_v2.tipos import Chave, Ligacao, Restricoes

JA = "Tormenta20 - Jogo do Ano"
TABELAS = frozenset({"Classes", "Raças", "Armas", "Perícias", "Magias",
                     "Poderes (Bárbaro)", "Poderes Gerais", "Condições",
                     "Encantamentos de Armaduras"})


def _lig(tabela, nome, sub=None, alternativas=()):
    return Ligacao(nome, 0, len(nome), Chave(tabela, nome, JA, sub), 1.0, "exata",
                   alternativas)


def _pares(necessidades):
    return [(n.tabela_alvo, n.entidade, n.obrigatoria) for n in necessidades]


def test_entidade_simples_pede_o_proprio_registro():
    nec = gerar((_lig("Magias", "Bola de Fogo"),), Restricoes(), "direta", TABELAS)
    assert _pares(nec) == [("Magias", "Bola de Fogo", True)]


def test_classe_com_nivel_pede_registro_e_habilidades_ate_o_nivel():
    nec = gerar((_lig("Classes", "Bárbaro"),),
                Restricoes(nivel=4, classes=("Bárbaro",)), "direta", TABELAS)
    assert ("Classes", "Bárbaro", True) in _pares(nec)
    assert any("até o nível 4" in n.descricao for n in nec)


def test_build_de_classe_pede_os_poderes_da_classe_se_a_tabela_existe():
    nec = gerar((_lig("Classes", "Bárbaro"),),
                Restricoes(nivel=4, classes=("Bárbaro",)), "build", TABELAS)
    assert ("Poderes (Bárbaro)", "Bárbaro", True) in _pares(nec)


def test_build_nao_inventa_tabela_de_poderes_que_nao_existe():
    nec = gerar((_lig("Classes", "Inventada"),),
                Restricoes(classes=("Inventada",)), "build", TABELAS)
    assert all(n.tabela_alvo != "Poderes (Inventada)" for n in nec)


def test_build_com_pericia_ou_item_pede_poderes_gerais_opcional():
    ligs = (_lig("Classes", "Bárbaro"), _lig("Perícias", "Intimidação"),
            _lig("Armas", "Machado Táurico"))
    r = Restricoes(nivel=4, classes=("Bárbaro",), pericias=("Intimidação",),
                   itens=("Machado Táurico",))
    nec = gerar(ligs, r, "build", TABELAS)
    gerais = [n for n in nec if n.tabela_alvo == "Poderes Gerais"]
    assert len(gerais) == 1 and gerais[0].obrigatoria is False
    assert "Intimidação" in gerais[0].entidade and "Machado Táurico" in gerais[0].entidade


def test_habilidade_aninhada_pede_o_registro_pai_com_o_nome_da_habilidade():
    nec = gerar((_lig("Classes", "Bárbaro", sub="Fúria"),), Restricoes(), "direta", TABELAS)
    assert _pares(nec) == [("Classes", "Bárbaro > Fúria", True)]


def test_ligacao_ambigua_ganha_uma_necessidade_por_alternativa():
    alt = Chave("Encantamentos de Armaduras", "Abençoado", JA)
    nec = gerar((_lig("Condições", "Abençoado", alternativas=(alt,)),),
                Restricoes(), "direta", TABELAS)
    assert {n.tabela_alvo for n in nec} == {"Condições", "Encantamentos de Armaduras"}


def test_mesma_chave_duas_vezes_nao_duplica_necessidade():
    ligs = (_lig("Armas", "Adaga"), _lig("Armas", "Adaga"))
    assert len(gerar(ligs, Restricoes(), "direta", TABELAS)) == 1


def test_raca_nao_pede_campo_de_tamanho_que_nao_existe():
    nec = gerar((_lig("Raças", "Bugbear"),), Restricoes(racas=("Bugbear",)), "build", TABELAS)
    assert all("tamanho" not in n.descricao.lower() for n in nec)


def test_necessidade_de_registro_aponta_o_nome_do_registro():
    nec = gerar((_lig("Classes", "Bárbaro", sub="Fúria"), _lig("Armas", "Adaga")),
                Restricoes(), "direta", TABELAS)
    assert [n.registro for n in nec] == ["Bárbaro", "Adaga"]


def test_necessidade_de_tabela_nao_tem_registro_fixo():
    nec = gerar((_lig("Classes", "Bárbaro"),),
                Restricoes(nivel=4, classes=("Bárbaro",)), "build", TABELAS)
    poderes = [n for n in nec if n.tabela_alvo == "Poderes (Bárbaro)"]
    assert poderes and poderes[0].registro is None
