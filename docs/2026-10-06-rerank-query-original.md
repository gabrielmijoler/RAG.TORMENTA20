# Rerank só com a query original + reescopo do 42 + groundedness no chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** recuperar a cobertura (72% → ~99%) corrigindo a query de rerank, trocar a única query inválida do goldenset, e medir o groundedness **pelo caminho real do usuário** (`index.processar`), com A/B antes/depois.

**Architecture:** 7 tasks encadeadas: (1) dado reescopado → (2) sonda offline que **gata** a mudança → (3) chat "antes" na amostra de 28 → (4) 1 linha em `recuperar()` + TDD + docstrings → (5) chat "depois" + diff do grd → (6) `avaliar.py` completo em etapa nova → (7) documentação. Os dois caminhos de métrica ficam cobertos: **sonda/avaliar = cobertura**, **chat = groundedness correto**.

**Tech Stack:** Python/langchain/FlashRank/Qdrant(:6335)/pytest/ruff.

**Spec:** auditoria aprovada (11 queries <50%, 23 zeros de grd, 7 zeros de formato) + histórico em `CONTEXTO_SESSAO.md`.

## Global Constraints

- `avaliacao_baseline_fr_l12_ground.json` **imutável** (hash conferido no início e no fim): cob 72%, grd 52%, 23 zeros, 7 n/a, 61/61 `flashrank`, juiz 6,69/77%.
- `traducoes_cache.json` / `juiz_cache.json`: só acrescentar.
- `make lint` = **6 erros** (baseline MTC); `make test` = **116 → 122 testes**.
- Chat: `RERANK` default (`auto`, como o usuário usa); pausa de 10 s entre perguntas só p/ cota dos LLMs gratuitos; **zero adulteração do caminho** (`redirect_stdout` é a única instrumentação).
- Probe: `RERANK=flashrank`, sem LLM, sem Cohere.
- Qdrant de pé (`make qdrant-status`) antes de qualquer task que use retrieval.
- Sem commits (não pedido).

## Review Focus

1. **Driver de chat altera o comportamento** → só chama `index.processar()` e captura stdout; teste unitário de `parsear_ground`/`resolver_caso` (`tests/test_chat_usuario.py`) + smoke de 1 pergunta conferindo o rodapé `ground:`.
2. **Regressão do ensemble (Basilisco 08)** → teste `chamadas == ["reformulada", "original"]` em `test_reranker.py`.
3. **Consulta sem `consulta_real`** → teste dedicado (`queries == ["reformulada"]`).
4. **42 reescopado com entidade fora do chunk** → verificação script das 3 entidades no chunk único `[Perícias > Compendio T20] # Acrobacia`.
5. **Sondagem com limiar errado** (wrapper sem `ultimo_modo` → limiar 0,35 ignorado) → assert no probe `real.ultimo_modo == "flashrank"` por query.
6. **A/B de grd contaminado por reformulação ao vivo** → as duas rodadas logam `pergunta_t20`; toda query cujo grd mudou é inspecionada (resposta salva no JSON) antes de concluir.

---

### Task 1: Reescopar `42_cd_heroica` → `42_cd_escapar`

**Files:** Modify `goldenset.jsonl:42` · Test: `tests/test_goldenset.py`

**Por quê primeiro:** a sonda e as duas rodadas de chat precisam das 61/28 válidas; o A/B do chat fica limpo porque o 42 é idêntico nos dois lados.

- [ ] **Step 1: confirmar a regra no corpus**

```bash
grep -c "algemas (CD 30)" ../aTormenta/data/pericias.ts   # esperado: 1
```

- [ ] **Step 2: substituir a linha 42**

```json
{"id": "42_cd_escapar", "consulta": "Qual a CD para escapar de amarras com a perícia Acrobacia?", "entidades": ["acrobacia", "amarras", "algemas"], "resposta_esperada": "Com Acrobacia você pode escapar de amarras (ação completa): cordas CD = resultado do teste de Destreza de quem amarrou +10, redes CD 20 e algemas CD 30."}
```

- [ ] **Step 3:** `.venv/bin/python -m pytest tests/test_goldenset.py -v` → 7 PASS (61 casos)
- [ ] **Step 4: entidades no mesmo chunk do alvo**

```bash
.venv/bin/python - <<'PY'
import rag_core
alvo = [d for d in rag_core.montar_chunks(verbose=False)
        if d.metadata["Nome"] == "Acrobacia"][0]
falta = [e for e in ("acrobacia", "amarras", "algemas")
         if rag_core.normalizar(e) not in
         rag_core.normalizar(alvo.page_content + str(alvo.metadata))]
assert not falta, falta
print("OK", alvo.metadata["Tabela"], alvo.metadata["Fonte"], len(alvo.page_content))
PY
```
Expected: `OK Perícias Compendio T20 1962`

---

### Task 2: Sonda offline A/B (`probe_rerank_ab.py`) — **gate**

**Files:** Create `probe_rerank_ab.py` · artifacts `log_probe_rerank_ab.txt`, `probe_rerank_ab.json`

Mede as 61 queries no **mesmo** `rag_core.recuperar()`, variando só a query entregue ao FlashRank (candidatos = ensemble das duas formulações, idênticos nas 3 variantes): `combinada` (hoje), `original` (`consulta_real`), `reformulada`.

- [ ] **Step 1: escrever o script** (versão completa no corpo desta sessão / `probe_rerank_ab.py`)
- [ ] **Step 2:** `.venv/bin/python probe_rerank_ab.py 2>&1 | tee log_probe_rerank_ab.txt` → 3–8 min, 61/61 `flashrank`
- [ ] **Step 3 (gate):** prosseguir só se `cob_media(original) >= cob_media(combinada)` **e** regressões ≤ 5. Reverso → parar e reportar.

---

### Task 3: Chat "antes" — 28 queries, caminho real do usuário

**Files:** Create `chat_usuario.py` + `tests/test_chat_usuario.py` · artifacts `chat_usuario_antes.json`, `log_chat_antes.txt`

**Amostra dirigida** = união dos 23 `grd == 0%` com os 11 `cobertura < 50%` de `avaliacao_baseline_fr_l12_ground.json` → **28 queries**, pelo prefixo numérico (sobrevive ao reescopo do 42): `02 06 07 08 10 11 14 15 16 21 23 24 26 27 30 32 34 38 40 42 43 44 49 52 53 54 57 59`.

- [ ] **Step 1: teste do driver (TDD)** — `tests/test_chat_usuario.py`: `parsear_ground` (percentual / n/a / sem resposta), `resolver_caso` (prefixo), `len(AMOSTRA) == 28`
- [ ] **Step 2: implementar `chat_usuario.py`** — `main()` importa `index` e chama `index.processar()` com `chat_history`/`filtros_ativos` limpos por pergunta, `contextlib.redirect_stdout` capturando o rodapé; flags `--saida`, `--continuar`, `--pausa` (default 10 s)
- [ ] **Step 3:** `.venv/bin/python -m pytest tests/test_chat_usuario.py -v` → 4 PASS; `make test` verde
- [ ] **Step 4: smoke com 1 pergunta** — JSON com `ground` numérico e `reformulacao` preenchidos
- [ ] **Step 5: rodada ANTES** (código ainda com rerank combinado)

```bash
sha256sum avaliacao_baseline_fr_l12_ground.json > /tmp/opencode/baseline.sha256
.venv/bin/python chat_usuario.py --saida chat_usuario_antes.json 2>&1 | tee log_chat_antes.txt
```
Expected: 28/28, ~10–15 min, sem `ERRO`

---

### Task 4: `consulta_rerank` só com a query original (TDD)

**Files:** Modify `rag_core.py:1864-1872`, docstrings `rag_core.py:1838-1846`, `avaliar.py:365`, `index.py:168`, `README.md:112` · Test: `tests/test_reranker.py`

**Interfaces:** assinatura de `recuperar()` inalterada; produz `compressor.compress_documents(docs, consulta_real)` quando `consulta_real` existe e difere de `consulta`, senão `consulta`; ensemble continua com as duas.

- [ ] **Step 1: testes falhando** — `_Gravador(_Fake)` grava `queries`; `test_recuperar_reranka_somente_com_a_query_original` (afirma `chamadas == ["reformulada", "original"]` e `queries == ["original"]`) e `test_recuperar_sem_consulta_real_reranka_com_a_propria_query`
- [ ] **Step 2:** pytest `-k "query_original or propria_query"` → **FAIL**
- [ ] **Step 3: mudança de 1 linha** — `consulta_rerank = consulta_real` no fim do `if consulta_real ...` (era `f"{consulta} {consulta_real}"`)
- [ ] **Step 4:** `make test` → 122 PASS · `make lint` → **6 erros**
- [ ] **Step 5: docstrings/README** (5 locais), com a nota: *"com o FlashRank ms-marco-MiniLM-L-12 em pt-BR a query combinada enterrava os alvos nas posições 12–31 — medido em 61 queries; a nota antiga sobre 'Perícias'/'Símbolo'/'Cavalo' era do Cohere, em outro contexto"*
- [ ] **Step 6:** `make check`

---

### Task 5: Chat "depois" + diff do groundedness

**Files:** artifacts `chat_usuario_depois.json`, `log_chat_depois.txt`

- [ ] **Step 1:** `.venv/bin/python chat_usuario.py --saida chat_usuario_depois.json 2>&1 | tee log_chat_depois.txt`
- [ ] **Step 2: diff A/B** (médias, zeros, n/a, listagem de queries que mudaram e de reformulações distintas)
- [ ] **Step 3: inspeção manual** de toda query cujo grd mudou (o `log` está no JSON) — separar melhoria real de ruído de modelo

---

### Task 6: `avaliar.py` completo (etapa nova `fr_l12_qorig`)

**Files:** `avaliacao_fr_l12_qorig.json`, `log_fr_l12_qorig.txt` — **baseline intocado**

- [ ] **Step 1:** `make qdrant-status` → OK
- [ ] **Step 2 (~40 min):** `.venv/bin/python avaliar.py --etapa fr_l12_qorig --juiz 2>&1 | tee log_fr_l12_qorig.txt`
- [ ] **Step 3: sucesso** — cobertura **≥ 95%** (alvo ~99%); `RERANK … flashrank 61`; hash do baseline OK
- [ ] **Step 4: diff por query vs baseline** (mapeamento `42_cd_heroica` ≡ `42_cd_escapar`) → `REGREDIRAM` vazio ou ≤ 2, investigadas

---

### Task 7: Documentação + verificação final

**Files:** `CONTEXTO_SESSAO.md`

- [ ] **Step 1: nova seção** com (i) causa raiz, (ii) números da sonda, (iii) A/B do grd via chat (28) + ressalva do ruído de reformulação ao vivo, (iv) números do avaliar `fr_l12_qorig`, (v) reescopo do 42 com **mapeamento de id**, (vi) pendência dos 7 zeros de formato (`PADRAO_CITACAO`).
- [ ] **Step 2:** item 5.2 (`CONTEXTO_SESSAO.md:57-59`) marcado *superseded em 2026-10-06*.
- [ ] **Step 3:** `make check` + hash do baseline + `git status` só com os arquivos previstos.

---

## Ordem, decisões e custo

| # | Task | Gate/criterio | Tempo |
|---|---|---|---|
| 1 | Reescopo 42 | 3 entidades no chunk único | 2 min |
| 2 | Sonda A/B (61 × 3) | `original ≥ combinada`, regressões ≤ 5 | 3–8 min |
| 3 | Chat **antes** (28) | 28/28 sem `ERRO` | 10–15 min |
| 4 | 1 linha + TDD + docs | lint 6, 122 testes | 5 min |
| 5 | Chat **depois** (28) + diff | grd média ≥ antes; regressões inspecionadas | 10–15 min |
| 6 | `avaliar.py` completo | cob ≥ 95%, baseline hash OK | ~40 min |
| 7 | CONTEXTO_SESSAO + `make check` | tudo verde | 10 min |

**Decisões travadas:** amostra = 28 prefixos; chat A/B com sessão limpa por pergunta (um usuário que abre o chat e faz uma pergunta) e pausa de 10 s; `avaliar.py` roda mesmo (JSON oficial da série `avaliacao_*.json`); 42 renomeado com mapeamento documentado; nada é commitado. Execução **nativa**.

Total ≈ **1h30 de máquina**.
