from rag_core import Document, aplicar_filtros, parsear_filtros


def _doc(tabela="Magias", fonte="Tormenta20 - Jogo do Ano", tipo="Arcana"):
    return Document(
        page_content="x",
        metadata={"Tabela": tabela, "Fonte": fonte, "Tipo": tipo},
    )


def test_parse_aceita_chave_minuscula_e_valor_com_aspas():
    assert parsear_filtros('tabela=Magias fonte="Tormenta20 - Jogo do Ano"') == {
        "Tabela": "Magias",
        "Fonte": "Tormenta20 - Jogo do Ano",
    }


def test_parse_ignora_chave_desconhecida_e_token_solto():
    assert parsear_filtros("foo=bar solto tabela=Condições") == {"Tabela": "Condições"}


def test_parse_aspas_simples_e_acento_na_chave():
    assert parsear_filtros("FONTE='Ameaças de Arton'") == {"Fonte": "Ameaças de Arton"}


def test_parse_vazio_quando_nao_ha_par():
    assert parsear_filtros("limpar") == {}
    assert parsear_filtros("") == {}


def test_aplicar_filtro_casa_sem_acento_e_caixa():
    docs = [_doc(tabela="Perícias"), _doc(tabela="Magias")]
    sel = aplicar_filtros(docs, {"Tabela": "pericias"})
    assert [d.metadata["Tabela"] for d in sel] == ["Perícias"]


def test_aplicar_varios_filtros_e_e():
    docs = [_doc(), _doc(tipo="Divina"), _doc(tabela="Deuses")]
    sel = aplicar_filtros(docs, {"Tabela": "Magias", "Tipo": "arcana"})
    assert len(sel) == 1


def test_aplicar_sem_filtro_devolve_tudo_e_sem_match_devolve_vazio():
    docs = [_doc()]
    assert aplicar_filtros(docs, None) == docs
    assert aplicar_filtros(docs, {}) == docs
    assert aplicar_filtros(docs, {"Tabela": "Inexistente"}) == []
