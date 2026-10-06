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
