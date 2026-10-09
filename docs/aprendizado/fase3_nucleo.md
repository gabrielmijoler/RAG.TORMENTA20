# Núcleo do analisador (`rag_v2/`)

**O que foi construído.** Um pacote Python novo, `rag_v2/`, que lê a pergunta e devolve uma `Leitura`, sem chamar nenhuma IA. A v1 continua igual: nada nela usa este pacote ainda.

**As peças, na ordem em que trabalham:**
1. `dicionario.py` monta a lista de todos os nomes do corpus (5.752) em ~0,5 s. Cada nome é guardado em "forma de comparação": minúsculas, sem acento, sem pontuação. Habilidades de dentro de uma classe, como a Fúria, apontam para a classe.
2. `ligador.py` procura esses nomes na pergunta. Primeiro tenta igualdade exata; depois "parecido" com o `difflib`, que dá uma nota de 0 a 1. "machado toureo" vira Machado Táurico com nota 0,83.
3. `restricoes.py` acha o nível ("nv4" → 4) e separa classe, raça, perícia e item.
4. `tipo.py` decide se a pergunta é direta, multiparte, de build, sem nome ou fora do jogo, contando sinais simples.
5. `necessidades.py` lista o que a resposta precisa ter (ex.: "habilidades do Bárbaro até o nível 4").
6. `orcamento.py` diz quantos documentos buscar: 8 numa pergunta direta, até 15 num build, 12 se houver dúvida.
7. `leitura.py` junta tudo e dá a **confiança**: com alta, pula o LLM; com média, usa só a tradução; com baixa, faz tudo como a v1.

**O que aprendemos testando no corpus de verdade.** Os testes com dados inventados passavam, mas o corpus real mostrou armadilhas: "magia" e "condição" também são nomes de registros, e "dano, a área" parecia com "Dança da Areia". A correção vale para uma *classe* de erro, e não para uma pergunta só. Palavras de categoria viram pistas, e a comparação aproximada não atravessa vírgula.

**TDD** quer dizer escrever primeiro o teste que falha e depois o código que o faz passar. São 88 testes novos, todos rodando em menos de 1 segundo, sem banco e sem internet.
