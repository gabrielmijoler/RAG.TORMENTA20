# Fase 0 — medir antes de mexer

**O que foi feito.** Antes de construir a v2, medimos a v1 em três coisas: se ela sempre devolve o mesmo resultado, onde ela gasta tempo e o que existe de fato no corpus.

**Determinismo** quer dizer: mesma pergunta, mesmo índice, mesma resposta da busca. Rodamos 5 perguntas duas vezes, em processos separados (programas abertos do zero), e comparamos os documentos, a ordem e as notas. Deu tudo idêntico. A queda de cobertura que vimos na mq8 não veio do algoritmo. O servidor do Qdrant (o banco de vetores) caiu no meio da rodada, e o código passou sem avisar para uma cópia local velha, com 192 pedaços em vez de 5.674.

**Tempo.** Um script mediu cada etapa com um cronômetro "embrulhado" em volta das funções. O código do projeto não foi alterado: o embrulho existe só dentro do processo do script. Quase todo o tempo vai para o **reranker** (o FlashRank, um modelo que relê os candidatos e dá uma nota de relevância): uns 11 s por pergunta, e até 28 s quando a pergunta é dividida em partes. A busca em si (embedding, Qdrant e BM25) leva menos de meio segundo. As chamadas de LLM de tradução levam de 1 a 4 s, com picos de 24 s.

**Mapa do corpus.** O `tools/mapa_corpus.py` lê os mesmos dados da ingestão e escreve `docs/MAPA_CORPUS.md`: as tabelas, os campos de cada uma (com a porcentagem de registros que os preenchem), as fontes e os nomes que aparecem em mais de um lugar. Ele mostrou que a mesma fonte aparece com grafias diferentes ("Tormenta20 - Jogo do Ano" e "tormenta20 - jogo do ano"). Mostrou também que as habilidades de classe, como a Fúria, ficam *dentro* do registro da classe, sem registro próprio.

**Por que importa.** A v2 só pode prometer o que os dados têm. Se a raça não tem um campo "tamanho", nenhuma "necessidade" da v2 pode depender desse campo.
