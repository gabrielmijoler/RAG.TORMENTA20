---
name: RAG Evaluation
description: Run and analyze RAG evaluation pipelines (ground truth, retrieval metrics, generation quality)
---

## Workflow

1. **Understand the evaluation goal**: What metric? (recall@k, MRR, nDCG, faithfulness, answer relevance)
2. **Check existing evaluation scripts**: Look at `avaliar.py`, `test_*.py` files, and `goldenset.jsonl`
3. **Run baseline first**: Execute current pipeline to establish baseline metrics
4. **Make targeted changes**: Modify one component at a time (retriever, reranker, prompt, chunking)
5. **Re-run evaluation**: Compare against baseline
6. **Document results**: Save metrics in `avaliacao_*.json` with clear naming

## Key Files

- `avaliar.py` - Main evaluation runner
- `goldenset.jsonl` - Ground truth QA pairs
- `avaliacao_*.json` - Evaluation results
- `test_ground.py`, `test_reranker.py`, `test_hyde.py` - Component tests

## Common Evaluation Patterns

### Retrieval Metrics
```python
# Recall@k - did we retrieve the relevant chunk?
# MRR - rank of first relevant result
# nDCG - ranking quality considering relevance grades
```

### Generation Metrics
```python
# Faithfulness - answer grounded in retrieved context?
# Answer Relevance - addresses the question?
# Hallucination rate - unsupported claims?
```

## Experiment Tracking

Name result files clearly:
- `avaliacao_baseline.json` - Current production
- `avaliacao_exp_{component}_{variant}.json` - Experiments
- Include: timestamp, config hash, key params (chunk_size, top_k, reranker)

## Running Evaluations

```bash
# Full evaluation
python avaliar.py

# Specific test
pytest tests/test_reranker.py -v

# With coverage
pytest tests/ --cov=rag_core
```

## Debugging Failed Evaluations

1. Check `log_*.txt` for detailed traces
2. Inspect retrieved chunks vs ground truth
3. Verify prompt template changes didn't break formatting
4. Ensure embeddings model matches ingestion