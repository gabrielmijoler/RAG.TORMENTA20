import json
import sys
import time

from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.messages import AIMessage, HumanMessage

import rag_core
from rag_core import (
    MODELOS_GRATUITOS,
    PROMPT_TRADUCAO,
    SYSTEM_PROMPT,
    RecusaTraducao,
    e_cota_esgotada,
    e_modelo_indisponivel,
    e_recusa,
    e_transitorio,
    eh_saudacao_pura,
    reformular_pergunta,
    trocar_modelo,
)

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

# APENAS HumanMessage (pergunta bruta) e AIMessage (resposta final).
# Nunca o texto do {context} — o contexto é descartado a cada rodada.
chat_history = []

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

COMANDOS = ("/salvar  arquiva a sessão atual (relato opcional)  |  "
            "/novo  limpa o histórico e começa outra sessão  |  /sair  encerra")
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
        return texto

    # com_fallback ja engole RecusaTraducao (proximo modelo); se todos
    # recusarem/falharem ele devolve None e o contrato abaixo usa a pergunta crua.
    traducao = com_fallback(_traduzir, "reformulação")
    if not traducao or e_recusa(traducao):
        print(f"    -> sem reformulação válida, buscando com: {consulta[:70]}")
        return consulta
    return traducao


def buscar(pergunta_t20: str):
    """BM25 + denso + reranker, recebendo a pergunta JÁ reformulada."""
    docs = retriever_comprimido.invoke(pergunta_t20)
    for i, doc in enumerate(docs, 1):
        score = doc.metadata.get("relevance_score", 0)
        fonte = doc.metadata.get("Fonte") or doc.metadata.get("Tabela") or "Geral"
        print(f"    {i:>2}. {score:.3f}  [{str(fonte)[:44]}]")
    return docs


def gerar_resposta(entrada: str, docs):
    """Sintetiza a partir dos docs já recuperados, respondendo à entrada REAL.

    `entrada` (o que o usuário digitou) vai para {input} — é ela que carrega
    pedidos de formato ("liste em 3 colunas"); `docs` veio da etapa 3, buscada
    com a pergunta reformulada. Nunca mais de uma busca por pergunta.
    """
    def rodar():
        with get_openai_callback() as cb:
            saida = cadeia.invoke({
                "input": entrada,
                "context": docs,
                "chat_history": historico_recente(),
            })
        print(
            f"    tokens: {cb.total_tokens} "
            f"(prompt {cb.prompt_tokens} / resposta {cb.completion_tokens})"
        )
        return saida

    return com_fallback(rodar, "resposta final")


def processar(entrada: str) -> None:
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
            chat_history, entrada, llm, embeddings, client_qdrant, origem="auto"
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

    print("\n  [1/4] reformulando com o histórico")
    janela = historico_recente()
    print(f"    janela de memória: {len(janela)}/{len(chat_history)} mensagens")
    reescrita = reformular_pergunta(entrada, janela, llm)
    if reescrita != entrada:
        print(f"    -> {reescrita}")
    else:
        print("    -> sem histórico, pergunta mantida")

    print("  [2/4] traduzindo para termos do sistema")
    pergunta_t20 = traduzir_para_t20(reescrita)
    print(f"    -> {pergunta_t20}")

    print("  [3/4] recuperando (BM25 + denso + reranker)")
    docs = buscar(pergunta_t20)

    print("  [4/4] gerando resposta")
    resposta = gerar_resposta(entrada, docs)
    if resposta is None:
        return

    print("\n" + "=" * 78)
    print(resposta)
    print("=" * 78)

    chat_history.append(HumanMessage(entrada))
    chat_history.append(AIMessage(resposta))


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
            print("Histórico limpo — nova sessão de RPG.")
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
                chat_history, relato, llm, embeddings, client_qdrant, origem="manual"
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
