import json
import os
import sys
import time
from collections import Counter

# Proteção de CPU (igual rag_core): numpy (via langchain_community) carrega
# ANTES do rag_core aqui — as variáveis precisam valer desde o primeiro import.
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.messages import AIMessage, HumanMessage

import rag_core
from rag_core import (
    MODELOS_GRATUITOS,
    PROMPT_TRADUCAO,
    SYSTEM_PROMPT,
    RecusaTraducao,
    SaidaDegenerada,
    _e_degenerado,
    e_cota_esgotada,
    e_modelo_indisponivel,
    e_recusa,
    e_transitorio,
    eh_saudacao_pura,
    exigir_citacoes,
    linha_ground,
    precisa_de_historico,
    reformulacao_valida,
    reformular_pergunta,
    trocar_modelo,
)

# Flags lidas do ambiente SEM importar rag_v2: no caminho padrão (v1) nenhum módulo
# da v2 é importado (tests/test_v1_inalterada.py confere sys.modules).
V2_LIGADO = os.environ.get("ARQUITETURA", "").strip().lower() == "v2"
SINAIS_LIGADO = os.environ.get("SINAIS", "").strip().lower() in ("1", "true", "sim", "on")
if V2_LIGADO:
    from rag_v2.dicionario import do_corpus
    from rag_v2.integracao import bloco_dicas, descrever, usar_v2
    from rag_v2.leitura import ler
    from rag_v2.recuperacao import indexar_registros, recuperar_v2
    from rag_v2.sessao import Sessao
if SINAIS_LIGADO:
    from rag_v2 import sinais

# ==========================================
# 1. LLM + COLEÇÃO + RETRIEVER + CHAIN
# (chaves carregadas do .env pelo rag_core)
# ==========================================
llm = rag_core.criar_llm()
try:
    chunks = rag_core.montar_chunks()
except NotImplementedError as erro:
    print(erro)
    sys.exit(1)

# Cliente ÚNICO da sessão: o Qdrant embutido só admite um client aberto por
# path (lock exclusivo) e o mesmo client serve a busca e o arquivamento.
conexao = rag_core.escolher_conexao_qdrant()
client_qdrant = rag_core.QdrantClient(**conexao)
embeddings = rag_core.obter_embeddings()
retriever_comprimido = rag_core.montar_retriever(
    chunks, conexao=conexao, cliente=client_qdrant
)

# SYSTEM_PROMPT (com a regra anti-alucinação) entra intacto.
# com_historico=True só injeta as mensagens do diálogo entre system e human.
# Só a SÍNTESE: a busca acontece uma vez na etapa 3 com a pergunta reformulada,
# e a síntese recebe a ENTRADA REAL do usuário (formatos: 'liste em 3 colunas').
cadeia = rag_core.montar_cadeia_resposta(SYSTEM_PROMPT, llm, com_historico=True)

# v2 (ARQUITETURA=v2): analisador de pergunta sem LLM. Com v1 (padrão) nada
# disso é montado e o chat segue exatamente como antes.
if V2_LIGADO:
    print("Arquitetura v2: montando o dicionário de nomes do corpus...")
    dicionario_v2 = do_corpus()
    registros_v2 = indexar_registros(chunks)
    # Ficha (classe, raça, nível, itens) e foco (última entidade) da sessão v2.
    sessao = Sessao()
else:
    dicionario_v2, registros_v2, sessao = None, None, None
# Última leitura e telemetria da recuperação v2 (mostradas pelo /entendi).
ultima_leitura = None
ultima_telemetria = None
# Último evento de sinal (SINAIS=1): alvo do /errado e do /parcial.
ultimo_evento = None

# APENAS HumanMessage (pergunta bruta) e AIMessage (resposta final).
# Nunca o texto do {context} — o contexto é descartado a cada rodada.
chat_history = []

# Filtro por metadados ativo (/filtro tabela=Magias ...) — vale até /filtro
# limpar ou /novo; None/vazio = busca ampla (mesmo comportamento do A/B).
filtros_ativos: dict = {}

# O histórico completo fica na sessão, mas só a janela vai ao LLM: sem isso o
# prompt cresce um pouco a cada turno e estoura o limite de tokens.
JANELA_MEMORIA = 4  # últimas 4 mensagens = 2 perguntas + 2 respostas


def historico_recente() -> list:
    return chat_history[-JANELA_MEMORIA:]


# -----------------------------------------
# Detector de fim de sessão (gatilho da
# memória de longo prazo)
# -----------------------------------------
PALAVRAS_SUCESSO = ["sessão encerrada", "fim de sessão", "sessão terminou",
                    "derrotamos", "vencemos o boss", "campanha avançou",
                    "excelente sessão", "funcionou"]


def eh_relato_sucesso(texto: str) -> bool:
    """True para relatos de fim/resultado de sessão com corpo suficiente."""
    t = texto.lower()
    return any(p in t for p in PALAVRAS_SUCESSO) and len(t.split()) > 3

COMANDOS = ("/filtro tabela=X [fonte=Y tipo=Z]  restringe a busca por metadados ("
            "'/filtro' lista valores, 'limpar' desliga)  |  "
            "/salvar  arquiva a sessão atual (relato opcional)  |  "
            "/novo  limpa o histórico e começa outra sessão  |  "
            + ("/entendi  mostra como a última pergunta foi lida (v2)  |  "
               "/ficha [campo=valor]  mostra/corrige ficha e foco (v2)  |  "
               if V2_LIGADO else "")
            + ("/errado, /parcial  avaliam a última resposta (SINAIS=1)  |  "
               if SINAIS_LIGADO else "")
            + "/sair  encerra")
BANNER = """
==============================================================================
  RAG de Tormenta 20 — chat contínuo com memória de sessão
==============================================================================
  Digite sua pergunta de regra.
  Comandos: """ + COMANDOS + "\n" + "=" * 78


def com_fallback(rodar, descricao):
    """Tenta os modelos gratuitos em ordem. Devolve None se todos falharem."""
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                return rodar()
            except Exception as e:
                if e_cota_esgotada(e):
                    print(f"    [{modelo}] cota/chave esgotada, próximo modelo...")
                    break
                elif e_transitorio(e):
                    print(f"    [{modelo}] sobrecarregado ({str(e)[:80]}), "
                          f"aguardando 5s...")
                    time.sleep(5)
                elif e_modelo_indisponivel(e):
                    print(f"    [{modelo}] indisponível, próximo modelo...")
                    break
                elif isinstance(e, RecusaTraducao):
                    print(f"    [{modelo}] recusou a reformulação, próximo modelo...")
                    break
                elif isinstance(e, SaidaDegenerada):
                    # degeneração é não-determinística: 1 retry no MESMO
                    # modelo (2ª tentativa do loop) e depois o próximo.
                    print(f"    [{modelo}] saída degenerada, nova tentativa...")
                else:
                    raise
    print(f"    todos os modelos falharam em: {descricao}")
    return None


def traduzir_para_t20(consulta: str) -> str:
    """Converte a dúvida em pergunta técnica (PROMPT_TRADUCAO do rag_core).

    Nunca derruba a sessão e nunca devolve string de recusa: se todos os
    modelos recusarem (ou a tentativa esgotar), a busca recebe a pergunta
    CRUA original — melhor query ruim do que query bloqueio de segurança.
    """
    cadeia = PROMPT_TRADUCAO | llm

    def _traduzir():
        texto = cadeia.invoke({"queixa": consulta}).content.strip()
        if e_recusa(texto):
            raise RecusaTraducao(f"bloqueio de segurança: {texto[:60]}")
        if not reformulacao_valida(texto):
            raise RecusaTraducao(f"saída não é uma pergunta: {texto[:60]}")
        if _e_degenerado(texto):
            # 'Quellsellsellsells deep overtells…?' — pergunta com formato
            # válido mas com repetição quebrada: o com_fallback tenta o
            # próximo modelo em vez de buscar com a query envenenada.
            raise RecusaTraducao(f"saída degenerada: {texto[:60]}")
        return texto

    # com_fallback ja engole RecusaTraducao (proximo modelo); se todos
    # recusarem/falharem ele devolve None e o contrato abaixo usa a pergunta crua.
    traducao = com_fallback(_traduzir, "reformulação")
    if not traducao or e_recusa(traducao):
        print(f"    -> sem reformulação válida, buscando com: {consulta[:70]}")
        return consulta
    return traducao


def buscar(pergunta_t20: str, pergunta_real: str | None = None):
    """Candidatos (reformulada + real), rerank com a query real, 1 chunk/reg."""
    docs = rag_core.recuperar(
        retriever_comprimido, pergunta_t20, pergunta_real, filtros=filtros_ativos,
        decompor=rag_core.modo_estrategia() == "decompor",
    )
    if filtros_ativos:
        ativo = " ".join(f"{k}={v}" for k, v in filtros_ativos.items())
        print(f"    filtro: {ativo} -> {len(docs)} docs no top final")
    for i, doc in enumerate(docs, 1):
        score = doc.metadata.get("relevance_score", 0)
        fonte = doc.metadata.get("Fonte") or doc.metadata.get("Tabela") or "Geral"
        print(f"    {i:>2}. {score:.3f}  [{str(fonte)[:44]}]")
    return docs


def mostrar_docs_v2(docs) -> None:
    """Lista os documentos do caminho v2 (a buscar() da v1 não foi alterada)."""
    for i, doc in enumerate(docs, 1):
        score = doc.metadata.get("relevance_score", 0)
        fonte = doc.metadata.get("Fonte") or doc.metadata.get("Tabela") or "Geral"
        print(f"    {i:>2}. {score:.3f}  [{str(fonte)[:44]}]")


def gerar_resposta(entrada: str, docs):
    """Sintetiza a partir dos docs já recuperados, respondendo à entrada REAL.

    `entrada` (o que o usuário digitou) vai para {input} — é ela que carrega
    pedidos de formato ("liste em 3 colunas"); `docs` veio da etapa 3, buscada
    com a pergunta reformulada. Nunca mais de uma busca por pergunta.

    Guard da Regra 2 (exigir_citacoes): se a resposta sair sem nenhuma
    citação [...], re-invoca UMA vez com AVISO_CITACAO carimbado — recusa
    sem fonte também aciona. Com o contexto dos docs, uma citação FORA do
    contexto também re-invoca (aviso_reparo com as fontes inválidas e as
    válidas). Máx. 2 chamadas por tentativa de modelo.
    """
    def gerar(texto: str) -> str:
        with get_openai_callback() as cb:
            saida = cadeia.invoke({
                "input": texto,
                "context": docs,
                "chat_history": historico_recente(),
            })
        print(
            f"    tokens: {cb.total_tokens} "
            f"(prompt {cb.prompt_tokens} / resposta {cb.completion_tokens})"
        )
        return saida

    def rodar():
        contexto = "\n".join(getattr(d, "page_content", str(d)) for d in docs)
        saida = exigir_citacoes(gerar, entrada, contexto=contexto)
        if _e_degenerado(saida):
            # loop de lista (ex.: 49x 'T$ X [Alquímicos > …]') — nunca
            # imprimir nem anexar ao histórico; o com_fallback tenta de novo.
            raise SaidaDegenerada(f"saída degenerada: {saida[:60]!r}")
        return saida

    return com_fallback(rodar, "resposta final")


def tratar_filtro(arg: str) -> None:
    """Aplica, lista ou limpa o filtro de metadados (/filtro ...)."""
    if not arg:
        if filtros_ativos:
            ativo = " ".join(f"{k}={v}" for k, v in filtros_ativos.items())
            print(f"Filtro ativo: {ativo}")
        else:
            print("Sem filtro — busca ampla.")
        for chave in rag_core.CHAVES_FILTRO:
            valores = Counter(
                str(d.metadata.get(chave)) for d in chunks if d.metadata.get(chave)
            )
            top = ", ".join(f"{v}({n})" for v, n in valores.most_common(8))
            print(f"  {chave}: {top}")
        print('Uso: /filtro tabela=Magias  |  /filtro fonte="Tormenta20 - Jogo do Ano"'
              "  |  /filtro tipo=Arcana  |  /filtro limpar")
        return

    if arg.lower() in ("limpar", "off", "desligar"):
        filtros_ativos.clear()
        print("Filtro removido — busca ampla.")
        return

    novos = rag_core.parsear_filtros(arg)
    if not novos:
        print(f"Não entendi: {arg!r}")
        print('Uso: /filtro tabela=Magias  |  /filtro fonte="Tormenta20 - Jogo do Ano"'
              "  |  /filtro tipo=Arcana  |  /filtro limpar")
        return
    filtros_ativos.clear()
    filtros_ativos.update(novos)
    ativo = " ".join(f"{k}={v}" for k, v in filtros_ativos.items())
    print(f"Filtro aplicado: {ativo}")
    print("Vale para as próximas perguntas até /filtro limpar ou /novo.")


def processar(entrada: str) -> None:
    global ultima_leitura, ultima_telemetria, ultimo_evento
    # Saudação pura: resposta fixa, sem LLM, sem busca e SEM gravar no
    # chat_history — a janela de memória fica só com o que é de regra.
    if eh_saudacao_pura(entrada):
        print("\n  saudação detectada — RAG não chamado (0 tokens)")
        print("\n" + "=" * 78)
        print("Olá! Sou o arquivista de Tormenta 20. Posso responder perguntas "
              "sobre regras, raças, classes, magias e bestas descritas na "
              "base. Como posso ajudar?")
        print("=" * 78)
        return

    # Relato de fim de sessão: arquiva a sessão e sai SEM rodar o RAG e SEM
    # gravar no chat_history (janela de memória só com perguntas de regra).
    if eh_relato_sucesso(entrada):
        print("\n  [ok] fim de sessão detectado — arquivando resumo...")
        if len(chat_history) < 2:
            print("    sem sessão em andamento no histórico — nada para arquivar.")
            return
        resumo = rag_core.salvar_sessao_campanha(
            chat_history, relato_com_ficha(entrada) if V2_LIGADO else entrada, llm,
            embeddings, client_qdrant, origem="auto"
        )
        if resumo is None:
            print("    ⚠️  sessão NÃO arquivada (falha na extração do resumo).")
            return
        print("\n" + "=" * 78)
        print(f"Resumo arquivado: {json.dumps(resumo, ensure_ascii=False)}")
        print("Sessão salva na memória de longo prazo (sessoes_campanha).")
        print("Digite /novo para iniciar uma nova sessão.")
        print("=" * 78)
        return

    # v2: leitura sem LLM (com ficha e foco da sessão). Com /filtro ativo a
    # v1 assume (o filtro é dela).
    tempos: dict = {}
    t0 = time.perf_counter()
    leitura = ler(entrada, dicionario_v2, sessao) if dicionario_v2 is not None else None
    tempos["leitura"] = time.perf_counter() - t0
    v2 = leitura is not None and usar_v2(leitura) and not filtros_ativos
    ultima_leitura, ultima_telemetria = leitura, None
    if leitura is not None:
        print(f"\n  [v2] tipo={leitura.tipo} confiança={leitura.confianca} "
              f"k={leitura.k} -> {'v2' if v2 else 'v1 (fallback)'}  (/entendi detalha)")
        if leitura.texto_resolvido:
            print(f"    foco da sessão: {leitura.texto_resolvido}")

    print("\n  [1/4] reformulando com o histórico")
    t0 = time.perf_counter()
    janela = historico_recente()
    print(f"    janela de memória: {len(janela)}/{len(chat_history)} mensagens")
    if v2:
        # opção C: confiança média/alta dispensa a reformulação por LLM; a
        # referência ("e a CD dela?") já foi resolvida pelo foco da sessão
        reescrita = leitura.texto_resolvido or entrada
        print("    -> v2: reformulação pulada")
    elif not janela:
        reescrita = entrada
        print("    -> sem histórico, pergunta mantida")
    elif not precisa_de_historico(entrada):
        # sem anáfora a reescrita não agrega — e já devolveu card de resposta
        # fabricado (T$ 100 [Alquímicos > …]) que envenenou a busca do turno
        # seguinte; pular o LLM aqui é ao mesmo tempo barato e seguro.
        reescrita = entrada
        print("    -> sem anáfora, pergunta mantida")
    else:
        reescrita = reformular_pergunta(entrada, janela, llm)
        if reescrita != entrada:
            print(f"    -> {reescrita}")
        else:
            print("    -> reformulação inválida, pergunta original mantida")

    tempos["reformulacao"] = time.perf_counter() - t0

    print("  [2/4] traduzindo para termos do sistema")
    t0 = time.perf_counter()
    if v2 and leitura.usar_llm == "nenhum":
        pergunta_t20 = reescrita
        print("    -> v2: tradução pulada (confiança alta)")
    else:
        pergunta_t20 = traduzir_para_t20(reescrita)
        print(f"    -> {pergunta_t20}")

    tempos["traducao"] = time.perf_counter() - t0

    print("  [3/4] recuperando (BM25 + denso + reranker)")
    t0 = time.perf_counter()
    if v2:
        docs, ultima_telemetria = recuperar_v2(
            retriever_comprimido, leitura, registros_v2, pergunta_t20, reescrita)
        print(f"    v2: {ultima_telemetria['candidatos']} candidatos, "
              f"{ultima_telemetria['garantidos']} vagas garantidas")
        mostrar_docs_v2(docs)
    else:
        docs = buscar(pergunta_t20, reescrita)

    tempos["recuperacao"] = time.perf_counter() - t0

    print("  [4/4] gerando resposta")
    t0 = time.perf_counter()
    # a lista de verificação vai só para a síntese; o histórico guarda a entrada real
    resposta = gerar_resposta(entrada + (bloco_dicas(leitura) if v2 else ""), docs)
    tempos["geracao"] = time.perf_counter() - t0
    if resposta is None:
        print("\nNão consegui gerar uma resposta estável agora — "
              "tente reformular a pergunta.")
        return

    print("\n" + "=" * 78)
    print(resposta)
    print(linha_ground(resposta, docs))
    print("=" * 78)

    chat_history.append(HumanMessage(entrada))
    chat_history.append(AIMessage(resposta))
    if leitura is not None:
        sessao.atualizar(leitura)
    if SINAIS_LIGADO:
        ultimo_evento = sinais.montar_evento(
            leitura, docs, resposta, tempos, ultima_telemetria,
            "v2" if V2_LIGADO else "v1", pergunta=entrada)
        sinais.registrar(ultimo_evento)


def relato_com_ficha(relato: str) -> str:
    """A ficha da v2 vai junto do relato da memória longa (formato do resumo intacto)."""
    if sessao.ficha.vazia():
        return relato
    return f"{relato}\nFicha do personagem na sessão: {sessao.ficha.resumo()}."


def tratar_feedback(valor: str) -> None:
    """/errado e /parcial: sinal FORTE sobre a última resposta (só com SINAIS=1)."""
    if ultimo_evento is None:
        print("Nenhuma resposta para avaliar ainda.")
        return
    faltou = None
    if valor == "parcial":
        try:
            faltou = input("  o que faltou? ").strip() or None
        except (EOFError, KeyboardInterrupt):
            faltou = None
    if sinais.registrar(sinais.feedback(ultimo_evento, valor, faltou)):
        print(f"Obrigado — marcado como {valor}.")


def main() -> None:
    print(BANNER)
    while True:
        try:
            entrada = input("\nvocê> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando. Até logo!")
            break

        if not entrada:
            continue

        cmd = entrada.lower()
        if cmd == "/sair":
            print("Encerrando a sessão. Até logo!")
            break
        if cmd == "/novo":
            chat_history.clear()
            filtros_ativos.clear()
            if sessao is not None:
                sessao.zerar()
            print("Histórico limpo — nova sessão de RPG.")
            continue
        if V2_LIGADO and (cmd == "/ficha" or cmd.startswith("/ficha ")):
            argumentos = entrada[len("/ficha"):].strip()
            for erro in sessao.corrigir(argumentos) if argumentos else []:
                print(f"  ⚠️  {erro}")
            print(sessao.descrever())
            continue
        if SINAIS_LIGADO and cmd in ("/errado", "/parcial"):
            tratar_feedback(cmd[1:])
            continue
        if V2_LIGADO and cmd == "/entendi":
            print(descrever(ultima_leitura, ultima_telemetria))
            continue
        if cmd == "/filtro" or cmd.startswith("/filtro "):
            tratar_filtro(entrada[len("/filtro"):].strip())
            continue
        if cmd == "/salvar" or cmd.startswith("/salvar "):
            # Fallback manual do arquivamento: usa o histórico atual e o resto
            # da linha como relato (ou o padrão, se vier só o comando).
            relato = entrada[len("/salvar"):].strip() \
                or "Sessão arquivada manualmente pelo mestre."
            if len(chat_history) < 2:
                print("Sem sessão em andamento para arquivar (histórico vazio).")
                continue
            print("\n  arquivando sessão sob comando manual...")
            resumo = rag_core.salvar_sessao_campanha(
                chat_history, relato_com_ficha(relato) if V2_LIGADO else relato, llm,
                embeddings, client_qdrant, origem="manual"
            )
            if resumo is None:
                print("  ⚠️  sessão NÃO arquivada (falha na extração do resumo).")
            else:
                print(f"  Resumo: {json.dumps(resumo, ensure_ascii=False)}")
            continue
        if entrada.startswith("/"):
            print(f"Comando desconhecido: {entrada}\n  {COMANDOS}")
            continue

        processar(entrada)


if __name__ == "__main__":
    main()
