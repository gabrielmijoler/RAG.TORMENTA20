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


# ---------- métrica: título de entidade ('# Nome' do chunk) ----------

def test_partir_citacoes_separa_por_titulo_da_entidade():
    """avaliar.py grava fundamentadas/fora do registro — precisa seguir o
    MESMO matching do groundedness (senão o JSON oficial se contradiz:
    ground 100% com 'citação fora' na mesma query)."""
    from rag_core import partir_citacoes
    resposta = ("Caído sofre –5 [Caído > Tormenta20 - Jogo do Ano] "
                "e Voo [Voo > Guia dos Deuses Menores] dura 10 min.")
    contexto = "[Condições > Tormenta20 - Jogo do Ano]\n# Caído\nDescrição: –5."
    fundamentadas, fora = partir_citacoes(resposta, contexto)
    assert fundamentadas == {"caido > tormenta20 - jogo do ano"}
    assert fora == {"voo > guia dos deuses menores"}


def test_groundedness_caminho_e_titulo_da_entidade():
    """Caso 01/19/20/23/26/50: modelo citou '[Caído > Fonte]' (o heading '# Caído'
    do chunk) em vez de '[Condições > Fonte]' — a citação resolve para um chunk
    real do contexto: fundamentada."""
    resposta = ("A condição Caído impõe –5 na Defesa corpo a corpo "
                "[Caído > Tormenta20 - Jogo do Ano].")
    contexto = ("[Condições > Tormenta20 - Jogo do Ano]\n"
                "# Atordoado\nDescrição: fica desprevenido.\n"
                "# Caído\nDescrição: sofre –5 na Defesa corpo a corpo.")
    assert groundedness(resposta, contexto) == 1.0


def test_groundedness_titulo_certo_fonte_errada_continua_zero():
    """Heading existe no ctx, mas sob OUTRA fonte -> citação não resolve."""
    resposta = "Voo [Voo > Guia dos Deuses Menores] dura 10 min."
    contexto = "[Magias > Tormenta20 - Jogo do Ano]\n# Voo\nDuração: 10 min."
    assert groundedness(resposta, contexto) == 0.0


def test_groundedness_titulo_fora_do_contexto_continua_zero():
    """Pin de alucinação: heading que não existe no ctx -> 0.0."""
    resposta = "Bola de Fogo [Bola de Fogo > Tormenta20 - Jogo do Ano] causa 8d6."
    contexto = "[Perícias > Compendio T20]\n# Furtividade\nRegras da perícia."
    assert groundedness(resposta, contexto) == 0.0


def test_groundedness_titulo_fonte_truncada():
    """Truncamento de fonte ('tormenta20' sem ' - Jogo do Ano') vale p/ título."""
    resposta = "Caído [Caído > Tormenta20] sofre –5 na Defesa."
    contexto = "[Condições > Tormenta20 - Jogo do Ano]\n# Caído\nDescrição: –5."
    assert groundedness(resposta, contexto) == 1.0


def test_linha_ground_reconhece_titulo_da_entidade():
    docs = [Document(page_content="[Condições > Tormenta20 - Jogo do Ano]\n"
                                  "# Caído\nDescrição: –5 na Defesa.")]
    linha = linha_ground("Caído [Caído > Tormenta20 - Jogo do Ano] sofre –5.",
                         docs)
    assert linha.startswith("ground: 100%"), linha


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
        ("Não encontrei a regra [Condições > Tormenta20 - Jogo do Ano] "
         "nem em nenhuma outra fonte do contexto."),
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


# ---------- guard de reparo: citação FORA do contexto ----------

def test_aviso_reparo_lista_citacoes_fora_e_fontes_do_contexto():
    from rag_core import aviso_reparo
    aviso = aviso_reparo(
        {"classes > fonte errada"},
        {"classes > tormenta20 - jogo do ano"},
    )
    assert "classes > fonte errada" in aviso
    assert "classes > tormenta20 - jogo do ano" in aviso
    assert "[INSTRUÇÃO OBRIGATÓRIA" in aviso


def test_aviso_reparo_preserva_conteudo_e_proibe_recusa():
    """RED: o aviso da 2ª passada manda PRESERVAR o conteúdo útil e corrigir
    SÓ as citações — nunca emitir recusa quando a informação está nos trechos.

    Regressão da mq5: a cláusula "se o contexto não cobrir a regra, recuse"
    induziu recusa indevida na 64 ("Não encontrei a magia Voo") com o
    contexto idêntico CONTENDO a magia (juiz 6→0).
    """
    from rag_core import aviso_reparo
    aviso = aviso_reparo(
        {"magias > fonte errada"},
        {"magias > tormenta20 - jogo do ano"},
    )
    # preserva o texto bom, corrige só as fontes inválidas
    assert "informações úteis" in aviso.lower()
    assert "apenas as citações" in aviso.lower() or "somente as citações" in aviso.lower()
    # proíbe recusa quando a informação existe no contexto
    assert "nunca" in aviso.lower() and "recusa" in aviso.lower()
    assert "presente" in aviso.lower()
    # cláusula antiga (induceora da recusa) removida
    assert "se o contexto não cobrir a regra, recuse" not in aviso
    # listagem de inválidas/validas preservada (contrato do teste acima)
    assert "magias > fonte errada" in aviso
    assert "magias > tormenta20 - jogo do ano" in aviso


def test_exigir_citacoes_repara_citacao_fora_do_contexto():
    """RED: resposta cita fonte inexistente -> 2ª passada com o aviso de
    reparo listando a citação inválida (máx. 2 chamadas, como hoje)."""
    from rag_core import exigir_citacoes
    chamadas = []
    tentativas = iter([
        "Inventor é bom [Classes > Fonte Errada].",
        "Inventor é bom [Classes > Tormenta20 - Jogo do Ano].",
    ])

    def gerar(entrada):
        chamadas.append(entrada)
        return next(tentativas)

    contexto = "[Classes > Tormenta20 - Jogo do Ano]\n# Inventor\nDescrição"
    final = exigir_citacoes(gerar, "pergunta", contexto=contexto)
    assert len(chamadas) == 2, len(chamadas)
    assert "classes > fonte errada" in chamadas[1].lower()
    assert "classes > tormenta20 - jogo do ano" in chamadas[1].lower()
    assert final.startswith("Inventor é bom [Classes >")


def test_exigir_citacoes_com_contexto_nao_reinvoca_quando_fundamentado():
    from rag_core import exigir_citacoes
    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "regra [Classes > Tormenta20 - Jogo do Ano] aplicada."

    contexto = "[Classes > Tormenta20 - Jogo do Ano]\n# Inventor"
    exigir_citacoes(gerar, "pergunta", contexto=contexto)
    assert len(chamadas) == 1, chamadas


def test_exigir_citacoes_sem_contexto_nao_toca_no_fora():
    """compat: contexto=None -> comportamento antigo intacto (1 chamada)."""
    from rag_core import exigir_citacoes
    chamadas = []

    def gerar(entrada):
        chamadas.append(entrada)
        return "regra [Classes > Fonte Errada]."

    exigir_citacoes(gerar, "pergunta")
    assert len(chamadas) == 1, chamadas


# ---------- telemetria do guard no avaliador (responder) ----------

class _ChainFalso:
    """Rag chain de teste: devolve uma resposta fixa com um contexto dado."""

    def __init__(self, resposta: str, contexto: list):
        self._resposta = resposta
        self._contexto = contexto
        self.chamadas = 0

    def invoke(self, entrada: dict) -> dict:
        self.chamadas += 1
        return {"answer": self._resposta, "context": self._contexto}


class _SinteseFalsa:
    """Síntese de teste: registra as re-invocações e devolve o reparo."""

    def __init__(self, reparo: str):
        self._reparo = reparo
        self.entradas: list[dict] = []

    def invoke(self, entrada: dict) -> str:
        self.entradas.append(entrada)
        return self._reparo


def _llm_falso():
    from tests.fakes import FakeChat
    return FakeChat(respostas=["não deveria ser chamado"])


def test_responder_marca_guard_reparo_disparado():
    """RED: citação FORA do contexto -> 2ª passada no aviso_reparo e
    guard_reparo_disparado=True no dicionário de telemetria."""
    from avaliar import responder

    contexto = [Document(page_content="[Classes > Tormenta20 - Jogo do Ano]\n# Inventor")]
    chain = _ChainFalso("Inventor é bom [Classes > Fonte Errada].", contexto)
    sintese = _SinteseFalsa("Inventor é bom [Classes > Tormenta20 - Jogo do Ano].")

    resposta, guarda = responder(_llm_falso(), chain, sintese, "pergunta")

    assert chain.chamadas == 1
    assert len(sintese.entradas) == 1, sintese.entradas
    assert "classes > fonte errada" in sintese.entradas[0]["input"].lower()
    assert resposta.startswith("Inventor é bom [Classes >")
    assert guarda["guard_reparo_disparado"] is True
    assert guarda["guard_sem_citacao_disparado"] is False


def test_responder_sem_reparo_quando_fundamentada():
    """RED: resposta já fundamentada -> nenhuma re-invocação, os dois flags
    ficam False (mede exatamente quantas 2ª passadas NÃO houve)."""
    from avaliar import responder

    contexto = [Document(page_content="[Classes > Tormenta20 - Jogo do Ano]\n# Inventor")]
    chain = _ChainFalso("Inventor é bom [Classes > Tormenta20 - Jogo do Ano].", contexto)
    sintese = _SinteseFalsa("não deveria ser chamado")

    _, guarda = responder(_llm_falso(), chain, sintese, "pergunta")

    assert len(sintese.entradas) == 0, sintese.entradas
    assert guarda["guard_reparo_disparado"] is False
    assert guarda["guard_sem_citacao_disparado"] is False


def test_responder_marca_guard_sem_citacao_disparado():
    """RED: resposta sem NENHUMA citação -> 2ª passada com AVISO_CITACAO e
    guard_sem_citacao_disparado=True (o reparo continua False)."""
    from avaliar import responder

    contexto = [Document(page_content="[Classes > Tormenta20 - Jogo do Ano]\n# Inventor")]
    chain = _ChainFalso("Inventor é bom sem fonte nenhuma.", contexto)
    sintese = _SinteseFalsa("Inventor é bom [Classes > Tormenta20 - Jogo do Ano].")

    _, guarda = responder(_llm_falso(), chain, sintese, "pergunta")

    assert len(sintese.entradas) == 1, sintese.entradas
    assert "[INSTRUÇÃO OBRIGATÓRIA" in sintese.entradas[0]["input"]
    assert guarda["guard_sem_citacao_disparado"] is True
    assert guarda["guard_reparo_disparado"] is False
