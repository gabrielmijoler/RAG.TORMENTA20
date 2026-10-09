"""Dicionário de nomes do corpus: `nome normalizado -> registros`.

Construído dos mesmos registros da ingestão (formato de
`rag_core._extrair_fonte_ts`), com os mesmos rótulos de Tabela, Fonte e Nome
da metadata dos chunks. Não toca o Qdrant nem LLM.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

import rag_core

from .tipos import Chave

# Tabela onde o "Nome" é a pergunta inteira de um leitor: não é nome do jogo.
TABELAS_IGNORADAS = frozenset({"Regreiro (Perguntas e Respostas)"})

# Ordem de prioridade das fontes (decisão do usuário), em grafia normalizada.
PRIORIDADE_FONTES = (
    "tormenta20 - jogo do ano",
    "herois de arton",
    "ameacas de arton",
    "deuses de arton",
    "compendio t20",
    "guia dos deuses menores",
)

MAX_PALAVRAS = 5
# Uma palavra que aparece no texto do corpus pelo menos este número de vezes é
# uma palavra real, não erro de digitação (typos reais aparecem 0 vezes).
VOCAB_MIN_OCORRENCIAS = 3

_RE_PALAVRA = re.compile(r"[a-z0-9]+")
_RE_PARENTESE = re.compile(r"\s*\([^)]*\)\s*")
_RE_DB = re.compile(r"^db\b")


def chave_texto(texto: str) -> str:
    """Forma de comparação: minúsculas, sem acento, só palavras separadas por espaço."""
    return " ".join(_RE_PALAVRA.findall(rag_core.normalizar(texto)))


def _singular_palavra(palavra: str) -> str:
    if len(palavra) > 4 and palavra.endswith("oes"):
        return palavra[:-3] + "ao"
    if len(palavra) > 4 and palavra.endswith("es") and palavra[-3] in "rzs":
        return palavra[:-2]
    if len(palavra) > 3 and palavra.endswith("s") and not palavra.endswith("ss"):
        return palavra[:-1]
    return palavra


def singular(frase_normalizada: str) -> str:
    """Plural simples: tira o plural de cada palavra ('barbaros' -> 'barbaro')."""
    return " ".join(_singular_palavra(p) for p in frase_normalizada.split())


def normalizar_fonte(fonte: str) -> str:
    """Junta grafias da mesma Fonte ('DB - 228' == 'Dragão Brasil - 228')."""
    texto = " ".join(_RE_PALAVRA.findall(rag_core.normalizar(fonte)))
    texto = texto.replace("guia de deuses menores", "guia dos deuses menores")
    texto = _RE_DB.sub("dragao brasil", texto)
    # volta o hífen que a tokenização removeu: "x - y" só existia em fontes com número
    return re.sub(r"^(tormenta20) jogo do ano$", r"\1 - jogo do ano", texto)


def prioridade_fonte(fonte: str) -> int:
    """0 = mais prioritária; fontes fora da lista ficam depois de todas."""
    norma = normalizar_fonte(fonte)
    for i, prioritaria in enumerate(PRIORIDADE_FONTES):
        if norma == normalizar_fonte(prioritaria):
            return i
    return len(PRIORIDADE_FONTES)


@dataclass
class Dicionario:
    exatos: dict[str, tuple[Chave, ...]] = field(default_factory=dict)
    apelidos: dict[str, tuple[Chave, ...]] = field(default_factory=dict)
    max_palavras: int = 1
    tabelas: frozenset[str] = frozenset()
    vocabulario: frozenset[str] = frozenset()
    _por_palavras: dict[int, tuple[str, ...]] = field(default_factory=dict, repr=False)

    def exato(self, frase: str) -> tuple[Chave, ...]:
        chave = chave_texto(frase)
        return self.exatos.get(chave) or self.exatos.get(singular(chave)) or ()

    def apelido(self, frase: str) -> tuple[Chave, ...]:
        chave = chave_texto(frase)
        return self.apelidos.get(chave) or self.apelidos.get(singular(chave)) or ()

    def nomes_com_palavras(self, n: int) -> tuple[str, ...]:
        """Nomes normalizados com exatamente `n` palavras (base da ligação aproximada)."""
        if not self._por_palavras:
            grupos: dict[int, list[str]] = {}
            for nome in self.exatos:
                grupos.setdefault(len(nome.split()), []).append(nome)
            self._por_palavras.update({k: tuple(v) for k, v in grupos.items()})
        return self._por_palavras.get(n, ())


def _adicionar(indice: dict[str, list[Chave]], nome: str, chave: Chave) -> None:
    for forma in {chave_texto(nome), singular(chave_texto(nome))}:
        if forma and chave not in indice.setdefault(forma, []):
            indice[forma].append(chave)


def _subnomes(habilidades) -> list[str]:
    """Nomes das habilidades e, dentro delas, das `subAbilities` (ex.: Arcanista >
    Caminho do Arcanista > Feiticeiro)."""
    nomes: list[str] = []
    if not isinstance(habilidades, list):
        return nomes
    for hab in habilidades:
        if not isinstance(hab, dict):
            continue
        nome = hab.get("name")
        if isinstance(nome, str) and nome.strip():
            nomes.append(nome)
        nomes.extend(_subnomes(hab.get("subAbilities")))
    return nomes


def _textos(valor):
    """Todas as strings (recursivamente) de um registro."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, list):
        for item in valor:
            yield from _textos(item)
    elif isinstance(valor, dict):
        for item in valor.values():
            yield from _textos(item)


def _ordenar(chaves: list[Chave]) -> tuple[Chave, ...]:
    return tuple(sorted(chaves, key=lambda c: prioridade_fonte(c.fonte)))


def construir(dados: dict, apelidos: dict[str, Chave] | None = None) -> Dicionario:
    """Monta o dicionário a partir dos registros crus da extração."""
    indice: dict[str, list[Chave]] = {}
    tabelas: set[str] = set()
    palavras: Counter = Counter()
    for bloco in dados["tabelas"]:
        tabela = rag_core._rotulo_tabela(bloco["arquivo"], bloco["export"])
        tabelas.add(tabela)
        if tabela in TABELAS_IGNORADAS:
            continue
        for reg in bloco["elementos"]:
            palavras.update(_RE_PALAVRA.findall(
                rag_core.normalizar(" ".join(_textos(reg)))))
            nome = rag_core._nome_do_registro(reg)
            if not nome:
                continue
            fonte = rag_core._fonte_do_registro(reg)
            chave = Chave(tabela, nome, fonte)
            _adicionar(indice, nome, chave)
            sem_parentese = _RE_PARENTESE.sub(" ", nome).strip()
            if sem_parentese and sem_parentese != nome:
                _adicionar(indice, sem_parentese, chave)
            for sub in _subnomes(reg.get("abilities")):
                _adicionar(indice, sub, Chave(tabela, nome, fonte, sub))

    dic_apelidos: dict[str, tuple[Chave, ...]] = {}
    for apelido, chave in (apelidos or {}).items():
        dic_apelidos[chave_texto(apelido)] = (chave,)

    exatos = {k: _ordenar(v) for k, v in indice.items()}
    todas = list(exatos) + list(dic_apelidos)
    maior = max((len(k.split()) for k in todas), default=1)
    return Dicionario(exatos=exatos, apelidos=dic_apelidos,
                      max_palavras=min(maior, MAX_PALAVRAS),
                      tabelas=frozenset(tabelas),
                      vocabulario=frozenset(p for p, n in palavras.items()
                                            if n >= VOCAB_MIN_OCORRENCIAS))


def do_corpus(apelidos: dict[str, Chave] | None = None) -> Dicionario:
    """Dicionário dos registros reais (roda o extrator Node da ingestão, ~1 s).

    Sem `apelidos`, carrega os APROVADOS de conhecimento/apelidos.yaml.
    """
    if apelidos is None:
        # import tardio: conhecimento importa este módulo
        from .conhecimento import apelidos_ativos
        apelidos = apelidos_ativos()
    return construir(rag_core._extrair_fonte_ts(verbose=False), apelidos=apelidos)
