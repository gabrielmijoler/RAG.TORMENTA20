"""Conhecimento aprendido: apelidos e erros de digitação resolvidos.

O sistema aprende só a INTERPRETAR perguntas (um apelido aponta para a
chave completa Tabela + Nome + Fonte de um registro); nunca aprende regra.
Nada vale sem aprovação humana:
- `conhecimento/propostas.yaml`: entradas `proposta` e `recusada` (histórico);
- `conhecimento/apelidos.yaml`: entradas `aprovada` (lidas pelo ligador) e
  `suspensa` (o registro sumiu do corpus; nunca apagadas);
- `conhecimento/APRENDIZADOS.md`: gerado do YAML, nunca editado à mão.
"""

import datetime as dt
from pathlib import Path

import yaml

from .dicionario import Dicionario, chave_texto
from .tipos import Chave

PASTA = Path("conhecimento")
CAMINHO_PROPOSTAS = PASTA / "propostas.yaml"
CAMINHO_APELIDOS = PASTA / "apelidos.yaml"
CAMINHO_MD = PASTA / "APRENDIZADOS.md"

CAMPOS_OBRIGATORIOS = ("id", "apelido", "tabela", "nome", "fonte", "observado",
                       "onde_confirmar", "data", "status")
MIN_LETRAS_APELIDO = 3


def _hoje() -> dt.date:
    return dt.datetime.now(dt.UTC).astimezone().date()


def carregar(caminho) -> list[dict]:
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or []


def salvar(caminho, entradas: list[dict]) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(yaml.safe_dump(entradas, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")


def _chave(entrada: dict) -> Chave:
    return Chave(entrada["tabela"], entrada["nome"], entrada["fonte"])


def _proximo_id(*listas: list[dict]) -> str:
    numeros = [int(e["id"][1:]) for lista in listas for e in lista
               if str(e.get("id", "")).startswith("a") and e["id"][1:].isdigit()]
    return f"a{max(numeros, default=0) + 1:04d}"


def propor(apelido: str, chave: Chave, observado: str, onde_confirmar: str,
           caminho=CAMINHO_PROPOSTAS, caminho_apelidos=None, hoje: dt.date | None = None
           ) -> dict:
    """Registra uma proposta pendente (não vale no ligador até ser aprovada)."""
    propostas = carregar(caminho)
    aprovadas = carregar(caminho_apelidos or Path(caminho).with_name("apelidos.yaml"))
    entrada = {
        "id": _proximo_id(propostas, aprovadas),
        "apelido": apelido.strip(),
        "tabela": chave.tabela, "nome": chave.nome, "fonte": chave.fonte,
        "observado": observado,
        "correto": f"{chave.nome} [{chave.tabela} > {chave.fonte}]",
        "onde_confirmar": onde_confirmar,
        "data": (hoje or _hoje()).isoformat(),
        "status": "proposta",
        "aprovado_por": None,
        "motivo": None,
    }
    propostas.append(entrada)
    salvar(caminho, propostas)
    return entrada


def _registro_existe(chave: Chave, dicionario: Dicionario) -> bool:
    return chave in dicionario.exato(chave.nome)


def validar(entrada: dict, dicionario: Dicionario, aprovadas: list[dict]) -> list[str]:
    """Formato, registro alvo existente, sem colisão com nome real ou outro apelido."""
    faltando = [c for c in CAMPOS_OBRIGATORIOS if not entrada.get(c)]
    if faltando:
        return [f"campos obrigatórios vazios: {', '.join(faltando)}"]
    erros = []
    apelido = chave_texto(entrada["apelido"])
    if len(apelido) < MIN_LETRAS_APELIDO:
        erros.append(f"apelido curto demais: {entrada['apelido']!r}")
    if not _registro_existe(_chave(entrada), dicionario):
        erros.append(f"registro alvo não existe no corpus: {entrada['tabela']} > "
                     f"{entrada['nome']} [{entrada['fonte']}]")
    if dicionario.exato(apelido):
        erros.append(f"apelido colide com um nome real do corpus: {entrada['apelido']!r}")
    for outra in aprovadas:
        if outra.get("status") == "aprovada" and chave_texto(outra["apelido"]) == apelido:
            erros.append(f"apelido já existe ({outra['id']} -> {outra['nome']})")
    return erros


def aprovar(id_: str, por: str, dicionario: Dicionario, caminho_propostas=CAMINHO_PROPOSTAS,
            caminho_apelidos=CAMINHO_APELIDOS, hoje: dt.date | None = None) -> list[str]:
    """Valida e move a proposta para apelidos.yaml. Devolve os erros ([] = aprovada)."""
    propostas = carregar(caminho_propostas)
    entrada = next((e for e in propostas if e["id"] == id_), None)
    if entrada is None:
        return [f"proposta {id_} não encontrada"]
    if entrada["status"] != "proposta":
        return [f"{id_} está {entrada['status']}, não pendente"]
    aprovadas = carregar(caminho_apelidos)
    erros = validar(entrada, dicionario, aprovadas)
    if erros:
        return erros
    propostas.remove(entrada)
    entrada.update(status="aprovada", aprovado_por=por,
                   data_aprovacao=(hoje or _hoje()).isoformat())
    aprovadas.append(entrada)
    salvar(caminho_apelidos, aprovadas)
    salvar(caminho_propostas, propostas)
    return []


def recusar(id_: str, motivo: str, caminho_propostas=CAMINHO_PROPOSTAS) -> bool:
    propostas = carregar(caminho_propostas)
    for entrada in propostas:
        if entrada["id"] == id_ and entrada["status"] == "proposta":
            entrada.update(status="recusada", motivo=motivo)
            salvar(caminho_propostas, propostas)
            return True
    return False


def verificar(dicionario: Dicionario, caminho_apelidos=CAMINHO_APELIDOS) -> list[dict]:
    """Após reindexar/reingerir: suspende apelidos cujo registro sumiu (nunca apaga)."""
    aprovadas = carregar(caminho_apelidos)
    suspensas = []
    for entrada in aprovadas:
        if entrada["status"] == "aprovada" and not _registro_existe(_chave(entrada), dicionario):
            entrada.update(status="suspensa", motivo="registro alvo não existe mais no corpus")
            suspensas.append(entrada)
    if suspensas:
        salvar(caminho_apelidos, aprovadas)
    return suspensas


def apelidos_ativos(caminho_apelidos=CAMINHO_APELIDOS) -> dict[str, Chave]:
    """Só as entradas `aprovada`: é o que o dicionário/ligador enxerga."""
    return {chave_texto(e["apelido"]): _chave(e) for e in carregar(caminho_apelidos)
            if e.get("status") == "aprovada"}


def gerar_md(caminho_propostas=CAMINHO_PROPOSTAS, caminho_apelidos=CAMINHO_APELIDOS) -> str:
    entradas = carregar(caminho_apelidos) + carregar(caminho_propostas)
    linhas = ["# Aprendizados do analisador", "",
              ("Gerado de `conhecimento/*.yaml` por `tools/conhecimento.py gerar-md`: "
               "não edite à mão (o YAML é a fonte). O sistema aprende só a interpretar "
               "perguntas; as regras vêm sempre do corpus."), ""]
    for status in ("aprovada", "proposta", "suspensa", "recusada"):
        grupo = [e for e in entradas if e["status"] == status]
        linhas += [f"## {status.capitalize()}s ({len(grupo)})", ""]
        for e in sorted(grupo, key=lambda e: e["id"]):
            linhas += [
                f"### {e['id']} — \"{e['apelido']}\"",
                f"- Observado: {e['observado']}",
                f"- Correto: {e.get('correto') or e['nome']}",
                f"- Onde confirmar no livro: {e['onde_confirmar']}",
                f"- Data: {e['data']} · status: {e['status']}"
                + (f" · aprovado por: {e['aprovado_por']}" if e.get("aprovado_por") else "")
                + (f" · motivo: {e['motivo']}" if e.get("motivo") else ""),
                "",
            ]
    return "\n".join(linhas)
