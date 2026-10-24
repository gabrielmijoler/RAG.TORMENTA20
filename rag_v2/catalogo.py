"""Catálogo do corpus para o construtor de personagem.

Guarda, por tabela de poderes, o nome, a fonte, o pré-requisito (texto cru) e a
descrição de cada poder, mais os nomes de raças e as perícias de cada classe. É a
base para LISTAR e FILTRAR (poderes que o personagem pode pegar) sem depender da
busca por semelhança, que só devolve os registros mais parecidos com a pergunta.
"""

import re
from dataclasses import dataclass, field

import rag_core

_RE_ATRIBUTO_NA_PERICIA = re.compile(r"\s*\([^)]*\)\s*$")


@dataclass(frozen=True)
class PoderInfo:
    nome: str
    tabela: str
    fonte: str
    prerequisito: str
    descricao: str


@dataclass
class Catalogo:
    poderes: dict[str, list[PoderInfo]] = field(default_factory=dict)
    nomes_poderes: frozenset[str] = frozenset()
    racas: frozenset[str] = frozenset()
    pericias_classe: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    # classe normalizada -> [(nível, texto da progressão)]
    progressao: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    def niveis_com_poder(self, classe: str, nivel: int) -> list[int] | None:
        """Níveis (até `nivel`) em que a classe ganha 'poder de <classe>'; None sem progressão."""
        norma = rag_core.normalizar(classe).strip()
        linhas = self.progressao.get(norma)
        if linhas is None:
            return None
        return [n for n, texto in linhas
                if n <= nivel and f"poder de {norma}" in rag_core.normalizar(texto)]

    def tabela_de_poderes(self, classe: str) -> str | None:
        """'Inventor' -> 'Poderes (Inventor)', se existir essa tabela."""
        alvo = f"poderes ({rag_core.normalizar(classe).strip()})"
        return next((t for t in self.poderes if rag_core.normalizar(t).strip() == alvo), None)


def _pericia(texto: str) -> str:
    return rag_core.normalizar(_RE_ATRIBUTO_NA_PERICIA.sub("", texto)).strip()


def construir_catalogo(dados: dict) -> Catalogo:
    poderes: dict[str, list[PoderInfo]] = {}
    racas: set[str] = set()
    pericias: dict[str, dict[str, set[str]]] = {}
    progressao: dict[str, list[tuple[int, str]]] = {}
    for bloco in dados["tabelas"]:
        tabela = rag_core._rotulo_tabela(bloco["arquivo"], bloco["export"])
        for reg in bloco["elementos"]:
            nome = rag_core._nome_do_registro(reg).strip()
            if tabela.startswith("Poderes") and nome:
                poderes.setdefault(tabela, []).append(PoderInfo(
                    nome=nome, tabela=tabela, fonte=rag_core._fonte_do_registro(reg),
                    prerequisito=str(reg.get("prerequisite") or "").strip(),
                    descricao=" ".join(str(reg.get("description") or "").split())))
            elif tabela == "Raças" and nome:
                racas.add(rag_core.normalizar(nome).strip())
            if tabela == "Classes" and nome and isinstance(reg.get("levelProgression"), list):
                progressao.setdefault(rag_core.normalizar(nome).strip(), [
                    (int(e["level"]), str(e.get("abilities") or ""))
                    for e in reg["levelProgression"]
                    if isinstance(e, dict) and str(e.get("level", "")).isdigit()])
            if tabela == "Classes" and nome and isinstance(reg.get("skills"), dict):
                hab = reg["skills"]
                opcionais = hab.get("optional") or {}
                pericias[rag_core.normalizar(nome).strip()] = {
                    "obrigatorias": {_pericia(s) for s in hab.get("mandatory") or []},
                    "opcionais": {_pericia(s) for s in opcionais.get("skills") or []},
                }
    nomes = frozenset(rag_core.normalizar(p.nome).strip() for lista in poderes.values()
                      for p in lista)
    return Catalogo(poderes, nomes, frozenset(racas), pericias, progressao)
