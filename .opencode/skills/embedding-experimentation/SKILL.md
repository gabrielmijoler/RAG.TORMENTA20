---
name: Embedding Experimentation
description: Test and compare embedding models for Portuguese RAG retrieval
---

## Workflow

1. **Define experiment goal**: Better recall@k? Lower latency? Multilingual support?
2. **Select candidate models**: Check `MODELOS_GRATUITOS` in rag_core.py and MTEB leaderboard
3. **Re-ingest with new embeddings**: Vector store must match embedding model
4. **Run evaluation**: Compare retrieval metrics (recall, MRR, nDCG)
5. **Check latency/cost**: Embedding dims, inference time, API vs local
6. **Document decision**: Save config and metrics

## Current Setup (rag_core.py)

```python
MODELOS_GRATUITOS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # 384d
    "sentence-transformers/distiluse-base-multilingual-cased-v1",   # 512d
    # ... more models
]
```

## Candidate Models for Portuguese

| Model | Dims | Type | Notes |
|-------|------|------|-------|
| `intfloat/multilingual-e5-large` | 1024 | Local | Strong multilingual, heavy |
| `intfloat/multilingual-e5-base` | 768 | Local | Good balance |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | Local | Current strong baseline |
| `BAAI/bge-m3` | 1024 | Local | SOTA multilingual, supports dense+sparse |
| `cohere-embed-multilingual-v3.0` | 1024 | API | Managed, good Portuguese |
| `text-embedding-3-large` | 3072 | API | OpenAI, expensive |

## Experiment Protocol

### 1. Prepare Test Set
```bash
# Use goldenset.jsonl queries as test queries
# Ensure diverse: fact lookup, multi-hop, ambiguous, long-tail
```

### 2. Re-ingest (Critical!)
```python
# In rag_core.py: obter_embeddings() returns new model
# Qdrant collection must be recreated with new vectors
# Run: python -c "from rag_core import montar_chunks; montar_chunks()"
```

### 3. Evaluate Retrieval Only
```bash
# Disable reranker to isolate embedding quality
# Check: recall@5, recall@10, MRR@10
pytest tests/test_reranker.py -v -k "not rerank"
```

### 4. Full Pipeline Evaluation
```bash
python avaliar.py
# Compare: retrieval metrics + generation quality
```

## Key Metrics to Track

- **Retrieval**: Recall@5, Recall@10, MRR@10, nDCG@10
- **Latency**: Embedding time (ms/query), search time
- **Storage**: Vector size × num_chunks = disk usage
- **Quality**: Downstream generation faithfulness

## Common Pitfalls

- ❌ Changing embedding without re-ingesting
- ❌ Comparing different chunk sizes
- ❌ Ignoring query-side embedding (must match doc-side)
- ❌ Not testing on Portuguese-specific queries
- ❌ Forgetting reranker may mask embedding differences

## Results Template

```markdown
## Embedding Experiment: {model_name}
- Date: {date}
- Config: chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}
- Retrieval: R@5={x}, R@10={y}, MRR={z}
- Latency: embed={a}ms, search={b}ms
- Generation: Faithfulness={c}, Relevance={d}
- Verdict: {accept/reject/needs_more_testing}
```