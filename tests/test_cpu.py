"""Proteção de CPU: variáveis de limite de threads e cap do ONNX Runtime.

O rag_core define OMP/MKL/OPENBLAS_NUM_THREADS=2 antes de qualquer import de
ML e envolve ort.InferenceSession (threadpool próprio, ignora OMP) com
intra_op/inter_op = 2. Estes testes garantem que a proteção não seja removida.
"""

import os

import pytest

import rag_core


def test_variaveis_de_threads_limitadas():
    assert os.environ.get("OMP_NUM_THREADS") == "2"
    assert os.environ.get("MKL_NUM_THREADS") == "2"
    assert os.environ.get("OPENBLAS_NUM_THREADS") == "2"


@pytest.mark.skipif(not rag_core._ORT_LIMITADO, reason="onnxruntime indisponível")
def test_ort_limitado_ativo():
    assert rag_core._ORT_LIMITADO is True


@pytest.mark.skipif(not rag_core._ORT_LIMITADO, reason="onnxruntime indisponível")
def test_ort_wrapper_cria_sess_options_limitada(monkeypatch):
    capturado = {}

    class _Sessoes:
        def __call__(self, *args, **kwargs):
            capturado["kwargs"] = kwargs
            return "sessao-falsa"

    monkeypatch.setattr(rag_core, "_ORT_SESSION_ORIGINAL", _Sessoes())
    sessao = rag_core._inference_session_com_limite("/caminho/modelo.onnx")
    assert sessao == "sessao-falsa"
    opcoes = capturado["kwargs"]["sess_options"]
    assert opcoes.intra_op_num_threads == 2
    assert opcoes.inter_op_num_threads == 1


@pytest.mark.skipif(not rag_core._ORT_LIMITADO, reason="onnxruntime indisponível")
def test_ort_wrapper_respeita_sess_options_do_chamador(monkeypatch):
    capturado = {}

    class _Sessoes:
        def __call__(self, *args, **kwargs):
            capturado["args"] = args
            return "ok"

    proprio = rag_core._ort.SessionOptions()
    monkeypatch.setattr(rag_core, "_ORT_SESSION_ORIGINAL", _Sessoes())
    rag_core._inference_session_com_limite("/modelo.onnx", proprio)
    assert capturado["args"][1] is proprio
