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
          → filtro por metadados (se /filtro ativo) → CohereRerank (top 8)
          → 1 chunk por registro (_diversificar)
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

No chat: `/filtro tabela=Magias` restringe a busca por metadados (`/filtro`
lista os valores disponíveis com contagem; `/filtro limpar` desliga; vale até
`/novo`), `/salvar` arquiva a sessão, `/novo` limpa histórico, `/sair` encerra.

## Fase 2 — Ingestão (implementada)

Os dados vêm das **fontes `.ts` vivas** do app
[aTormenta](https://github.com/oClaus/aTormenta), esperado como irmão deste
repositório (`../aTormenta/data`, 74 arquivos / 110 exports / ~5.000
registros). Nada é convertido para `.md` nem copiado: a cada ingestão o
extrator Node `tools/ts_para_registros.mjs` lê os `export const` direto de lá.

Fluxo em `rag_core.montar_chunks()`:

1. `node tools/ts_para_registros.mjs --dir ../aTormenta/data` → JSON de
   registros (precisa de Node 20+ no PATH; ~0,4 s);
2. cada registro vira um `Document`:
   - `page_content` — registro renderizado em texto legível (cabeçalho
     `# Nome`, campos rotulados em português, listas aninhadas), **não** JSON;
   - `metadata` — `Tabela`, `Fonte`, `Nome`, `Tipo`, `id`, `arquivo`,
     `export` (alimentam BM25, rerank, exibição e a métrica de cobertura);
3. fatiamento por parágrafo (`_fatiar`) sem deixar cabeçalho órfão →
   `mesclar_pequenos()` → prefixo de procedência `[Tabela > Fonte]` que abre
   cada bloco (é dele que a citação `Nome [Fonte]` é copiada);
4. embeddings locais + Qdrant (coleção `tormenta20`).

Diagnóstico impresso a cada ingestão: registros por tabela, fontes
(`origin`/`source`/`//#region`), blocos antes/depois da fusão e prefixos.

Para reindexar do zero após mudanças no loader/dados:

```bash
REINDEXAR=1 make chat
```

## Avaliação

`avaliar.py` mede, sobre as mesmas queries:

| Métrica | O que mede |
|---|---|
| `cobertura_entidades` | entidades esperadas presentes no top-8 recuperado |
| `groundedness` | % das citações `Nome [Fonte]` da resposta que estão no contexto |
| `scores_rerank` | faixa de relevância do reranker |

As `CONSULTAS` são **18 perguntas reais** cobrindo regras, condições,
perícias, magias, classes, raças, itens, ameaças, deuses, origens e
distinções — com as `entidades` verificadas contra o corpus indexado.

```bash
make avaliar ETAPA=baseline                         # primeira medição
.venv/bin/python avaliar.py --etapa depois --continuar  # retoma o parcial
.venv/bin/python avaliar.py --so-recuperacao        # sem chamar o LLM
```

Baseline (2026-10-01, `avaliacao_baseline.json`): **cobertura 95%**,
**groundedness 81%**, rerank até 0,91 — 16/18 queries com cobertura total.

Etapa "depois" (2026-10-01, `avaliacao_depois.json`) — mesmas 18 queries e
mesmo cache de reformulações, após as correções (exemplos e citação integral
no `SYSTEM_PROMPT`, query `04` reescopada para o Escriba Arcano, e recuperação
em 3 estágios: candidatos das duas formulações → rerank com query combinada →
`_diversificar` com 1 chunk por registro).
Em 2026-10-06 o rerank passou a usar só a query original: com o FlashRank
(`ms-marco-MiniLM-L-12`, inglês) a query combinada em português enterrava os
alvos nas posições 12–31 — medido nas 61 queries (cobertura 72,4% → 95,9%);
ver `CONTEXTO_SESSAO.md`.

| Métrica | baseline | depois |
|---|---|---|
| cobertura_entidades | 95% | **100%** (18/18, estável em 3 rodadas) |
| groundedness | 81% | 88–94% (média ~90%) |

A groundedness oscila entre rodadas (falhas de formato de citação do LLM
gratuito pulam de query a query — 08/13, depois 03/04, depois 11/12); o
retrieval fica 100% em todas. A query `08` (regressão do 1º A/B) foi
consertada: o registro real do Basilisco agora entra no rank 1 do top-8.

## Estrutura

```
rag_core.py                    # core: LLM fallback, busca híbrida, Qdrant, prompts
index.py                       # chat CLI com memória de sessão
avaliar.py                     # suite de avaliação (baseline/depois)
tools/ts_para_registros.mjs    # extrator dos .ts do aTormenta → JSON
tests/                         # pytest (make test)
avaliacao_baseline.json        # resultado da medição inicial
compose.yaml                   # Qdrant na porta 6335
```
