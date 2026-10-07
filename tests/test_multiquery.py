"""RED→GREEN: decompor_consulta — decomposição regra-based sem LLM.

Evolução Multi-Query / Multi-hop Reasoning:
- bypass em pergunta simples (lista unitária, zero custo);
- até 3 sub-queries focadas em pergunta composta (classe, raça, itens);
- dedup dos chunks das sub-queries no recuperar();
- rerank continua usando APENAS a consulta original (precisão FlashRank).
"""
import rag_core


def _doc(chave, corpo):
    from langchain_core.documents import Document
    return Document(page_content=corpo, metadata={"chave": chave})


# ---------- decompor_consulta ----------

def test_decompor_simples_bypass():
    """Pergunta simples (1 ?) retorna [consulta] — busca original intacta."""
    consulta = "Qual a melhor raça para cavaleiro?"
    assert rag_core.decompor_consulta(consulta) == [consulta]


def test_decompor_composto_gera_3_sub_queries():
    """Exemplo da especificação: classe + raça + alimentos."""
    resultado = rag_core.decompor_consulta(
        "Para um inventor qual a melhor raça? "
        "fabricar engenhoca ou poção? quais alimentos?"
    )
    assert len(resultado) == 3, resultado
    textos = [r.lower() for r in resultado]
    assert any("classe inventor" in t for t in textos), textos
    assert any(t.startswith("racas") for t in textos), textos
    assert any("alimentos" in t for t in textos), textos
    # spec: "Alimentos e pocoes com bonus para Inventor"
    assert any("para inventor" in t for t in textos), textos


def test_decompor_nunca_mais_que_3():
    for entrada in ("qualquer coisa aqui", "pergunta ? dupla ? tripla ?"):
        assert len(rag_core.decompor_consulta(entrada)) <= 3, entrada


def test_decompor_vazia_devolve_lista_vazia():
    assert rag_core.decompor_consulta("") == []


def test_decompor_bypass_sem_acento_sem_interrogacao():
    consulta = "Qual a melhor raca para cavaleiro"
    assert rag_core.decompor_consulta(consulta) == [consulta]


# ---------- integração em recuperar() ----------

class _BuscaFalsa:
    """Devolvé corpos duplicados entre sub-queries para exercitar o dedup."""

    def __init__(self):
        self.consultas = []

    def invoke(self, query):
        self.consultas.append(query)
        if query == "consulta original":
            return [_doc("base", "corpo base")]
        if query == "sub 1":
            # repete "corpo base" e traz "corpo b"
            return [_doc("dup", "corpo base"), _doc("b", "corpo b")]
        if query == "sub 2":
            # repete "corpo b" e traz "corpo c"
            return [_doc("b2", "corpo b"), _doc("c", "corpo c")]
        return []


class _CompressorFalso:
    """Espelha o CascataReranker: top_n setável + compress_documents(docs, q)."""

    def __init__(self):
        self.top_n = 8
        self.ultimo_modo = None
        self.queries_rerank = []

    def compress_documents(self, docs, query, callbacks=None):
        self.queries_rerank.append(query)
        return list(docs)


class _RerankFalso:
    def __init__(self, base):
        self.base_retriever = base
        self.base_compressor = _CompressorFalso()


def test_recuperar_deduplica_chunks_entre_subqueries(monkeypatch):
    base = _BuscaFalsa()
    monkeypatch.setattr(
        rag_core, "decompor_consulta", lambda q: ["sub 1", "sub 2"]
    )
    rerank = _RerankFalso(base)
    docs = rag_core.recuperar(rerank, "consulta original", decompor=True)
    # "corpo base" (base+sub1) e "corpo b" (sub1+sub2) entram UMA vez
    assert {d.page_content for d in docs} == {"corpo base", "corpo b", "corpo c"}
    assert base.consultas == ["consulta original", "sub 1", "sub 2"]


def test_recuperar_rerank_somente_com_consulta_original(monkeypatch):
    """ATENÇÃO da spec: FlashRank pontua só com a query do usuário."""
    base = _BuscaFalsa()
    monkeypatch.setattr(
        rag_core, "decompor_consulta", lambda q: ["sub 1", "sub 2"]
    )
    rerank = _RerankFalso(base)
    rag_core.recuperar(rerank, "consulta original", decompor=True)
    assert rerank.base_compressor.queries_rerank == ["consulta original"]


def test_recuperar_por_padrao_nao_decompoe(monkeypatch):
    def _explode(q):
        raise AssertionError("decompor_consulta só com decompor=True")

    monkeypatch.setattr(rag_core, "decompor_consulta", _explode)
    base = _BuscaFalsa()
    rerank = _RerankFalso(base)
    docs = rag_core.recuperar(rerank, "consulta original")
    assert base.consultas == ["consulta original"]
    assert {d.page_content for d in docs} == {"corpo base"}
