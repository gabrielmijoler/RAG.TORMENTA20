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
    "É PROIBIDO gerar respostas afirmativas sem citações anexadas",
    "[Caminho > Fonte]",
)


def test_prompt_mantem_as_seis_protecoes():
    for trecho in PROTECOES:
        assert trecho in SYSTEM_PROMPT, f"proteção perdida: {trecho!r}"


def test_prompt_inclui_reforcos_da_regra_2():
    for trecho in REFORCOS:
        assert trecho in SYSTEM_PROMPT, f"reforço ausente: {trecho!r}"


def test_prompt_preserva_placeholder_e_tamanho():
    assert "{context}" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) < 4000
