"""Pergunta em camadas ("liste N comidas que ajudam com mana"): tipo de item x efeito."""

from langchain_core.documents import Document

from rag_v2.camadas import camadas
from rag_v2.dicionario import construir
from rag_v2.integracao import bloco_dicas
from rag_v2.leitura import ler
from rag_v2.orcamento import calcular
from rag_v2.recuperacao import indexar_registros, recuperar_v2

PERGUNTA = "me liste 5 comidas que ajuda com a mana"
TABELAS = frozenset({"Alimentos", "Poções", "Magias"})


def test_comida_com_mana_vira_alimentos_com_subconsultas_no_vocabulario_do_livro():
    c = camadas(PERGUNTA, TABELAS)
    assert c.tabela == "Alimentos" and c.quantidade == 5
    assert any("PM temporários" in s for s in c.subconsultas)
    assert all(s.startswith("alimento") for s in c.subconsultas)


def test_sem_efeito_ou_sem_categoria_nao_ha_camadas():
    assert camadas("quais comidas existem?", TABELAS) is None
    assert camadas("como recuperar mana?", TABELAS) is None


def test_tabela_fora_do_corpus_nao_gera_camadas():
    assert camadas(PERGUNTA, frozenset({"Magias"})) is None


def test_quantidade_por_extenso_e_ausente():
    assert camadas("liste cinco bebidas que dao PM", TABELAS).quantidade == 5
    assert camadas("comidas que ajudam com mana", TABELAS).quantidade is None


def _d():
    return construir({"tabelas": [
        {"arquivo": "food.ts", "export": "food", "elementos": [
            {"name": "Gorad Quente", "origin": "Tormenta20"}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Bola de Fogo", "origin": "Tormenta20 - Jogo do Ano"}]},
    ]})


def test_leitura_da_pergunta_em_camadas():
    leitura = ler(PERGUNTA, _d())
    assert leitura.tipo == "lista" and leitura.confianca == "media"
    assert leitura.usar_llm == "traducao"
    assert leitura.camadas.tabela == "Alimentos"
    assert {n.tabela_alvo for n in leitura.necessidades} == {"Alimentos"}
    assert all(n.registro is None for n in leitura.necessidades)
    assert leitura.k == 8


def test_orcamento_da_lista_segue_a_quantidade_pedida():
    assert calcular("lista", (), "media", quantidade=5) == 8
    assert calcular("lista", (), "media", quantidade=10) == 13
    assert calcular("lista", (), "media", quantidade=40) == 15


def test_dicas_da_lista_mandam_dizer_quantos_achou_sem_completar():
    dicas = bloco_dicas(ler(PERGUNTA, _d()))
    assert "5" in dicas and "não complete" in dicas.lower()
    assert "PM temporários" in dicas


def _doc(nome):
    return Document(page_content=f"[Alimentos > F]\n# {nome}\nDescrição: {nome}",
                    metadata={"Tabela": "Alimentos", "Nome": nome, "Fonte": "F"})


class _Busca:
    def __init__(self, por_consulta):
        self.por_consulta, self.chamadas = por_consulta, []

    def invoke(self, consulta):
        self.chamadas.append(consulta)
        return list(self.por_consulta.get(consulta, []))


class _Rerank:
    top_n, ultimo_modo = 12, None

    def __init__(self):
        self.consultas = []

    def compress_documents(self, docs, query):
        self.consultas.append(query)
        return [Document(page_content=d.page_content,
                         metadata=dict(d.metadata, relevance_score=0.05)) for d in docs]


class _Retriever:
    def __init__(self, busca, rerank):
        self.base_retriever, self.base_compressor = busca, rerank


def test_recuperacao_busca_cada_camada_e_rerankeia_com_o_vocabulario_do_livro():
    leitura = ler(PERGUNTA, _d())
    sub = leitura.camadas.subconsultas
    gorad, sopa = _doc("Gorad Quente"), _doc("Sopa de Peixe")
    busca = _Busca({sub[0]: [gorad], sub[1]: [sopa]})
    rerank = _Rerank()
    top, _ = recuperar_v2(_Retriever(busca, rerank), leitura, indexar_registros([gorad, sopa]),
                             "q", PERGUNTA)
    assert set(sub) <= set(busca.chamadas)
    assert {d.metadata["Nome"] for d in top} == {"Gorad Quente", "Sopa de Peixe"}   # abaixo do limiar, mas garantidos
    assert rerank.consultas == [sub[0]]
