from rag_core import Document, _diversificar


def _doc(tabela, nome, pagina):
    return Document(page_content=pagina, metadata={"Tabela": tabela, "Nome": nome})


def test_dedup_remove_chunk_repetido_e_preenche_por_score():
    docs = [
        _doc("Regras", "Habilidades", "chunk A"),
        _doc("Regras", "Habilidades", "chunk B"),
        _doc("Ameaças", "Basilisco", "basilisco"),
        _doc("Raças", "Suraggel", "suraggel"),
    ]
    sel = _diversificar(docs, top_n=3)
    assert [d.page_content for d in sel] == ["chunk A", "basilisco", "suraggel"]


def test_dedup_preenche_com_duplicatas_quando_faltam_vagas():
    docs = [
        _doc("Regras", "Testes", "t1"),
        _doc("Regras", "Testes", "t2"),
        _doc("Regras", "Testes", "t3"),
    ]
    sel = _diversificar(docs, top_n=2)
    assert [d.page_content for d in sel] == ["t1", "t2"]


def test_dedup_preserva_ordem_de_score_no_top():
    docs = [
        _doc("Chefes", "A", "1"),
        _doc("Magias", "B", "2"),
        _doc("Chefes", "A", "3"),
        _doc("Perícias", "C", "4"),
    ]
    sel = _diversificar(docs, top_n=3)
    assert [d.page_content for d in sel] == ["1", "2", "4"]


def test_cota_minima_de_tabelas_puxa_tabelas_ausentes_do_score():
    """RED: topo colapsado numa tabela -> cota=4 garante 4 tabelas distintas.

    Sem a cota, o top-4 seria Regras×3 + Magias (2 tabelas) mesmo com
    Origens e Ameaças disponíveis no pool.
    """
    docs = [
        _doc("Regras", "A", "r1"),
        _doc("Regras", "B", "r2"),
        _doc("Regras", "C", "r3"),
        _doc("Magias", "M", "m1"),
        _doc("Origens", "O", "o1"),
        _doc("Ameaças", "X", "a1"),
    ]
    sel = _diversificar(docs, top_n=4, cota_tabelas=4)
    tabelas = {d.metadata["Tabela"] for d in sel}
    assert len(sel) == 4, len(sel)
    assert len(tabelas) == 4, tabelas


def test_cota_maior_que_o_pool_e_best_effort():
    """cota impossível (pool só tem 1 tabela) -> devolve o topo, sem crash."""
    docs = [
        _doc("Regras", "A", "r1"),
        _doc("Regras", "B", "r2"),
        _doc("Regras", "C", "r3"),
    ]
    sel = _diversificar(docs, top_n=3, cota_tabelas=5)
    assert [d.page_content for d in sel] == ["r1", "r2", "r3"]
