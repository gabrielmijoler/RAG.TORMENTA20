# Fase 6 — o sistema aprende a interpretar, sem treinar nada

**Dois sinais, dois pesos.** Quando o usuário digita `/errado` ou `/parcial`, é um sinal **forte**: ele apertou um botão. Quando só escreve "deu certo" ou "em partes" na conversa, o programa tenta entender (`rag_v2/feedback.py`) e grava um sinal **fraco**, com a confiança anotada. O silêncio não conta como acerto: se ninguém diz nada, nada é registrado.

**Como o programa "entende" a frase, sem IA.** Ele tira acentos e pontuação e procura expressões prontas ("deu certo", "não era isso"). Para não errar, faz três coisas: ignora perguntas (com `?` ou começando por "qual", "como"…), ignora frases longas e, se a mesma mensagem tem um sentido positivo e um negativo, desiste em vez de adivinhar. "Não funcionou" vira *errado* porque a negação é tratada antes de olhar a palavra "funcionou".

**De sinal a proposta.** O comando `tools/conhecimento.py gerar-propostas` lê o arquivo `sinais/sinais.jsonl` e procura um padrão: em pelo menos 2 perguntas diferentes, o usuário disse que "faltou" algo parecido com o mesmo registro do corpus e o analisador não tinha ligado esse registro. Para comparar, reaproveita o próprio ligador (com os mesmos limiares de semelhança). Aí **propõe** um apelido em `conhecimento/propostas.yaml`.

**A regra que não muda.** Proposta não vale nada. Só passa a valer quando uma pessoa roda `aprovar`, e antes disso o script confere se o registro existe e se o apelido não colide com um nome real. Rodar o gerador de novo não duplica nada, e um apelido recusado não volta.

**Um limite honesto.** O apelido proposto é a palavra que o usuário escreveu no "faltou". Pode não ser a frase exata da pergunta original. Por isso a proposta guarda os ids dos eventos que a originaram: quem revisa vê o contexto e decide.
