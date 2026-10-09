"""Executa index.py ou avaliar.py com TUDO externo falso e imprime um JSON do que aconteceu.

Uso:  python tests/_harness_v1.py index|avaliar <caminho do arquivo>
Roda num processo à parte, sem nenhuma variável de flag, para provar três coisas
sobre o caminho padrão (v1): a saída impressa, as funções chamadas e quais módulos
`rag_v2` foram importados. Nada de Qdrant, LLM, Cohere ou reranker real.
"""
import builtins
import contextlib
import importlib.util
import io
import json
import os
import sys
from types import SimpleNamespace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
for var in ("ARQUITETURA", "SINAIS", "EMBEDDING_PREFIXOS", "RERANK", "FEEDBACK_NATURAL"):
    os.environ.pop(var, None)

from langchain_core.documents import Document

import rag_core

alvo, caminho = sys.argv[1], sys.argv[2]
chamadas: list = []
DOCS = [Document(page_content="[Magias > Tormenta20 - Jogo do Ano]\n# Teia\n\nconteudo",
                 metadata={"Tabela": "Magias", "Nome": "Teia", "Fonte": "Tormenta20 - Jogo do Ano",
                           "relevance_score": 0.91})]


def carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def rag_v2_importados():
    return sorted(k for k in sys.modules if k == "rag_v2" or k.startswith("rag_v2."))


# --- tudo externo falso -------------------------------------------------------
rag_core.criar_llm = lambda: SimpleNamespace(nome="llm-falso")
rag_core.montar_chunks = lambda verbose=True: []
rag_core.escolher_conexao_qdrant = lambda: {"path": ":memory:"}
rag_core.QdrantClient = lambda **kw: SimpleNamespace(close=lambda: None)
rag_core.obter_embeddings = lambda: SimpleNamespace()
rag_core.montar_retriever = lambda chunks, **kw: SimpleNamespace(
    base_compressor=SimpleNamespace(ultimo_modo="flashrank", top_n=12))
rag_core.montar_cadeia_resposta = lambda *a, **k: None
rag_core.reranker_ativo = lambda: "flashrank"

saida: dict = {"colecao": rag_core.COLECAO}

if alvo == "index":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m = carregar("index_alvo")
    saida["stdout_import"] = buf.getvalue()

    m.traduzir_para_t20 = lambda c: (chamadas.append(["traduzir", c]), "TRAD:" + c)[1]
    m.buscar = lambda t, r=None: (chamadas.append(["buscar", t, r]), DOCS)[1]
    m.gerar_resposta = lambda e, d: (
        chamadas.append(["gerar", e, [x.page_content for x in d]]),
        "A Teia prende. [Magias > Tormenta20 - Jogo do Ano]")[1]
    m.reformular_pergunta = lambda e, j, l=None: (
        chamadas.append(["reformular", e, len(j)]), "REESCRITA:" + e)[1]

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for pergunta in ("o que faz a magia Teia?", "e a CD dela?", "oi"):
            m.processar(pergunta)
    saida["stdout_processar"] = buf.getvalue()

    entradas = iter(["/ficha", "/ficha nivel=5", "/errado", "/parcial", "/entendi",
                     "/comando_inexistente", "/novo", "/sair"])
    original = builtins.input
    builtins.input = lambda prompt="": next(entradas)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            m.main()
    finally:
        builtins.input = original
    saida["stdout_main"] = buf.getvalue()
    saida["banner"] = m.BANNER
    saida["comandos"] = m.COMANDOS

elif alvo == "avaliar":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m = carregar("avaliar_alvo")
    casos = [{"id": "01_teia", "consulta": "o que faz a magia Teia?", "entidades": ["teia"],
              "resposta_esperada": "x"},
             {"id": "02_voo", "consulta": "qual a duração de Voo?", "entidades": ["voo"],
              "resposta_esperada": "y"}]
    m.carregar_goldenset = lambda *a, **k: casos
    m.carregar_cache = dict
    m._pontos_colecao = lambda: 5674
    m.INTERVALO_QUERY = 0
    m.reformular = lambda llm, c, cache: (chamadas.append(["reformular", c]), "TRAD:" + c)[1]
    m.buscar = lambda r, c, cr=None, limiar=None, decompor=False: (
        chamadas.append(["buscar", c, cr, limiar, decompor]), list(DOCS))[1]
    m.responder = lambda llm, top, sintese, pergunta: (
        chamadas.append(["responder", pergunta]),
        ("A Teia. [Magias > Tormenta20 - Jogo do Ano]",
         {"guard_reparo_disparado": False, "guard_sem_citacao_disparado": False,
          "passadas": []}))[1]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resultado = m.avaliar(None, so_recuperacao=False, saida=None, estrategia="baseline")
        resultado_sr = m.avaliar(None, so_recuperacao=True, saida=None, estrategia="decompor",
                                 ids=["01"])
    for r in (resultado, resultado_sr):
        r.pop("data", None)
    saida["stdout"] = buf.getvalue()
    saida["resultado"] = resultado
    saida["resultado_so_recuperacao"] = resultado_sr

saida["chamadas"] = chamadas
saida["modulos_rag_v2"] = rag_v2_importados()
print("@@JSON@@" + json.dumps(saida, ensure_ascii=False, sort_keys=True, default=str))
