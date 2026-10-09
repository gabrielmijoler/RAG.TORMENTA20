# Fase 1 — o desenho da v2

**O que foi feito.** Só o desenho (`docs/ARQUITETURA_V2.md`), sem código. Ele precisa da sua aprovação antes de qualquer construção.

**A ideia central.** Hoje um LLM reescreve a pergunta antes da busca, e às vezes estraga os nomes: "machado toureo" virou "Machado Touro". A v2 coloca antes da busca um **analisador** em Python comum, sem inteligência artificial. Ele compara as palavras da pergunta com a lista de todos os nomes do corpus. Isso é um **dicionário**: uma tabela "nome → onde está no livro".

**Como acha nomes com erro de digitação.** Para cada trecho da pergunta, o `difflib`, que já vem com o Python, calcula a semelhança entre dois textos, de 0 a 1. "machado toureo" contra "machado taurico" deu 0,828. Se passar do limiar (proposto 0,80), o analisador liga o trecho ao registro. O limiar é um chute inicial que ainda vamos ajustar com perguntas rotuladas.

**O que sai do analisador.** Uma "leitura": nomes achados, restrições (ex.: nível 4), tipo da pergunta e **necessidades**, que são o que a resposta precisa conter. A leitura decide quantos documentos buscar e vira uma lista de verificação no prompt.

**Rede de segurança.** Se o analisador não tiver certeza, o sistema faz exatamente o que a v1 faz hoje. Assim a v2 nunca fica pior por falta de entendimento.

**Por que um único rerank.** A Fase 0 mostrou que o rerank custa ~11 s. Buscar por necessidade multiplicaria esse custo se cada busca fosse reordenada à parte. Por isso todos os candidatos passam por uma reordenação só.
