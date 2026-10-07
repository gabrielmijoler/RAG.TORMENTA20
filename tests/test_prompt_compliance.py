from rag_core import SYSTEM_PROMPT

PROTECOES = (
    "declare que a base não cobre o ponto",
    "PROIBIÇÃO DE EXTRAPOLAÇÃO NUMÉRICA",
    "NUNCA agrupe citações apenas no final do texto",
    "declare isso imediatamente",
    "'N colunas' significa SEMPRE uma tabela Markdown",
    "NUNCA pode inventar regras mecânicas",
    "IDIOMA OBRIGATÓRIO",
)

REFORCOS = (
    "[Caminho > Fonte]",
    # calibração: qualidade > quantidade (rodada fr_l12_posguard mostrou
    # 22 citações de tabela-não-recuperada puxadas pelo pânico frase a frase)
    "ao final daquele bloco lógico",
    "Não é necessário citar a cada frase",
    "ESTRITAMENTE PROIBIDO inventar uma fonte",
    "rodapé da tabela",
)

REMOVIDOS = (
    # pânico frase a frase — removidos pela calibração
    "É PROIBIDO gerar respostas afirmativas sem citações anexadas",
    "toda frase que afirma uma regra",
    "no final da frase ou do item",
)


def test_prompt_mantem_as_seis_protecoes():
    for trecho in PROTECOES:
        assert trecho in SYSTEM_PROMPT, f"proteção perdida: {trecho!r}"


def test_prompt_inclui_reforcos_da_regra_2():
    for trecho in REFORCOS:
        assert trecho in SYSTEM_PROMPT, f"reforço ausente: {trecho!r}"


def test_prompt_removeu_panico_frase_a_frase():
    """Citação por BLOCO lógico substituiu a exigência por frase."""
    for trecho in REMOVIDOS:
        assert trecho not in SYSTEM_PROMPT, f"panico remanescente: {trecho!r}"


def test_prompt_preserva_placeholder_e_tamanho():
    assert "{context}" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) < 4000
