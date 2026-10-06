from rag_core import _e_degenerado, _reescrita_utilizavel, precisa_de_historico

# Reproduz os bugs filmados no chat (sessão 2026-10-01):
# [1/4] devolveu card de resposta em vez de pergunta e fabricou números.


def test_card_de_resposta_como_reescrita_e_rejeitado():
    assert not _reescrita_utilizavel(
        "T$ 100 [Alquímicos > Tormenta20 - Jogo do Ano]",
        "quantos custa pote de mana ?",
    )


def test_eco_multilinha_de_resposta_anterior_e_rejeitado():
    eco = (
        "Essência de Mana [Alquímicos > Tormenta20 - Jogo do Ano]\n"
        "\nPreço: T$ 50\nEspaços: 0,5"
    )
    assert not _reescrita_utilizavel(eco, "me traga esse item descrito.")


def test_reescrita_pergunta_unica_e_aceita():
    assert _reescrita_utilizavel(
        "Quais as penalidades da condição Caído em Tormenta 20?",
        "quais penalidades caido?",
    )


def test_reescrita_identica_a_entrada_e_aceita_mesmo_sem_interrogacao():
    # entrada do usuário termina em '.' — devolver igual não é lixo
    assert _reescrita_utilizavel(
        "me traga esse item descrito.", "me traga esse item descrito."
    )


def test_anafora_depende_de_historico():
    assert precisa_de_historico("me traga esse item descrito.")
    assert precisa_de_historico("qual o preço disso?")
    assert precisa_de_historico("como funciona ela no combate?")


def test_pergunta_autossuficiente_nao_depende_de_historico():
    assert not precisa_de_historico("quanto custa uma essencia de mana ?")
    assert not precisa_de_historico(
        "Qual o ND, a defesa e o deslocamento de um Basilisco?"
    )
    assert not precisa_de_historico("O que faz a magia Curar Ferimentos?")


def test_degeneracao_bloco_consecutivo_e_detectada():
    # run real do chat: bloco 'ells' repetido 4x seguidos
    assert _e_degenerado(
        "Quellsellsellsells deep overtells quantos custa um pote de mana?"
    )


def test_degeneracao_unidade_espalhada_e_detectada():
    # run real do chat: 'ells' 4x espalhado por palavras quebradas
    assert _e_degenerado(
        "Quais as regrasells asells regras deells deep lore de custo "
        "e de Manaells e disponibilidade?"
    )


def test_pergunta_legitima_nao_e_degenerada():
    assert not _e_degenerado(
        "Quais as penalidades da condição Caído em Tormenta 20?"
    )
    assert not _e_degenerado(
        "Quanto custa uma essência de mana que recupera 1d4 pontos de mana?"
    )


def test_reescrita_degenerada_com_interrogacao_e_rejeitada():
    # termina em '?' e cabe em 300 chars — só o detector de repetição pega
    assert not _reescrita_utilizavel(
        "Quellsellsellsells deep overtells quantos custa um pote de mana?",
        "quantos custa pote de mana ?",
    )


def test_loop_de_precos_dobrados_na_resposta_e_detectado():
    # saída real do chat: linhas "T$ X [Alquímicos > …]" com preço dobrando
    saida = "\n".join(
        f"T$ {5 * 2 ** i} [Alquímicos > Tormenta20 - Jogo do Ano]"
        for i in range(12)
    )
    assert _e_degenerado(saida)


def test_resposta_longa_legitima_com_repeticao_de_termo_passa():
    texto = (
        "O Basilisco é uma ameaça de ND 4 com Defesa 23 e deslocamento de 9m. "
        "O olhar do Basilisco petrifica a vítima; a criatura afetada pode "
        "resistir com Fortitude para reduzir o efeito do olhar. Encontre um "
        "Basilisco em ermos, ruínas e cavernas — o Basilisco age sempre que "
        "pode. Um grupo experiente sobrevive ao Basilisco se preparando.\n\n"
        "| Atributo  | Valor |\n|-----------|-------|\n| ND        | 4     |\n"
        "| Defesa    | 23    |\n| Desloca.  | 9m    |"
    )
    assert not _e_degenerado(texto)


def test_tabela_markdown_com_separador_longo_nao_e_marcada():
    texto = (
        "Preço das poções:\n\n| Item | Preço |\n|----------|-------|\n"
        "| Essência de Mana | T$ 50 |\n| Bálsamo | T$ 10 |"
    )
    assert not _e_degenerado(texto)
