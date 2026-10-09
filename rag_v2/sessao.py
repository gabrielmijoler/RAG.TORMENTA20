"""Ficha e foco da sessão: o que o chat lembra entre uma pergunta e outra.

- ficha: classe, raça, nível e itens que o usuário disse ter (herdados por
  perguntas em primeira pessoa: "isso combina comigo?");
- foco: a última entidade em discussão (herdada por referências: "e a CD dela?").
Aprende só interpretação da conversa; regra do jogo vem sempre do corpus.
"""

import re
from dataclasses import dataclass, field

from .dicionario import chave_texto
from .restricoes import NIVEL_MAX, NIVEL_MIN
from .tipos import Chave, Leitura

_RE_REFERENCIA = re.compile(
    r"\b(?:ele|ela|eles|elas|dele|dela|deles|delas|nele|nela|esse|essa|desse|dessa|"
    r"nesse|nessa|este|esta|deste|desta|isso|disso|nisso|isto|disto|o mesmo|a mesma)\b")
_RE_PRIMEIRA_PESSOA = re.compile(
    r"\b(?:eu|meu|minha|meus|minhas|sou|posso|pego|consigo|comigo|tenho|uso|quero|mim)\b")
# "e a duração?", "e se eu pegar X?": continuação curta de uma pergunta anterior
MAX_PALAVRAS_CONTINUACAO = 6
_RE_PAR = re.compile(r'(\w+)\s*=\s*("[^"]*"|\S+)')


def precisa_de_foco(texto: str) -> bool:
    norma = chave_texto(texto)
    if _RE_REFERENCIA.search(norma):
        return True
    palavras = norma.split()
    return bool(palavras) and palavras[0] == "e" and len(palavras) <= MAX_PALAVRAS_CONTINUACAO


def primeira_pessoa(texto: str) -> bool:
    return bool(_RE_PRIMEIRA_PESSOA.search(chave_texto(texto)))


@dataclass
class Ficha:
    classe: str | None = None
    raca: str | None = None
    nivel: int | None = None
    itens: list[str] = field(default_factory=list)

    def vazia(self) -> bool:
        return not (self.classe or self.raca or self.nivel or self.itens)

    def resumo(self) -> str:
        partes = []
        if self.classe:
            partes.append(self.classe)
        if self.raca:
            partes.append(self.raca)
        if self.nivel is not None:
            partes.append(f"nível {self.nivel}")
        return ", ".join(partes + self.itens)


@dataclass
class Sessao:
    ficha: Ficha = field(default_factory=Ficha)
    foco: Chave | None = None

    def atualizar(self, leitura: Leitura) -> None:
        """Guarda o que a pergunta disse do personagem e a última entidade discutida."""
        r = leitura.restricoes
        if r.classes:
            self.ficha.classe = r.classes[0]
        if r.racas:
            self.ficha.raca = r.racas[0]
        if r.nivel is not None:
            self.ficha.nivel = r.nivel
        for item in r.itens:
            if item not in self.ficha.itens:
                self.ficha.itens.append(item)
        if leitura.ligacoes:
            self.foco = leitura.ligacoes[-1].chave

    def corrigir(self, texto: str) -> list[str]:
        """/ficha nivel=5 classe=Bárbaro raca=Bugbear itens="Adaga, Escudo" -> erros."""
        erros = []
        pares = _RE_PAR.findall(texto)
        if not pares:
            return ["use campo=valor (nivel, classe, raca, itens)"]
        for campo, valor in pares:
            valor = valor.strip('"').strip()
            campo = chave_texto(campo)
            if campo == "nivel":
                if not valor.isdigit() or not NIVEL_MIN <= int(valor) <= NIVEL_MAX:
                    erros.append(f"nível inválido: {valor} (use {NIVEL_MIN} a {NIVEL_MAX})")
                else:
                    self.ficha.nivel = int(valor)
            elif campo == "classe":
                self.ficha.classe = valor or None
            elif campo == "raca":
                self.ficha.raca = valor or None
            elif campo == "itens":
                self.ficha.itens = [i.strip() for i in valor.split(",") if i.strip()]
            else:
                erros.append(f"campo desconhecido: {campo}")
        return erros

    def zerar(self) -> None:
        self.ficha = Ficha()
        self.foco = None

    def descrever(self) -> str:
        ficha = self.ficha.resumo() or "vazia"
        foco = (f"{self.foco.tabela} > {self.foco.nome}"
                + (f" > {self.foco.sub}" if self.foco.sub else "")
                + f" [{self.foco.fonte}]") if self.foco else "nenhum"
        return (f"Ficha: {ficha}\nFoco: {foco}\n"
                "Corrija com /ficha campo=valor (nivel, classe, raca, itens); /novo zera.")
