"""Ligador: acha na pergunta os nomes do jogo e diz a que registro cada um aponta.

Duas passadas sobre janelas de 1 a N palavras (da maior para a menor):
1. exata: nome do dicionário ou apelido aprovado;
2. aproximada (`difflib`), só nas palavras que a 1ª passada não usou, sem
   atravessar pontuação e sem palavra comum ou de categoria na janela.
Cada palavra da pergunta entra em no máximo uma ligação.

Empates (o mesmo nome em mais de um registro) seguem a política fixada:
pista de tabela na pergunta → restrição já ligada (`refinar_por_restricoes`)
→ prioridade de fonte (o dicionário já devolve as chaves nessa ordem) →
se nada desempata, a ligação fica ambígua e guarda as alternativas.
Tabelas de categoria ("Categorias de Poder") perdem para a entidade.
"""

import re
from difflib import SequenceMatcher

import rag_core

from .dicionario import Dicionario, chave_texto, singular
from .tipos import Chave, Ligacao, Restricoes

# Limiares iniciais (decisão do Ponto 1), a calibrar com o conjunto rotulado.
LIMIAR_VARIAS_PALAVRAS = 0.80
LIMIAR_UMA_PALAVRA = 0.90
MIN_LETRAS_UMA_PALAVRA = 6
# Diferença de score abaixo da qual dois nomes aproximados contam como empate.
MARGEM_EMPATE = 0.02
# Distância (em palavras) em que uma pista de tabela vale para um trecho.
ALCANCE_PISTA = 3

PALAVRAS_VAZIAS = frozenset([
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das",
    "dos", "e", "em", "no", "na", "nos", "nas", "que", "se", "com", "por", "para",
    "pra", "pro", "ao", "aos", "sou", "eu", "meu", "minha", "qual", "quais",
    "como", "quanto", "ou", "isso", "esse", "essa", "este", "esta", "ele", "ela",
    # referências: apontam para algo já dito e nunca fazem parte de um nome
    "eles", "elas", "dele", "dela", "deles", "delas", "nele", "nela", "neles", "nelas",
    "desse", "dessa", "desses", "dessas", "nesse", "nessa", "deste", "desta", "disso",
    "nisso", "disto", "isto", "aquele", "aquela", "mesmo", "mesma", "comigo",
])

# Nomes do jogo que também são palavras comuns: só ligam por nome exato
# e com uma pista da tabela por perto.
PALAVRAS_COMUNS = frozenset([
    "cura", "grande", "acido", "forca", "luta", "medo", "fogo", "gelo", "luz",
    "sorte", "morte", "terra", "agua", "vento", "corte", "golpe", "escudo",
    "grito", "sono", "dano", "defesa", "ataque", "teste", "alcance", "tamanho",
    "nivel", "mestre", "grupo", "arma", "armas", "veneno", "fome", "sede",
])

# palavra normalizada (singular) -> predicado sobre o rótulo da Tabela
_PISTAS = {
    "magia": lambda t: t == "Magias",
    "condicao": lambda t: t == "Condições",
    "pericia": lambda t: t == "Perícias",
    "poder": lambda t: t.startswith("Poderes"),
    "arma": lambda t: t.startswith("Armas"),
    "armadura": lambda t: t.startswith("Armaduras"),
    "classe": lambda t: t == "Classes",
    "raca": lambda t: t == "Raças",
    "deus": lambda t: t == "Deuses",
    "deusa": lambda t: t == "Deuses",
    "divindade": lambda t: t == "Deuses",
    "origem": lambda t: t == "Origens",
    "ameaca": lambda t: t in ("Ameaças", "Chefes"),
    "monstro": lambda t: t in ("Ameaças", "Chefes"),
    "criatura": lambda t: t in ("Ameaças", "Chefes"),
    "distincao": lambda t: t == "Distinções",
    "encantamento": lambda t: t.startswith("Encantamentos"),
    "pocao": lambda t: t == "Poções",
    "alimento": lambda t: t == "Alimentos",
    "comida": lambda t: t == "Alimentos",
    "parceiro": lambda t: t == "Parceiros",
    "montaria": lambda t: t == "Montarias",
}

# Palavras que nomeiam uma categoria ("a magia X", "a condição Y") e também
# existem como nome de registro ou de habilidade (Arcanista > Magias, Regras >
# Habilidades, Magias > Condição): sozinhas, são pista, nunca nome.
PALAVRAS_DE_CATEGORIA = frozenset(_PISTAS) | frozenset(
    ["habilidade", "regra", "item", "tipo", "efeito", "custo"])

# Tabelas que descrevem categorias, não entidades: perdem o empate.
_PREFIXOS_META = ("Categorias de",)

_RE_PALAVRA = re.compile(r"\w+", re.UNICODE)
_RE_PONTUACAO = re.compile(r"[,.;:?!()\[\]]")


def _tokens(texto: str) -> list[tuple[str, int, int, int]]:
    """(palavra normalizada, início, fim, trecho entre pontuações) de cada palavra."""
    saida = []
    segmento, fim_anterior = 0, 0
    for m in _RE_PALAVRA.finditer(texto):
        if _RE_PONTUACAO.search(texto, fim_anterior, m.start()):
            segmento += 1
        fim_anterior = m.end()
        norma = chave_texto(m.group())
        if norma:
            saida.append((norma, m.start(), m.end(), segmento))
    return saida


def _e_categoria(norma: str) -> bool:
    return norma in PALAVRAS_DE_CATEGORIA or singular(norma) in PALAVRAS_DE_CATEGORIA


def _pistas_perto(tokens, inicio: int, fim: int) -> list:
    """Predicados de tabela cujas palavras-pista estão até ALCANCE_PISTA palavras."""
    janela = tokens[max(0, inicio - ALCANCE_PISTA):fim + ALCANCE_PISTA]
    achadas = []
    for norma, *_ in janela:
        predicado = _PISTAS.get(singular(norma))
        if predicado is not None:
            achadas.append(predicado)
    return achadas


def ambigua(lig: Ligacao) -> bool:
    """Ambígua = sobrou alternativa de OUTRA tabela (fonte diferente já se resolve)."""
    return any(a.tabela != lig.chave.tabela for a in lig.alternativas)


def _escolher(chaves: tuple[Chave, ...], pistas: list) -> tuple[Chave, tuple[Chave, ...]] | None:
    """Aplica pista de tabela e descarta categorias; devolve (escolhida, alternativas)."""
    if pistas:
        filtradas = tuple(c for c in chaves if any(p(c.tabela) for p in pistas))
        if filtradas:
            chaves = filtradas
    entidades = tuple(c for c in chaves if not c.tabela.startswith(_PREFIXOS_META))
    if entidades:
        chaves = entidades
    if not chaves:
        return None
    escolhida = chaves[0]
    # mesma tabela com outra fonte não é ambiguidade: a prioridade já decidiu
    outras = tuple(c for c in chaves[1:] if c.tabela != escolhida.tabela)
    return escolhida, outras


def _janela_utilizavel(normas: list[str]) -> bool:
    # "de machado" ou "machado de" nunca é um nome melhor que "machado"
    if normas[0] in PALAVRAS_VAZIAS or normas[-1] in PALAVRAS_VAZIAS:
        return False
    return not (len(normas) == 1 and (len(normas[0]) < 3 or _e_categoria(normas[0])))


def _janela_aproximavel(tokens, i: int, j: int) -> bool:
    """Aproximada só dentro de um trecho sem pontuação e com ao menos uma palavra
    própria: 'arma espiitual' pode ser Arma Espiritual, mas 'a arma' sozinha não."""
    if len({t[3] for t in tokens[i:j]}) > 1:
        return False
    return any(t[0] not in PALAVRAS_COMUNS and not _e_categoria(t[0])
               and t[0] not in PALAVRAS_VAZIAS for t in tokens[i:j])


def distancia_edicao(a: str, b: str) -> int:
    """Edições (inserir, apagar, trocar, transpor letras vizinhas) entre duas palavras."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            custo = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + custo)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def _melhor_aproximado(frase: str, n_palavras: int, dicionario: Dicionario):
    """(score, [nomes empatados]) do nome mais parecido acima do limiar, ou None."""
    if n_palavras == 1:
        if len(frase) < MIN_LETRAS_UMA_PALAVRA:
            return None
        limiar = LIMIAR_UMA_PALAVRA
    else:
        limiar = LIMIAR_VARIAS_PALAVRAS
    comparador = SequenceMatcher(autojunk=False)
    comparador.set_seq2(frase)
    pontuados = []
    for nome in dicionario.nomes_com_palavras(n_palavras):
        # uma só edição (inclusive transposição) é erro de digitação, mesmo que o
        # ratio() fique abaixo do limiar: 'vlakaria' x 'valkaria' dá 0,875
        uma_edicao = (n_palavras == 1 and abs(len(nome) - len(frase)) <= 1
                      and distancia_edicao(nome, frase) <= 1)
        comparador.set_seq1(nome)
        # filtros baratos primeiro: só calcula o ratio() de quem pode passar
        if not uma_edicao and (comparador.real_quick_ratio() < limiar
                               or comparador.quick_ratio() < limiar):
            continue
        score = comparador.ratio()
        if score >= limiar or uma_edicao:
            pontuados.append((score, nome))
    if not pontuados:
        return None
    melhor = max(s for s, _ in pontuados)
    empatados = sorted(n for s, n in pontuados if melhor - s <= MARGEM_EMPATE)
    return melhor, empatados


def ligar(texto: str, dicionario: Dicionario) -> tuple[Ligacao, ...]:
    """Ligações da pergunta, na ordem em que aparecem no texto."""
    tokens = _tokens(texto)
    usados = [False] * len(tokens)
    ligacoes: list[Ligacao] = []

    def registrar(i, j, chaves, score, tipo):
        pistas = _pistas_perto(tokens, i, j)
        if j - i == 1 and tokens[i][0] in PALAVRAS_COMUNS and not pistas:
            return
        escolha = _escolher(chaves, pistas)
        if escolha is None:
            return
        escolhida, outras = escolha
        inicio, fim = tokens[i][1], tokens[j - 1][2]
        ligacoes.append(Ligacao(texto[inicio:fim], inicio, fim, escolhida,
                                round(score, 3), tipo, outras))
        for k in range(i, j):
            usados[k] = True

    def janelas():
        for n in range(min(dicionario.max_palavras, len(tokens)), 0, -1):
            for i in range(len(tokens) - n + 1):
                j = i + n
                normas = [t[0] for t in tokens[i:j]]
                if not any(usados[i:j]) and _janela_utilizavel(normas):
                    yield i, j, " ".join(normas)

    for i, j, frase in janelas():
        if any(usados[i:j]):
            continue
        if chaves := dicionario.apelido(frase):
            registrar(i, j, chaves, 1.0, "apelido")
        elif chaves := dicionario.exato(frase):
            registrar(i, j, chaves, 1.0, "exata")

    for i, j, frase in janelas():
        if any(usados[i:j]) or not _janela_aproximavel(tokens, i, j):
            continue
        achado = _melhor_aproximado(frase, j - i, dicionario)
        if achado is None:
            continue
        score, nomes = achado
        chaves = tuple(c for nome in nomes for c in dicionario.exatos[nome])
        registrar(i, j, chaves, score, "aproximada")

    return tuple(sorted(ligacoes, key=lambda lig: lig.inicio))


def refinar_por_restricoes(ligacoes: tuple[Ligacao, ...],
                           restricoes: Restricoes) -> tuple[Ligacao, ...]:
    """2º critério de desempate: 'Poderes (Classe)' da classe já ligada na pergunta."""
    classes = {rag_core.normalizar(c) for c in restricoes.classes}
    saida = []
    for lig in ligacoes:
        if not ambigua(lig) or not classes:
            saida.append(lig)
            continue
        todas = (lig.chave, *lig.alternativas)
        alvo = [c for c in todas
                if any(rag_core.normalizar(c.tabela) == f"poderes ({k})" for k in classes)]
        if len(alvo) == 1:
            # resolvida: as demais tabelas deixam de ser alternativa
            saida.append(Ligacao(lig.trecho, lig.inicio, lig.fim, alvo[0],
                                 lig.score, lig.tipo, ()))
        else:
            saida.append(lig)
    return tuple(saida)
