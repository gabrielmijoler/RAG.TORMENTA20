"""Montagem do contexto do LLM-as-Judge com cota por documento (juiz v2).

Antes da cota, o juiz recebia `join(todos_os_docs)[:6000]` — com a expansão
parent-child (contexto médio ~20k, pico ~76k) docs inteiros ficavam fora do
que o juiz via (28: Lena no rank 2; 49: Exausto no rank 8; 64: Voo no rank
11 — todos reprovados com justificativa "contexto não tem X").
"""

import hashlib
import json

from langchain_core.documents import Document

import avaliar
from avaliar import juizar, montar_contexto_juiz


def _doc_com_header(tabela, fonte, corpo):
    header = f"[{tabela} > {fonte}]"
    return Document(page_content=f"{header}\n{corpo}",
                    metadata={"Tabela": tabela, "Fonte": fonte})


def _corpo_de_linhas(n=50, tam=99):
    """Corpo com `n` linhas de `tam` chars + quebra = linhas de tam+1 chars."""
    return "\n".join("L" * tam for _ in range(n)) + "\n"


def test_todos_documentos_entram_com_cabecalho():
    docs = [
        _doc_com_header("Deuses", "GoA", "# Lena\n" + _corpo_de_linhas()),
        _doc_com_header("Condicoes", "GoA", "# Exausto\n" + _corpo_de_linhas()),
        _doc_com_header("Magias", "GoA", "# Voo\n" + _corpo_de_linhas()),
    ]

    texto, resumo = montar_contexto_juiz(docs)

    for d in docs:
        header = d.page_content.split("\n", 1)[0]
        assert header in texto, f"cabecalho {header} ausente no contexto do juiz"
    assert resumo["docs"] == 3


def test_ordem_de_rank_preservada():
    docs = [
        _doc_com_header("Poderes", "GoA", "# Autômato\n" + _corpo_de_linhas()),
        _doc_com_header("Ameacas", "Arton", "# Elefante\n" + _corpo_de_linhas()),
        _doc_com_header("Montarias", "GoA", "# Grifo\n" + _corpo_de_linhas()),
    ]

    texto, _ = montar_contexto_juiz(docs)

    i1 = texto.index("[Poderes > GoA]")
    i2 = texto.index("[Ameacas > Arton]")
    i3 = texto.index("[Montarias > GoA]")
    assert i1 < i2 < i3, "a ordem de rank dos docs foi alterada"


def test_corpo_respeita_cota_e_corta_em_fim_de_linha():
    corpo = _corpo_de_linhas(n=60)  # 6.000 chars, muito acima da cota
    docs = [_doc_com_header("Deuses", "GoA", corpo)]

    texto, resumo = montar_contexto_juiz(docs)

    corpo_entregue = texto.split("\n", 1)[1]  # depois do cabecalho
    cota = avaliar.JUIZ_COTA_DOC
    assert len(corpo_entregue) <= cota, "corpo do doc passou da cota"
    assert corpo.startswith(corpo_entregue)
    # corte no fim de linha/paragrafo, nunca no meio da linha
    assert corpo[len(corpo_entregue)] == "\n", "corte no meio da linha"
    assert resumo["truncados"] == 1
    assert resumo["chars"] == len(texto)


def test_docs_curtos_ficam_intactos():
    corpo = "Basilisco ND 4, Defesa 23."
    docs = [_doc_com_header("Ameacas", "GoA", corpo)]

    texto, resumo = montar_contexto_juiz(docs)

    assert texto == f"[Ameacas > GoA]\n{corpo}"
    assert resumo["truncados"] == 0


def test_juizar_registra_resumo_do_contexto_no_log(capsys):
    from fakes import FakeChat

    llm = FakeChat(respostas=['{"score": 8, "aprovado": true, "justificativa": "ok"}'])
    docs = [_doc_com_header("Deuses", "GoA", "# Lena\n" + _corpo_de_linhas())]

    juizar(llm, "Quem é Lena?", docs, cache={})

    saida = capsys.readouterr().out
    assert "juiz contexto" in saida
    assert "docs" in saida
    assert str(avaliar.JUIZ_COTA_DOC) in saida


def test_chave_do_cache_inclui_a_cota_da_regua(monkeypatch):
    docs = [_doc_com_header("Deuses", "GoA", "# Lena")]

    chave = avaliar._chave_juiz("Quem é Lena?", docs, None)
    monkeypatch.setattr(avaliar, "JUIZ_COTA_DOC", 999)
    chave_cota_diferente = avaliar._chave_juiz("Quem é Lena?", docs, None)

    assert chave != chave_cota_diferente, "cota mudou e a chave nao mudou"


def test_chave_do_cache_inclui_a_versao_da_regua(monkeypatch):
    docs = [_doc_com_header("Deuses", "GoA", "# Lena")]

    chave = avaliar._chave_juiz("Quem é Lena?", docs, None)
    monkeypatch.setattr(avaliar, "JUIZ_REGUA_VERSAO", "juiz_v9")
    chave_versao_diferente = avaliar._chave_juiz("Quem é Lena?", docs, None)

    assert chave != chave_versao_diferente, "versao da regua nao entrou na chave"


def test_entradas_antigas_do_cache_nao_sao_reutilizadas():
    """A chave v1 (sem o campo da régua) não casa com a chave da régua nova."""
    docs = [_doc_com_header("Deuses", "GoA", "# Lena")]
    base = json.dumps({
        "pergunta": "Quem é Lena?",
        "contexto": [d.page_content for d in docs],
        "resposta": "",
    }, ensure_ascii=False, sort_keys=True)
    chave_v1 = hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

    assert avaliar._chave_juiz("Quem é Lena?", docs, None) != chave_v1
