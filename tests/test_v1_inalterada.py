"""Prova, sem rodar o pipeline real, que o caminho PADRÃO (v1) não mudou.

`tests/golden/v1_*.json` foi gerado pelo mesmo harness (`tests/_harness_v1.py`) sobre
os arquivos de `b7b4a30` (antes de qualquer código da v2). O harness roda `index.py` e
`avaliar.py` num processo à parte, sem variável de flag e com tudo externo falso
(Qdrant, LLM, reranker). Aqui o código atual é comparado com esse golden:

- mesmas funções chamadas, na mesma ordem e com os mesmos argumentos;
- mesma saída impressa (processar, banner e comandos);
- nenhum módulo `rag_v2` importado;
- no `avaliar.py`, a ÚNICA diferença é a chave aditiva `arquitetura` no resultado.

Para regenerar o golden depois de uma mudança INTENCIONAL da v1:
  git show <commit>:index.py > /tmp/i.py && python tests/_harness_v1.py index /tmp/i.py
"""

import json
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rodar(alvo: str) -> dict:
    ambiente = {k: v for k, v in os.environ.items()
                if k not in ("ARQUITETURA", "SINAIS", "EMBEDDING_PREFIXOS", "RERANK",
                             "FEEDBACK_NATURAL")}
    proc = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "tests", "_harness_v1.py"), alvo,
         os.path.join(RAIZ, f"{alvo}.py")],
        capture_output=True, text=True, env=ambiente, cwd=RAIZ, timeout=300, check=False)
    linhas = [ln for ln in proc.stdout.splitlines() if ln.startswith("@@JSON@@")]
    assert linhas, f"harness sem saída JSON:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    return json.loads(linhas[-1][len("@@JSON@@"):])


def _golden(alvo: str) -> dict:
    with open(os.path.join(RAIZ, "tests", "golden", f"v1_{alvo}.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def index_atual():
    return _rodar("index")


@pytest.fixture(scope="module")
def avaliar_atual():
    return _rodar("avaliar")


# --- chat ---------------------------------------------------------------------

def test_chat_nenhum_modulo_rag_v2_e_importado_no_caminho_padrao(index_atual):
    assert index_atual["modulos_rag_v2"] == []


def test_chat_chama_exatamente_as_funcoes_da_v1_na_mesma_ordem(index_atual):
    assert index_atual["chamadas"] == _golden("index")["chamadas"]


def test_chat_a_resposta_recebe_a_entrada_do_usuario_sem_acrescimo(index_atual):
    gerar = [c for c in index_atual["chamadas"] if c[0] == "gerar"]
    assert [c[1] for c in gerar] == ["o que faz a magia Teia?", "e a CD dela?"]


def test_chat_saida_impressa_do_processar_e_identica(index_atual):
    assert index_atual["stdout_processar"] == _golden("index")["stdout_processar"]
    assert index_atual["stdout_import"] == _golden("index")["stdout_import"]


def test_chat_banner_e_comandos_sao_os_de_antes(index_atual):
    ouro = _golden("index")
    assert index_atual["banner"] == ouro["banner"]
    assert index_atual["comandos"] == ouro["comandos"]


def test_chat_comandos_da_v2_respondem_comando_desconhecido_como_antes(index_atual):
    ouro = _golden("index")
    assert index_atual["stdout_main"] == ouro["stdout_main"]
    for comando in ("/ficha", "/errado", "/parcial", "/entendi"):
        assert f"Comando desconhecido: {comando}" in index_atual["stdout_main"]


def test_colecao_padrao_continua_tormenta20_sem_variavel_de_ambiente(index_atual):
    assert index_atual["colecao"] == "tormenta20"


# --- avaliador -------------------------------------------------------------------

def test_avaliador_nenhum_modulo_rag_v2_e_importado_no_caminho_padrao(avaliar_atual):
    assert avaliar_atual["modulos_rag_v2"] == []


def test_avaliador_chama_exatamente_as_funcoes_da_v1(avaliar_atual):
    assert avaliar_atual["chamadas"] == _golden("avaliar")["chamadas"]


def test_avaliador_a_unica_diferenca_de_formato_e_a_chave_aditiva_arquitetura(avaliar_atual):
    ouro = _golden("avaliar")
    for chave in ("resultado", "resultado_so_recuperacao"):
        atual = dict(avaliar_atual[chave])
        assert atual.pop("arquitetura") == "v1"
        assert atual == ouro[chave]
    assert avaliar_atual["stdout"] == ouro["stdout"]


def test_avaliador_registros_da_v1_nao_ganham_a_chave_v2(avaliar_atual):
    for registro in avaliar_atual["resultado"]["registros"]:
        assert "v2" not in registro
