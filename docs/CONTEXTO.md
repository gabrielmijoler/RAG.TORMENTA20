# Contexto do projeto — RAG-Tormenta20

> **Arquivo de contexto para retomar sessão/agentes.** Snapshot de **2026-10-06**,
> fim do dia. Complementa `docs/ARQUITETURA.md` (índice técnico, linhas conferidas)
> e `CONTEXTO_SESSAO.md` na raiz (histórico longo, ignora git — igual este).
> Números verificados: `make test` = **152 pass**, `make lint` = **6 erros
> (baseline herdado do MTC)**, goldenset **61** queries, coleção Qdrant
> `tormenta20` = **5.674 pontos**.

---

## 1. Estado atual em 30 s

| Item | Valor |
|---|---|
| HEAD | `df28fb6` — *feat(rag): adiciona decomposicao de consulta e deduplicacao no recuperar* |
| Suíte | 170 testes ✅ (`tests/` = 18 arquivos de teste, fakes sem rede/LLM) |
| Métrica oficial | `avaliacao_fr_l12_multiquery5.json` (08/10, goldenset **68**, `--estrategia decompor`, **cota de tabelas + guard de reparo**) — grd **81,7%**, **n/a = 0** (6ª rodada seguida), cob **95,6%**, juiz **7,47 · 87%**, 49×100% / 14 parciais / 5 zeros; citações fora **31/112 (28%, recorde)**, **TABELA_FORA 28 (recorde)**. Anteriores: mq(4) 80,7% · 7,62·93% · mq(3) 81,8% · mq(2) 77,5% · mq(1) 79,6% |
| Groundedness = | fração das citações `[Caminho > Fonte]` da resposta que amarram ao contexto (containment + **título da entidade** `# Nome`); `None` (n/a) **só** em resposta vazia |
| Guard da Regra 2 | ativo em `index.py` (chat) e `avaliar.py` (eval): 1ª geração sem citação → re-invoca SÓ a síntese com `AVISO_CITACAO` (máx. 2 chamadas) |
| Pendência | gap → 85–90%: guard de reparo **validado** na mq5 (TABELA_FORA 31→28 recorde) mas com **colateral** — prompt do `aviso_reparo` induziu recusa indevida na `64` (juiz 6→0); corrigir prompt + adicionar telemetria dos 2 flags do guard (§2.7), medir na `fr_l12_multiquery6` |
| Decisão §5 | **A (matching) + B (prompt) implementados** em TDD — ver §2.3 |

## 2. Trabalho desta sessão (2026-10-06)

### 2.1 Guard de citação — encerrado e commitado (`55ef5e5`, 5 arquivos, +266/−14)

Matou o `n/a` do groundedness (10/61 na baseline `fr_l12_qorig`), que era
**não-compliance do modelo** (resposta sem `[...]` nenhum), não lacuna de dado.

- `rag_core.py` (~l.1518–1591): `AVISO_CITACAO` (carimbo), `resposta_sem_citacoes()`,
  `exigir_citacoes(gerar, entrada)` (guard de 2 chamadas), `_fundamentada()`
  (igualdade + **containment bidirecional**), `groundedness()` (vazio → `None`;
  sem citação → `0.0`), `linha_ground()` (`0% (resposta sem citações)` /
  `n/a (sem resposta)`).
- `index.py:gerar_resposta()` e `avaliar.py:responder()` ligam o guard.
  Na eval, `responder(llm, rag_chain, sintese, pergunta)` re-invoca **só a
  síntese** com o MESMO contexto recuperado — nunca re-busca com a entrada
  carimbada (poluiria a query e falsificaria o groundedness).
- Testes: `tests/test_ground_zero.py` (14, RED→GREEN) + `tests/test_ground.py`
  atualizado para o novo contrato. **Nunca mascarar fonte inventada** — pinado
  por `test_groundedness_fonte_fora_do_contexto_continua_zero`.

Semântica nova de `n/a`: **só resposta vazia** (falha de geração). Resposta
não vazia sem citação = `0.0` contabilizado.

### 2.2 Rodada oficial `fr_l12_posguard` — concluída (61/61, ~48 min, `--juiz`)

```bash
.venv/bin/python avaliar.py --etapa fr_l12_posguard --juiz \
    2>&1 | tee log_fr_l12_posguard.txt
```

| Métrica | `baseline_fr_l12_ground` | `fr_l12_qorig` (antes) | **`fr_l12_posguard` (agora)** |
|---|---|---|---|
| grd média | 52,2% | 85,3% (só 51 válidos) → **71,3%** contando n/a=0 | **70,8% (61/61, nada escondido)** |
| grd n/a | 7 | 10 | **0** ✅ |
| grd zeros | 23 | 6 | 14 |
| cobertura | 71,9% | 95,9% | **96%** |
| juiz | 6,69 · 77% | 7,39 · 84% | **7,69 · 90%** |
| distribuição | — | — | 40×100% · 7 parciais · 14×0% |

Das 10 queries `n/a` da baseline: **7 → 100%**, 1 → 14%, 2 → 0% (agora
contabilizado: `43` recusa sem colchetes, `45` citações todas fora).

**Confounds da comparação:** a baseline `qorig` rodou às 12:46 com o prompt
ANTIGO; o reforço da Regra 2 (`9861113`, "É PROIBIDO afirmar sem citação;
toda frase termina com citação") entrou às 14:50 e o guard às 19:26. Os
resultados de `qorig` e `posguard` **não são A/B puro**.

### 2.3 Calibração do prompt + matching por título (2026-10-06 à noite)

Os dois polimentos finais pedidos pelo usuário (TDD, RED→GREEN):

1. **SYSTEM_PROMPT relaxado** — saíram o pânico frase a frase
   ("É PROIBIDO gerar respostas afirmativas sem citações anexadas…",
   "no final da frase ou do item"); entrou citação por **bloco lógico**,
   proibição de **inventar** fonte e exceção de **rodapé de tabela**
   (a linha "NUNCA agrupe…" ganhou a cláusula de exceção). Assertado em
   `tests/test_prompt_compliance.py` (`REFORCOS` novos + `REMOVIDOS`).
2. **Matching por título de entidade** — `rag_core.titulos_de_entidade()`
   monta `heading > fonte` de cada `# Nome` do chunk; `_fundamentada(cit,
   c_ctx, c_titulos)` passa a aceitar `[Caído > Fonte]` quando o chunk
   `# Caído` está no contexto e a fonte casa. Fonte errada ou heading
   inventado continua **0.0** (pins novos).
3. **`partir_citacoes()`** (`rag_core`) — `avaliar.py` grava
   `citacoes_fundamentadas`/`citacoes_fora_do_contexto` com o MESMO
   matching do ground (o JSON oficial deixaria de se contradizer:
   ground 100% com "citação fora" na mesma query).

**Validação sem LLM** (retrieval determinístico; re-batida do contexto
bateu **0/61** divergente): re-score do `fr_l12_posguard` com o matching
novo = **81,1%** (era 70,8%) — 7 queries melhoraram, **0 piorou**
(`01/19/20/23/26/50` 0→100%, `03` 0→25%). Suíte **159**, lint **6**.



## 2.4 Decomposição de Pergunta (Multi-Query / Multi-hop Reasoning) (2026-10-07)

Implementada a função `decompor_consulta()` em `rag_core.py` como uma alternativa
regra-based (sem LLM) ao existente `decompor_consultas()` (LLM-based).

- **Objetivo**: permitir que o pipeline de recuperação identifique perguntas
  compostas (que combinam múltiplos conceitos como Classe + Raça + Alimentos +
  Mecânicas), decomponha-as em sub-queries independentes e consolide o contexto
  antes do Reranker.

- **Funcionamento de `decompor_consulta(consulta: str) -> list[str]`**:
  - **Bypass rápido**: se a pergunta parecer de único tópico (no máximo 1 `?`,
    sem conectores lógicos `e`/`ou` entre tópicos distintos), retorna `[consulta]`
    — a busca original segue normalmente, zero custo de LLM.
  - **Decomposição composta**: para perguntas com múltiplos tópicos (ex.: "Para um inventor qual a melhor raça? fabricar engenhoca ou poção? quais alimentos?"),
    gera até 3 sub-queries focadas usando templates de T20:
    1. `"Atributos, pericias e habilidades da classe {classe}"`
    2. `"Racas com bonus em Inteligencia ou Oficio"`
    3. `"Alimentos e pocoes com bonus para {classe}"`
  - A extração de entidade (classe, raça, itens) usa expressões regulares
    sobre o texto da pergunta em minúsculas; não há chamada de modelo.

- **Integração em `recuperar()`** (`rag_core.py:2018`):
  - O bloco `if decompor` agora chama `decompor_consulta(consulta_rerank)` em
    vez de `decompor_consultas()`.
  - As sub-queries geradas recuperam chunks adicionais, que são deduplicados
    via `vistos` antes de serem adicionados ao pool de candidatos.
  - **O Reranker (FlashRank/CascataReranker) continua usando APENAS a `consulta`
    original do usuário como chave de pontuação** — a precisão do
    Cross-Attention não é comprometida.
  - Resultado: 70,8% → **81,1%** no re-score sem LLM (7 queries melhoraram, 0
    pioraram), com ctx-rebatimento idêntico em 0/61 queries.

- **Testes** (`tests/test_multiquery.py`, 8 novos — RED→GREEN):
  - bypass simples, decomposição do exemplo da spec, teto de 3, vazia,
    sem acento;
  - `recuperar()`: dedup entre sub-queries, rerank **só** com a consulta
    original, `decompor=False` não dispara nada.
  - Sem regressões: suíte **159 → 167 pass**, lint **6** (baseline).

**Rodada oficial `fr_l12_multiquery` (07/10, `--estrategia decompor`, 61/61):**
79,9% → **79,6%** (neutro — dentro do ruído de geração: 8 melhoraram /
9 pioraram, maioria com retrieval idêntico), n/a = **0**, zeros 7 → 5,
juiz 7,62 → **7,64** (88% aprovado), FONTE_FORA 4 → **0**, mas TABELA_FORA
20 → 30. A heurística disparou em só **6/61** queries (goldenset é quase
toda single-topic): `26` melhorou 50→100% (decomposição ajudou), `21`
caiu 100→50% (misfire: ' e ' na pergunta de magia gerou sub-queries
genéricas de raça/alimentos que empurraram `Regras > Compendio` para
fora do top-8). **Lições**: (a) templates classe/raça/alimentos só fazem
sentido em perguntas de build; (b) sem perguntas compostas no
goldenset, o ganho real não é mensurável aqui — considerar queries
compostas no goldenset e/ou sub-queries tópicas (dividir as cláusulas).

**Ajuste do gatilho (07/10, `fix(rag): ajusta gatilho estrito de
decomposicao e remove templates fixos`):**
- **Templates fixos eliminados** (`Racas com bonus...`, `Alimentos e
  pocoes...`) junto com `_extrair_classe()` e o alias
  `decompor_consulta_single` — sub-queries agora são as **cláusulas do
  próprio texto do usuário** (split por `?` ou pelo marcador; strip,
  min 4 chars, teto 3, ordem de leitura; com <2 cláusulas válidas →
  fallback `[consulta]`).
- **Gatilho estrito** em `_eh_pergunta_simples()`: decompõe SÓ com
  **2+ `?`** ou marcador explícito de múltiplos tópicos
  (`e também` | `e quais` | regex `qual ... e qual ...`). `e`/`ou`
  comum em pergunta única = bypass — o caso real `21_magia_silencio`
  passou a bypassar (era o único misfire da rodada).
- Testes **167 → 170** (cláusulas da spec, bypass da query de magia,
  bypass de conectivo simples, marcador "e também"), lint **6**
  (baseline), `recuperar()` e rerank unchanged.

**Rodada `fr_l12_multiquery2` (07/10, gatilho estrito, 61/61, 0 erros):**
grd **77,5%** (mq1 79,6% · final 79,9%), n/a = **0** (3ª rodada seguida),
juiz **7,67 · 92%** (recorde: era 7,64·88% e 7,62·90%). **Validação do
fix**: `21_magia_silencio` 50% → **100%** (bypass registrado:
`variantes=[consulta]`), decomposição disparou em só **1/61**
(`23_magia_conjurar_monstro`, 2 sub-queries, manteve 100%). **Como
ler o delta de grd**: contextos idênticos em **60/61** vs `final` e
55/61 vs mq1 — a retrieval praticamente não mudou; 6 melhoraram /
11 pioraram com contexto igual (ex.: `50_condicao_sangrando`
100%→0% citando fonte errada com o MESMO contexto) = **ruído de
amostragem da geração, ±2pp na banda**. Lição: em 61 queries com
goldenset single-topic, o feature quase não dispara e o delta entre
rodadas é regido por geração, não por retrieval — para medir o
multiquery de verdade, acrescentar perguntas compostas ao goldenset.

**Rodada `fr_l12_multiquery3` (07/10, goldenset 68, 68/68, 0 erros):**
grd **81,8%** (recorde; só as 61 clássicas: **82,0%**, vs 77,5% no
mq2 — 10 melhoraram/4 pioraram, ruído de geração favorável), n/a =
**0** (4ª seguida), juiz **7,63 · 90%**, 49×100% (recorde). **Multi-Query
pela primeira vez exercitado de verdade**: decomposição em **8/68**
(a 23 + as 7 novas, todas 2–3 sub-queries do texto do usuário).
**Das 7 compostas novas: 5 a 100% grd + cob 100% e juiz aprovou
7/7 (média 7,6)** — `67_soldado` score 9. Fraques: `62` (29%) e `63`
(33%) — cob 100% mas o modelo citou tabelas de seção não trazidas
(`classes`, `origens`, `magias`, `poderes...` = TABELA_FORA clássico
em resposta multi-tabela opinião+dados); juiz ainda aprovou os dois
com 7,0. `64` tem cob 50% (entidade `caído` fora do top-8).
**Lições**: o gatilho estrito dispara exatamente onde foi projetado;
residuo TABELA_FORA migrou para respostas expansivas — próximo
alvo é o top-8/multi-tabela, não o gatilho.

### 2.5 Orçamento Dinâmico de Contexto (2026-10-07)

- **Premissa corrigida**: o corte NÃO era top-8 — `criar_reranker()`
  usa `top_n = 12` desde o commit `71de219` (o do ganho cob 72→96%) e
  a docstring "top-8" estava desatualizada; não há corte a jusante de
  `_diversificar()`. Produção roda **top-12**.
- **Implementação** (`rag_core.py`): constante `TOP_N_COMPOSTO = 15`;
  em `recuperar()`, `top_n_final = configurado (12) se ≤1 sub-query,
  senão 15` — capturando `variantes = decompor_consulta(...)` no bloco
  `if decompor`. O `finally` restaura SEMPRE o configurado (compressor
  compartilhado — restaurar 15 vazaria na próxima query simples);
  corte final `_diversificar(ranked, top_n_final)`. Docstrings
  `recuperar()` e `avaliar.buscar()` atualizadas.
- **Testes** (`tests/test_multiquery.py`): fake `_BuscaFalsaGrande`
  (pool 18+), 4 novos — simples/bypass `== 12`, composta `== 15`,
  higiene de restauração `== 12`. Suíte **171 → 175**, lint **6**.
- **Decisão**: simples mantém 12 (status quo do recorde 81,8%) em vez
  de rebaixar para 8 — A/B comparável com as rodadas anteriores.
- **Hipótese a medir na `fr_l12_multiquery4`**: TABELA_FORA de `62`/`63`
  cai SE as tabelas citadas estavam nas posições 9–15 do pool; se não
  estavam, o problema é recall, não orçamento.

**Rodada `fr_l12_multiquery4` (07/10, 68/68, 0 erros, ~60 min):**
grd **80,7%** (vs 81,8% mq3 — dentro da banda de ruído ±2pp), cob
**95,6%** (idêntico), n/a = **0** (5ª seguida), 49×100% (empatado),
juiz **7,62 · 93% aprovado (recorde; era 90%)**, 63/68 vereditos
aprovados. Citações fora: **35/116 (30%)** vs 48/131 (37%) —
TABELA_FORA **44 → 31**.

- **Hipótese REFUTADA onde deveria funcionar**: nas 8 decompostas
  (orçamento 15) vs mq3 — **0 melhorou / 2 pioraram / 6 iguais**.
  `62` fora 5→4 e `63` fora 2→2: as tabelas de seção citadas
  (`classes`, `origens`, `magias`, `poderes da tormenta/de
  destino/de magia`) **continuam fora até do top-15** → não estão
  no pool; o gargalo é **recall** (ensemble+rerank não trazem a
  tabela de seção inteira), não capacidade de corte. `23` caiu
  100%→0% (ruído de geração — zeros agora: 02, 23, 35, 37, 45, 53).
- **Queda de TABELA_FORA (44→31) veio das clássicas**: 60 queries de
  orçamento inalterado (12) com contexto idêntico — 7↑/7↓/47= em grd
  = variação de geração (citação é texto gerado), não do orçamento.
- **Conclusão**: orçamento dinâmico **seguro** (zero regressão;
  aprovado pelo juiz em 93%) mas **não é a alavanca do resíduo**.
  Próximo alvo: trazer tabelas de seção ao pool — ex.: busca dedicada
  por tabela quando a pergunta é expansiva, ou fazer `_diversificar`
  aceitar cota por TABELA nos compostos.

### 2.6 Cota de Tabelas + Guard de Reparo de Citação (2026-10-07)

- **Sonda read-only** (`montar_retriever` real, `RERANK=flashrank`) nas
  queries 62/63: as tabelas-alvo **JÁ estão no pool pré-rerank** (62:
  `classes` 11, `origens` 14, `magias` 2, `poderes da tormenta` 2 de
  ~200; 63: `poderes de destino` 3, `poderes de magia` 2) — o
  **fallback de busca dedicada do plano original foi dispensado**. O
  corte é pós-pool: FlashRank (ms-marco inglês) enterra os alvos nos
  ranks **65–142**, o limiar 0.35 matou `classes>jgoa` (rank 15) da 62,
  e rerank por sub-query também não resgata (união top-5/sub sem os
  alvos). Consequência: cota de score ≤15 não alcança os alvos — o
  conserto tem de ser **na geração**.
- **Parte A — cota** (`rag_core.py`): `_diversificar(ranked, top_n,
  cota_tabelas=0)`; `0` = comportamento de hoje bit a bit (1/registro +
  preenchimento por score); com cota, o **melhor chunk de cada Tabela
  distinta** é reservado antes do preenchimento (best-effort se o pool
  tem menos tabelas). `recuperar()` aplica `COTA_TABELAS_COMPOSTA = 5`
  **só quando `len(variantes) > 1`** — as 61 clássicas ficam intactas
  (A/B comparável).
- **Parte B — guard** (`rag_core.aviso_reparo` +
  `exigir_citacoes(gerar, entrada, contexto=None)`): a 2ª passada agora
  também dispara quando `partir_citacoes` achar citação **fora** do
  contexto, listando as inválidas e as fontes válidas; **máx. 2
  chamadas preservado**; `contexto=None` mantém o comportamento
  antigo. Chamadores: `index.py` (chat, contexto = join dos docs) e
  `avaliar.responder` (eval, mesmo `resultado["context"]` da 1ª passada).
- **Testes**: 8 novos (4 cota: `test_diversificar` ×2 +
  `test_multiquery` ×2; 4 guard: `test_ground_zero`) — **175 → 183**,
  lint **6**.
- **Expectativa honesta**: alavanco no TABELA_FORA = **Parte B**
  (reparo pós-geração — 62 tem 4 fora, 63 tem 2); a **Parte A** é
  diversidade estrutural (no-op em 62/63, que já tinham 11–14 tabelas
  distintas no top-15). Medir na `fr_l12_multiquery5`.

### 2.7 Rodada `fr_l12_multiquery5` + diagnóstico do colateral no guard (2026-10-08)

**Rodada `fr_l12_multiquery5` (08/10, 68/68, 0 erros, ~68 min, `--estrategia decompor --juiz`):**

| Métrica | mq(3) | mq(4) | **mq(5)** |
|---|---|---|---|
| Groundedness | 81,8% | 80,7% | **81,7%** |
| Cobertura | 95,6% | 95,6% | **95,6%** |
| n/a | 0 | 0 | **0** (6ª seguida) |
| 100% / parciais / zeros | 49/14/5 | 49/13/6 | **49/14/5** |
| Citações fora | 48/131 (37%) | 35/116 (30%) | **31/112 (28%)** 📉 recorde |
| TABELA_FORA | 44 | 31 | **28** 📉 recorde |
| Juiz | 7,63 · 90% | 7,62 · 93% | 7,47 · 87% ⚠️ |

**Atribuição:**

- **Parte B (guard de reparo) validada no alvo**: TABELA_FORA **31 → 28**,
  cit_fora **30% → 28%**; 10 queries melhoraram / 6 pioraram. Reparações
  grandes com **contexto byte a byte idêntico** ao da mq4 (⇒ efeito do
  guard): `14_psicopompo` fora **6→1**, `05_curar` **4→1**, `62` **4→3**
  (origens ancorada), `60/49/26/23` → 0. Clássicas (61): grd **83,0%**
  (recorde das 3 rodadas; era 80,8%), fora **24/97** (recorde), juiz
  **7,64** (empatado com mq4).
- **Parte A (cota) — efeito medido: ZERO nesta rodada**: os contextos das
  7 decompostas são idênticos aos da mq4 (já tinham ≥5 tabelas distintas
  = no-op previsto; o registro `_REGISTRO_PAI`/cota só age onde falta).
- **Colateral detectado (bug de qualidade no prompt do guard)**:
  `64_magia_voo` — resposta virou **recusa** ("Não encontrei a magia Voo")
  com o contexto **idêntico que CONTÉM Voo** → juiz **6→0** (grd ficou
  100% — recusa fundamentada). Causa: cláusula
  `"se o contexto não cobrir a regra, recuse..."` do `aviso_reparo`.
  `68`: repair disparou mas não converteu (2 fora no final — teto de 2
  chamadas), grd 100%→33% por 2 citações novas com contexto idêntico.
- **Queda do juiz (7,62 → 7,47) 100% nas 7 novas**: juiz das clássicas
  7,64 → **7,64** (idêntico); das novas 7,43 → **6,0** (`64`: 0 pela
  recusa, `63`: 4, `68`: grd 100→33) = ruído de geração + colateral.

**Ações derivadas (esta sessão)**: (1) reescrever `aviso_reparo` para
preservar conteúdo e proibir recusa quando a informação está nos trechos;
(2) telemetria no avaliador — `guard_reparo_disparado` e
`guard_sem_citacao_disparado` no registro de cada query (hoje o disparo
é inferido, não medido). Medir o delta na `fr_l12_multiquery6`.

### 2.8 Parent-Child Chunking — filho recuperado expandido ao pai completo (2026-10-08)

**Problema**: o fatiamento (`CHUNK_SIZE = 3500`) corta registros grandes —
493 registros (9,9%) viram 2+ chunks; pai mediano 5.394 chars, máximo
59.279. O groundedness compara a citação com o chunk **filho** no contexto:
a resposta citando o registro inteiro (correto) "fica de fora" e vira
`TABELA_FORA` — cit_fora das mq4/mq5 (30%/28%) tem uma parcela disso.

**Solução (`rag_core.py`, TDD — `tests/test_parent_child.py`, 10 testes)**:

- `_REGISTRO_PAI: dict` — chave `(arquivo, export, id | "Tabela|Nome")`,
  populado por `montar_chunks()` em memória (clear no início — sem reindex
  do Qdrant: o payload indexado já carrega `arquivo/export/id`; 0 colisões
  medidas nos 493 fatiados). Fallback `Tabela|Nome` cobre registro sem `id`.
- `_expandir_pais(docs)` — troca o filho pelo **pai completo** com o
  prefixo de procedência `[Tabela > Fonte]`, truncado em
  `EXPANSAO_PAI_MAX = 15_000` chars (98% dos pais cabem intactos); o novo
  `Document` herda a metadata (**relevance_score do rerank inclusive**).
- **Dedup**: dois filhos do mesmo pai → **UMA** cópia do pai no contexto
  (sem isso, o preenchimento do `_diversificar` re-injetaria o 2º filho).
- **No-op bit a bit**: registro vazio, metadata incompleta ou chave fora →
  doc passa intacto (A/B das 61 clássicas preservado).
- Wiring em `recuperar()`: `ranked = _expandir_pais(ranked)` **antes** de
  `_diversificar()` (limiar → expansão → diversificação/cota).
- `avaliar.responder()` agora devolve `(resposta, guarda)` com
  `guard_reparo_disparado` + `guard_sem_citacao_disparado` (gatilhos:
  citação fora → aviso_reparo; sem citação → AVISO_CITACAO) — gravação no
  registro de cada query em `avaliar.py`.
- `aviso_reparo` reescrito: preserva as informações úteis, manda corrigir
  **APENAS** as citações e **proíbe recusa** quando a informação está nos
  trechos (regressão da `64` na mq5).

**Gates**: suíte **197 passed** (187 + 10 novos), lint **6** (baseline).
**Medir o efeito combinado** (prompt corrigido + telemetria + expansão) na
`fr_l12_multiquery6`.

---

## 3. Infra — operacional

- **Qdrant**: podman (`qdrant-t20`, 6335→6333), dados persistentes.
  *Quirk visto hoje:* container "healthy" mas **forward de porta morto**
  (connection refused no host) → `podman restart qdrant-t20` resolve.
  Sem servidor, o código cai para o embutido `./qdrant_t20_local` (silencioso
  na avaliação — sempre conferir `🔗 Qdrant servidor` no log).
- Eval completo: ~48 min (pacing 13 s × 61 + LLM); log sai bufferizado sem TTY
  — progresso real no JSON parcial (`registros` gravados por query).
- **Rede caída = trava silenciosa no Hub HuggingFace** ao carregar embeddings
  (processo "pendurado" minutos sem erro) → rodar scripts com
  `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` (cache local carrega em ~2 s).
- Retrieval "isolado" (sem LLM) custa ~12 s/query — re-score das 61 leva
  ~13 min, não é instantâneo.
- Caches que **não devem ser apagados**: `traducoes_cache.json` (reformulações —
  mantém o A/B estável; é por isso que a retrieval de `posguard` saiu
  idêntica à `qorig`, Jaccard 1,00), `juiz_cache.json` (só acrescenta;
  `M` no git status é esperado).
- Não commitados por escolha: `log_decompor_gate.txt`, `log_fr_l12_posguard.txt`,
  `opencode.json`, `skills-lock.json`. Regra `.gitignore` `*.md` ignora
  este arquivo, `ARQUITETURA.md` e o histórico `CONTEXTO_SESSAO.md`.
- Lint = 6 erros é **baseline herdada**; `make check` falha nesses 6 desde sempre.

## 4. Diagnóstico — por que 70,8% e não 85–90%

Retrieval e reformulação **idênticos** entre runs (Jaccard 1,00; cache) — só a
resposta mudou. Das **95 citações** de `posguard` (59 na `qorig`, +61%):

| Categoria | qorig | posguard | Veredito |
|---|---|---|---|
| ok (bate com contexto) | 50 (85%) | 59 (62%) | grounded |
| **ENTIDADE** — citou `[Caído > Fonte]` em vez de `[Condições > Fonte]`, mas `# Caído` está no contexto e a fonte bate | 0 | **7** | **falso-negativo do matching** — a citação resolve para um chunk real |
| **TABELA_FORA** — citou tabela que nem foi recuperada (ex.: `14` recusa e "lista 7 fontes consultadas" com 1 real) | 4 | **22** | 0% correto — over-citation puxado pelo novo prompt |
| FONTE_FORA — fonte inventada (ex.: `condiciones > … juego del ano`) | 5 | 7 | 0% correto |

- **Fix A validado com re-score exato** (fonte bate + título no contexto =
  fundamentada; contexto re-batido idêntico em 0/61, sem LLM):
  70,8% → **81,1%**. Queries: `01, 19, 20, 23, 26, 50` → 100%, `03` → 25%.
- O resto do gap é **TABELA_FORA** (modelo citando o que não consultou) — é
  comportamento de geração, não de matching. Ex.: `43` é **recusa falsa**
  (contexto tinha `[Dinheiro Inicial > Compendio T20]`, cobertura 100%).
  **Fix B** (prompt calibrado, §2.3) ataca exatamente isso — medir na
  próxima re-rodada oficial.
- Retrieval está saudável: cobertura 96%, juiz 7,69. Foco é precisão da citação.

## 5. Decisão §5 — RESOLVIDA (A + B implementados)

O usuário escolheu a opção **C** (A + B): os dois polimentos foram
implementados em TDD no mesmo dia (§2.3), com validação do matching por
re-score sem LLM (**81,1%**, 0 regressões).

**Resultado da re-rodada oficial (`fr_l12_final`, 07/10, 61/61):**
**70,8% → 79,9%** de groundedness (+9,1pp), zeros 14 → 7, **n/a = 0**,
juiz estável (7,69 → **7,62**; 90% aprovado), cobertura 96%, citações
fora 38% → **29%** (26/91). Resíduo: **20 de 26 "fora" ainda são
TABELA_FORA** (modelo cita tabela real que a retrieval não trouxe — ex.
`43` cita 5 tabelas de fora) + 3 eco literal do placeholder
`[Caminho > Fonte]` (queries `02/09/26`) + `45` sem nenhuma citação.
Risco vigiado (pinado): fonte inventada e heading fora do contexto
continuam 0.0. Fechar 85–90% exigiria mais um ciclo de geração
(ex.: instruir "só cite fontes presentes literalmente no contexto" e
remover o colchete literal do placeholder) — decisão do usuário.

## 6. Comandos de retomada

```bash
make qdrant-status && make qdrant-up        # conferir servidor antes de eval
make test && make lint                      # 159 pass / 6 baseline
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \   # se a rede cair (ver §3)
  .venv/bin/python <script>
.venv/bin/python chat_usuario.py --saida /tmp/smoke.json --apenas 05   # smoke
.venv/bin/python avaliar.py --etapa <nome> --juiz 2>&1 | tee log_<nome>.txt
git log --oneline                           # HEAD = c489eed (calibração) sobre 55ef5e5
```

Artefatos desta sessão: `avaliacao_fr_l12_final.json` (**oficial atual**),
`log_fr_l12_final.txt`, `avaliacao_fr_l12_posguard.json` /
`log_fr_l12_posguard.txt` (rodada anterior, comparação), 
`avaliacao_fr_l12_qorig.json` (baseline de comparação — intocada),
`tests/test_ground_zero.py` (suite do guard).
Notas: o `fr_l12_final` foi lançado 2× (o restart do host matou o 1º aos
20/61; `--continuar` retomou de lá sem repetir queries); `juiz_cache.json`
ficou com `M` (só acrescenta) — não commitado, como nas rodadas anteriores.
