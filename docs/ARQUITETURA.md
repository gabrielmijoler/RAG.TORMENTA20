# Arquitetura — RAG-Tormenta20

> **Índice técnico para agentes LLM.** Paths relativos à raiz do repo, funções
> com nº de linha conferido em **2026-10-06** (linha muda com edição — sempre
> re-conferir com `grep -n`). Números verificados: `make test` = **122 pass**,
> `make lint` = **6 erros (baseline herdado do MTC)**, goldenset **61** queries,
> coleção Qdrant `tormenta20` = **5.674 pontos**.
>
> Fonte da verdade para histórico/A-B: `CONTEXTO_SESSAO.md` (ignorado pelo git).
> Este arquivo também é ignorado pelo git (regra `*.md` do `.gitignore`).

---

## 1. Visão em 30 s

| Componente | Arquivo | Papel |
|---|---|---|
| Core (ingestão + busca + prompts + LLM) | `rag_core.py` (2.186 l.) | todo o processo reutilizável |
| Chat interativo | `index.py` (368 l.) | CLI de perguntas, `/filtro`, `/novo` |
| Suite de avaliação | `avaliar.py` (635 l.) | goldenset → métricas + juiz LLM |
| Medição A/B do caminho real do chat | `chat_usuario.py` (137 l.) | driver read-only sobre `index.processar` |
| Sonda offline de rerank | `probe_rerank_ab.py` (162 l.) | 61 q × 3 variantes, sem LLM |
| Extração dos dados-fonte | `tools/ts_para_registros.mjs` (620 l.) | `.ts` de `../aTormenta` → JSON de registros |
| Testes | `tests/` (14 `test_*.py` + `conftest.py` + `fakes.py`) | 122 testes, fakes (zero rede/LLM) |
| Infra | `compose.yaml`, `Makefile`, `pyproject.toml`, `.env` | Qdrant :6335, comandos, deps |

```
CHAT                                    AVALIAÇÃO
pergunta → [1/4] reformula c/ histórico  goldenset.jsonl (61)
        → [2/4] traduz p/ termos do T20 → reformular(cache) → buscar()
        → [3/4] recuperar()              → responder() → groundedness()
        → [4/4] gerar_resposta()         → juizar() (LLM-as-Judge, opcional)
        → rodapé `ground: NN%`           → avaliacao_<etapa>.json + log
```

---

## 2. Árvore do repositório

```
RAG-Tormenta20/
├── rag_core.py            # CORE — ingestão, Qdrant, rerank, prompts, LLM, recuperar()
├── index.py               # chat (entry point `rag-chat` / `make chat`)
├── avaliar.py             # suite de avaliação (entry point `rag-avaliar`)
├── chat_usuario.py        # A/B do chat real (28 queries dirigidas)
├── probe_rerank_ab.py     # sonda offline: combinada vs original vs reformulada
├── goldenset.jsonl        # 61 casos: id/consulta/entidades/resposta_esperada
├── Makefile               # install dev qdrant-{up,down,status} chat avaliar lint fmt test check
├── pyproject.toml         # deps, scripts rag-chat/rag-avaliar, pytest (pythonpath=["."])
├── compose.yaml           # Qdrant v1.19.1 em 6335→6333 (não conflita com o MTC na 6333)
├── .env                   # chaves (IGNORADO pelo git)
├── .gitignore             # ver §7 (regras `*.md`, `avaliacao_*.json`, `traducoes_cache.json`…)
├── README.md              # setup + visão geral (único .md versionado)
├── CONTEXTO_SESSAO.md     # diário de decisões/A-B (ignorado pelo git)
├── data/                  # vazio, só .gitkeep (os dados vêm de fora — ver §6)
├── docs/
│   ├── ARQUITETURA.md     # este arquivo (ignorado)
│   └── superpowers/plans/ # planos de implementação (ignorados)
├── tools/
│   └── ts_para_registros.mjs   # Node: avalia os .ts e exporta registros
├── tests/                 # 122 testes; conftest.py (fixtures) + fakes.py (LLMs falsos)
├── qdrant_storage/        # volume do container (IGNORADO)
├── .venv/ .pip-tmp/ __pycache__/ *.egg-info/ .pytest_cache/ .ruff_cache/   # IGNORADOS
└── artefatos na raiz:     # ver §7 — logs, JSONs de avaliação, caches
```

---

## 3. Tabela-mestra de arquivos

| path | Papel | Lê | Escreve | Chamado por |
|---|---|---|---|---|
| `rag_core.py` | core reutilizável (§4) | `../aTormenta/data/*.ts`, Qdrant | coleções Qdrant | `index.py`, `avaliar.py`, `chat_usuario.py`, `probe_rerank_ab.py`, todos os testes |
| `index.py` | chat: 4 etapas, filtros, histórico, memória longa | `rag_core` | `sessoes_campanha` (Qdrant) | usuário / `make chat` / `chat_usuario.py` |
| `avaliar.py` | métricas (cobertura, ground, juiz) + CLI | `goldenset.jsonl`, caches | `avaliacao_<etapa>.json`, `log` (stdout), `juiz_cache.json` | `make avaliar ETAPA=… ARGS=…` |
| `chat_usuario.py` | driver A/B do chat (sessão limpa/paleta 10 s) | `index.processar`, `goldenset.jsonl` | `chat_usuario_{antes,depois}.json` | manual (2× por A/B) |
| `probe_rerank_ab.py` | gate offline da query de rerank | `rag_core.recuperar`, `traducoes_cache.json` | `probe_rerank_ab.json` | manual |
| `goldenset.jsonl` | 61 queries de regressão (uma por linha JSON) | — | — | `avaliar.carregar_goldenset` |
| `tools/ts_para_registros.mjs` | extrai/normaliza exports `.ts` (Node) | `../aTormenta/data/*.ts` | stdout JSON p/ ingestão | `rag_core._extrair_fonte_ts` (836) |
| `tests/conftest.py` | fixtures globais: **monkeypatch dos construtores** de rerank (nada baixa modelo nem bate na API) | — | — | pytest |
| `tests/fakes.py` | `FakeLLM`/respostas prontas compartilhadas | — | — | testes |
| `Makefile` | alvos de dev (§8) | — | — | humano/agente |
| `pyproject.toml` | deps, `py-modules`, scripts, `pythonpath=["."]` | — | — | `pip install -e .` |
| `compose.yaml` | serviço `qdrant` + healthcheck `/readyz` | — | `./qdrant_storage` | `make qdrant-up` |
| `.env` | `OPENROUTER_API_KEY` `COHERE_API_KEY` `QDRANT_URL` `NVIDIA_API_KEY` `GROQ_API_KEY` `VOYAGE_API_KEY` | — | — | carregado por `python-dotenv` |
| `README.md` | setup/uso (único `.md` versionado) | — | — | humano |
| `CONTEXTO_SESSAO.md` | diário de estado, A-B, pendências | — | — | sessões seguintes |
| `docs/superpowers/plans/*.md` | planos de implementação aprovados | — | — | execução de planos |

> **Deriva de doc conhecida:** o `README.md` ainda cita embedding
> `paraphrase-multilingual-MiniLM-L12-v2`; o código usa
> **`intfloat/multilingual-e5-base`** (`rag_core.py:106`). Confiar no código.

---

## 4. `rag_core.py` por zonas (2.186 linhas)

| Zona | Linhas | Conteúdo-chave |
|---|---|---|
| imports + proteção CPU | 1–91 | `OMP/MKL/OPENBLAS_NUM_THREADS=2` **antes** de qualquer import de numpy (exigência do ambiente) |
| constantes | 92–177 | `RAIZ_PROJETO` (92), `PASTA_DADOS=../aTormenta/data` (93), `FERRAMENTA_TS` (94), `CHUNK_SIZE=3500`/`CHUNK_OVERLAP=400` (96–97), `COLECAO="tormenta20"` (99), `COLECAO_HISTORICO="sessoes_campanha"` (102), `PASTA_QDRANT="./qdrant_t20_local"` (103), `MODELO_EMBEDDING="intfloat/multilingual-e5-base"` (106), `MODELO_RERANK="rerank-v3.5"` (107, Cohere), `MODELO_FLASHRANK="ms-marco-MiniLM-L-12-v2"` (111, **inglês**), `MODELOS_NVIDIA/GROQ/OPENROUTER` → `MODELOS_GRATUITOS` (118–142), URLs (144–146), `PROVEDOR_DO_MODELO` (150), `FALHA_TRANSITORIA/DE_MODELO/DE_CREDITO` (157–171) |
| utilitários de diálogo | 179–342 | `e_transitorio`/`e_modelo_indisponivel`/`e_cota_esgotada` (179/184/189) alimentam a cascata; `eh_saudacao_pura` (205); exceções `RecusaTraducao` (212) e `SaidaDegenerada` (216); `reformulacao_valida` (240) e `_e_degenerado` (260) filtram saída do LLM; `_reescrita_utilizavel` (302); `precisa_de_historico` (330) = gate de anáfora do passo [1/4] |
| prompts | 343–462 | `SYSTEM_PROMPT` (343, regra anti-alucinação + citação obrigatória), `PROMPT_TRADUCAO` (374), `PROMPT_REFORMULACAO` (406), `PROMPT_HYDE` (425), `PROMPT_RESUMO_SESSAO` (446) |
| **ingestão** | 463–1232 | mapas de rótulo `Tabela` (466–806), `IGNORAR_CAMPOS` (809), helpers de renderização (816–1040), fatiamento `_dividir`/`_fatiar` (1041/1067), **`montar_chunks()` (1111)** → `list[Document]`, `mesclar_pequenos()` (1188) |
| **Qdrant** | 1233–1377 | `escolher_conexao_qdrant()` (1233, Docker :6335 → embutido local), `obter_embeddings()` (1263, singleton), `reindexar_solicitado()` (1271, flag `REINDEXAR=1`), `garantir_colecao_historico()` (1284), `preparar_colecao()` (1315, cria/ popula) |
| limiar + reranker | 1378–1481 | `_filtrar_fragmentos_preco` (1378), `LIMIARES_PADRAO` (1397: voyage 0,60 / cohere 0,70 / **flashrank 0,35**), `limiar_padrao` (1413), `limiar_relevancia()` (1424, env `LIMIAR_RELEVANCIA`), `_aplicar_limiar` (1440), `limiar_confianca_flashrank` (1453), `reranker_ativo()` (1468, env `RERANK`: auto/flashrank/cohere/desligado) |
| métricas de citação | 1482–1514 | `normalizar` (1482), `citacoes_em` (1488), **`groundedness()` (1493)**, `linha_ground()` (1501, rodapé `ground:` — fonte única p/ chat e avaliador) |
| HyDE | 1515–1576 | `gerar_documento_hipotetico` (1526, cache), `RecuperadorDensoHyDE` (1557) |
| **reranker** | 1577–1688 | `CascataReranker` (1577; `top_n` default 8, `ultimo_modo` registra o que rolou), `criar_reranker()` (1646; `top_n=12`) |
| **retriever** | 1689–1750 | `montar_retriever()`: denso `k=50` (1723), BM25 `k=3` (1728), `EnsembleRetriever` **0,5/0,5** (1732), `ContextualCompressionRetriever(compressor=CascataReranker)` (1745) |
| diversificação + filtros | 1751–1830 | `_diversificar()` (1751, 1 chunk por registro no top), `CHAVES_FILTRO` (1781), `parsear_filtros` (1793), `aplicar_filtros` (1814) |
| **`recuperar()`** | 1831–1916 | entrada única de busca: ensemble `consulta`+`consulta_real` → filtros → **rerank com a query ORIGINAL** (`consulta_rerank = consulta_real`, 1879) → limiar (arg > env > `LIMIARES_PADRAO`) → `_diversificar` → top-8; fallback `ensemble_fallback` se o rerank falhar |
| cadeias | 1917–1950 | `montar_cadeia_resposta` (1917, chat: busca separada da síntese), `montar_rag_chain` (1938, avaliador one-shot) |
| LLM | 1951–2035 | `ChatComFallback` (1951, `MODELOS_GRATUITOS` em cascata), `criar_llm()` (2026), `trocar_modelo()` (2031) |
| reformulação | 2036–2095 | `reformular_pergunta()` (2036), `_formatar_historico` (2078) |
| memória longa | 2096–2186 | `salvar_sessao_campanha()` (2096) → coleção `sessoes_campanha` |

---

## 5. Fluxos

### 5.1 Chat — `index.processar(entrada)` (index.py:245)

| Passo | Função (linha) | O que faz | Sai do fluxo em |
|---|---|---|---|
| atalhos | `eh_relato_sucesso` (88), `eh_saudacao_pura` (`rag_core`:205) | relato de fim de sessão → `salvar_sessao_campanha`; saudação → resposta fixa | sem LLM/busca, **sem** gravar no histórico |
| `[1/4]` | `reformular_pergunta` (`rag_core`:2036) + gate `precisa_de_historico` (330) | reescreve "desse monstro"/"ele" com a janela de histórico | sem anáfora → pula (economiza 1 chamada LLM) |
| `[2/4]` | `traduzir_para_t20` (index:136) | pergunta → termos do sistema via `PROMPT_TRADUCAO`; valida (`RecusaTraducao`) e tenta de novo | inválida/degenerada → usa a pergunta crua |
| `[3/4]` | `buscar()` (index:167) → `rag_core.recuperar()` (1831) | 1 chamada de busca: ensemble → `filtros_ativos` → rerank (query original) → top-8; imprime scores | — |
| `[4/4]` | `gerar_resposta()` (index:182) | `SYSTEM_PROMPT` + `context` já buscado + `{input}` real + histórico; `get_openai_callback` imprime tokens | degenerada → `SaidaDegenerada` → `com_fallback` (105) tenta outro modelo |
| rodapé | `linha_ground` (`rag_core`:1501) | `ground: 89% (8/9 citações no contexto)` ou `n/a` | — |
| comandos | `tratar_filtro` (209), `COMANDOS` (93) | `/filtro tabela=X…`, `/filtro limpar`, `/novo` | estado em `filtros_ativos`/`chat_history` |

### 5.2 Avaliação — `avaliar.main()` (avaliar.py:619)

`criar_parser()` (600) → `avaliar()` (390) por query: `reformular()` (311, cache
`traducoes_cache.json`) → `buscar()` (363, retries 4×) → `responder()` (344, one-shot
`montar_rag_chain`) → `groundedness()` (`rag_core`:1493) → `juizar()` (262, opcional,
cache `juiz_cache.json`) → `gravar()` (537, **JSON a cada query**) → `resumir()` (565).

Flags: `--etapa <nome>` (sufixo do arquivo), `--so-recuperacao`, `--continuar`
(retoma parcial), `--estrategia baseline|hyde`, `--limiar <float>`, `--juiz`.

Fórmulas: **cobertura** = `entidades esperadas presentes / total` no top-8
(comparação `normalizar()` sobre `page_content` + metadata str);
**groundedness** = `citacoes_na_resposta ∩ citacoes_no_contexto / na_resposta`
(`None` = n/a, resposta sem citações).

### 5.3 Medições A/B (2026-10-06)

| Ferramenta | Mede | Saída |
|---|---|---|
| `probe_rerank_ab.py` | cobertura com 3 queries de rerank nos **mesmos** candidatos (combinada/original/reformulada), `RERANK=flashrank`, zero LLM | `probe_rerank_ab.json` + log |
| `chat_usuario.py` | groundedness **no caminho real do usuário** (chama `index.processar`, stdout capturado, sessão limpa por pergunta) | `chat_usuario_{antes,depois}.json` |
| `avaliar.py --etapa fr_l12_qorig --juiz` | série oficial (JSON nomeado por etapa) | `avaliacao_fr_l12_qorig.json` |

Resultado registrado em `CONTEXTO_SESSAO.md`: cobertura 71,9% → 95,9%,
grd 52% → 85%, juiz 6,69 → 7,39.

---

## 6. Infra e configuração

| Item | Detalhe |
|---|---|
| Banco vetorial | Qdrant **:6335** (container `qdrant-t20`; 6333/6334 expostos em 6335/6336), coleção `tormenta20` (5.674 pts) + `sessoes_campanha`. `make qdrant-up/down/status`. Sem Docker → `./qdrant_t20_local` embutido (`escolher_conexao_qdrant`, 1233) |
| Embeddings | `intfloat/multilingual-e5-base`, **local** (sentence-transformers), singleton em `obter_embeddings()` (1263) |
| Dados-fonte | `../aTormenta/data/*.ts` (**externo ao repo**, vindo do projeto irmão) → `tools/ts_para_registros.mjs` → `montar_chunks()`. `data/` aqui é só `.gitkeep` |
| Chunking | `CHUNK_SIZE=3500`, `CHUNK_OVERLAP=400`, prefixo de procedência `[Tabela > Fonte]` obrigatório nas citações |
| LLMs | cascata gratuita `MODELOS_GRATUITOS` = NVIDIA → Groq → OpenRouter (`ChatComFallback`, 1951); classificação de erro por `FALHA_*` (157–171) → retry/fallback/troca de modelo |
| Rerank | env `RERANK` (`auto` default): FlashRank local `ms-marco-MiniLM-L-12-v2` → escalada Cohere `rerank-v3.5` se top-1 < 0,35; falha do Cohere mantém FlashRank |
| `.env` | 6 chaves (§3); **nunca** logar/commitar (`.gitignore`) |
| Proteção CPU | `OMP/MKL/OPENBLAS_NUM_THREADS=2` no topo de `rag_core.py`, `index.py`, `avaliar.py`, `chat_usuario.py`, `probe_rerank_ab.py` (antes do numpy) |

---

## 7. Artefatos, caches e o que o git ignora

| Arquivo | Gerado por | Versionado? | Regra |
|---|---|---|---|
| `avaliacao_<etapa>.json` | `avaliar.py` | **não** | `.gitignore`: `avaliacao_*.json` |
| `traducoes_cache.json` | `avaliar` (reformulações) | **não** | `.gitignore` — **nunca apagar** (mantém o A/B estável;61→62 entradas) |
| `juiz_cache.json` | `avaliar --juiz` | sim (não ignorado) | só **acrescenta** (sha256 do conteúdo) |
| `log_*.txt`, `log_chat_*.txt`, `log_probe_*.txt` | `tee` de cada rodada | sim (não ignorado) | evidência de A/B |
| `chat_usuario_{antes,depois}.json`, `probe_rerank_ab.json` | drivers A/B | sim (não ignorado) | evidência de A/B |
| `docs/*.md`, `CONTEXTO_SESSAO.md` | manual | **não** | `.gitignore`: `*.md` (só `README.md` é exempt) |
| `.env`, `.venv/`, `.pip-tmp/`, `qdrant_storage/`, `qdrant_t20_local/`, `__pycache__/`, `*.egg-info/` | ambiente | não | `.gitignore` |

Baseline de A/B **imutável**: `avaliacao_baseline_fr_l12_ground.json`
(sha256 `f88dff617f…b07275`) — conferir com `sha256sum -c` antes/depois de medições.

---

## 8. Convenções e comandos

```bash
make install | make dev        # .venv + deps / ruff + pytest
make qdrant-up|qdrant-status   # subir/verificar banco
make chat                      # index.py
make avaliar ETAPA=x ARGS="--juiz"   # avaliar.py --etapa x --juiz
make lint && make test         # ruff (6 erros = baseline) + pytest (122)
make check                     # lint + test falha enquanto os 6 do baseline existirem
```

- **TDD**: escrever o teste primeiro (red) → implementar (green) → `make lint`.
  Precedentes: `tests/test_reranker.py`, `test_limiar.py`, `test_hyde.py`.
- **Testes nunca tocam rede/LLM/Qdrant**: `tests/conftest.py` monkeypatcha os
  construtores `FlashrankRerank`/`CohereRerank`; LLMs viram `tests/fakes.py`.
- **Lint baseline = 6 erros** (`avaliar.py:332,525`; `rag_core.py:376,408,1252,2062`)
  — não aumentar; não "consertar" fora do escopo (quebra a comparabilidade).
- **Estado entre sessões**: `CONTEXTO_SESSAO.md` (o que já foi feito/por quê) e
  `docs/superpowers/plans/*.md` (planos aprovados).
- Commits: só quando pedido; mensagens em pt-BR minúsculas, estilo
  `fase 2 e etapa depois: ingestao .ts, suite de avaliacao e correcoes A/B`.

---

## 9. Índice de testes

| Arquivo | L. | Cobre |
|---|---|---|
| `tests/test_ingestao.py` | 114 | rótulos/fatiamento/renderização dos registros `.ts` |
| `tests/test_diversificar.py` | 37 | `_diversificar` (dedup por registro, ordem por score) |
| `tests/test_filtros.py` | 47 | `parsear_filtros`/`aplicar_filtros` (aspas, acento, chave desconhecida) |
| `tests/test_reformulacao.py` | 109 | `reformulacao_valida`, `_reescrita_utilizavel`, `_e_degenerado` (cards/eco/degeneração) |
| `tests/test_ground.py` | 63 | `normalizar`/`citacoes_em`/`groundedness`/`linha_ground` |
| `tests/test_reranker.py` | 277 | `CascataReranker` (limiar/falha Cohere/flags `RERANK`/`top_n`), `recuperar()` incl. **rerank só com a query original** |
| `tests/test_fallback_rerank.py` | 47 | rerank fora → ordem do ensemble, limiar ignorado, `top_n` restaurado |
| `tests/test_hyde.py` | 124 | `gerar_documento_hipotetico`, cache, `RecuperadorDensoHyDE` |
| `tests/test_limiar.py` | 157 | `limiar_relevancia`/`_aplicar_limiar` (env, corte total, sem score) |
| `tests/test_juiz.py` | 134 | `parsear_veredito`, `juizar`, cache do juiz |
| `tests/test_cli.py` | 54 | `criar_parser` (flags/defaults/erro) |
| `tests/test_goldenset.py` | 77 | schema/duplicatas do `goldenset.jsonl`, fallback p/ `CONSULTAS` |
| `tests/test_chat_usuario.py` | 26 | `parsear_ground`, `resolver_caso` (prefixo), amostra de 28 |
| `tests/test_cpu.py` | 55 | variáveis de thread + cap do ONNX Runtime |
| `tests/conftest.py` | 28 | fixtures globais (patch dos construtores de rerank) |
| `tests/fakes.py` | 32 | fakes de LLM |

---

## 10. Onde mexer para…

| Tarefa | Onde |
|---|---|
| Mudar o texto/formato da resposta | `SYSTEM_PROMPT` (`rag_core.py:343`) |
| Mudar a tradução "pergunta → termos do T20" | `PROMPT_TRADUCAO` (374) + `index.traduzir_para_t20` (136) |
| Mudar a busca (k, pesos, rerank, limiar) | `montar_retriever` (1689), `criar_reranker` (1646), `recuperar` (1831), `LIMIARES_PADRAO` (1397) |
| Mudar o chunking/ingestão | `montar_chunks` (1111), `_fatiar` (1067), mapas de rótulo (463–806), `tools/ts_para_registros.mjs` |
| Adicionar/corrigir uma query de regressão | `goldenset.jsonl` + `tests/test_goldenset.py` |
| Nova métrica/flag de avaliação | `avaliar.py` (`avaliar` 390, `criar_parser` 600) |
| Novo comando no chat | `index.py` (`COMANDOS` 93, `processar` 245, `tratar_filtro` 209) |
| Novo LLM/modelo gratuito | `MODELOS_*` (`rag_core`:118–142), `PROVEDOR_DO_MODELO` (150), `FALHA_*` (157–171) |
| Proibir/ajustar citação ausente | `SYSTEM_PROMPT` + `groundedness` (1493) + limite de 60 chars de `PADRAO_CITACAO` (pendência conhecida) |
