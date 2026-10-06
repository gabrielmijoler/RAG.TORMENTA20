"""RED: matar os n/a e os 0% legítimos do grounded (só o que estava baixo/n/a).

Alvo, tirado das avaliações (avaliacao_fr_l12_qorig.json e
avaliacao_baseline_fr_l12_ground.json):

- n/a (10/61 e 7/61): resposta afirmativa SEM nenhuma citação [...] ->
  métrica passa a devolver 0.0; guard de geração re-invoca UMA vez com
  AVISO_CITACAO cobrando o formato (recusa sem citação também aciona).
  None (n/a) fica reservado para resposta VAZIA (falha de geração).
- 0% legítimos: modelo colou prefixo de entidade ("agarrado > condicoes > …")
  ou truncou a fonte ("alquimicos > tormenta20") — a fonte do contexto está
  contida na citação da resposta (ou vice-versa) -> fundamentada.
- 0% alucinado ("condiciones > tormenta20 - jogo del ano") continua 0.0:
  containment NÃO pode mascarar fonte inventada.
"""
from rag_core import Document, groundedness, linha_ground

# AVISO_CITACAO, exigir_citacoes e resposta_sem_citacoes ainda não existem:
# cada teste de guard importa dentro do corpo para falhar por teste, não na
# coleta do arquivo inteiro.


# ---------- métrica: n/a -> 0.0 ----------

def test_groundedness_resposta_sem_citacoes_zera():
    assert groundedness("resposta afirmativa sem fonte",
                        "ctx [magias > x]") == 0.0


def test_groundedness_resposta_vazia_continua_none():
    """Vazio = falha de geração (não há o que fundamentar) -> n/a."""
    assert groundedness("", "ctx [magias > x]") is None


def test_linha_ground_sem_citacoes_zera():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano]")]
    linha = linha_ground("resposta sem fonte", docs)
    assert linha.startswith("ground: 0%"), linha


def test_linha_ground_resposta_vazia_continua_n_a():
    docs = [Document(page_content="trecho [Magias > Tormenta20 - Jogo do Ano]")]
    linha = linha_ground("", docs)
    assert linha.startswith("ground: n/a"), linha


# ---------- métrica: 0% com fonte colada/truncada ----------

def test_groundedness_citacao_com_prefixo_de_entidade():
    """Caso 02_agarrado: modelo prefixou a entidade na fonte."""
    resposta = ("Agarrado [Agarrado > Condições > Tormenta20 - Jogo do Ano] "
                "imobiliza o alvo.")
    contexto = ("condicao agarrado: o alvo fica agarrado "
                "[Condições > Tormenta20 - Jogo do Ano]")
    assert groundedness(resposta, contexto) == 1.0


def test_groundedness_citacao_truncada_pelo_modelo():
    """Caso 18_bomba: modelo cortou ' - Jogo do Ano' do fim da fonte."""
    resposta = ("Bomba [Alquímicos > Tormenta20] custa T$ 30 "
                "e causa 1d6 de dano.")
    contexto = "preco da bomba [Alquímicos > Tormenta20 - Jogo do Ano]"
    assert groundedness(resposta, contexto) == 1.0


def test_groundedness_fonte_fora_do_contexto_continua_zero():
    """Pin de regressão: containment não pode mascarar fonte inventada
    (caso 24/26/27_ameacas e 49_exausto — citou tabela que não está no ctx)."""
    resposta = ("O goblin tem ND 2 [Ameaças > Tormenta20 - Jogo do Ano].")
    contexto = "magia qualquer [Magias > Tormenta20 - Jogo do Ano]"
    assert groundedness(resposta, contexto) == 0.0


# ---------- guard de geração ----------

def test_resposta_sem_citacoes_detecta_ausencia():
    from rag_core import resposta_sem_citacoes
    assert resposta_sem_citacoes("O Caído fica caído.") is True
    assert resposta_sem_citacoes(
        "Caído [Condições > Tormenta20 - Jogo do Ano] fica caído.") is False


def test_resposta_sem_citacoes_vazia_nao_e_gatilho():
    """Vazio não é 'sem citação' — é falha de outro tipo (não re-invoca)."""
    from rag_core import resposta_sem_citacoes
    assert resposta_sem_citacoes("") is False


def test_aviso_citacao_cobra_formato_e_recusa():
    from rag_core import AVISO_CITACAO
    assert "[Caminho > Fonte]" in AVISO_CITACAO
    assert "fontes consultadas" in AVISO_CITACAO.lower()


def test_exigir_citacoes_reinvoca_uma_vez_com_aviso():
    from rag_core import AVISO_CITACAO, exigir_citacoes
    chamadas = []
    tentativas = iter([
        "resposta afirmativa sem fonte nenhuma",
        "regra [Magias > Tormenta20 - Jogo do Ano] aplicada.",
    ])

    def gerar(entrada):
        chamadas.append(entrada)
        return next(tentativas)

    final = exigir_citacoes(gerar, "quais regras de flanco?")
    assert "Magias" in final
    assert chamadas[0] == "quais regras de flanco?"
    assert AVISO_CITACAO in chamadas[1]


def test_exigir_citacoes_recusa_sem_citacao_tambem_reinvoca():
    """Recusa legítima sem citação aciona o guard (vira 'recusa com fontes')."""
    from rag_core import exigir_citacoes
    chamadas = []
    tentativas = iter([
        "Não encontrei essa regra no contexto fornecido.",
        "Não encontrei a regra [Condições > Tormenta20 - Jogo do Ano] "
        "nem em nenhuma outra fonte do contexto.",
    ])

    def gerar(entrada):
        chamadas.append(entrada)
        return next(tentativas)

    final = exigir_citacoes(gerar, "pergunta obscura")
    assert len(chamadas) == 2
    assert "Condições" in final


def test_exigir_citacoes_nao_reinvoca_se_ja_citou():
    from rag_core import exigir_citacoes
    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "regra [Magias > Tormenta20 - Jogo do Ano]"

    final = exigir_citacoes(gerar, "pergunta")
    assert chamadas == ["pergunta"]
    assert "Magias" in final


def test_exigir_citacoes_sem_laco_na_segunda_tentativa():
    """2ª tentativa ainda sem citação -> devolve como está (métrica: 0.0),
    no máximo DUAS chamadas — nunca loop."""
    from rag_core import exigir_citacoes
    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "insiste sem fonte"

    assert exigir_citacoes(gerar, "p") == "insiste sem fonte"
    assert len(chamadas) == 2
