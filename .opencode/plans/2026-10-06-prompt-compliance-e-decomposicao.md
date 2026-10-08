# Prompt Compliance + Decomposição de Query — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) reforçar a Regra 2 do `SYSTEM_PROMPT` sem perder as 6 proteções atuais; (2) criar módulo opt-in de decomposição de query que amplia recall com +1 chamada LLM e mantém rerank na query original + síntese única.

**Architecture:** Etapa 1 = mescla de string em `rag_core.SYSTEM_PROMPT` com teste de regressão que pinada proteções novas **e** antigas. Etapa 2 = `decompor_consultas()` (LLM + cache em memória + parser defensivo) chamado por `recuperar(..., decompor=True)`; união de candidatos aproveita o loop de dedup já existente; opt-in por `ESTRATEGIA=decompor` no chat e `--estrategia decompor` no avaliar (default = off, baseline intocada).

**Tech Stack:** Python 3.13, LangChain (`ChatPromptTemplate`), pytest, flashrank/Qdrant/BM25 já existentes.

**Spec:** decisões travadas no brainstorming de 2026-10-06 nesta sessão: (a) Etapa 1 = **mesclar** (manter as 6 proteções atuais + 2 reforços novos); (b) Etapa 2 = **arquitetura C híbrida** (1 chamada LLM → sub-consultas → união → 1 síntese); (c) **opt-in** por flag/env (default baseline); (d) validação **completa com gate barato** (sonda de cobertura offline antes das rodadas com LLM).

## Global Constraints
- `make lint` = **6 erros baseline MTC — não mudar**; `make test` deve sair de 122 e só subir.
- Baseline imutável: `avaliacao_baseline_fr_l12_ground.json` (sha256 `f88dff617fd1ecb971cccfda7b7ea860f9ec8af40f881caba89c78d560b07275`).
- `avaliacao_fr_l12_qorig.json` (cob 95,9% = 56/61, grd média 85,3%, juiz 7,39/84%) é o "antes" da Etapa 1 — não re-rodar baseline.
- `chat_usuario_depois.json` (22/28 com citação, grd 78,6%, HEAD anterior ao prompt novo) é o "antes" do chat da Etapa 1 — não re-rodar.
- Rerank continua **só** com `consulta_real` (`rag_core.py:1879`) — nenhuma etapa mexe nisso.
- Opt-in estrito: default `baseline` = zero chamada extra, zero diff de comportamento.
- `PADRAO_CITACAO` aceita até 60 chars; medido em 2026-10-06: 322 prefixos `[Tabela > Fonte]` no corpus, máx 57 → exigir cópia literal é seguro para a métrica.
- Commits em pt-BR minúsculo sem acento, um por task.
- `*.md` é gitignored (exceto `README.md`): CONTEXTO_SESSAO/docs/ARQUITETURA ficam fora do commit.

## Review Focus
1. **LLM de decompor devolve lixo** (markdown, numeração, eco) → parser limpa e devolve `[]` se sobrar nada: `test_decompor_*` (Task 2).
2. **Edição do prompt remove proteção ou quebra `{context}`** → `tests/test_prompt_compliance.py` pinada 7 trechos + `{context}` + teto de tamanho (Task 1).
3. **Custo/latência em toda pergunta** → default off: `test_recuperar_por_padrao_nao_decompoe` (Task 3), teste de cache (Task 2), `test_avaliar_buscar_nao_decompoe_sem_flag` (Task 4).
4. **Recall piora** (união envenena o rerank) → gate offline de cobertura (Task 5) com critério objetivo.
5. **`ESTRATEGIA` vazando para rodadas baseline** → `avaliar.py` nunca lê env (flag explícita) + teste com env ligada (Task 3).

## File Structure
- **Modify** `rag_core.py`: `SYSTEM_PROMPT` (343–368), `modo_estrategia()` (~1470, perto de `modo_rerank`), `PROMPT_DECOMPOR` (~425, perto de `PROMPT_HYDE`), `decompor_consultas()` (~2036, perto de `reformular_pergunta`), `recuperar()` (1831–1890, antes de `aplicar_filtros`).
- **Modify** `index.py:167-172` (`buscar` → `decompor=`).
- **Modify** `avaliar.py`: `buscar` (:363), `avaliar()` (:395-435), parser `--estrategia` (:607).
- **Create** `tests/test_prompt_compliance.py`, `tests/test_decompor.py`.
- **Modify** `tests/test_cli.py` (aceita `decompor`).
- **Artefatos de execução:** `log_decompor_gate.txt`, `avaliacao_decompor_so.json`, `avaliacao_prompt_cit.json`, `chat_usuario_prompt_depois.json`, `log_avaliar_prompt_cit.txt`, `avaliacao_decompor.json`, `chat_usuario_decompor.json`, `log_avaliar_decompor.txt`.

---

### Task 1: SYSTEM_PROMPT mesclado (Etapa 1)

**Files:**
- Modify: `rag_core.py:343-368`
- Test: `tests/test_prompt_compliance.py` (criar)

**Interfaces:**
- Consumes: `SYSTEM_PROMPT` atual (6 proteções).
- Produces: `SYSTEM_PROMPT` final consumido por `index.py:60` e `avaliar.py:419` — nenhum chamador muda.

- [ ] **Step 1: escrever o teste falhando**

```python
# tests/test_prompt_compliance.py
from rag_core import SYSTEM_PROMPT

PROTECOES = (
    "declare que a base não cobre o ponto",
    "PROIBIÇÃO DE EXTRAPOLAÇÃO NUMÉRICA",
    "NUNCA agrupe citações apenas no final do texto",
    "declare isso imediatamente",
    "'N colunas' significa SEMPRE uma tabela Markdown",
    "NUNCA pode inventar regras mecânicas",
    "IDIOMA OBRIGATÓRIO",
)

REFORCOS = (
    "É PROIBIDO gerar respostas afirmativas sem citações anexadas",
    "[Caminho > Fonte]",
)


def test_prompt_mantem_as_seis_protecoes():
    for trecho in PROTECOES:
        assert trecho in SYSTEM_PROMPT, f"proteção perdida: {trecho!r}"


def test_prompt_inclui_reforcos_da_regra_2():
    for trecho in REFORCOS:
        assert trecho in SYSTEM_PROMPT, f"reforço ausente: {trecho!r}"


def test_prompt_preserva_placeholder_e_tamanho():
    assert "{context}" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) < 4000
```

- [ ] **Step 2: rodar esperando falha**

Run: `pytest tests/test_prompt_compliance.py -v`
Expected: 3 coletados, **2 FAILED** (só os reforços ausentes).

- [ ] **Step 3: trocar a constante** em `rag_core.py:343` pelo texto abaixo:

```python
SYSTEM_PROMPT = (
    "Você é um Arquivista Técnico e Mestre de Regras de Tormenta 20 (T20). "
    "Sua função é consultar o contexto fornecido e responder dúvidas de regras com absoluta precisão.\n\n"
    "IDIOMA OBRIGATÓRIO: Responda SEMPRE em português do Brasil (pt-BR) — é proibido "
    "usar inglês ou misturar idiomas em qualquer parte da resposta.\n\n"
    "1. **Fidelidade Estrita ao Contexto (REGRA INVIOLÁVEL):**\n"
    "   - Responda EXCLUSIVAMENTE com base nas informações literalmente presentes no {context}.\n"
    "   - É PROIBIDO utilizar conhecimento prévio, memória externa, deduções mecânicas, analogias ou "
    "completar regras omitidas. Se um valor, taxa, PV, PM, CD ou regra não está no contexto, declare "
    "que a base não cobre o ponto.\n"
    "   - PROIBIÇÃO DE EXTRAPOLAÇÃO NUMÉRICA: NUNCA crie sequências ou progressões de valores (ex: preços, "
    "dano por nível) que não estejam explicitamente escritas.\n\n"
    "2. **Citação Obrigatória por Item/Linha (REGRA ABSOLUTA):**\n"
    "   - Sempre que utilizar informação do contexto, É OBRIGATÓRIO citar a fonte no final da frase ou do item.\n"
    "   - Cite no formato exato [Caminho > Fonte], copiando os dois trechos literalmente do contexto, "
    "por exemplo: [Alquímicos > Tormenta20 - Jogo do Ano].\n"
    "   - NUNCA altere, resuma, abrevie ou invente o nome ou caminho da fonte. Você deve copiar EXATAMENTE a string fornecida no contexto.\n"
    "   - É PROIBIDO gerar respostas afirmativas sem citações anexadas: toda frase que afirma uma regra, "
    "valor ou preço termina com a citação da fonte usada.\n"
    "   - Exemplo correto:\n"
    "     - Essência de Mana: recupera 1d4 PM. Preço: T$ 50. [Alquímicos > Tormenta20 - Jogo do Ano]\n"
    "   - NUNCA agrupe citações apenas no final do texto. Cada fato deve ter sua própria citação grudada a ele.\n"
    "   - Se não houver contexto útil para a dúvida, declare isso imediatamente e responda sem inventar regras ou citações falsas.\n\n"
    "3. **Respeito Estrito ao Formato Solicitado:**\n"
    "   - Se o usuário pedir um formato específico (ex: 'apenas tabela', '3 colunas', 'sem explicações'), "
    "entregue EXCLUSIVAMENTE o formato pedido.\n"
    "   - 'N colunas' significa SEMPRE uma tabela Markdown com exatamente N colunas e cabeçalhos nomeados.\n\n"
    "4. **Aconselhamento do Mestre (Única Exceção de Opinião):**\n"
    "   - Ao responder situações táticas ou dúvidas de construção de personagem, apresente primeiro a regra "
    "exata extraída do contexto com citação.\n"
    "   - Se relevante, adicione ao final um bloco destacado `**Sugestão do Mestre:**` oferecendo orientação tática. "
    "Esta sugestão NUNCA pode inventar regras mecânicas ou alterar valores do contexto.\n\n"
    "Contexto Técnico de Tormenta 20:\n{context}"
)
```

- [ ] **Step 4: rodar esperando passar**

Run: `pytest tests/test_prompt_compliance.py -v`
Expected: **3 PASS**

- [ ] **Step 5: suíte + lint**

Run: `make test` e `make lint`
Expected: 126 passed (122 + 4); lint **6** intocado.

- [ ] **Step 6: commit**

```bash
git add rag_core.py tests/test_prompt_compliance.py
git commit -m "reforca regra 2 de citacao no system prompt"
```

---

### Task 2: `modo_estrategia` + `PROMPT_DECOMPOR` + `decompor_consultas`

**Files:**
- Modify: `rag_core.py` (~1470, ~425, ~2036)
- Test: `tests/test_decompor.py` (criar)

**Interfaces:**
- Consumes: `criar_llm()` (`rag_core.py:2026`), `ChatPromptTemplate`, `re`, `os` (todos já importados).
- Produces: `modo_estrategia() -> str`; `decompor_consultas(consulta: str, llm=None) -> list[str]`; `PROMPT_DECOMPOR`; `_CACHE_DECOMPOR`; `LIMITE_VARIANTES`; `_variantes_utilizaveis(bruto, consulta) -> list[str]`. Task 3 consome `decompor_consultas`; Task 4 consome `modo_estrategia` e `decompor_consultas`.

- [ ] **Step 1: escrever os testes falhando**

```python
# tests/test_decompor.py
import rag_core


def test_modo_estrategia_padrao_e_baseline(monkeypatch):
    monkeypatch.delenv("ESTRATEGIA", raising=False)
    assert rag_core.modo_estrategia() == "baseline"


def test_modo_estrategia_lê_env_valida(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    assert rag_core.modo_estrategia() == "decompor"


def test_modo_estrategia_ignora_lixo(monkeypatch):
    monkeypatch.setenv("ESTRATEGIA", "banana")
    assert rag_core.modo_estrategia() == "baseline"


class _LlmFalso:
    def __init__(self, texto, falha=False):
        self.texto, self.falha, self.n = texto, falha, 0

    def __ror__(self, other):  # cadeia = PROMPT | llm
        return self

    def invoke(self, payload):
        self.n += 1
        if self.falha:
            raise RuntimeError("cota")
        return type("M", (), {"content": self.texto})()


def test_decompor_limpa_marcadores_e_limita_a_3():
    llm = _LlmFalso(
        "1. como funciona armadura pesada\n"
        "- qual a penalidade de armadura\n"
        "* armadura pesada\n"
        "penalidade de armadura; vestir armadura pesada\n"
        "uma linha a mais para estourar o limite\n"
    )
    var = rag_core.decompor_consultas("como funciona armadura pesada", llm=llm)
    assert var == [
        "qual a penalidade de armadura",
        "armadura pesada",
        "penalidade de armadura; vestir armadura pesada",
    ]


def test_decompor_falha_devolve_vazio():
    var = rag_core.decompor_consultas("x" * 40, llm=_LlmFalso("", falha=True))
    assert var == []


def test_decompor_cacheia_por_query():
    llm = _LlmFalso("uma outra forma de perguntar\ndois termos aqui\ntres sub questoes")
    q = "quantos pv tem um ogro"
    rag_core.decompor_consultas(q, llm=llm)
    rag_core.decompor_consultas(q, llm=llm)
    assert llm.n == 1
```

- [ ] **Step 2: rodar esperando falha**

Run: `pytest tests/test_decompor.py -v`
Expected: FAIL — `AttributeError: module 'rag_core' has no attribute 'modo_estrategia'`.

- [ ] **Step 3: implementar (3 blocos)**

```python
# após modo_rerank (rag_core.py ~1470)
def modo_estrategia() -> str:
    """'baseline' (default), 'hyde' ou 'decompor' — opt-in pela env ESTRATEGIA."""
    valor = os.environ.get("ESTRATEGIA", "").strip().lower()
    return valor if valor in {"baseline", "hyde", "decompor"} else "baseline"
```

```python
# ao lado de PROMPT_HYDE (rag_core.py ~425)
PROMPT_DECOMPOR = ChatPromptTemplate.from_messages([
    ("system",
     "Você gera consultas de busca para uma base técnica de Tormenta 20. "
     "Responda APENAS com 3 linhas de texto puro, sem markdown, sem numeração "
     "e sem aspas, cada uma uma forma diferente de perguntar o mesmo assunto: "
     "1) outra redação da pergunta; 2) termos técnicos alternativos "
     "(sinônimos do sistema, ex.: PV/pontos de vida, CD/dificuldade); "
     "3) a pergunta quebrada em sub-questões separadas por ponto e vírgula. "
     "Não responda a pergunta."),
    ("human", "{pergunta}"),
])
```

```python
# ao lado de reformular_pergunta (rag_core.py ~2036)
_CACHE_DECOMPOR: dict[str, list[str]] = {}
LIMITE_VARIANTES = 3


def _variantes_utilizaveis(bruto: str, consulta: str) -> list[str]:
    saida: list[str] = []
    vistos = {consulta.strip().lower()}
    for linha in bruto.splitlines():
        limpa = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", linha).strip().strip('"“”')
        if len(limpa) < 8 or limpa.lower() in vistos:
            continue
        vistos.add(limpa.lower())
        saida.append(limpa)
        if len(saida) >= LIMITE_VARIANTES:
            break
    return saida


def decompor_consultas(consulta: str, llm=None) -> list[str]:
    """3 variações da query para ampliar recall; `[]` em qualquer falha.

    Opt-in: só é chamada quando quem recupera recebe `decompor=True`.
    Falha (cota, saída vazia, lixo) devolve [] — a busca segue com as
    formulações de sempre, nunca piora por causa da decomposição.
    """
    consulta = consulta.strip()
    if not consulta:
        return []
    if consulta in _CACHE_DECOMPOR:
        return list(_CACHE_DECOMPOR[consulta])
    try:
        cadeia = PROMPT_DECOMPOR | (llm or criar_llm())
        bruto = cadeia.invoke({"pergunta": consulta}).content
        if not isinstance(bruto, str) or not bruto.strip():
            raise ValueError("saída vazia")
        variantes = _variantes_utilizaveis(bruto, consulta)
    except Exception:
        variantes = []
    _CACHE_DECOMPOR[consulta] = variantes
    return list(variantes)
```

- [ ] **Step 4: rodar esperando passar**

Run: `pytest tests/test_decompor.py -v`
Expected: **6 PASS**

- [ ] **Step 5: suíte + lint**

Run: `make test` e `make lint`
Expected: 132 passed; lint 6.

- [ ] **Step 6: commit**

```bash
git add rag_core.py tests/test_decompor.py
git commit -m "adiciona decompor_consultas com cache e guarda de falha"
```

---

### Task 3: `recuperar(..., decompor=False)` une as variantes

**Files:**
- Modify: `rag_core.py:1831-1890`
- Test: `tests/test_decompor.py` (adicionar)

**Interfaces:**
- Consumes: `decompor_consultas()` (Task 2); contrato real de `CascataReranker` (`rag_core.py` — conferir assinaturas antes de escrever o falso).
- Produces: `recuperar(retriever, consulta, consulta_real=None, filtros=None, limiar=None, decompor: bool = False) -> list[Document]` — Task 4 passa `decompor=`.

- [ ] **Step 1: escrever o teste falhando**

```python
# em tests/test_decompor.py
from langchain_core.documents import Document


def _doc(chave, corpo):
    return Document(page_content=corpo, metadata={"chave": chave})


class _BuscaFalsa:
    def __init__(self):
        self.consultas = []

    def invoke(self, query):
        self.consultas.append(query)
        if query == "consulta real":
            return [_doc("real", "corpo real")]
        if query == "variante inutil":
            return [_doc("extra", "corpo da variante")]
        return []


class _RerankFalso:
    """Espelha o contrato de CascataReranker — conferir antes de rodar."""

    def __init__(self, base):
        self.base_retriever = base

    @property
    def ultimo_modo(self):
        return "flashrank"


def test_recuperar_com_decompor_reune_variantes(monkeypatch):
    base = _BuscaFalsa()
    monkeypatch.setattr(
        rag_core, "decompor_consultas", lambda q, llm=None: ["variante inutil"]
    )
    docs = rag_core.recuperar(
        _RerankFalso(base), "consulta reformulada", "consulta real", decompor=True
    )
    assert {d.page_content for d in docs} == {"corpo real", "corpo da variante"}
    assert base.consultas == [
        "consulta reformulada", "consulta real", "variante inutil",
    ]  # rerank recebeu `consulta real` — a query original


def test_recuperar_por_padrao_nao_decompoe(monkeypatch):
    def _explode(q, llm=None):
        raise AssertionError("decompor não pode rodar por padrão")

    monkeypatch.setattr(rag_core, "decompor_consultas", _explode)
    monkeypatch.setenv("ESTRATEGIA", "decompor")  # env ligada não muda o default
    base = _BuscaFalsa()
    docs = rag_core.recuperar(
        _RerankFalso(base), "consulta reformulada", "consulta real"
    )
    assert base.consultas == ["consulta reformulada", "consulta real"]
    assert {d.page_content for d in docs} == {"corpo real"}
```

- [ ] **Step 2: rodar esperando falha**

Run: `pytest tests/test_decompor.py -v`
Expected: FAIL — `TypeError: recuperar() got an unexpected keyword argument 'decompor'` (2 novos).

- [ ] **Step 3: implementar**

Novo parâmetro na assinatura + bloco **depois** do bloco `consulta_real` e **antes** de `aplicar_filtros`:

```python
    if decompor and consulta_rerank.strip():
        vistos = {d.page_content for d in docs}
        for variante in decompor_consultas(consulta_rerank):
            for extra in retriever.base_retriever.invoke(variante):
                if extra.page_content not in vistos:
                    vistos.add(extra.page_content)
                    docs.append(extra)
```

Docstring: "`decompor=True` (opt-in, `ESTRATEGIA=decompor`) gera 3 variações da query original e entra na união dos candidatos; o **rerank continua só com a query original**; falha da decomposição vira busca normal."

- [ ] **Step 4: rodar esperando passar**

Run: `pytest tests/test_decompor.py -v`
Expected: **8 PASS**

- [ ] **Step 5: suíte + lint**

Run: `make test` e `make lint`
Expected: 134 passed; lint 6.

- [ ] **Step 6: commit**

```bash
git add rag_core.py tests/test_decompor.py
git commit -m "recupera variantes extras no modo decompor"
```

---

### Task 4: opt-in nos dois pontos de entrada

**Files:**
- Modify: `index.py:167-172`
- Modify: `avaliar.py:363-371`, `avaliar.py:395-435`, `avaliar.py:607-609`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `recuperar(..., decompor=)` (Task 3), `modo_estrategia()`/`decompor_consultas()` (Task 2), fakes `_RerankFalso`/`_BuscaFalsa` de `tests/test_decompor.py`.
- Produz: contrato `ESTRATEGIA=decompor` (chat) e `--estrategia decompor` (avaliar) usados pelas Tasks 6–7.

- [ ] **Step 1: escrever o teste falhando** (em `tests/test_cli.py`)

```python
def test_parser_aceita_estrategia_decompor():
    from avaliar import criar_parser
    args = criar_parser().parse_args(
        ["--etapa", "decompor", "--estrategia", "decompor"]
    )
    assert args.estrategia == "decompor"


def test_avaliar_buscar_nao_decompoe_sem_flag(monkeypatch):
    import rag_core
    from avaliar import buscar
    from tests.test_decompor import _BuscaFalsa, _RerankFalso

    def _explode(q, llm=None):
        raise AssertionError("avaliar baseline não pode decompôr")

    monkeypatch.setattr(rag_core, "decompor_consultas", _explode)
    monkeypatch.setenv("ESTRATEGIA", "decompor")
    buscar(_RerankFalsa(_BuscaFalsa()), "consulta reformulada", "consulta real")
```

- [ ] **Step 2: rodar esperando falha**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ValueError: argument --estrategia: invalid choice: 'decompor'`.

- [ ] **Step 3: implementar (3 mudanças)**

```python
# index.py:167
docs = rag_core.recuperar(
    retriever_comprimido, pergunta_t20, pergunta_real, filtros=filtros_ativos,
    decompor=rag_core.modo_estrategia() == "decompor",
)
```

```python
# avaliar.py:363
def buscar(retriever, consulta: str, consulta_real: str | None = None,
           limiar: float | None = None, decompor: bool = False):
    """Top-8: candidatos das duas formulações, rerank com a query original."""
    for i in range(4):
        try:
            return rag_core.recuperar(retriever, consulta, consulta_real,
                                      limiar=limiar, decompor=decompor)
        ...
```

```python
# avaliar.py — chamada em ~435 e registro em ~500
top = buscar(retriever, reformulada, caso["consulta"], limiar=limiar,
             decompor=estrategia == "decompor")
...
if estrategia == "decompor":
    registro["variantes"] = rag_core.decompor_consultas(caso["consulta"])
```

```python
# avaliar.py:607
ap.add_argument("--estrategia", choices=("baseline", "hyde", "decompor"),
                default="baseline",
                help="estratégia de recuperação: baseline, hyde ou "
                     "decompor (3 variações da query por LLM, opt-in)")
```

(`avaliar.py:413` já mapeia tudo que não é `hyde` para `hibrida` → `decompor` usa o retriever normal, correto por construção.)

- [ ] **Step 4: rodar esperando passar**

Run: `pytest tests/test_cli.py tests/test_decompor.py -v`
Expected: **10 PASS**

- [ ] **Step 5: suíte + lint**

Run: `make test` e `make lint`
Expected: 136 passed; lint 6.

- [ ] **Step 6: commit**

```bash
git add index.py avaliar.py tests/test_cli.py
git commit -m "liga decompor opt-in em chat e avaliar"
```

---

### Task 5: gate barato (cobertura offline)

**Files:**
- Create: `log_decompor_gate.txt`, `avaliacao_decompor_so.json`

**Interfaces:**
- Consumes: `--estrategia decompor` (Task 4); baseline `avaliacao_fr_l12_qorig.json`.
- Produz: veredito que autoriza (ou não) a Task 7.

- [ ] **Step 1: rodar o gate** (~12 min, sem LLM final)

```bash
.venv/bin/python avaliar.py --etapa decompor_so --so-recuperacao --estrategia decompor | tee log_decompor_gate.txt
```

- [ ] **Step 2: comparar com a baseline de cobertura**

Ler `avaliacao_fr_l12_qorig.json`: cobertura 56/61 = 95,9%; queries a 50% = `28, 30, 32, 35, 53`.
Critério de passagem (os dois): cob ≥ 95% **e** ≥ 2 das 5 a 50% sobem.

- [ ] **Step 3: se falhar** — ajustar `PROMPT_DECOMPOR` (Task 2) e re-rodar o gate antes de qualquer rodada com LLM; se passar, seguir.

- [ ] **Step 4: commit**

```bash
git add log_decompor_gate.txt avaliacao_decompor_so.json
git commit -m "gate de cobertura do modo decompor"
```

---

### Task 6: validação Etapa 1 (prompt mesclado)

**Files:**
- Create: `avaliacao_prompt_cit.json`, `chat_usuario_prompt_depois.json`, `log_avaliar_prompt_cit.txt`

**Interfaces:**
- Consumes: Task 1; baselines já existentes `avaliacao_fr_l12_qorig.json` e `chat_usuario_depois.json`.
- Produz: métricas da Etapa 1 (n/a, cob, grd, juiz) p/ CONTEXTO e p/ A/B da Task 7.

- [ ] **Step 1: avaliar com o prompt novo** (~75 min)

```bash
.venv/bin/python avaliar.py --etapa prompt_cit --juiz | tee log_avaliar_prompt_cit.txt
```

- [ ] **Step 2: comparar com `avaliacao_fr_l12_qorig.json`**

Alvo: `n/a` cai de 10; cob ≥ 95%; grd média ≥ 80% (base 85,3%); juiz ≥ 7,0 (base 7,39).

- [ ] **Step 3: chat com o prompt novo** (~15 min)

```bash
.venv/bin/python chat_usuario.py --saida chat_usuario_prompt_depois.json --pausa 10
```

- [ ] **Step 4: comparar com `chat_usuario_depois.json`**

Alvo: ≥ 24/28 com citação (base 22) e grd ≥ 78% (base 78,6%).

- [ ] **Step 5: commit**

```bash
git add avaliacao_prompt_cit.json chat_usuario_prompt_depois.json log_avaliar_prompt_cit.txt
git commit -m "valida prompt de citacao: n/a, cobertura, grd e juiz"
```

---

### Task 7: validação Etapa 2 (decompor ponta a ponta)

**Files:**
- Create: `avaliacao_decompor.json`, `chat_usuario_decompor.json`, `log_avaliar_decompor.txt`

**Interfaces:**
- Consumes: Task 4 (estratégia), Task 5 (gate aprovado), baseline da Etapa 1 = `avaliacao_prompt_cit.json` + `chat_usuario_prompt_depois.json` (mesma prompt dos dois lados).
- Produz: métricas da Etapa 2 p/ CONTEXTO.

- [ ] **Step 1: avaliar com estratégia** (~75 min)

```bash
.venv/bin/python avaliar.py --etapa decompor --juiz --estrategia decompor | tee log_avaliar_decompor.txt
```

- [ ] **Step 2: comparar com `avaliacao_prompt_cit.json`**

Alvo: cob ≥ base; grd ≥ base − 1 p.p.; juiz ≥ base − 0,2. Conferir `registro["variantes"]`.

- [ ] **Step 3: chat com a env** (~15 min)

```bash
ESTRATEGIA=decompor .venv/bin/python chat_usuario.py --saida chat_usuario_decompor.json --pausa 12
```

- [ ] **Step 4: comparar com `chat_usuario_prompt_depois.json`**

Alvo: citações ≥ base, grd ≥ base; latência média por turno anotada no log (+1 chamada LLM esperada).

- [ ] **Step 5: commit**

```bash
git add avaliacao_decompor.json chat_usuario_decompor.json log_avaliar_decompor.txt
git commit -m "valida modo decompor: cobertura, grd, juiz e chat"
```

---

### Task 8: docs e fechamento

**Files:**
- Modify: `CONTEXTO_SESSAO.md`, `docs/ARQUITETURA.md`, `README.md`

- [ ] **Step 1: `CONTEXTO_SESSAO.md`** — seção "Prompt compliance + decomposição de query (2026-10-06)": decisões, gate, números das Tasks 5–7, comandos.
- [ ] **Step 2: `docs/ARQUITETURA.md`** — item em "Onde mexer para…": "ampliar recall sem tocar no rerank → `decompor_consultas()` + `recuperar(decompor=True)`" (números de linha por grep).
- [ ] **Step 3: `README.md`** — `--estrategia decompor` nas etapas + linha de `ESTRATEGIA=decompor` no chat.
- [ ] **Step 4: verificação final**

Run: `make test` e `make lint`
Expected: 136 passed; lint 6; `git log --oneline -8` com os commits das tasks.

- [ ] **Step 5: commit**

```bash
git add README.md
git commit -m "documenta modo decompor no readme"
```
