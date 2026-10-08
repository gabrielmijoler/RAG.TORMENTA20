"""Parent-child: o chunk FILHO recuperado e expandido ao registro PAI completo.

Motivo (mq5): o fatiamento (CHUNK_SIZE=3500) corta registros grandes e o
groundedness compara a citação com o FILHO no contexto — a resposta citando
o registro inteiro (correto) "fica de fora" e vira TABELA_FORA. Expandir o
filho ao pai DURANTE a recuperação devolve o texto integral sem reindexar o
Qdrant (o payload já carrega arquivo/export/id).

Decisões do plano:
- teto `EXPANSAO_PAI_MAX = 15_000` chars (98% dos 493 pais medidos cabem);
- `_REGISTRO_PAI` vazio = no-op bit a bit (A/B das 61 clássicas intacto);
- deduplicação: 2 filhos do mesmo pai -> UMA cópia do pai no contexto;
- expansão ANTES de `_diversificar` (herda o relevance_score do rerank);
- pai não cabe -> JANELA de EXPANSAO_PAI_MAX posicionada no filho (o corte
  de cabeça perdia o trecho que o reranker ranqueou no fim do registro);
- sanidade filho⊂pai: a chave (arquivo, export, id|Tabela|Nome) pode colidir
  -> se o trecho do filho não existe no pai, o doc passa INTACTO (nunca o
  pai de outro registro entra no contexto com a nota alta do filho);
- dedup pela CHAVE do pai (não pelo texto): com janelas diferentes, 2 filhos
  gerariam 2 textos parciais distintos — a janela fica centrada no 1º filho
  (maior rank) e filhos seguintes fora da janela perdem a evidência.
"""

import os
import shutil
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import rag_core as rc

METADATA_FILHO = {
    "Tabela": "Magias",
    "Fonte": "Tormenta20 - Jogo do Ano",
    "Tipo": "magia",
    "Nome": "Bola de Fogo",
    "id": "bola-de-fogo",
    "arquivo": "magics.ts",
    "export": "spells",
}


def _filho(conteudo: str, **meta) -> Document:
    metadata = dict(METADATA_FILHO)
    metadata.update(meta)
    return Document(page_content=conteudo, metadata=metadata)


@pytest.fixture
def registro_pai():
    """`_REGISTRO_PAI` vazio durante o teste; restaura o estado ao terminar."""
    original = dict(rc._REGISTRO_PAI)
    rc._REGISTRO_PAI.clear()
    yield rc._REGISTRO_PAI
    rc._REGISTRO_PAI.clear()
    rc._REGISTRO_PAI.update(original)


# ---------- _chave_pai ----------

def test_chave_pai_monta_chave_com_id():
    assert rc._chave_pai(METADATA_FILHO) == ("magics.ts", "spells",
                                             "bola-de-fogo")


def test_chave_pai_fallback_tabela_nome_sem_id():
    """id vazio cai no par Tabela|Nome (0 colisões medido nos 493 fatiados)."""
    sem_id = dict(METADATA_FILHO, id="")
    assert rc._chave_pai(sem_id) == ("magics.ts", "spells",
                                     "Magias|Bola de Fogo")


def test_chave_pai_metadata_incompleta_retorna_none():
    assert rc._chave_pai({}) is None
    # sem arquivo/export não há como localizar o pai
    assert rc._chave_pai({"Tabela": "Magias", "Nome": "Bola de Fogo"}) is None
    # sem identificador (sem id e sem Tabela/Nome) também é no-op
    assert rc._chave_pai({"arquivo": "magics.ts", "export": "spells"}) is None


# ---------- _expandir_pais ----------

def test_expandir_pais_devolve_pai_completo_com_prefixo(registro_pai):
    # o filho precisa EXISTIR dentro do pai (formato real: o pedaço vem do
    # _fatiar do próprio corpo) — fixture fiel à ingestão, assertions iguais
    corpo = ("# Bola de Fogo\n…parte 1…\nDescrição: esfera de fogo.\n"
             "Efeito: d8 de dano de fogo.")
    registro_pai[rc._chave_pai(METADATA_FILHO)] = corpo
    filho = _filho("[Magias > Tormenta20 - Jogo do Ano]\n"
                   "# Bola de Fogo\n…parte 1…",
                   relevance_score=0.9)

    saida = rc._expandir_pais([filho])

    assert len(saida) == 1
    assert saida[0].page_content == (
        "[Magias > Tormenta20 - Jogo do Ano]\n" + corpo
    )
    # herda o relevance_score do rerank (expansão antes do _diversificar)
    assert saida[0].metadata["relevance_score"] == 0.9
    # o filho original não é mutado
    assert "parte 1" in filho.page_content


def test_expandir_pais_com_registro_vazio_e_noop_bit_a_bit(registro_pai):
    """Registry vazio -> mesmos objetos, mesmo conteúdo (A/B intacta)."""
    docs = [
        _filho("[Magias > Tormenta20 - Jogo do Ano]\nconteúdo filho"),
        _filho("[Magias > Tormenta20 - Jogo do Ano]\noutro filho",
               arquivo="outros.ts", export="regras", id="outro"),
    ]

    saida = rc._expandir_pais(docs)

    assert saida == docs
    assert saida[0] is docs[0]
    assert saida[1] is docs[1]


def test_expandir_pais_trunca_pai_no_teto(registro_pai):
    """Pai gigante (max medido = 59.279 chars) truncado em EXPANSAO_PAI_MAX.

    O trecho fica no MEIO do pai: a janela precisa alcançá-lo (o corte de
    cabeça antigo perdia qualquer coisa além do teto).
    """
    registro_pai[rc._chave_pai(METADATA_FILHO)] = (
        "x" * 40_000 + "parte 1" + "y" * 20_000)

    saida = rc._expandir_pais([
        _filho("[Magias > Tormenta20 - Jogo do Ano]\nparte 1")])

    assert len(saida[0].page_content) <= rc.EXPANSAO_PAI_MAX


def test_expandir_pais_deduplica_dois_filhos_do_mesmo_pai(registro_pai):
    corpo = ("# Bola de Fogo\nparte 1 do registro. "
             + "corpo do registro. " * 45 + "\nparte 2 do registro.")
    registro_pai[rc._chave_pai(METADATA_FILHO)] = corpo
    filho_1 = _filho("[Magias > Tormenta20 - Jogo do Ano]\nparte 1 do registro.")
    filho_2 = _filho("[Magias > Tormenta20 - Jogo do Ano]\nparte 2 do registro.")

    saida = rc._expandir_pais([filho_1, filho_2])

    assert len(saida) == 1
    assert saida[0].page_content == (
        "[Magias > Tormenta20 - Jogo do Ano]\n" + corpo
    )


def test_expandir_pais_metadata_incompleta_noop(registro_pai):
    """Filho sem arquivo/export/id não quebra nem é tocado."""
    registro_pai[rc._chave_pai(METADATA_FILHO)] = "# pai completo"
    orfao = Document(page_content="filho órfão", metadata={})

    saida = rc._expandir_pais([orfao])

    assert saida[0] is orfao


# ---------- registro populado pela ingestão ----------

def test_montar_chunks_popula_registro_pai():
    if shutil.which("node") is None or not os.path.isdir(rc.PASTA_DADOS):
        pytest.skip("Node ou ../aTormenta/data indisponivel")
    rc.montar_chunks(verbose=False)

    chaves = list(rc._REGISTRO_PAI)
    assert len(chaves) > 4_500
    # chave sempre (arquivo, export, identificador) completo
    assert all(k[0] and k[1] and k[2] for k in chaves)
    # o pai é o registro INTEIRO — maiores passam de CHUNK_SIZE (3500)
    assert max(len(v) for v in rc._REGISTRO_PAI.values()) > rc.CHUNK_SIZE


# ---------- wiring: recuperar() expande antes do _diversificar ----------

class _BaseFalsa:
    """Base retriever de teste: devolve os docs fixos, qualquer consulta."""

    def __init__(self, docs):
        self._docs = docs

    def invoke(self, consulta: str):
        return list(self._docs)


class _CompressorFalso:
    """Compressor de teste: candidatos intactos, SEM relevance_score
    (força o limiar a ser ignorado — sem score não há o que cortar)."""

    top_n = 12

    def compress_documents(self, documents, query, callbacks=None):
        return list(documents)


def test_recuperar_expande_pais_antes_do_diversificar(registro_pai):
    """2 filhos do MESMO registro -> UMA cópia do pai no contexto final.

    Sem a expansão+dedup, o _diversificar preencheria as vagas com o 2o
    filho (chunk duplicado do mesmo registro); com ela, só o pai completo.
    """
    corpo = ("# Bola de Fogo\nparte 1\n\n"
             + "corpo do registro completo. " * 50 + "\n\nparte 2 final")
    registro_pai[rc._chave_pai(METADATA_FILHO)] = corpo
    filho_1 = _filho(
        "[Magias > Tormenta20 - Jogo do Ano]\n# Bola de Fogo\nparte 1")
    filho_2 = _filho(
        "[Magias > Tormenta20 - Jogo do Ano]\nparte 2 final")
    retriever = SimpleNamespace(
        base_retriever=_BaseFalsa([filho_1, filho_2]),
        base_compressor=_CompressorFalso(),
    )

    saida = rc.recuperar(retriever, "quantos de dano Bola de Fogo causa?")

    assert len(saida) == 1
    assert saida[0].page_content == (
        "[Magias > Tormenta20 - Jogo do Ano]\n" + corpo
    )
