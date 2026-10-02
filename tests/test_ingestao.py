"""Testes da ingestão Fase 2: rotulos, fatiamento e renderização de registros."""

import os
import shutil

import pytest

import rag_core as rc


def test_rotulo_traduz_campos_conhecidos():
    assert rc._rotulo("prerequisite") == "Requisito"
    assert rc._rotulo("pvBase") == "PV Base"
    assert rc._rotulo("uniquePower") == "Poder único"


def test_rotulo_fallback_e_chave_numerica():
    assert rc._rotulo("campoDesconhecido") == "campo Desconhecido"
    assert rc._rotulo("0") == ""


def test_linha_omite_rotulo_vazio():
    assert rc._linha("0", {"step": "Normal"}) == "Etapa: Normal"
    assert rc._linha("prerequisite", "Nível 5") == "Requisito: Nível 5"


def test_fonte_prioriza_origin_depois_source_depois_regiao():
    assert rc._fonte_do_registro({"origin": "A", "source": "B", "__regiao": "C"}) == "A"
    assert rc._fonte_do_registro({"source": "B", "__regiao": "C"}) == "B"
    assert rc._fonte_do_registro({"__regiao": "C"}) == "C"
    assert rc._fonte_do_registro({}) == "Compendio T20"


def test_rotulo_tabela_para_export_duplicado():
    assert rc._rotulo_tabela("magics.ts", "enchantments") == "Encantamentos de Itens Mágicos"
    assert rc._rotulo_tabela("curseds.ts", "enchantments") == "Encantamentos Amaldiçoados"
    assert rc._rotulo_tabela("qualquer.ts", "spells") == "Magias"
    assert rc._rotulo_tabela("qualquer.ts", "exportQualquer") == "export Qualquer"


def test_formatar_registro_gera_cabecalho_e_pula_ui():
    registro = {
        "id": "espada-longa",
        "name": "Espada Longa",
        "icon": "Swords",
        "image": "x.png",
        "description": "Arma típica de soldados.",
        "price": "T$ 15",
        "damage": "1d8",
    }
    texto = rc._formatar_registro(registro)
    assert texto.startswith("# Espada Longa")
    assert "Descrição: Arma típica de soldados." in texto
    assert "Preço: T$ 15" in texto
    assert "Swords" not in texto and "x.png" not in texto
    assert "espada-longa" not in texto


def test_formatar_registro_campo_escalar_como_linha():
    texto = rc._formatar_registro({"name": "Caído", "type": "condição"})
    assert texto == "# Caído\n\nTipo: condição"
    texto = rc._formatar_registro({"title": "Testes", "content": "Um teste é uma rolagem de 1d20."})
    assert texto == "# Testes\n\nConteúdo: Um teste é uma rolagem de 1d20."


def test_fatiar_texto_curto_devolve_um_bloco():
    assert rc._fatiar("texto curto") == ["texto curto"]


def test_fatiar_cabecalho_nao_vira_fragmento_orfao():
    gigante = "Uma frase longa. " * 400
    texto = "# Basilisco\n\n" + gigante
    pedacos = rc._fatiar(texto)
    assert len(pedacos) > 1
    assert pedacos[0].startswith("# Basilisco")
    assert len(pedacos[0]) >= 100
    assert all(len(p) <= rc.CHUNK_SIZE + 100 for p in pedacos)


def test_fatiar_nenhum_fragmento_minusculo():
    paragrafos = ["# Registro"] + [f"Parágrafo {i}: " + ("palavra " * 60) for i in range(8)]
    texto = "\n\n".join(paragrafos)
    pedacos = rc._fatiar(texto)
    assert len(pedacos) > 1
    assert all(len(p) >= 100 for p in pedacos)
    assert " ".join(" ".join(pedacos).split()) == " ".join(texto.split())


def test_fatiar_ultimo_bloco_pequeno_vai_para_o_vizinho():
    paragrafos = ["# Registro", "x" * 1150, "y" * 40]
    pedacos = rc._fatiar("\n\n".join(paragrafos))
    assert len(pedacos) == 1
    assert pedacos[0].endswith("y" * 40)


def test_dividir_cola_rotulo_solto_no_conteudo():
    bloco = "História:\n" + ("Uma frase de história. " * 200)
    pedacos = rc._dividir(bloco, rc.CHUNK_SIZE)
    assert all(len(p) >= 100 for p in pedacos)
    assert pedacos[0].startswith("História:")


def test_montar_chunks_do_corpus_real():
    if shutil.which("node") is None or not os.path.isdir(rc.PASTA_DADOS):
        pytest.skip("Node ou ../aTormenta/data indisponivel")
    chunks = rc.montar_chunks(verbose=False)
    assert len(chunks) > 5000
    tamanhos = [len(c.page_content) for c in chunks]
    assert min(tamanhos) >= 50
    assert all(c.page_content.startswith("[") and " > " in c.page_content.split("\n", 1)[0]
               for c in chunks)
    tabelas = {c.metadata["Tabela"] for c in chunks}
    assert {"Magias", "Ameaças", "Regras"} <= tabelas
    assert all(c.metadata["Fonte"] and c.metadata["Tabela"] for c in chunks)
