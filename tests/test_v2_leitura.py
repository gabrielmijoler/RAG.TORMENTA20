"""Leitura da v2: o analisador inteiro sobre registros fake (sem Qdrant, sem LLM)."""

from rag_v2.dicionario import construir
from rag_v2.leitura import ler

JA = "Tormenta20 - Jogo do Ano"
SEMENTE = ("Sou um barbaro, bugbear, nv4, quero usar intimidacao e machado toureo "
           "para causar dano. Quais habilidades combam com isso.")


def _d():
    return construir({"tabelas": [
        {"arquivo": "armas.ts", "export": "weapons", "elementos": [
            {"name": "Machado Táurico", "origin": JA}]},
        {"arquivo": "classes.ts", "export": "classes", "elementos": [
            {"name": "Bárbaro", "origin": JA, "abilities": [{"name": "Fúria"}]}]},
        {"arquivo": "races.ts", "export": "races", "elementos": [
            {"name": "Bugbear", "origin": "Ameaças de Arton"}]},
        {"arquivo": "skills.ts", "export": "skills", "elementos": [
            {"name": "Intimidação", "origin": "Compendio T20"},
            {"name": "Cura", "origin": "Compendio T20"}]},
        {"arquivo": "powers-barbaro.ts", "export": "powersBarbaro", "elementos": [
            {"name": "Crítico Brutal", "origin": JA}]},
        {"arquivo": "powers-gerais.ts", "export": "powersGerais", "elementos": [
            {"name": "Ataque Poderoso", "origin": JA}]},
        {"arquivo": "conditions.ts", "export": "conditions", "elementos": [
            {"name": "Abençoado", "origin": JA}]},
        {"arquivo": "magicarmor.ts", "export": "enchantments", "elementos": [
            {"name": "Abençoado", "origin": JA}]},
        {"arquivo": "spells.ts", "export": "spells", "elementos": [
            {"name": "Bola de Fogo", "origin": JA}]},
    ]})


def test_caso_semente_vira_build_com_restricoes_e_necessidades():
    leitura = ler(SEMENTE, _d())
    assert leitura.tipo == "build"
    assert leitura.restricoes.nivel == 4
    assert leitura.restricoes.classes == ("Bárbaro",)
    assert leitura.restricoes.racas == ("Bugbear",)
    alvos = {n.tabela_alvo for n in leitura.necessidades}
    assert {"Classes", "Raças", "Perícias", "Armas", "Poderes (Bárbaro)"} <= alvos
    assert leitura.k == 15


def test_caso_semente_com_aproximada_abaixo_de_085_e_confianca_media():
    leitura = ler(SEMENTE, _d())
    assert leitura.confianca == "media"
    assert leitura.usar_llm == "traducao"
    assert any("aproximada" in m for m in leitura.motivos)


def test_pergunta_direta_so_com_nome_exato_e_confianca_alta_e_pula_o_llm():
    leitura = ler("Qual o dano da Bola de Fogo?", _d())
    assert leitura.tipo == "direta"
    assert leitura.confianca == "alta"
    assert leitura.usar_llm == "nenhum"
    assert leitura.k == 8


def test_sem_nome_cai_na_v1_completa():
    leitura = ler("quanto dano causa um ataque critico?", _d())
    assert leitura.tipo == "sem_nome"
    assert leitura.confianca == "baixa"
    assert leitura.usar_llm == "completo"
    assert leitura.k == 12


def test_fora_de_escopo_cai_na_v1_completa():
    leitura = ler("qual a capital da França?", _d())
    assert leitura.tipo == "fora_de_escopo"
    assert leitura.usar_llm == "completo"


def test_ligacao_so_por_palavra_comum_e_confianca_baixa():
    leitura = ler("como funciona a pericia cura", _d())
    assert leitura.ligacoes and leitura.confianca == "baixa"


def test_texto_original_preservado():
    assert ler(SEMENTE, _d()).texto_original == SEMENTE


def test_empate_sem_desempate_traz_todas_as_alternativas_com_confianca_media():
    # política: sem desempate, traz todos com vaga — não joga a leitura fora
    leitura = ler("o que é abençoado", _d())
    assert leitura.confianca == "media"
    assert {n.tabela_alvo for n in leitura.necessidades} == {
        "Condições", "Encantamentos de Armaduras"}
