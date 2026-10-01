# RAG-Tormenta20

RAG (Retrieval-Augmented Generation) para perguntas de regra de **Tormenta 20**,
o RPG de mesa da Jambo Editora. Herdado do projeto RAG-MTC: mesmo core de
processo (busca híbrida + rerank + LLM com fallback) e mesmo banco de dados
vetorial (Qdrant).

## Arquitetura

```
pergunta do usuário
  → [1/4] reformulação com histórico (resolve "desse monstro", "ele"...)
  → [2/4] tradução para termos do sistema (PROMPT_TRADUCAO)
  → [3/4] recuperação: Qdrant (k=50) + BM25 (k=50) → ensemble 0.5/0.5
          → CohereRerank (top 8)
  → [4/4] síntese: SYSTEM_PROMPT (anti-alucinação) + contexto + histórico
```

- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` (local, multilíngue)
- **LLM**: NVIDIA → Groq → OpenRouter (todos gratuitos, com retry automático)
- **Citações**: resposta exige `Nome [Fonte]` copiado do contexto (Regra anti-alucinação)
- **Memória longa**: fim de sessão → resumo JSON arquivado em `sessoes_campanha`

## Setup

```bash
make install      # cria .venv e instala o projeto (comandos rag-*)
make dev          # ruff + pytest
cp ../RAG/.env .  # chaves (NVIDIA/GROQ/OPENROUTER/COHERE/QDRANT) já no formato
```

Qdrant em Docker (porta 6335, não conflita com o MTC na 6333):

```bash
make qdrant-up
make qdrant-status
```

Sem Docker, o Qdrant embutido local (`./qdrant_t20_local`) é usado
automaticamente.

## Comandos

```bash
make chat              # chat interativo
make avaliar           # suite de avaliação (ETAPA=baseline|depois)
make lint && make fmt  # ruff
```

No chat: `/salvar` arquiva a sessão, `/novo` limpa histórico, `/sair` encerra.

## Fase 2 — Ingestão dos dados JSON (aguardando)

A ingestão está formalmente definida em `rag_core.montar_chunks()`, que hoje
falha com instrução clara enquanto não há dados. Quando você passar os JSONs
(estilo banco de dados) eles vão em `./data/*.json` e o loader será
implementado para:

1. Ler cada arquivo/tabela JSON;
2. Converter cada registro em `Document` com:
   - `page_content` — texto legível (registro renderizado, anexos juntos);
   - `metadata` — `Tabela`, `id`, `Nome`, `Tipo`, `Fonte` (usadas pelo
     filtro, pelo BM25, pelo rerank e pela exibição no chat);
3. Aplicar `mesclar_pequenos()` (já pronto, genérico) e indexar no Qdrant.

Contrato mínimo esperado por registro (sujeito a ajuste quando os dados
chegarem):

```json
{
  "tabela": "magias",
  "registros": [
    {"id": 1, "nome": "Fogueirada", "circulo": 1, "custo_pm": 1, "...": "..."}
  ]
}
```

Enquanto isso, `montar_chunks()` imprime os JSONs que encontrar em `data/` e
aborta — nada é indexado em silêncio.

## Avaliação

`avaliar.py` mede, sobre as mesmas queries:

| Métrica | O que mede |
|---|---|
| `cobertura_entidades` | entidades esperadas presentes no top-8 recuperado |
| `groundedness` | % das citações `Nome [Fonte]` da resposta que estão no contexto |
| `scores_rerank` | faixa de relevância do reranker |

As `CONSULTAS` no topo de `avaliar.py` são **placeholders** — troque pelas
queries do seu dataset após a Fase 2.

## Estrutura

```
rag_core.py           # core: LLM fallback, busca híbrida, Qdrant, prompts
meu_primeiro_rag.py   # chat CLI com memória de sessão
avaliar.py            # suite de avaliação (baseline/depois)
data/                 # JSONs de origem (Fase 2)
compose.yaml          # Qdrant na porta 6335
```
