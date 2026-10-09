"""Necessidades: o que a resposta precisa conter para atender a pergunta inteira.

Cada modelo usa só campos que `docs/MAPA_CORPUS.md` confirma (ex.: Classes têm
`levelProgression` em 100% dos registros; Raças têm `abilities` e
`attributeModifiers`, mas nenhum campo de tamanho).
"""

from .tipos import Chave, Ligacao, Necessidade, Restricoes


def _do_registro(chave: Chave, restricoes: Restricoes) -> list[Necessidade]:
    tabela, nome = chave.tabela, chave.nome
    if chave.sub is not None:
        return [Necessidade(f"habilidade {chave.sub} de {nome}", tabela,
                            f"{nome} > {chave.sub}", registro=nome)]
    if tabela == "Classes":
        saida = [Necessidade(f"registro da classe {nome}", tabela, nome, registro=nome)]
        if restricoes.nivel is not None:
            saida.append(Necessidade(
                f"habilidades de {nome} até o nível {restricoes.nivel} "
                "(progressão por nível)", tabela, nome, registro=nome))
        return saida
    if tabela == "Raças":
        return [Necessidade(f"registro da raça {nome} (habilidades e modificadores "
                            "de atributo)", tabela, nome, registro=nome)]
    if tabela.startswith("Armas"):
        return [Necessidade(f"registro da arma {nome} (dano, crítico, empunhadura, "
                            "proficiência)", tabela, nome, registro=nome)]
    return [Necessidade(f"registro de {nome} ({tabela})", tabela, nome, registro=nome)]


def gerar(ligacoes: tuple[Ligacao, ...], restricoes: Restricoes, tipo: str,
          tabelas: frozenset[str]) -> tuple[Necessidade, ...]:
    """`tabelas` = rótulos existentes no corpus; nenhuma necessidade aponta fora deles."""
    vistas: set[Chave] = set()
    saida: list[Necessidade] = []

    def adicionar(necessidade: Necessidade) -> None:
        if necessidade not in saida:
            saida.append(necessidade)

    for lig in ligacoes:
        # ambígua: a política traz todas as alternativas, cada uma com vaga
        for chave in (lig.chave, *lig.alternativas):
            if chave in vistas:
                continue
            vistas.add(chave)
            for necessidade in _do_registro(chave, restricoes):
                adicionar(necessidade)

    if tipo == "build":
        for classe in restricoes.classes:
            tabela = f"Poderes ({classe})"
            if tabela in tabelas:
                nivel = f" até o nível {restricoes.nivel}" if restricoes.nivel else ""
                adicionar(Necessidade(f"poderes de {classe}{nivel}", tabela, classe))
        alvos = restricoes.pericias + restricoes.itens
        if alvos and "Poderes Gerais" in tabelas:
            adicionar(Necessidade("poderes gerais que usam " + ", ".join(alvos),
                                  "Poderes Gerais", ", ".join(alvos), obrigatoria=False))
    return tuple(saida)
