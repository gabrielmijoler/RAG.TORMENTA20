"""Ficha e foco da sessão (v2): o que o chat lembra entre perguntas."""

import pytest

from rag_v2.dicionario import construir
from rag_v2.leitura import ler
from rag_v2.sessao import Sessao, precisa_de_foco, primeira_pessoa
from rag_v2.tipos import Chave

JA = "Tormenta20 - Jogo do Ano"


def _d():
    return construir({"tabelas": [
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": JA, "abilities": [{"name": "Fúria"}]}]},
        {"arquivo": "races.ts", "export": "races", "elementos": [
            {"name": "Bugbear", "origin": "Ameaças de Arton"}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Teia", "origin": JA}, {"name": "Bola de Fogo", "origin": JA}]},
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}]},
        {"arquivo": "powers-barbaro.ts", "export": "powersBarbaro", "elementos": [
            {"name": "Crítico Brutal", "origin": JA}]},
    ]})


@pytest.mark.parametrize("texto", [
    "e a CD dela?", "e ela causa dano?", "e quanto custa isso?", "o mesmo vale pra esse?",
    "e a duração?", "dessa magia, qual a área?"])
def test_precisa_de_foco_em_referencia_ou_continuacao_curta(texto):
    assert precisa_de_foco(texto)


def test_pergunta_completa_nao_precisa_de_foco():
    assert not precisa_de_foco("o que faz a magia Teia")


def test_pronome_que_aponta_nome_da_propria_pergunta_nao_usa_o_foco():
    d = _d()
    sessao = Sessao()
    sessao.atualizar(ler("o que faz a magia Teia", d))
    leitura = ler("Qual o dano da Bola de Fogo e como ela funciona?", d, sessao)
    assert [lig.chave.nome for lig in leitura.ligacoes] == ["Bola de Fogo"]
    assert leitura.texto_resolvido is None


@pytest.mark.parametrize("texto,esperado", [
    ("que poderes eu posso pegar?", True), ("meu personagem combina com isso?", True),
    ("sou bárbaro", True), ("o que faz a Teia", False)])
def test_primeira_pessoa(texto, esperado):
    assert primeira_pessoa(texto) is esperado


def test_atualizar_guarda_ficha_e_foco_da_leitura():
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro bugbear nv4 com machado taurico", _d()))
    assert sessao.ficha.classe == "Bárbaro" and sessao.ficha.raca == "Bugbear"
    assert sessao.ficha.nivel == 4 and sessao.ficha.itens == ["Machado Táurico"]
    assert sessao.foco == Chave("Armas", "Machado Táurico", JA)


def test_ficha_nao_e_apagada_por_pergunta_que_nao_fala_do_personagem():
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro nv4", _d()))
    sessao.atualizar(ler("o que faz a magia Teia", _d()))
    assert sessao.ficha.classe == "Bárbaro" and sessao.ficha.nivel == 4
    assert sessao.foco.nome == "Teia"


def test_referencia_herda_o_foco_e_vira_leitura_confiante():
    d = _d()
    sessao = Sessao()
    sessao.atualizar(ler("o que faz a magia Teia", d))
    leitura = ler("e a CD dela?", d, sessao)
    assert [lig.chave.nome for lig in leitura.ligacoes] == ["Teia"]
    assert leitura.texto_resolvido and "Teia" in leitura.texto_resolvido
    assert leitura.texto_original == "e a CD dela?"
    assert leitura.confianca == "media"
    assert any("foco" in m for m in leitura.motivos)


def test_referencia_sem_foco_continua_sem_nome_e_cai_na_v1():
    leitura = ler("e a CD dela?", _d(), Sessao())
    assert leitura.tipo in ("sem_nome", "fora_de_escopo")
    assert leitura.confianca == "baixa"


def test_primeira_pessoa_herda_a_ficha_e_vira_build():
    d = _d()
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro nv4", d))
    leitura = ler("o machado taurico combina comigo?", d, sessao)
    assert leitura.restricoes.classes == ("Bárbaro",) and leitura.restricoes.nivel == 4
    assert leitura.tipo == "build"
    assert any(n.tabela_alvo == "Poderes (Bárbaro)" for n in leitura.necessidades)
    assert any("ficha" in m for m in leitura.motivos)


def test_pergunta_impessoal_nao_herda_a_ficha():
    d = _d()
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro nv4", d))
    leitura = ler("qual o dano do machado taurico?", d, sessao)
    assert leitura.restricoes.classes == () and leitura.restricoes.nivel is None


def test_corrigir_ficha_por_comando():
    sessao = Sessao()
    assert sessao.corrigir("nivel=5 classe=Bárbaro raca=Bugbear") == []
    assert (sessao.ficha.nivel, sessao.ficha.classe, sessao.ficha.raca) == (5, "Bárbaro", "Bugbear")
    assert sessao.corrigir("nivel=30") != []
    assert sessao.ficha.nivel == 5
    assert sessao.corrigir("cor=azul") != []


def test_zerar_limpa_ficha_e_foco():
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro nv4", _d()))
    sessao.zerar()
    assert sessao.foco is None and sessao.ficha.vazia()


def test_descrever_mostra_ficha_e_foco():
    sessao = Sessao()
    sessao.atualizar(ler("sou barbaro nv4 com machado taurico", _d()))
    texto = sessao.descrever()
    assert "Bárbaro" in texto and "nível 4" in texto and "Machado Táurico" in texto
