"""Contratos da v2: dados puros, imutáveis e sem lógica."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chave:
    """Identifica um registro do corpus (e, opcionalmente, uma habilidade dentro dele)."""

    tabela: str
    nome: str
    fonte: str
    sub: str | None = None


@dataclass(frozen=True)
class Ligacao:
    """Um trecho da pergunta ligado a um registro."""

    trecho: str
    inicio: int
    fim: int
    chave: Chave
    score: float
    tipo: str  # "exata" | "aproximada" | "apelido" | "foco"
    alternativas: tuple[Chave, ...] = ()


@dataclass(frozen=True)
class Restricoes:
    nivel: int | None = None
    classes: tuple[str, ...] = ()
    racas: tuple[str, ...] = ()
    pericias: tuple[str, ...] = ()
    itens: tuple[str, ...] = ()


@dataclass(frozen=True)
class Necessidade:
    """Algo que a resposta precisa conter para atender a pergunta inteira."""

    descricao: str
    tabela_alvo: str
    entidade: str
    obrigatoria: bool = True
    # Nome do registro exato em `tabela_alvo` (busca direta); None = qualquer
    # registro da tabela serve (ex.: "poderes de Bárbaro").
    registro: str | None = None


@dataclass(frozen=True)
class Leitura:
    """Resultado do analisador. Os padrões são o comportamento da v1 (fallback total)."""

    texto_original: str
    ligacoes: tuple[Ligacao, ...] = ()
    restricoes: Restricoes = Restricoes()
    tipo: str = "sem_nome"  # direta | multiparte | build | sem_nome | fora_de_escopo
    necessidades: tuple[Necessidade, ...] = ()
    k: int = 12
    confianca: str = "baixa"  # alta | media | baixa
    motivos: tuple[str, ...] = ()
    usar_llm: str = "completo"  # nenhum | traducao | completo
    # Pergunta com a referência resolvida pelo foco ("e a CD dela? (Teia)");
    # None = a própria pergunta original.
    texto_resolvido: str | None = None
