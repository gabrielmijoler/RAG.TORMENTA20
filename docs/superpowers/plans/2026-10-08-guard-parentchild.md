# Plano FINAL — Guard (mq5) + Parent-Child (Tarefas A–F)

> Executado inline (executing-plans) por ordem do usuário em 2026-10-08.

**Goal:** Documentar mq5, corrigir o prompt do `aviso_reparo` (anti-recusa indevida), adicionar telemetria de 2 flags do guard, e implementar Parent-Child chunking (teto 15.000 chars, dedup) — TDD, gates `make test`/`make lint` (baseline 183 testes / lint 6), commits e push por bloco.

**Decisões confirmadas (Q1–Q3):** teto = truncar pai em `EXPANSAO_PAI_MAX = 15_000` chars · telemetria = `guard_reparo_disparado` + `guard_sem_citacao_disparado` (bools) · bloco 2 = docs §2.8 dentro do commit feat + push.

## Tarefas
- **A** — docs mq5 (`docs/CONTEXTO.md`: linha 18 Métrica oficial, linha 21 Pendência, §2.7 novo) → commit `docs(rag): documenta fr_l12_multiquery5 — recorde em TABELA_FORA (28) e diagnostico do colateral no guard`
- **B** — TDD prompt `aviso_reparo` (RED em tests/test_ground_zero.py → GREEN em rag_core.py:1540)
- **C** — TDD telemetria (RED: 3 testes → GREEN: `avaliar.responder` retorna tupla `(resposta, dict)`; call site l.524; `registro.update` grava os 2 flags)
- **D** — gate (`make test`, `make lint`), commit `fix(rag): ajusta prompt do guard de reparo para EVITAR recusas indevidas e adiciona telemetria`, `git push origin master`
- **E** — TDD parent-child (RED em `tests/test_parent_child.py` → GREEN: `_chave_pai`, `_expandir_pais`, `_REGISTRO_PAI` em `montar_chunks`, wiring em `recuperar()` antes de `_diversificar`)
- **F** — gate, docs §2.8, commit `feat(rag): implementa parent-child chunking para expansao de tabelas`, push

## Global Constraints
- TDD obrigatório (RED→GREEN pelo motivo certo); suíte completa + lint só no fim de cada tarefa.
- pt-BR; números oficiais do `avaliar.py` completo; lint baseline **6**.
- `juiz_cache.json` e `log_*.txt` NUNCA commitados; commits com mensagens exatas; `git add` sempre com paths explícitos.

## Review Focus
1. Prompt novo não troca recusa induzida por afirmação sem fonte (condição de presença mantida).
2. Assinatura nova de `responder` — único call site + 3 testes de flag.
3. Registry vazio / metadata incompleta = no-op sem crash.
4. Pai de 59 KB — teto 15.000.
5. Expansão incondicional muda contexto da mq6 (medida futura).
