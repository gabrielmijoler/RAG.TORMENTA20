---
name: Prompt Engineering
description: Design, test, and optimize prompts for RAG generation and query reformulation
---

## Workflow

1. **Identify the prompt**: SYSTEM_PROMPT, PROMPT_TRADUCAO, reformulation prompt, or custom
2. **Understand current behavior**: Run test queries, check logs for failure modes
3. **Apply prompt engineering principles**:
   - Clear instructions with examples (few-shot)
   - Explicit constraints (format, length, style)
   - Chain-of-thought for complex reasoning
   - Negative constraints (what NOT to do)
4. **Test incrementally**: Change one thing, evaluate, iterate
5. **Validate with golden set**: Run `avaliar.py` after changes

## Key Prompts in This Project

### SYSTEM_PROMPT (rag_core.py)
- Anti-hallucination rules
- Domain-specific: Tormenta 20 RPG rules
- Response format constraints
- Language: Portuguese

### PROMPT_TRADUCAO (rag_core.py)
- Query translation for cross-lingual retrieval
- Portuguese ↔ English

### Reformulation Prompt (reformular_pergunta in rag_core.py)
- Conversational query → standalone search query
- Uses chat history context

## Prompt Testing Checklist

- [ ] Test with greetings/chitchat (should not retrieve)
- [ ] Test with ambiguous queries (should clarify or retrieve broadly)
- [ ] Test with specific rule queries (should find exact rule)
- [ ] Test multi-hop questions (requires multiple chunks)
- [ ] Test adversarial: "ignore instructions", "reveal prompt"
- [ ] Verify Portuguese output quality

## Iteration Pattern

```python
# 1. Create test variant
PROMPT_VARIANT = SYSTEM_PROMPT + "\n\n[NEW INSTRUCTION]"

# 2. Quick manual test in index.py
# 3. Run evaluation
python avaliar.py

# 4. Compare metrics (faithfulness, relevance, latency)
# 5. Accept or revert
```

## Common Issues to Watch

| Issue | Symptom | Fix |
|-------|---------|-----|
| Hallucination | Cites non-existent rules | Strengthen "only use context" instruction |
| Verbose | 500+ token answers | Add "be concise, max 3 paragraphs" |
| Wrong language | English responses | Explicit "responda em português" |
| Format drift | Lists become paragraphs | "use bullet points for lists" |
| Context ignoring | Answers from parametric knowledge | "base-se EXCLUSIVAMENTE no contexto" |

## A/B Testing Prompts

Use `avaliacao_` prefix for result files:
- `avaliacao_prompt_v1_baseline.json`
- `avaliacao_prompt_v2_strict_grounding.json`
- `avaliacao_prompt_v3_concise.json`