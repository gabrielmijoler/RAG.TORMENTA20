"""RED→GREEN: decompor_consulta — decomposição regra-based sem LLM.

Evolução Multi-Query / Multi-hop Reasoning:
- bypass em pergunta simples (lista unitária, zero custo);
- gatilho estrito: só decompõe com 2+ '?' ou marcador multi-tópico
  explícito ('e também', 'e quais', 'qual ... e qual ...');
- sub-queries derivadas ESTRICTAMENTE do texto do usuário (fatiamento
  das cláusulas), NUNCA templates fixos de raça/alimento;
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


def test_decompor_composto_deriva_clausulas_do_usuario():
    """Exemplo da spec (3 '?'): as sub-queries são as cláusulas do usuário.

    RED: hoje devolve templates fixos (classe/raça/alimentos) em vez do
    texto original — precisa falhar por conter conteúdo alheio à pergunta.
    """
    consulta = (
        "Para um inventor qual a melhor raça? "
        "fabricar engenhoca ou poção? quais alimentos?"
    )
    resultado = rag_core.decompor_consulta(consulta)
    assert resultado == [
        "Para um inventor qual a melhor raça?",
        "fabricar engenhoca ou poção?",
        "quais alimentos?",
    ], resultado


def test_query_magia_com_conector_faz_bypass():
    """Misfire real da rodada fr_l12_multiquery (21_magia_silencio).

    1 '?' e apenas ' e '/' ou ' comum => BYPASS, sem injetar sub-queries
    de raça/alimento na pergunta de magia.
    """
    consulta = ("O que a magia Silêncio faz com a área "
                "e com lançamentos de magia?")
    assert rag_core.decompor_consulta(consulta) == [consulta]


def test_conectivo_simples_faz_bypass_sem_templates():
    """Spec: frase com conectivo sem múltiplas perguntas => bypass puro."""
    consulta = "Regras sobre magia de silêncio e área de efeito"
    resultado = rag_core.decompor_consulta(consulta)
    assert resultado == [consulta]
    # guarda de regressão: nenhum template de raça/alimento pode aparecer
    assert not any("raça" in r.lower() or "alimento" in r.lower()
                   for r in resultado), resultado


def test_marcador_e_tambem_decompoe_texto_do_usuario():
    """1 '?' com marcador explícito de múltiplos tópicos => decompor,
    fatiando o PRÓPRIO texto do usuário (sem templates)."""
    consulta = "Quais regras de armadura e também de escudo?"
    resultado = rag_core.decompor_consulta(consulta)
    assert len(resultado) >= 2, resultado
    for pedaco in resultado:
        base = pedaco.rstrip("?").strip().lower()
        assert base in consulta.lower(), (pedaco, consulta)
    assert not any("raça" in r.lower() or "alimento" in r.lower()
                   for r in resultado), resultado


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


# ---------- goldenset enriquecido com perguntas compostas ----------

def test_goldenset_compostas_disparam_decompor():
    """As perguntas compostas do goldenset acionam o gatilho estrito e
    geram sub-queries derivadas do texto do usuário (sem templates)."""
    import json as _json
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / "goldenset.jsonl"
    casos = [_json.loads(l) for l in
             caminho.read_text(encoding="utf-8").splitlines() if l.strip()]
    compostas = []
    for caso in casos:
        subs = rag_core.decompor_consulta(caso["consulta"])
        if len(subs) > 1:
            compostas.append((caso["id"], subs, caso["consulta"]))

    # 1 pré-existente (23_magia_conjurar_monstro) + 5..8 novas compostas
    assert 6 <= len(compostas) <= 9, sorted(c[0] for c in compostas)

    for _id, subs, consulta in compostas:
        # toda sub-query é um trecho do próprio texto do usuário
        for s in subs:
            base = s.rstrip("?").strip().lower()
            assert base and base in consulta.lower(), (_id, s)
        # nenhum template fixo de raça/alimento pode aparecer
        assert not any("racas com bonus" in s.lower()
                       or "alimentos e pocoes" in s.lower()
                       for s in subs), _id
