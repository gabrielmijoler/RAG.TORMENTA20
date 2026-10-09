# Plugue da v2 no chat, sessão, conhecimento e sinais

**Como ligar.** `ARQUITETURA=v2 make chat` usa a v2; sem a variável, o chat é exatamente a v1. Uma **flag** é um interruptor lido do ambiente: dá para comparar e voltar atrás sem mexer no código.

**O que muda numa pergunta, com a v2 ligada:**
1. O analisador lê a pergunta (em milissegundos, sem IA).
2. Com confiança alta, o chat **pula** as duas chamadas ao LLM que reescreviam a pergunta. Isso economiza tempo e evita o "Machado Touro".
3. A busca traz **direto** o registro de cada nome reconhecido. Ele não depende do reranker, que é um modelo em inglês e às vezes enterrava o certo. Cada necessidade ganha uma vaga garantida no contexto.
4. O LLM recebe uma **lista de verificação** do que a pergunta pede e a ordem de dizer "a base não cobre" quando faltar algo.

**Sessão.** O chat lembra a **ficha** (classe, raça, nível, itens) e o **foco** (o último assunto). "e a CD dela?" vira uma pergunta sobre a última entidade discutida. "isso combina comigo?" usa a ficha. `/ficha` mostra e corrige; `/novo` apaga.

**Aprendizado com aprovação.** Um apelido ("machado do minotauro") nasce como *proposta* em `conhecimento/propostas.yaml`. Só depois de `tools/conhecimento.py aprovar` ele vai para `apelidos.yaml` e passa a valer. Antes de aprovar, o script confere se o registro existe e se o apelido não colide com um nome real. O sistema aprende só a **entender** perguntas, nunca regras.

**Sinais.** Com `SINAIS=1`, cada resposta vira uma linha em `sinais/sinais.jsonl` (fora do git), com a pergunta, o que foi lido, os documentos usados, se citou certo e o tempo de cada etapa. `/errado` e `/parcial` marcam a resposta; `/parcial` pergunta o que faltou. Esses registros alimentam a fila de falhas.
