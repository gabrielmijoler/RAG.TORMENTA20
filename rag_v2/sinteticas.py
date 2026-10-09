"""Perguntas sintéticas SEM LLM, com gabarito por construção.

Cada pergunta nasce de UM registro do corpus e de UM campo dele: o registro é
a entidade esperada e o valor do campo é o fato esperado, então o gabarito
não depende de ninguém ter conferido. A amostra é nova a cada semente.

Só registros da fonte base (Tormenta20 - Jogo do Ano) com nome único no
dicionário entram: nome em outra fonte ou tabela tornaria o gabarito ambíguo.
Ruído controlado imita jogador de mesa: erro de digitação no NOME (uma edição),
sem acento, minúsculas e abreviações. `descritiva` descreve a magia pelos
campos sem dizer o nome — só quando a combinação de campos é única no corpus.
"""

import random
from collections import Counter
from difflib import SequenceMatcher

import rag_core

from .dicionario import TABELAS_IGNORADAS, normalizar_fonte

FONTE_BASE = "tormenta20 - jogo do ano"
MIN_LETRAS_ERRO = 7
SIMILARIDADE_MIN = 0.85

# (tabela, campo, modelo de pergunta, modelo de fato). Só campos de texto simples.
MODELOS = [
    ("Magias", "duration", "Qual a duração da magia {nome}?", "duração: {v}"),
    ("Magias", "resistance", "Que teste de resistência a magia {nome} permite?", "resistência: {v}"),
    ("Magias", "range", "Qual o alcance da magia {nome}?", "alcance: {v}"),
    ("Magias", "target", "Qual o alvo ou área da magia {nome}?", "alvo/área: {v}"),
    ("Armas", "damage", "Qual o dano da arma {nome}?", "dano: {v}"),
    ("Armas", "critical", "Qual a margem e o multiplicador de crítico de {nome}?", "crítico: {v}"),
    ("Armas", "grip", "{nome} é arma de uma ou de duas mãos?", "empunhadura: {v}"),
    ("Armas", "price", "Quanto custa a arma {nome}?", "preço: {v}"),
    ("Condições", "description", "O que causa a condição {nome}?", "descrição: {v}"),
    ("Perícias", "attribute", "Qual o atributo-chave da perícia {nome}?", "atributo: {v}"),
    ("Deuses", "preferredWeapon", "Qual a arma preferida do deus {nome}?", "arma preferida: {v}"),
    ("Deuses", "channelEnergy", "Que energia canaliza o deus {nome}?", "energia: {v}"),
]
CAMPOS_DESCRITIVA = ("circle", "school", "range", "duration", "execution", "target",
                     "resistance")
_ABREVIACOES = (("quanto", "qto"), ("que", "q"), ("qual", "qual"), ("nível", "nv"),
                ("porque", "pq"), ("você", "vc"), ("também", "tb"))


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def com_erro_de_digitacao(nome: str, rng: random.Random) -> str:
    """Uma edição (troca de letras vizinhas ou letra a menos) em uma palavra longa."""
    palavras = nome.split(" ")
    candidatas = [i for i, p in enumerate(palavras) if len(p) >= MIN_LETRAS_ERRO]
    if not candidatas:
        return nome
    i = rng.choice(candidatas)
    p = palavras[i]
    pos = rng.randrange(1, len(p) - 2)  # preserva a primeira letra e a última
    if rng.random() < 0.5:
        p = p[:pos] + p[pos + 1] + p[pos] + p[pos + 2:]
    else:
        p = p[:pos] + p[pos + 1:]
    palavras[i] = p
    editado = " ".join(palavras)
    return editado if similaridade(nome, editado) >= SIMILARIDADE_MIN else nome


def informalizar(texto: str, rng: random.Random) -> str:
    """Minúsculas, sem acento nem pontuação final e algumas abreviações."""
    saida = rag_core.normalizar(texto).replace("?", "").strip()
    for longa, curta in _ABREVIACOES:
        if rng.random() < 0.5:
            saida = saida.replace(rag_core.normalizar(longa), curta)
    return saida


def taxa_gabarito_errado(conferidos: int, errados: int) -> float | None:
    return errados / conferidos if conferidos else None


def _fonte_ok(reg: dict) -> bool:
    return normalizar_fonte(rag_core._fonte_do_registro(reg)) == normalizar_fonte(FONTE_BASE)


def _texto(valor) -> str | None:
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str) and valor.strip():
        return " ".join(valor.split())
    return None


def _registros(dados: dict):
    """(tabela, reg) de todos os registros utilizáveis + contagem de nomes por fonte."""
    todos, contagem = [], Counter()
    for bloco in dados["tabelas"]:
        tabela = rag_core._rotulo_tabela(bloco["arquivo"], bloco["export"])
        if tabela in TABELAS_IGNORADAS:
            continue
        for reg in bloco["elementos"]:
            nome = rag_core._nome_do_registro(reg)
            if not nome:
                continue
            contagem[rag_core.normalizar(nome)] += 1
            todos.append((tabela, reg, nome))
    return todos, contagem


def _entidade(tabela: str, reg: dict, nome: str) -> dict:
    return {"nome": nome, "tabela": tabela, "fonte": rag_core._fonte_do_registro(reg),
            "sub": None}


def _caso(i, semente, tipo, modelo, consulta, ent, fato, ruidosa, informal) -> dict:
    return {
        "id": f"sint{semente}_{i:03d}", "nivel": "sintetica", "conjunto": "sintetico",
        "consulta": consulta, "mensagens": None, "subperguntas": [consulta],
        "entidades": [rag_core.normalizar(ent["nome"])], "entidades_esperadas": [ent],
        "fatos_esperados": [fato], "resposta_esperada": fato, "armadilhas": [],
        "origem": f"sintetica:semente={semente}", "premissa_falsa": False,
        "informal": informal, "verificacao": "ok", "entidades_nao_encontradas": [],
        "tipo_pergunta": tipo, "modelo": modelo, "com_erro_de_digitacao": ruidosa,
    }


def _intercalar_por_tabela(candidatos: list, rng: random.Random) -> list:
    """Sorteia dentro de cada tabela e intercala as tabelas (round-robin).

    Sem isso a tabela maior (Magias, 264 registros e vários campos) ocupa quase
    toda a amostra e esconde as falhas das outras.
    """
    grupos: dict[str, list] = {}
    for item in candidatos:
        grupos.setdefault(item[4], []).append(item)
    filas = list(grupos.values())
    for fila in filas:
        rng.shuffle(fila)
    rng.shuffle(filas)
    saida = []
    while any(filas):
        for fila in filas:
            if fila:
                saida.append(fila.pop())
    return saida


def gerar(dados: dict, n: int, semente: int, ruido: float = 0.35) -> list[dict]:
    """`n` perguntas novas (menos, se o corpus não der); `ruido` = chance de erro/informal."""
    rng = random.Random(semente)
    todos, contagem = _registros(dados)
    unicos = {(t, nome): reg for t, reg, nome in todos
              if _fonte_ok(reg) and contagem[rag_core.normalizar(nome)] == 1}

    candidatos = []
    for tabela, campo, pergunta, fato in MODELOS:
        for (tab, nome), reg in unicos.items():
            valor = _texto(reg.get(campo))
            if tab == tabela and valor:
                candidatos.append(("direta", f"{tabela}.{campo}", pergunta, fato,
                                   tab, nome, reg, valor))

    # descritivas: assinatura de campos única entre TODAS as magias do corpus
    assinaturas = Counter()
    magias = [(t, r, n_) for t, r, n_ in todos if t == "Magias"]
    for _, reg, _ in magias:
        assinaturas[tuple(_texto(reg.get(c)) for c in CAMPOS_DESCRITIVA)] += 1
    for (tab, nome), reg in unicos.items():
        assinatura = tuple(_texto(reg.get(c)) for c in CAMPOS_DESCRITIVA)
        if tab == "Magias" and all(assinatura) and assinaturas[assinatura] == 1:
            candidatos.append(("descritiva", "Magias.descritiva", "", "", tab, nome, reg, ""))

    candidatos = _intercalar_por_tabela(candidatos, rng)
    casos, vistos = [], set()
    for tipo, modelo, pergunta, fato, tabela, nome, reg, valor in candidatos:
        if len(casos) >= n:
            break
        chave = (tipo, nome, modelo)
        if chave in vistos:
            continue
        vistos.add(chave)
        ent = _entidade(tabela, reg, nome)
        ruidosa = rng.random() < ruido
        if tipo == "descritiva":
            campos = {c: _texto(reg.get(c)) for c in CAMPOS_DESCRITIVA}
            consulta = (f"Qual magia de {campos['circle']}º círculo, escola {campos['school']}, "
                        f"execução {campos['execution']}, alcance {campos['range']}, "
                        f"alvo {campos['target']}, duração {campos['duration']} e "
                        f"resistência {campos['resistance']}?")
            texto_fato = f"a magia descrita é {nome}"
        else:
            exibido = com_erro_de_digitacao(nome, rng) if ruidosa else nome
            consulta = pergunta.format(nome=exibido)
            texto_fato = fato.format(v=valor)
        informal = ruidosa and rng.random() < 0.6
        if informal:
            consulta = informalizar(consulta, rng)
        casos.append(_caso(len(casos) + 1, semente, tipo, modelo, consulta, ent,
                           texto_fato, ruidosa and tipo != "descritiva", informal))
    return casos
