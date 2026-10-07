import rag_core
from tests.fakes import FakeChat


def test_modo_estrategia_padrao_e_baseline(monkeypatch):
    monkeypatch.delenv("ESTRATEGIA", raising=False)
    assert rag_core.modo_estrategia() == "baseline"


def test_modo_estrategia_lê_env_valida(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    assert rag_core.modo_estrategia() == "decompor"


def test_modo_estrategia_ignora_lixo(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "banana")
    assert rag_core.modo_estrategia() == "baseline"


def test_decompor_limpa_marcadores_e_limita_a_3():
    llm = FakeChat(respostas=[(
        "1. como funciona armadura pesada\n"
        "- qual a penalidade de armadura\n"
        "* armadura pesada\n"
        "penalidade de armadura; vestir armadura pesada\n"
        "uma linha a mais para estourar o limite\n"
    )])
    var = rag_core.decompor_consultas("como funciona armadura pesada", llm=llm)
    assert var == [
        "qual a penalidade de armadura",
        "armadura pesada",
        "penalidade de armadura",  # a 4ª linha partiu em 2 e o teto de 3 pegou a 1ª
    ]


def test_decompor_falha_devolve_vazio():
    llm = FakeChat(respostas=[RuntimeError("cota")])
    var = rag_core.decompor_consultas("x" * 40, llm=llm)
    assert var == []


def test_decompor_cacheia_por_query():
    llm = FakeChat(respostas=["uma outra forma de perguntar\ndois termos aqui\ntres sub questoes"])
    q = "quantos pv tem um ogro"
    rag_core.decompor_consultas(q, llm=llm)
    rag_core.decompor_consultas(q, llm=llm)
    assert llm.chamadas == 1


def _doc(chave, corpo):
    from langchain_core.documents import Document
    return Document(page_content=corpo, metadata={"chave": chave})


class _BuscaFalsa:
    def __init__(self):
        self.consultas = []

    def invoke(self, query):
        self.consultas.append(query)
        if query == "consulta real":
            return [_doc("real", "corpo real")]
        if query == "variante inutil":
            return [_doc("extra", "corpo da variante")]
        return []


class _CompressorFalso:
    """Espelha o CascataReranker: top_n setável + compress_documents(docs, query)."""

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


def test_recuperar_com_decompor_reune_variantes(monkeypatch):
    base = _BuscaFalsa()
    monkeypatch.setattr(
        rag_core, "decompor_consulta", lambda q, llm=None: ["variante inutil"]
    )
    rerank = _RerankFalso(base)
    docs = rag_core.recuperar(
        rerank, "consulta reformulada", "consulta real", decompor=True
    )
    assert {d.page_content for d in docs} == {"corpo real", "corpo da variante"}
    assert base.consultas == [
        "consulta reformulada", "consulta real", "variante inutil",
    ]
    assert rerank.base_compressor.queries_rerank == ["consulta real"]


def test_recuperar_por_padrao_nao_decompoe(monkeypatch):
    def _explode(q, llm=None):
        raise AssertionError("decompor não pode rodar por padrão")

    monkeypatch.setattr(rag_core, "decompor_consultas", _explode)
    monkeypatch.setenv("ESTRATEGIA", "decompor")  # env ligada não muda o default
    base = _BuscaFalsa()
    rerank = _RerankFalso(base)
    docs = rag_core.recuperar(rerank, "consulta reformulada", "consulta real")
    assert base.consultas == ["consulta reformulada", "consulta real"]
    assert rerank.base_compressor.queries_rerank == ["consulta real"]
    assert {d.page_content for d in docs} == {"corpo real"}


def test_decompor_quebra_sub_questoes_por_ponto_e_virgula():
    llm = FakeChat(respostas=["custo da magia; requisitos; quem ensina"])
    var = rag_core.decompor_consultas("quem ensina magia de 3 circulo", llm=llm)
    assert var == ["custo da magia", "requisitos", "quem ensina"]
