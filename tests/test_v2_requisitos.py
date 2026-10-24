"""Leitor de pré-requisitos de poderes (texto livre do livro) e avaliação contra uma ficha."""

import pytest

from rag_v2.requisitos import Ficha, avaliar, interpretar

PODERES = frozenset({"armeiro", "alquimista iniciado", "engenhoqueiro", "afinidade (ar ou fogo)"})
RACAS = frozenset({"goblin", "anao", "hynne"})


def _ler(texto):
    return interpretar(texto, PODERES, RACAS)


def _tipos(texto):
    return [[r.tipo for r in alternativas] for alternativas in _ler(texto)]


# --- leitura -------------------------------------------------------------------------

@pytest.mark.parametrize("texto", ["", "—", "-", None, "   "])
def test_sem_pre_requisito_devolve_lista_vazia(texto):
    assert _ler(texto) == []


def test_atributo():
    (alt,) = _ler("Int 3")
    assert (alt[0].tipo, alt[0].a, alt[0].n) == ("atributo", "int", 3)


def test_atributo_por_extenso_e_maiusculas():
    assert _ler("Sabedoria 2")[0][0].a == "sab"
    assert _ler("CAR 1")[0][0].a == "car"


def test_nivel_de_classe_com_varios_formatos_de_ordinal():
    for texto in ("10º nível de inventor", "5° nível de inventor", "7o nível de Inventor.",
                  "10º nível de arcanista"):
        r = _ler(texto)[0][0]
        assert r.tipo == "nivel" and r.n in (10, 5, 7)
    assert _ler("10º nível de inventor")[0][0].a == "inventor"


def test_treinado_em_varias_pericias_e_todas_sao_exigidas():
    alts = _ler("treinado em Luta e Ofício (armeiro)")
    assert [a[0].tipo for a in alts] == ["treinado", "treinado"]
    assert (alts[0][0].a, alts[0][0].sub) == ("luta", None)
    assert (alts[1][0].a, alts[1][0].sub) == ("oficio", "armeiro")


def test_treinado_com_ou_vira_alternativas():
    (alt,) = _ler("treinado em Adestramento (parceiro animal) ou Diplomacia (parceiro humanoide)")
    assert [r.a for r in alt] == ["adestramento", "diplomacia"]


def test_outro_poder_conhecido_vira_requisito_de_poder():
    r = _ler("Armeiro, 5º nível de inventor.")
    assert [x[0].tipo for x in r] == ["poder", "nivel"]
    assert r[0][0].a == "armeiro"


def test_poder_com_parenteses_nao_e_quebrado_pelo_ou_interno():
    (alt,) = _ler("Afinidade (ar ou fogo)")
    assert [r.tipo for r in alt] == ["poder"] and alt[0].a == "afinidade (ar ou fogo)"


def test_raca_e_devoto_e_circulo():
    assert _tipos("goblin") == [["raca"]]
    assert _tipos("devoto de Azgher") == [["devoto"]]
    assert _tipos("lançar magias de 2º círculo") == [["circulo"]]
    assert _ler("lançar magias de 2º círculo")[0][0].n == 2


def test_texto_que_nao_entende_vira_desconhecido_e_nunca_some():
    (alt,) = _ler("alguma regra estranha da mesa")
    assert alt[0].tipo == "desconhecido" and "estranha" in alt[0].texto


def test_varios_requisitos_separados_por_virgula():
    assert _tipos("Int 3, Sab 3, Alquimista Iniciado, 10º nível de inventor.") == [
        ["atributo"], ["atributo"], ["poder"], ["nivel"]]


# --- avaliação contra a ficha ------------------------------------------------------------

def _f(**kw):
    return Ficha(**{"classe": "Inventor", "nivel": 7, "atributos": {"int": 6}, **kw})


def test_sem_requisito_esta_disponivel():
    assert avaliar([], _f()).status == "disponivel"


def test_atributo_suficiente_e_insuficiente():
    assert avaliar(_ler("Int 3"), _f()).status == "disponivel"
    r = avaliar(_ler("Int 9"), _f())
    assert r.status == "indisponivel" and any("Int 9" in p for p in r.pendencias)


def test_atributo_nao_informado_e_indeterminado_nunca_presumido():
    r = avaliar(_ler("Sab 3"), _f(atributos={}))
    assert r.status == "indeterminado"


def test_nivel_insuficiente_e_indisponivel_e_suficiente_e_ok():
    assert avaliar(_ler("10º nível de inventor"), _f()).status == "indisponivel"
    assert avaliar(_ler("5º nível de inventor"), _f()).status == "disponivel"


def test_nivel_de_outra_classe_e_indisponivel():
    assert avaliar(_ler("5º nível de bárbaro"), _f()).status == "indisponivel"


def test_nivel_sem_ficha_de_nivel_e_indeterminado():
    assert avaliar(_ler("5º nível de inventor"), _f(nivel=None)).status == "indeterminado"


def test_oficio_com_todos_os_oficios_ou_subtipo_ou_nao_informado():
    assert avaliar(_ler("treinado em Ofício (armeiro)"), _f(todos_oficios=True)).status == "disponivel"
    assert avaliar(_ler("treinado em Ofício (armeiro)"), _f(oficios={"armeiro"})).status == "disponivel"
    assert avaliar(_ler("treinado em Ofício (armeiro)"), _f()).status == "indeterminado"


def test_pericia_nao_informada_e_indeterminada_com_a_pendencia_dita():
    r = avaliar(_ler("treinado em Luta"), _f())
    assert r.status == "indeterminado" and any("Luta" in p for p in r.pendencias)
    assert avaliar(_ler("treinado em Luta"), _f(pericias={"luta"})).status == "disponivel"


def test_ou_entre_pericias_basta_uma():
    texto = "treinado em Adestramento ou Diplomacia"
    assert avaliar(_ler(texto), _f(pericias={"diplomacia"})).status == "disponivel"


def test_poder_ausente_vira_encadeado_e_poder_possuido_vira_disponivel():
    r = avaliar(_ler("Armeiro, 5º nível de inventor."), _f())
    assert r.status == "encadeado" and r.encadeados == ["armeiro"]
    assert avaliar(_ler("Armeiro, 5º nível de inventor."), _f(poderes={"armeiro"})).status == "disponivel"


def test_encadeado_nao_esconde_um_impedimento_definitivo():
    r = avaliar(_ler("Armeiro, 10º nível de inventor."), _f())
    assert r.status == "indisponivel"


def test_raca_e_devoto_conferem_quando_informados():
    assert avaliar(_ler("goblin"), _f(raca="Goblin")).status == "disponivel"
    assert avaliar(_ler("goblin"), _f(raca="Anão")).status == "indisponivel"
    assert avaliar(_ler("goblin"), _f()).status == "indeterminado"
    assert avaliar(_ler("devoto de Azgher"), _f(devoto="Khalmyr")).status == "indisponivel"


def test_desconhecido_deixa_indeterminado():
    assert avaliar(_ler("regra estranha"), _f()).status == "indeterminado"
