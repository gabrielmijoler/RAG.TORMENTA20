"""Recuperação por necessidade da v2 (retriever e reranker falsos, sem Qdrant)."""

import pytest
from langchain_core.documents import Document

from rag_v2.recuperacao import VAGAS_POR_TABELA, indexar_registros, recuperar_v2
from rag_v2.tipos import Leitura, Necessidade


def _doc(tabela, nome, extra=""):
    return Document(page_content=f"[{tabela} > F]\n# {nome}\nDescrição: {nome} {extra}",
                    metadata={"Tabela": tabela, "Nome": nome, "Fonte": "F"})


class BuscaFalsa:
    def __init__(self, por_consulta=None, padrao=()):
        self.por_consulta = por_consulta or {}
        self.padrao = list(padrao)
        self.chamadas = []

    def invoke(self, consulta):
        self.chamadas.append(consulta)
        return list(self.por_consulta.get(consulta, self.padrao))


class RerankFalso:
    def __init__(self, scores, falhar=False):
        self.scores = scores
        self.falhar = falhar
        self.top_n = 12
        self.ultimo_modo = None
        self.consultas = []

    def compress_documents(self, docs, query):
        self.consultas.append(query)
        if self.falhar:
            raise RuntimeError("cota")
        saida = []
        for d in docs:
            meta = dict(d.metadata, relevance_score=self.scores.get(d.metadata["Nome"], 0.1))
            saida.append(Document(page_content=d.page_content, metadata=meta))
        self.ultimo_modo = "flashrank"
        return sorted(saida, key=lambda d: -d.metadata["relevance_score"])[: self.top_n]


class RetrieverFalso:
    def __init__(self, busca, rerank):
        self.base_retriever = busca
        self.base_compressor = rerank


GRIFO = _doc("Montarias", "Grifo")
OUTROS = [_doc("Poderes de Destino", f"Parceiro {i}") for i in range(20)]
REGISTROS = indexar_registros([GRIFO, *OUTROS])


def _leitura(*necessidades, k=8):
    return Leitura(texto_original="q", necessidades=tuple(necessidades), k=k,
                   confianca="alta", tipo="direta")


def _grifo():
    return Necessidade("registro de Grifo", "Montarias", "Grifo", registro="Grifo")


def test_registro_ligado_entra_mesmo_que_a_busca_nao_o_traga():
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({"Grifo": 0.9}))
    top, tele = recuperar_v2(ret, _leitura(_grifo()), REGISTROS, "q", "q")
    assert any(d.metadata["Nome"] == "Grifo" for d in top)
    assert tele["necessidades"][0]["atendida"] is True


def test_registro_garantido_entra_mesmo_abaixo_do_limiar():
    scores = {f"Parceiro {i}": 0.99 for i in range(20)} | {"Grifo": 0.05}
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso(scores))
    top, _ = recuperar_v2(ret, _leitura(_grifo()), REGISTROS, "q", "q", limiar=0.5)
    assert any(d.metadata["Nome"] == "Grifo" for d in top)


def test_rerank_unico_com_a_pergunta_original():
    rerank = RerankFalso({})
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), rerank)
    nec = Necessidade("poderes de Bárbaro", "Poderes de Destino", "Bárbaro")
    recuperar_v2(ret, _leitura(_grifo(), nec), REGISTROS, "traduzida", "original")
    assert rerank.consultas == ["original"]
    assert rerank.top_n == 12  # o configurado volta depois do rerank


def test_busca_com_as_duas_formulacoes_e_com_a_descricao_da_necessidade_de_tabela():
    busca = BuscaFalsa(padrao=OUTROS)
    nec = Necessidade("poderes de Bárbaro", "Poderes de Destino", "Bárbaro")
    recuperar_v2(RetrieverFalso(busca, RerankFalso({})), _leitura(nec),
                 REGISTROS, "traduzida", "original")
    assert busca.chamadas == ["traduzida", "original", "poderes de Bárbaro"]


def test_necessidade_de_tabela_garante_ate_n_vagas_da_tabela():
    scores = {"Grifo": 0.9}  # os poderes ficam com 0.1, abaixo do limiar
    nec = Necessidade("poderes", "Poderes de Destino", "x")
    ret = RetrieverFalso(BuscaFalsa(padrao=[GRIFO, *OUTROS]), RerankFalso(scores))
    top, _ = recuperar_v2(ret, _leitura(nec), REGISTROS, "q", "q", limiar=0.5)
    poderes = [d for d in top if d.metadata["Tabela"] == "Poderes de Destino"]
    assert len(poderes) == VAGAS_POR_TABELA


def test_orcamento_k_e_um_documento_por_registro():
    duplicado = _doc("Poderes de Destino", "Parceiro 1", "outro trecho")
    ret = RetrieverFalso(BuscaFalsa(padrao=[*OUTROS, duplicado]),
                         RerankFalso({f"Parceiro {i}": 0.9 for i in range(20)}))
    top, _ = recuperar_v2(ret, _leitura(k=5), REGISTROS, "q", "q")
    assert len(top) == 5
    nomes = [d.metadata["Nome"] for d in top]
    assert len(nomes) == len(set(nomes))


def test_falha_do_rerank_segue_na_ordem_da_busca_e_ainda_garante():
    rerank = RerankFalso({}, falhar=True)
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), rerank)
    top, tele = recuperar_v2(ret, _leitura(_grifo()), REGISTROS, "q", "q")
    assert any(d.metadata["Nome"] == "Grifo" for d in top)
    assert tele["reranker"] == "ensemble_fallback"
    assert rerank.top_n == 12


def test_necessidade_sem_registro_no_corpus_fica_nao_atendida():
    falta = Necessidade("registro de X", "Montarias", "X", registro="X")
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({}))
    _, tele = recuperar_v2(ret, _leitura(falta), REGISTROS, "q", "q")
    assert tele["necessidades"][0]["atendida"] is False


@pytest.mark.parametrize("k", [1, 3])
def test_garantidos_podem_passar_do_k_mas_nao_o_preenchimento(k):
    a = Necessidade("a", "Montarias", "Grifo", registro="Grifo")
    b = Necessidade("b", "Poderes de Destino", "Parceiro 1", registro="Parceiro 1")
    c = Necessidade("c", "Poderes de Destino", "Parceiro 2", registro="Parceiro 2")
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({}))
    top, _ = recuperar_v2(ret, _leitura(a, b, c, k=k), REGISTROS, "q", "q")
    assert len(top) == max(k, 3)


def test_telemetria_traz_o_rastro_por_etapa():
    scores = {f"Parceiro {i}": 0.99 for i in range(20)} | {"Grifo": 0.05}
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso(scores))
    _, tele = recuperar_v2(ret, _leitura(_grifo(), k=5), REGISTROS, "q", "q", limiar=0.5)
    rastro = tele["rastro"]
    assert "Montarias|Grifo" in rastro["candidatos"]           # entrou direto
    assert "Montarias|Grifo" in rastro["rerank"]               # foi reordenado
    assert "Montarias|Grifo" not in rastro["limiar"]           # caiu no corte de score
    assert "Montarias|Grifo" in rastro["garantidos"]           # mas a vaga garantida o salvou
    assert "Montarias|Grifo" in rastro["final"]
    assert len(rastro["final"]) == len(set(rastro["final"]))
    assert rastro["rerank"][0].startswith("Poderes de Destino|Parceiro")


def test_rastro_sem_rerank_nao_tem_etapa_limiar():
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({}, falhar=True))
    _, tele = recuperar_v2(ret, _leitura(k=5), REGISTROS, "q", "q")
    assert tele["rastro"]["rerank"] == []
    assert len(tele["rastro"]["final"]) == 5


# --- registros fundidos no chunk do vizinho (mesclar_pequenos da ingestão) ---

def _fundido():
    return Document(
        page_content=("[Condições > F]\n# Doente\n\nDescrição: Sob efeito de uma doença.\n\n"
                      "# Em Chamas\n\nDescrição: O personagem está pegando fogo."),
        metadata={"Tabela": "Condições", "Nome": "Em Chamas", "Fonte": "F"})


def test_indexar_registros_acha_o_registro_fundido_pelo_cabecalho():
    fundido = _fundido()
    indice = indexar_registros([fundido, *OUTROS])
    assert indice[("Condições", "Doente")] == [fundido]
    assert indice[("Condições", "Em Chamas")] == [fundido]


def test_registro_fundido_e_buscado_direto_e_conta_como_atendido():
    indice = indexar_registros([_fundido(), *OUTROS])
    nec = Necessidade("registro de Doente", "Condições", "Doente", registro="Doente")
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({}))
    top, tele = recuperar_v2(ret, _leitura(nec), indice, "q", "q")
    assert any("# Doente" in d.page_content for d in top)
    assert tele["necessidades"][0]["atendida"] is True
    assert "Condições|Doente" in tele["rastro"]["final"]
    assert "Condições|Em Chamas" in tele["rastro"]["final"]


def test_cabecalho_no_meio_de_uma_linha_nao_vira_registro():
    doc = Document(page_content="[Magias > F]\n# Voo\n\nDescrição: veja # Teia na página 3",
                   metadata={"Tabela": "Magias", "Nome": "Voo", "Fonte": "F"})
    assert ("Magias", "Teia") not in indexar_registros([doc])


def test_nome_com_espaco_no_fim_casa_com_o_registro_da_necessidade():
    doc = Document(page_content="[Poderes (Bárbaro) > F]\n# Crítico Brutal \n\nDescrição: x",
                   metadata={"Tabela": "Poderes (Bárbaro)", "Nome": "Crítico Brutal ",
                             "Fonte": "F"})
    indice = indexar_registros([doc, *OUTROS])
    nec = Necessidade("registro", "Poderes (Bárbaro)", "Crítico Brutal ",
                      registro="Crítico Brutal ")
    ret = RetrieverFalso(BuscaFalsa(padrao=OUTROS), RerankFalso({}))
    _, tele = recuperar_v2(ret, _leitura(nec), indice, "q", "q")
    assert tele["necessidades"][0]["atendida"] is True
    assert "Poderes (Bárbaro)|Crítico Brutal" in tele["rastro"]["final"]
