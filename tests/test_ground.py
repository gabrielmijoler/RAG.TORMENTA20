from rag_core import Document, citacoes_em, groundedness, linha_ground, normalizar


def test_normalizar_caixa_e_acento():
    assert normalizar("Caído") == "caido"
    assert normalizar("CAÍDO") == normalizar("caido")


def test_citacoes_em_extrai_e_normaliza():
    texto = ("O Caído está caído [Condições > Tormenta20 - Jogo do Ano] "
             "e o Basilisco tem ND 4 [Ameaças > Tormenta20 - Jogo do Ano].")
    assert citacoes_em(texto) == {
        "condicoes > tormenta20 - jogo do ano",
        "ameacas > tormenta20 - jogo do ano",
    }


def test_citacoes_em_sem_citacoes():
    assert citacoes_em("resposta sem fonte nenhuma") == set()


def test_groundedness_todas_fundamentadas():
    resposta = "Caído [Condições > Tormenta20 - Jogo do Ano] fica caído."
    contexto = ("condicao caido: ... [condicoes > tormenta20 - jogo do ano] ..."
                "outra linha [magias > tormenta20 - jogo do ano]")
    assert groundedness(resposta, contexto) == 1.0


def test_groundedness_parcial():
    resposta = ("A [Magias > Tormenta20 - Jogo do Ano] e "
                "B [Fonte Inventada > X].")
    contexto = "trecho qualquer [magias > tormenta20 - jogo do ano]"
    assert groundedness(resposta, contexto) == 0.5


def test_groundedness_sem_citacoes_na_resposta_zera():
    # Contrato novo (matar n/a): sem citação = 0.0 (não fundamentada);
    # None ficou reservado para resposta VAZIA (falha de geração).
    assert groundedness("resposta sem citação", "contexto com [magias > x]") == 0.0


def test_groundedness_resposta_vazia_continua_n_a():
    assert groundedness("", "contexto com [magias > x]") is None


def test_linha_ground_percentual():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano] "
                                  "outro [Armas > Tormenta20 - Jogo do Ano]")]
    resposta = ("Bola de Fogo [Magias > Tormenta20 - Jogo do Ano] dano 6d6, "
                "espada longa [Armas > Tormenta20 - Jogo do Ano] 1d8.")
    assert linha_ground(resposta, docs) == "ground: 100% (2/2 citações no contexto)"


def test_linha_ground_parcial():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano]")]
    resposta = ("Bola de Fogo [Magias > Tormenta20 - Jogo do Ano] e "
                "outra [Fonte Inventada > Qualquer].")
    assert linha_ground(resposta, docs) == "ground: 50% (1/2 citações no contexto)"


def test_linha_ground_sem_citacoes_zera():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano]")]
    assert linha_ground("resposta sem fonte", docs) == \
        "ground: 0% (resposta sem citações)"


def test_linha_ground_resposta_vazia_continua_n_a():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano]")]
    assert linha_ground("", docs) == "ground: n/a (sem resposta)"


def test_linha_ground_com_docs_vazios_e_citacao():
    resposta = "X [Magias > Tormenta20 - Jogo do Ano]."
    assert linha_ground(resposta, []) == "ground: 0% (0/1 citações no contexto)"
