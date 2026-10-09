# Fase 2 — medir a v2 sem se enganar

**O que foi construído.** Uma forma de medir a v2 sozinha, em números absolutos. Não há tabela comparando com a v1, porque a v1 foi ajustada olhando as mesmas perguntas e uma comparação sairia enviesada.

**Quatro fontes de teste, cada uma com um papel:**
1. **12 perguntas com gabarito** (`propostas/goldenset_proposta_12.jsonl`). Cada entidade esperada é conferida no corpus por um script, nunca de memória. Oito são **dev** (para consertar) e quatro são **teste fechado**, que só roda com `--confirmar-teste` e nunca serve para ajustar nada.
2. **Perguntas sintéticas** (`tools/gerar_sinteticas.py`). Um script, sem IA, lê um registro e um campo e escreve a pergunta com o gabarito. O gabarito sai certo por construção, porque pergunta e resposta nascem do mesmo registro. Cada rodada usa uma **semente** nova (o número que decide o sorteio): assim a amostra é inédita e ninguém consegue "decorar" a prova.
3. **Perguntas rotuladas à mão** (`propostas/rotulado_proposta.jsonl`). Medem o *analisador* em si: achou os nomes? o nível? o tipo?
4. **O uso real**, pelos sinais do chat (Fase 6).

**Rastreio por etapa.** Quando um registro esperado não chega ao contexto, o avaliador diz **onde** ele se perdeu: não veio na busca (`candidatos`), foi cortado pela nota do reranker (`limiar`) ou não coube no tamanho do contexto (`orcamento`). Dizer só "faltou" não ensina nada; dizer "caiu no limiar" aponta o conserto.

**O que a medição achou (e foi consertado como classe de erro, não caso a caso):**
- registros muito curtos que a ingestão **fundiu no vizinho**: a busca direta não os via;
- um pronome ("dela") entrando num nome e roubando o foco da conversa;
- um erro de digitação que é, na verdade, **uma palavra que existe no corpus** ("preciso" não é erro de "Precisa");
- a classe herdada da ficha da sessão, que entrava nas restrições mas nunca era buscada.

**Cuidado com a própria régua.** Uma semente usada para consertar deixa de ser inédita. Por isso o ganho é conferido com uma semente nova.
