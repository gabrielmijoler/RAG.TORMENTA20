"""Nucleo compartilhado do RAG de Tormenta 20.

`meu_primeiro_rag.py` (pipeline de producao) e `avaliar.py` (suite de
avaliacao) importam daqui para garantir que o eval meca EXATAMENTE o mesmo
pipeline que o script usa — se a pilha de busca divergir, o eval passa a
medir outra coisa em silencio.

O core (LLM com fallback, busca hibrida BM25+vetorial+rerank e conexao
Qdrant) foi herdado do projeto RAG-MTC e mantido identico. O que e
especifico de dominio (prompts, ingestao, colecoes) esta isolado abaixo.
"""

import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.retrievers import EnsembleRetriever
from langchain_classic.retrievers.contextual_compression import (
    ContextualCompressionRetriever,
)
from langchain_cohere import CohereRerank
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import APIError
from pydantic import PrivateAttr
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------
# Ingestao: fontes .ts VIVAS do app aTormenta (repositorio irmão em
# Documentos/). Os .ts sao a fonte da verdade do app — nada e convertido para
# .md nem copiado: o extrator Node le os exports direto de lá a cada ingestao.
RAIZ_PROJETO = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.normpath(os.path.join(RAIZ_PROJETO, "..", "aTormenta", "data"))
FERRAMENTA_TS = os.path.join(RAIZ_PROJETO, "tools", "ts_para_registros.mjs")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

COLECAO = "tormenta20"
# Memoria de longo prazo: resumos de sessoes de campanha arquivados pelo chat
# (dado derivado, independente do REINDEXAR=1 da colecao principal).
COLECAO_HISTORICO = "sessoes_campanha"
PASTA_QDRANT = "./qdrant_t20_local"
QDRANT_URL = os.environ.get("QDRANT_URL", "").strip()

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
MODELO_RERANK = "rerank-v3.5"

# LLM em tres camadas: NVIDIA (free tier de build.nvidia.com, ~40 RPM, sem
# cota mensal, zero headers de billing) primeiro, Groq (Free tier: 30 RPM,
# 1K req/dia, 8K TPM por modelo) em segundo e OpenRouter (:free) por ultimo.
# O Cohere e so reranker (CohereRerank la embaixo) — nao entra aqui.
# Nenhum modelo pago.
MODELOS_NVIDIA = [
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "meta/muse-glimmer-30b",
    "poolside/laguna-xs-2.1",
]

MODELOS_GROQ = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-safeguard-20b",
    "openai/gpt-oss-20b",
]

MODELOS_OPENROUTER = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3.8-27b:free",
    "google/gemma-4-31b-it:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "openrouter/free",
]

MODELOS_GRATUITOS = MODELOS_NVIDIA + MODELOS_GROQ + MODELOS_OPENROUTER

URL_NVIDIA = "https://integrate.api.nvidia.com/v1"
URL_GROQ = "https://api.groq.com/openai/v1"
URL_OPENROUTER = "https://openrouter.ai/api/v1"

# Dicionario explicito (e nao fatias da lista): inserir um modelo no meio de
# um grupo nao reclassifica os demais por engano.
PROVEDOR_DO_MODELO = {
    **{m: "nvidia" for m in MODELOS_NVIDIA},
    **{m: "groq" for m in MODELOS_GROQ},
    **{m: "openrouter" for m in MODELOS_OPENROUTER},
}

# 429/503 -> esperar e tentar de novo no MESMO modelo.
FALHA_TRANSITORIA = ["429", "503", "overloaded", "rate limit", "temporar",
                     "timeout", "timed out"]

# 404/400 -> o modelo nao existe mais (ex.: alias "command-r" sem data).
# Nao adianta repetir: pula direto para o proximo da lista.
FALHA_DE_MODELO = [
    "404", "400", "not found", "does not exist", "no such model",
    "is not a valid model", "invalid model id",
    "model_not_found", "unavailable for free", "use this slug instead",
]

# Cota diaria, chave invalida ou credito esgotado: repetir nao resolve e o
# proximo modelo da lista vai falhar igual. Casa com 401/402/403 e com o
# 429 de quota do OpenRouter ("usage limit", "limit will reset").
FALHA_DE_CREDITO = [
    "401", "402", "403", "unauthorized", "forbidden", "invalid api key",
    "insufficient", "credit", "billing", "payment", "quota",
    "usage limit", "exceeded your", "limit will reset", "free models",
    "requests per day", "tokens per day",
]


def e_transitorio(erro: Exception) -> bool:
    texto = str(erro).lower()
    return any(s in texto for s in FALHA_TRANSITORIA)


def e_modelo_indisponivel(erro: Exception) -> bool:
    texto = str(erro).lower()
    return any(s in texto for s in FALHA_DE_MODELO)


def e_cota_esgotada(erro: Exception) -> bool:
    texto = str(erro).lower()
    return any(s in texto for s in FALHA_DE_CREDITO)


# ---------------------------------------------------------------------------
# Short-circuit de saudacoes puras ("oi", "bom dia"...)
# ---------------------------------------------------------------------------
# Detecta conversa casual SEM consulta ao RAG: saudacao pura nao gera busca
# vetorial, nao chama LLM e nao ocupa a janela de memoria do chat_history.
SAUDACOES_PURAS = {
    "oi", "ola", "olá", "bom dia", "boa tarde", "boa noite",
    "ola mundo", "olá mundo", "hello", "hi", "e ai", "e aí", "opa",
}


def eh_saudacao_pura(texto: str) -> bool:
    """True só para saudações triviais; qualquer pedido de regra passa adiante."""
    limpo = re.sub(r"[^\w\s]", "", texto.strip().lower())
    limpo = " ".join(limpo.split())
    return limpo in SAUDACOES_PURAS


class RecusaTraducao(Exception):
    """O LLM de tradução respondeu com um 'não posso' em vez da pergunta."""


# Recusa tipica: o modelo ignora o papel de reformulador e emite bloqueio de
# seguranca.
_E_COMECO_RECUSA = (
    "não posso", "nao posso", "desculpe", "como modelo", "como assistente",
    "não é possível", "nao e possivel", "infelizmente", "não posso fornecer",
    "sigo diretrizes", "diretrizes de segurança", "diretrizes rigorosas",
)


def e_recusa(texto: str) -> bool:
    """Detecta bloqueio de segurança onde deveria vir uma pergunta reformulada."""
    t = texto.strip().lower()
    return any(t.startswith(p) or p in t[:120] for p in _E_COMECO_RECUSA)


def reformulacao_valida(texto: str) -> bool:
    """True só para UMA pergunta completa — descarta preâmbulo/cotação do LLM.

    Um LLM gratuito já devolveu `Quoting: "Qualcomm\\nThe user's query is...`
    no meio da resposta; usar isso como query de busca derruba o rerank
    inteiro, então lixo assim é regenerado (nunca cacheado) ou ignorado.
    """
    t = texto.strip()
    return (
        8 <= len(t) <= 300
        and "\n" not in t
        and t.endswith("?")
        and not t.lower().startswith(("quoting", "resposta"))
    )


# ---------------------------------------------------------------------------
# Prompts (fonte unica: meu_primeiro_rag.py e avaliar.py usam os mesmos)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "Você é um Mestre Sênior e Arquivista de Tormenta 20, com domínio total do "
    "Livro do Jogador, Bestiário, Atlas de Arton e demais fontes oficiais do "
    "sistema: raças, classes, origens, poderes, perícias, condições de combate, "
    "bestas, itens, magias e regras de criação de personagem.\n\n"
    "REGRA DE FORMATO E CONCISÃO: Se o usuário pedir um formato específico "
    "(ex: 'apenas uma tabela', 'liste em 3 colunas', 'só a ficha', 'sem "
    "explicações'), obedeça IMEDIATAMENTE: entregue EXCLUSIVAMENTE o formato "
    "pedido, suprimindo regras gerais e explicações longas. 'N colunas' SEMPRE "
    "significa tabela Markdown com exatamente N colunas nomeadas e uma linha por "
    "entrada, e NUNCA uma lista corrida ou tabela com menos colunas.\n"
    "1. **Fidelidade à Base — REGRA INVIOLÁVEL:** Responda EXCLUSIVAMENTE com "
    "informações que estejam literalmente escritas no {context} abaixo. É "
    "TERMINANTEMENTE PROIBIDO citar regras, números (PV, PM, dano, CD, "
    "deslocamento), habilidades ou itens que não apareçam no contexto, sob "
    "QUALQUER pretexto: nem por conhecimento prévio, nem por memória, nem por "
    "raciocínio de regra, nem por analogia com outra raça/classe, nem por "
    "pressupor que a regra é clássica. Se não está escrito no contexto, NÃO "
    "existe para esta resposta — não mencione, não deduza, não sugira, não "
    "complete. Quando a resposta não estiver no contexto, declare apenas que a "
    "base não cobre o ponto, sem inventar.\n"
    "2. **Citação da Fonte:** Todo fato citado DEVE ser acompanhado da origem no "
    "formato: Nome [Fonte] — copiando o prefixo que abre cada bloco do contexto "
    "(ex: 'Caído [Condições > Tormenta20 - Jogo do Ano]', 'Basilisco "
    "[Ameaças > Tormenta20 - Jogo do Ano]').\n"
    "3. **Mestre de Mesa:** Quando o usuário trouxer uma situação de jogo "
    "(encontro, dúvida de construção de personagem, regra de combate), use o "
    "contexto para resolver a situação citando a regra exata, e depois, se "
    "cabível, dê uma sugestão de mestre claramente marcada como tal.\n"
    "4. **Flexibilidade de Formato:** Quando o usuário solicitar um formato "
    "específico, respeite estritamente essa restrição de brevidade, mantendo "
    "obrigatoriamente a citação da fonte no formato Nome [Fonte].\n\n"
    "Contexto Técnico de Tormenta 20:\n{context}"
)

PROMPT_TRADUCAO = ChatPromptTemplate.from_messages([
    ("system",
     "Você é um REFORMULADOR DE TEXTO TÉCNICO especializado em Tormenta 20, "
     "não um assistente de RPG: sua única tarefa é converter a dúvida/pedido "
     "do usuário em UMA ÚNICA pergunta técnica fluida e natural em português, "
     "para consultar o compêndio de regras de Tormenta 20.\n\n"
     "VOCÊ NÃO ANALISA, NÃO RESPONDE E NUNCA SE RECUSA: pedido nenhum é "
     "proibido aqui, porque você apenas reescreve o texto em uma pergunta de "
     "busca interna — quem responde é outra etapa do sistema, com as regras "
     "abertas.\n\n"
     "REGRAS:\n"
     "1. NÃO crie listas de palavras soltas ou tags.\n"
     "2. Use a terminologia correta do sistema (ex: poderes, perícias, "
     "condições, testes de resistência, área de efeito, custo em PM).\n"
     "3. NUNCA adivinhe nem cite a resposta na pergunta: descreva apenas a "
     "dúvida com os termos do sistema — a própria busca encontra as regras "
     "reais na base.\n"
     "4. Exemplo de saída esperada: 'Quais as regras de flanco e cobertura "
     "em combate corpo a corpo em Tormenta 20?'\n"
     "5. Responda APENAS com a pergunta formulada, sem aspas e sem "
     "introduções.\n"
     "6. Se a entrada já for uma pergunta técnica clara, completa e "
     "autossuficiente, devolva-a praticamente intacta: preserve a estrutura, o "
     "verbo inicial e as palavras-chave (nomes próprios e termos técnicos). "
     "NÃO reescreva por reescrever — ex.: 'O que concede X?' NUNCA vira 'Quais "
     "as regras e efeitos de X?' — e não troque pergunta por rótulo de tópico."),
    ("human", "{queixa}")
])

# Etapa anterior a traducao: resolve pronomes e referencias ("desse monstro",
# "ele", "essa arma") usando o dialogo, para que a busca receba uma
# pergunta autossuficiente. Nao mexe no {context} nem no SYSTEM_PROMPT.
PROMPT_REFORMULACAO = ChatPromptTemplate.from_messages([
    ("system",
     "Você é exclusivamente um reformulador de termos de busca. "
     "NUNCA responda à pergunta do usuário, NUNCA gere listas de respostas. "
     "Sua única saída permitida é UMA pergunta interrogativa para busca técnica "
     "(ex: 'Quais as regras... ?').\n\n"
     "Dado o histórico da conversa e a nova pergunta do usuário, reescreva a pergunta "
     "para que ela seja independente e autossuficiente para uma busca vetorial. "
     "Se a pergunta for sobre um novo assunto, ignore o histórico. "
     "Responda APENAS com a pergunta reescrita, sem aspas e sem introduções."),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
])


# ---------------------------------------------------------------------------
# Memoria de longo prazo: resumo de sessoes de campanha
# ---------------------------------------------------------------------------
PROMPT_RESUMO_SESSAO = ChatPromptTemplate.from_messages([
    ("system",
     ("Você é um arquivista de campanhas de RPG. Leia o histórico da sessão e "
      "o relato final (fim de sessão, derrota, vitória etc.). Extraia um JSON "
      "estrito com as chaves: "
      "'campanha' (nome da campanha ou 'não informada'), "
      "'personagens' (lista envolvida na sessão), "
      '"assuntos_tratados" (lista: encontros, regras, decisões), '
      '"desfecho" (o relato do fim/resultado da sessão). '
      "NUNCA invente dados, use apenas o que está no histórico.\n"
      "Responda APENAS com o JSON puro, sem cercas de código e sem texto fora dele.")),
    ("human",
     ("HISTÓRICO DA SESSÃO:\n{historico}\n\n"
      "RELATO FINAL:\n{relato}")),
])


# ---------------------------------------------------------------------------
# Ingestao (Fase 2): fontes .ts -> chunks
# ---------------------------------------------------------------------------
# Rotulo legivel de cada export (vira a metadata `Tabela` e o primeiro nivel do
# prefixo de procedencia `[Tabela > Fonte]` exigido pelo SYSTEM_PROMPT).
ROTULO_TABELA: dict[str, str] = {
    "accessories": "Acessórios",
    "adventures": "Aventuras",
    "aharadak": "Dádivas de Aharadak",
    "alchemy": "Alquímicos",
    "ageComplications": "Complicações de Idade",
    "ageGroups": "Faixas Etárias",
    "animals": "Animais",
    "aparatos": "Aparatos",
    "armors": "Armaduras",
    "artifacts": "Artefatos",
    "attributes": "Atributos",
    "bosses": "Chefes",
    "classes": "Classes",
    "clothing": "Vestuário",
    "complications": "Complicações",
    "conditions": "Condições",
    "creatureSizeTable": "Tamanho de Criaturas",
    "creatureSizeTableFootnote": "Nota de Tamanho de Criaturas",
    "damageProgressionTable": "Progressão de Dano",
    "dangers": "Perigos",
    "difficulties": "Dificuldades de Teste",
    "difficultiesNote": "Nota de Dificuldades",
    "distinctions": "Distinções",
    "equipmentCategories": "Categorias de Equipamento",
    "esoteric": "Esotéricos",
    "extendedTests": "Testes Estendidos",
    "food": "Alimentos",
    "gear": "Equipamentos",
    "gods": "Deuses",
    "groupRoles": "Papéis no Grupo",
    "heroicGoals": "Objetivos Heroicos",
    "improvements": "Melhorias de Item",
    "initialMoneyTable": "Dinheiro Inicial",
    "liturgico": "Itens Litúrgicos",
    "materialPrices": "Preços de Materiais",
    "mounts": "Montarias",
    "music": "Instrumentos Musicais",
    "objectStats": "Atributos de Objetos",
    "organizations": "Organizações",
    "origins": "Origens",
    "partners": "Parceiros",
    "powerCategories": "Categorias de Poder",
    "priceImprovements": "Preços de Melhorias",
    "races": "Raças",
    "regreiroQAs": "Regreiro (Perguntas e Respostas)",
    "ruleSections": "Regras",
    "services": "Serviços",
    "skills": "Perícias",
    "spells": "Magias",
    "specialSituations": "Situações Especiais de Combate",
    "tesouros": "Tesouros",
    "threats": "Ameaças",
    "tool": "Ferramentas",
    "vehicles": "Veículos",
    "weapons": "Armas",
    "ACESSORIO_POR_GRAU": "Acessórios por Grau",
    "ACESSORIOS_MAIORES": "Acessórios Mágicos Maiores",
    "ACESSORIOS_MEDIOS": "Acessórios Mágicos Médios",
    "ACESSORIOS_MENORES": "Acessórios Mágicos Menores",
    "ARMADURAS_ESPECIFICAS": "Armaduras Específicas",
    "ARMADURAS_MAGICAS": "Armaduras Mágicas",
    "ARMAS_ESPECIFICAS": "Armas Específicas",
    "ARMAS_MAGICAS": "Armas Mágicas",
    "DIVERSO": "Itens Diversos",
    "EQUIPAMENTO_ARMA": "Armas",
    "EQUIPAMENTO_ARMADURA": "Armaduras",
    "EQUIPAMENTO_ESOTER": "Esotéricos",
    "EQUIPAMENTO_CATEGORIAS": "Categorias de Equipamento",
    "MAGICO_CATEGORIAS": "Categorias de Item Mágico",
    "POCOES": "Poções",
    "RIQUEZAS": "Riquezas",
    "SUPERIOR_ARMA": "Armas Superiores",
    "SUPERIOR_ARMADURA": "Armaduras Superiores",
    "SUPERIOR_CATEGORIAS": "Categorias de Item Superior",
    "SUPERIOR_ESOTER": "Esotéricos Superiores",
    "powersArcanista": "Poderes (Arcanista)",
    "powersBarbaro": "Poderes (Bárbaro)",
    "powersBardo": "Poderes (Bardo)",
    "powersBucaneiro": "Poderes (Bucaneiro)",
    "powersCacador": "Poderes (Caçador)",
    "powersCavaleiro": "Poderes (Cavaleiro)",
    "powersClerigo": "Poderes (Clérigo)",
    "powersDruida": "Poderes (Druida)",
    "powersFrade": "Poderes (Frade)",
    "powersGerais": "Poderes Gerais",
    "powersGeraisConcedido": "Poderes Concedidos",
    "powersGeraisDestino": "Poderes de Destino",
    "powersGeraisGrupo": "Poderes de Grupo",
    "powersGeraisMagia": "Poderes de Magia",
    "powersGeraisRaca": "Poderes de Raça",
    "powersGeraisTormenta": "Poderes da Tormenta",
    "powersGuerreiro": "Poderes (Guerreiro)",
    "powersInventor": "Poderes (Inventor)",
    "powersLadino": "Poderes (Ladino)",
    "powersLutador": "Poderes (Lutador)",
    "powersMistico": "Poderes (Místico)",
    "powersNobre": "Poderes (Nobre)",
    "powersPaladino": "Poderes (Paladino)",
    "powersSamurai": "Poderes (Samurai)",
    "powersTreinador": "Poderes (Treinador)",
    "powersVampiro": "Poderes (Vampiro)",
    "enchantments": "Encantamentos",
    "specificWeapons": "Itens Mágicos Específicos",
}

# O mesmo nome de export se repete em arquivos diferentes (5 `enchantments`,
# 3 `specificWeapons`...): aqui o rotulo vem do PAR arquivo+export.
ROTULO_TABELA_POR_ARQUIVO: dict[tuple[str, str], str] = {
    ("acessorios.ts", "enchantments"): "Encantamentos de Acessórios",
    ("curseds.ts", "enchantments"): "Encantamentos Amaldiçoados",
    ("magicarmor.ts", "enchantments"): "Encantamentos de Armaduras",
    ("magicesoterics.ts", "enchantments"): "Encantamentos de Esotéricos",
    ("magics.ts", "enchantments"): "Encantamentos de Itens Mágicos",
    ("magicarmor.ts", "specificWeapons"): "Armas Mágicas Específicas",
    ("magicesoterics.ts", "specificWeapons"): "Esotéricos Mágicos Específicos",
    ("magics.ts", "specificWeapons"): "Itens Mágicos Específicos",
    ("equipamentos.ts", "equipmentCategories"): "Categorias de Equipamento",
    ("itensmagicos.ts", "equipmentCategories"): "Categorias de Item Mágico",
}

# Campo do registro -> rotulo em portugus no texto indexado.
ROTULOS: dict[str, str] = {
    "ability": "Habilidade",
    "abilities": "Habilidades",
    "admission": "Admissão",
    "age": "Idade",
    "areasOfInfluence": "Áreas de Influência",
    "Arma": "Arma",
    "Armadura Leve": "Armadura Leve",
    "Armadura Pesada": "Armadura Pesada",
    "attribute": "Atributo",
    "attributeModifiers": "Modificadores de Atributo",
    "attributes": "Atributos",
    "attack": "Ataque",
    "benefit": "Benefício",
    "benefits": "Benefícios",
    "beliefs": "Crenças",
    "cd": "CD",
    "cdIncrease": "Aumento de CD",
    "channelEnergy": "Canalizar Energia",
    "churchAndClergy": "Igreja e Clero",
    "circle": "Círculo",
    "cookingCost": "Custo de Preparo",
    "cookingDC": "CD de Preparo",
    "complexity": "Complexidade",
    "conclusion": "Conclusão",
    "content": "Conteúdo",
    "critical": "Crítico",
    "damage": "Dano",
    "defenseBonus": "Bônus de Defesa",
    "defesa": "Defesa",
    "degree": "Grau",
    "delivery": "Entrega",
    "density": "Densidade",
    "description": "Descrição",
    "description_arma": "Descrição (arma)",
    "description_armadura": "Descrição (armadura)",
    "description_escudo": "Descrição (escudo)",
    "description_esoterico": "Descrição (esotérico)",
    "deslocamento": "Deslocamento",
    "devotos": "Devotos",
    "devotees": "Devotos",
    "dinheiro": "Dinheiro",
    "duration": "Duração",
    "effect": "Efeito",
    "effects": "Efeitos",
    "Efeito": "Efeito",
    "enhancements": "Aprimoramentos",
    "Escudo": "Escudo",
    "Esotéricos": "Esotéricos",
    "example": "Exemplo",
    "examples": "Exemplos",
    "exemplos": "Exemplos",
    "execution": "Execução",
    "extras": "Extras",
    "famousExamples": "Exemplos famosos",
    "for": "Força",
    "des": "Destreza",
    "con": "Constituição",
    "int": "Inteligência",
    "sab": "Sabedoria",
    "car": "Carisma",
    "fort": "Fortitude",
    "ref": "Reflexos",
    "von": "Vontade",
    "functions": "Funções",
    "grantedPowers": "Poderes concedidos",
    "grip": "Empunhadura",
    "habilidades": "Habilidades",
    "history": "História",
    "iniciativa": "Iniciativa",
    "ingredient": "Ingrediente",
    "ingredients": "Ingredientes",
    "label": "Rótulo",
    "level": "Nível",
    "levelProgression": "Progressão por nível",
    "longevidade": "Longevidade",
    "lore": "Lóre",
    "magnus": "Magnum",
    "mark": "Marca",
    "materia": "Matéria",
    "material": "Material",
    "max": "Máximo",
    "mecanica": "Mecânica",
    "membros": "Membros",
    "min": "Mínimo",
    "mod": "Modificador",
    "modifiers": "Modificadores",
    "money": "Dinheiro",
    "motivations": "Motivações",
    "obligationsRestrictions": "Obrigações e restrições",
    "otherNames": "Outros nomes",
    "penalty": "Penalidade",
    "percepcao": "Percepção",
    "pericias": "Perícias",
    "pm": "PM",
    "poderes": "Poderes",
    "powers": "Poderes",
    "preco": "Preço",
    "price": "Preço",
    "priceIncrease": "Aumento de preço",
    "prerequisite": "Requisito",
    "proficiency": "Proficiência",
    "purpose": "Propósito",
    "question": "Pergunta",
    "range": "Alcance",
    "rank": "Grau",
    "relationships": "Relações",
    "resistance": "Resistência",
    "resistenciaDano": "Resistência a dano",
    "result": "Resultado",
    "sacredSymbol": "Símbolo sagrado",
    "school": "Escola",
    "sections": "Seções",
    "skills": "Perícias",
    "spaceAndReach": "Espaço e alcance",
    "spaces": "Espaços",
    "stealthAndManeuverModifier": "Modificador de furtividade e manobra",
    "status": "Status",
    "subtitle": "Subtítulo",
    "successes": "Sucessos",
    "summary": "Resumo",
    "target": "Alvo",
    "tema": "Tema",
    "tesouro": "Tesouro",
    "tipo": "Tipo",
    "type": "Tipo",
    "trainedOnly": "Somente treinada",
    "uniquePower": "Poder único",
    "valor": "Valor",
    "value": "Valor",
    "answer": "Resposta",
    "armorPenalty": "Penalidade de armadura",
    "ataqueCorpoACorpo": "Ataque corpo a corpo",
    "ataqueDistancia": "Ataque à distância",
    "category": "Categoria",
    "dicas": "Dicas",
    "difficulty": "Dificuldade",
    "encanto": "Encanto",
    "equips": "Equipamentos",
    "equipamentos": "Equipamentos",
    "fonte": "Fonte",
    "forca": "Força",
    "habilidade": "Habilidade",
    "historia": "História",
    "howToAcquire": "Como obter",
    "nd": "ND",
    "note": "Nota",
    "obligations": "Obrigações",
    "origin": "Fonte",
    "papel": "Papel",
    "pv": "PV",
    "reaction": "Reação",
    "req": "Requisito",
    "resist": "Resistência",
    "source": "Fonte",
    "space": "Espaço",
    "tamanho": "Tamanho",
    "treasure": "Tesouro",
    "when": "Quando",
    "size": "Tamanho",
    "progression": "Progressão",
    "race": "Raça",
    "requirements": "Requisitos",
    "scope": "Escopo",
    "service": "Serviço",
    "speed": "Velocidade",
    "title": "Título",
    "topic": "Tópico",
    "trigger": "Gatilho",
    "usage": "Uso",
    "weight": "Peso",
    "cost": "Custo",
    "modifier": "Modificador",
    "efeito": "Efeito",
    "iniciante": "Iniciante",
    "veterano": "Veterano",
    "mestre": "Mestre",
    "preferredWeapon": "Arma Preferida",
    "items": "Itens",
    "itens": "Itens",
    "magazineNumber": "Número da Revista",
    "theme": "Tema",
    "introduction": "Introdução",
    "intro": "Introdução",
    "step": "Etapa",
    "characteristics": "Características",
    "pvBase": "PV Base",
    "pvPerLevel": "PV por Nível",
    "pmPerLevel": "PM por Nível",
    "mandatory": "Obrigatórias",
    "optional": "Opcionais",
    "count": "Quantidade",
    "subAbilities": "Subhabilidades",
    "rd": "RD",
    "significantColors": "Cores Significativas",
    "motto": "Lema",
    "comoUsar": "Como Usar",
    "kind": "Tipo",
    "menor": "Menor",
    "maior": "Maior",
    "media": "Média",
    "medio": "Médio",
    "condition": "Condição",
    "def": "Defesa",
    "extra": "Extra",
    "archetype": "Arquétipo",
    "task": "Tarefa",
    "abbreviation": "Abreviação",
    "table": "Tabela",
    "headers": "Cabeçalhos",
    "rows": "Linhas",
    "footer": "Rodapé",
    "attacker": "Atacante",
    "geral": "Geral",
    "equipamento": "Equipamento",
}

# Campo ignorado no texto indexado (ruido de UI) — o que importa ja vira
# metadata (`Fonte`, `Nome`, `Tabela`, `Tipo`).
IGNORAR_CAMPOS = {
    "id", "image", "images", "icon", "color", "href", "slug", "powersUrl",
    "name", "title", "question", "__regiao",
    "origin", "source", "fonte",
}


def _rotulo(campo: str) -> str:
    if campo.isdigit():
        return ""
    return ROTULOS.get(campo) or re.sub(r"(?<!^)(?=[A-Z])", " ", campo).replace("_", " ").strip()


def _linha(campo: str, valor) -> str:
    rotulo = _rotulo(campo)
    texto = _resumo(valor)
    return f"{rotulo}: {texto}" if rotulo else texto


def _rotulo_tabela(arquivo: str, export: str) -> str:
    return (
        ROTULO_TABELA_POR_ARQUIVO.get((arquivo, export))
        or ROTULO_TABELA.get(export)
        or _rotulo(export)
    )


def _extrair_fonte_ts(verbose: bool = True) -> dict:
    """Roda o extrator Node sobre os .ts e devolve os registros em JSON."""
    if not os.path.isdir(PASTA_DADOS):
        raise NotImplementedError(
            f"Pasta de dados nao encontrada: {PASTA_DADOS}\n"
            "  Esperado o repositorio do app aTormenta como irmão de "
            "RAG-Tormenta20 (ou ajuste PASTA_DADOS em rag_core.py)."
        )
    if shutil.which("node") is None:
        raise NotImplementedError(
            "Node.js nao encontrado no PATH — a extracao dos .ts precisa dele "
            "(uma unica vez por ingestao). Instale o Node 20+ e rode de novo."
        )
    if verbose:
        print(f"Extraindo registros de {PASTA_DADOS} ...")
    proc = subprocess.run(
        ["node", FERRAMENTA_TS, "--dir", PASTA_DADOS],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        raise NotImplementedError(
            f"Extrator TS falhou (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    if verbose and proc.stderr.strip():
        print(f"  {proc.stderr.strip()}")
    dados = json.loads(proc.stdout)
    for aviso in dados.get("avisos", []):
        print(f"  ⚠️  {aviso}")
    return dados


def _fonte_do_registro(reg: dict) -> str:
    """Procedencia do registro: campo `origin` > `source` > `//#region`."""
    for campo in ("origin", "source", "__regiao"):
        valor = str(reg.get(campo) or "").strip()
        if valor:
            return valor
    return "Compendio T20"


def _nome_do_registro(reg: dict) -> str:
    for campo in ("name", "title", "question", "task", "id"):
        valor = reg.get(campo)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


def _resumo(valor) -> str:
    """Versao em uma linha de um valor arbitrario (usado em campos aninhados)."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        return " ".join(valor.split())
    if isinstance(valor, list):
        return ", ".join(p for p in (_resumo(v) for v in valor) if p)
    if isinstance(valor, dict):
        partes = [
            _linha(k, v)
            for k, v in valor.items()
            if k not in IGNORAR_CAMPOS and _resumo(v)
        ]
        return "; ".join(partes)
    return str(valor)


def _com_bloco(texto: str, com_bullet: bool) -> str:
    linhas = [l for l in texto.split("\n")]
    if not com_bullet:
        return texto
    return "- " + linhas[0] + "".join("\n  " + l for l in linhas[1:])


def _renderar_item(item) -> tuple[str, bool]:
    """(texto, e_bloco): bloco = paragrafo solto, sem bullet de lista."""
    if not isinstance(item, dict):
        return _resumo(item), False
    campos = {k: v for k, v in item.items() if k not in IGNORAR_CAMPOS}
    # blocos narrativos de aventuras: {type, content}
    if set(campos) <= {"type", "content", "speaker", "title", "subtitle"}:
        tipo = str(campos.get("type") or "")
        conteudo = campos.get("content") or campos.get("title") or campos.get("subtitle")
        if tipo == "break" or not conteudo:
            return "", False
        if tipo == "subtitle":
            return f"## {conteudo}", True
        if tipo in {"quote", "dialog"}:
            return "> " + str(conteudo), True
        if tipo == "text" or set(campos) == {"type", "content"}:
            return str(conteudo), True
    nome = _resumo(
        next(
            (campos[k] for k in ("name", "title", "label", "task", "cost", "age", "rank")
             if campos.get(k) is not None),
            None,
        )
    )
    if "level" in campos and not nome:
        nome = f"Nível {campos['level']}"
    corpo = _resumo(
        next(
            (campos[k] for k in ("description", "effect", "content", "text",
                                 "answer", "example", "benefit", "abilities")
             if campos.get(k) is not None),
            None,
        )
    )
    linhas = []
    if nome and corpo and corpo != nome:
        linhas.append(f"{nome} — {corpo}")
    elif corpo:
        linhas.append(corpo)
    elif nome:
        linhas.append(nome)
    extras = [
        _linha(k, v)
        for k, v in campos.items()
        if v is not None and not isinstance(v, (list, dict))
        and k not in {"level"}
        and _resumo(v) not in {nome, corpo}
    ]
    if extras:
        linhas.append(" · ".join(extras))
    aninhados = []
    for k, v in campos.items():
        if isinstance(v, list) and v:
            itens = []
            for sub in v:
                texto_sub, bloco_sub = _renderar_item(sub)
                if texto_sub:
                    itens.append(texto_sub if bloco_sub else _com_bloco(texto_sub, True))
            if itens:
                aninhados.append("\n".join(itens))
        elif isinstance(v, dict) and v:
            aninhados.append(_linha(k, v))
    if aninhados:
        linhas.append("\n".join(aninhados))
    return "\n".join(l for l in linhas if l), False


def _renderar_campo(rotulo: str, valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            return ""
        if "\n" in texto or len(texto) > 400:
            return f"{rotulo}:\n{texto}" if rotulo else texto
        return f"{rotulo}: {texto}"
    if not isinstance(valor, (list, dict)):
        return f"{rotulo}: {_resumo(valor)}" if rotulo else _resumo(valor)
    if isinstance(valor, dict):
        linhas = [
            _com_bloco(_linha(k, v), True)
            for k, v in valor.items()
            if k not in IGNORAR_CAMPOS and v is not None and _resumo(v)
        ]
        if not linhas:
            return ""
        cabecalho = f"{rotulo}:" if rotulo else ""
        return (cabecalho + "\n" if cabecalho else "") + "\n".join(linhas)
    blocos = []
    for item in valor:
        texto, solto = _renderar_item(item)
        if not texto:
            continue
        blocos.append(texto if solto else _com_bloco(texto, True))
    if not blocos:
        return ""
    cabecalho = f"{rotulo}:" if rotulo else ""
    return (cabecalho + "\n" if cabecalho else "") + "\n".join(blocos)


def _formatar_registro(reg: dict) -> str:
    """Registro -> texto legivel (o que o retriever realmente indexa)."""
    partes: list[str] = []
    nome = _nome_do_registro(reg)
    if nome and len(nome) < 200:
        partes.append(f"# {nome}")
    if "__valor" in reg:
        bruto = reg["__valor"]
        texto = bruto.strip() if isinstance(bruto, str) else _renderar_campo("", bruto)
        if texto:
            partes.append(texto)
    else:
        for campo, valor in reg.items():
            if campo in IGNORAR_CAMPOS or (
                nome and isinstance(valor, str) and valor.strip() == nome
            ):
                continue
            bloco = _renderar_campo(_rotulo(campo), valor)
            if bloco:
                partes.append(bloco)
    return "\n\n".join(p for p in partes if p).strip()


def _dividir(texto: str, tamanho: int) -> list[str]:
    """Parte um bloco gigante e cola pedacos minusculos no vizinho.

    O splitter recursivo chega a devolver so o rotulo (`História:`, `Dicas:`)
    quando a linha seguinte ja extrapola; um fragmento desse vira chunk orfao.
    """
    divisor = RecursiveCharacterTextSplitter(
        chunk_size=tamanho,
        chunk_overlap=min(CHUNK_OVERLAP, max(tamanho // 4, 1)),
    )
    brutos = [p.strip() for p in divisor.split_text(texto) if p.strip()]
    pedacos: list[str] = []
    indice = 0
    while indice < len(brutos):
        atual = brutos[indice]
        while len(atual) < 100 and indice + 1 < len(brutos):
            atual = atual + "\n\n" + brutos[indice + 1]
            indice += 1
        pedacos.append(atual)
        indice += 1
    if len(pedacos) > 1 and len(pedacos[-1]) < 100:
        ultimo = pedacos.pop()
        pedacos[-1] = pedacos[-1] + "\n\n" + ultimo
    return pedacos


def _fatiar(texto: str) -> list[str]:
    """Quebra o texto por paragrafo, sem deixar cabecalho orfao.

    Os paragrafos vao sendo encaixados ate estourar o limite; quando o proximo
    nao cabe e o pendente e minusculo (ex.: `# Nome`), ele cola no inicio do
    proximo bloco em vez de virar um chunk de uma linha.
    """
    if len(texto) <= CHUNK_SIZE:
        return [texto]
    saida: list[str] = []
    pendente: list[str] = []
    tamanho = 0

    def _fechar() -> None:
        nonlocal pendente, tamanho
        if pendente:
            saida.append("\n\n".join(pendente))
            pendente, tamanho = [], 0

    for bruto in texto.split("\n\n"):
        paragrafo = bruto.strip()
        if not paragrafo:
            continue
        if pendente and tamanho + len(paragrafo) + 2 > CHUNK_SIZE:
            espaco = CHUNK_SIZE - tamanho - 2
            if len("\n\n".join(pendente)) < 100 and espaco >= CHUNK_SIZE // 2:
                pedacos = _dividir(paragrafo, espaco)
                pendente.append(pedacos.pop(0))
                _fechar()
                saida.extend(pedacos)
                continue
            _fechar()
        if len(paragrafo) > CHUNK_SIZE:
            saida.extend(_dividir(paragrafo, CHUNK_SIZE))
            continue
        pendente.append(paragrafo)
        tamanho += len(paragrafo) + 2
    _fechar()
    if len(saida) > 1 and len(saida[-1]) < 100:
        ultimo = saida.pop()
        saida[-1] = saida[-1] + "\n\n" + ultimo
    return saida or [texto]


def montar_chunks(verbose: bool = True) -> list[Document]:
    """Le os .ts do aTormenta e devolve os blocos indexaveis.

    Cada registro vira um `Document`: `page_content` e o registro renderizado
    (texto legivel, nao JSON) e a metadata carrega Tabela/Fonte/Tipo/Nome,
    usadas pelo filtro, pelo BM25, pelo rerank e pela citacao `Nome [Fonte]`.
    """
    dados = _extrair_fonte_ts(verbose=verbose)
    chunks: list[Document] = []
    contagem: Counter = Counter()
    fontes: Counter = Counter()
    vazios = 0
    fatiados = 0

    for tabela_json in dados["tabelas"]:
        arquivo = tabela_json["arquivo"]
        export = tabela_json["export"]
        tabela = _rotulo_tabela(arquivo, export)
        for reg in tabela_json["elementos"]:
            corpo = _formatar_registro(reg)
            if not corpo:
                vazios += 1
                continue
            fonte = _fonte_do_registro(reg)
            nome = _nome_do_registro(reg)
            tipo = str(reg.get("type") or reg.get("tipo") or "")
            metadata = {
                "Tabela": tabela,
                "Fonte": fonte,
                "Tipo": tipo,
                "Nome": nome,
                "id": str(reg.get("id") or ""),
                "arquivo": arquivo,
                "export": export,
            }
            partes = _fatiar(corpo)
            if len(partes) > 1:
                fatiados += 1
            for parte in partes:
                chunks.append(Document(page_content=parte, metadata=dict(metadata)))
            contagem[tabela] += 1
            fontes[fonte] += 1

    if verbose:
        print(
            f"  registros: {sum(contagem.values())} em {len(contagem)} tabelas"
            f" | vazios: {vazios} | divididos: {fatiados}"
        )
        print(
            "  maiores tabelas: "
            + " · ".join(f"{t} ({n})" for t, n in contagem.most_common(6))
        )
        print(
            "  fontes: "
            + " · ".join(f"{f} ({n})" for f, n in fontes.most_common(6))
        )

    antes = len(chunks)
    chunks = mesclar_pequenos(chunks)
    if verbose:
        print(
            f"  blocos: {antes} -> {len(chunks)} após fusão de pequenos "
            f"({antes - len(chunks)} anexados ao vizinho)"
        )

    for doc in chunks:
        doc.page_content = (
            f"[{doc.metadata['Tabela']} > {doc.metadata['Fonte']}]\n"
            + doc.page_content
        )

    if verbose:
        com_prefixo = sum(1 for d in chunks if d.page_content.startswith("["))
        print(f"  com prefixo de procedencia: {com_prefixo}/{len(chunks)}")
    return chunks


def mesclar_pequenos(chunks: list[Document], limite: int = 100) -> list[Document]:
    """Gruda blocos minusculos no vizinho, para nao perderem conteudo.

    Generico: dois blocos sao vizinhos do mesmo pedaco se compartilham a
    metadata de hierarquia (mesmos valores ou ambos ausentes) e a soma ainda
    cabe em CHUNK_SIZE.
    """
    def _chaves(doc: Document) -> tuple:
        return tuple(
            sorted((k, str(v)) for k, v in doc.metadata.items()
                   if k in ("Fonte", "Tabela", "Tipo", "categoria"))
        )

    docs = list(chunks)
    saida: list[Document] = []
    i = 0
    while i < len(docs):
        atual = docs[i]
        if len(atual.page_content) < limite:
            prox = docs[i + 1] if i + 1 < len(docs) else None
            if prox is not None and _chaves(atual) == _chaves(prox) and \
                    len(atual.page_content) + len(prox.page_content) + 2 <= CHUNK_SIZE:
                prox.page_content = (
                    atual.page_content.rstrip() + "\n\n" + prox.page_content.lstrip()
                )
                i += 1
                continue
            if saida and _chaves(saida[-1]) == _chaves(atual) and \
                    len(saida[-1].page_content) + len(atual.page_content) + 2 <= CHUNK_SIZE:
                saida[-1].page_content = (
                    saida[-1].page_content.rstrip() + "\n\n" + atual.page_content.lstrip()
                )
                i += 1
                continue
        saida.append(atual)
        i += 1
    return saida


# ---------------------------------------------------------------------------
# Conexao Qdrant
# ---------------------------------------------------------------------------
_CONEXAO_CACHE: dict | None = None


def escolher_conexao_qdrant() -> dict:
    """Usa o Qdrant do docker (com dashboard) se QDRANT_URL responder; senao, local.

    Sondada 1x por processo: repetir a chamada devolve o mesmo dict sem
    reimprimir os prints de diagnóstico.
    """
    global _CONEXAO_CACHE
    if _CONEXAO_CACHE is not None:
        return _CONEXAO_CACHE
    if QDRANT_URL:
        try:
            teste = QdrantClient(url=QDRANT_URL, timeout=5)
            teste.get_collections()
            if hasattr(teste, "close"):
                teste.close()
            print(f"🔗 Qdrant servidor: {QDRANT_URL}")
            print(f"   Dashboard: {QDRANT_URL}/dashboard")
            _CONEXAO_CACHE = {"url": QDRANT_URL}
            return _CONEXAO_CACHE
        except Exception as erro:
            print(f"⚠️  Qdrant servidor em {QDRANT_URL} indisponível ({erro.__class__.__name__}).")
            print("   Suba o container com `make qdrant-up` — usando armazenamento local.")
    print(f"💾 Qdrant embutido: {PASTA_QDRANT}")
    _CONEXAO_CACHE = {"path": PASTA_QDRANT}
    return _CONEXAO_CACHE


_EMBEDDINGS_CACHE: HuggingFaceEmbeddings | None = None


def obter_embeddings() -> HuggingFaceEmbeddings:
    """Instância única do modelo de embeddings (carregada 1x por processo)."""
    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is None:
        _EMBEDDINGS_CACHE = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDING)
    return _EMBEDDINGS_CACHE


def reindexar_solicitado() -> bool:
    """REINDEXAR=1 ./.venv/bin/python meu_primeiro_rag.py — default: off."""
    return os.environ.get("REINDEXAR", "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _tamanho_vetor(cliente: QdrantClient, colecao: str) -> int:
    """Dimensão dos vetores de uma coleção (anônima ou nomeada)."""
    vetores = cliente.get_collection(colecao).config.params.vectors
    if isinstance(vetores, dict):
        vetores = next(iter(vetores.values()))
    return vetores.size


def garantir_colecao_historico(cliente: QdrantClient) -> None:
    """Cria (ou valida) a coleção de sessões arquivadas, idempotente.

    O tamanho do vetor vem da coleção principal; se ela ainda não existir
    (primeira execução), usa a dimensão dos embeddings atuais — o mesmo
    valor que o langchain usará ao criar a principal. Divergência de tamanho
    (troca de modelo de embedding) recria a coleção: vetor incompatível não
    tem como ser recuperado. O REINDEXAR=1 NÃO mexe aqui (dado derivado).
    """
    embeddings = obter_embeddings()
    existentes = [c.name for c in cliente.get_collections().collections]
    tamanho: int | None = None
    if COLECAO in existentes:
        tamanho = _tamanho_vetor(cliente, COLECAO)

    if COLECAO_HISTORICO in existentes:
        atual = _tamanho_vetor(cliente, COLECAO_HISTORICO)
        if tamanho is None or atual == tamanho:
            return
        cliente.delete_collection(COLECAO_HISTORICO)
        print(f"⚠️  '{COLECAO_HISTORICO}' tinha {atual} dims (esperado {tamanho}) — recriando.")

    if tamanho is None:
        tamanho = len(embeddings.embed_query("probe"))
    cliente.create_collection(
        collection_name=COLECAO_HISTORICO,
        vectors_config=models.VectorParams(size=tamanho, distance=models.Distance.COSINE),
    )
    print(f"📚 Coleção '{COLECAO_HISTORICO}' pronta ({tamanho} dims, coseno) — memória de longo prazo.")


def preparar_colecao(
    conexao: dict,
    chunks: list[Document],
    cliente: QdrantClient | None = None,
) -> QdrantVectorStore:
    """Apaga (so se REINDEXAR=1), carrega ou indexa a colecao.

    `cliente` opcional: quando informado pelo chat, é o cliente ÚNICO da
    sessão (o Qdrant embutido só admite um client aberto por path) e ele
    também vira o client da store. Sem ele, o comportamento é o de antes.
    """
    embeddings = obter_embeddings()
    proprio = cliente is None
    if proprio:
        cliente = QdrantClient(**conexao)
    try:
        existentes = [c.name for c in cliente.get_collections().collections]
        total_pontos = 0
        if COLECAO in existentes:
            total_pontos = cliente.get_collection(COLECAO).points_count
        if reindexar_solicitado() and COLECAO in existentes:
            cliente.delete_collection(COLECAO)
            print(f"🗑️  REINDEXAR=1 — coleção '{COLECAO}' apagada ({total_pontos} pontos).")
            existentes.remove(COLECAO)
        # Segunda coleção (sessões arquivadas) validada na mesma janela do client.
        garantir_colecao_historico(cliente)
    finally:
        if proprio and hasattr(cliente, "close"):
            cliente.close()

    if COLECAO in existentes:
        print(f"⚡ Coleção '{COLECAO}' já existe com {total_pontos} pontos — carregando...")
        print("   Para reindexar do zero: REINDEXAR=1 ./.venv/bin/python meu_primeiro_rag.py")
        if not proprio:
            return QdrantVectorStore(
                client=cliente, collection_name=COLECAO, embedding=embeddings
            )
        return QdrantVectorStore.from_existing_collection(
            embedding=embeddings,
            collection_name=COLECAO,
            **conexao,
        )

    print(f"📦 Criando coleção '{COLECAO}' com {len(chunks)} blocos...")
    if not proprio:
        dim = len(embeddings.embed_query("probe"))
        cliente.create_collection(
            collection_name=COLECAO,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        store = QdrantVectorStore(
            client=cliente, collection_name=COLECAO, embedding=embeddings
        )
        store.add_documents(chunks)
        return store
    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLECAO,
        **conexao,
    )


# ---------------------------------------------------------------------------
# Recuperacao hibrida + rerank
# ---------------------------------------------------------------------------
def montar_retriever(
    chunks: list[Document],
    conexao: dict | None = None,
    verbose: bool = True,
    cliente: QdrantClient | None = None,
) -> ContextualCompressionRetriever:
    """Qdrant -> BM25 -> ensemble 0.5/0.5 -> CohereRerank."""
    if conexao is None:
        conexao = escolher_conexao_qdrant()

    if verbose:
        print("Configurando embeddings multilingues locais...")
    vectorstore = preparar_colecao(conexao, chunks, cliente=cliente)

    retriever_vetorial = vectorstore.as_retriever(search_kwargs={"k": 50})

    if verbose:
        print("Criando índice de termos exatos (BM25)...")
    retriever_palavra_chave = BM25Retriever.from_documents(chunks)
    retriever_palavra_chave.k = 50

    retriever_hibrido = EnsembleRetriever(
        retrievers=[retriever_vetorial, retriever_palavra_chave],
        weights=[0.5, 0.5],
    )

    if verbose:
        print("Configurando o Filtro de Qualidade (Reranker)...")
    return ContextualCompressionRetriever(
        base_compressor=CohereRerank(top_n=8, model=MODELO_RERANK),
        base_retriever=retriever_hibrido,
    )


def recuperar(
    retriever: ContextualCompressionRetriever,
    consulta: str,
    consulta_real: str | None = None,
) -> list[Document]:
    """Ensemble (BM25+denso) com `consulta`; rerank com `consulta` + `consulta_real`.

    O CohereRerank mede query×documento e erra quando depende de UMA redação:
    só a reformulada, 'Dom do Psicopompo' caía para a 19ª posição (fora do
    top-8); só a original, 'Perícias', 'Símbolo sagrado' e 'Cavalo' saíam.
    A query de rerank junta as duas formulações (técnica + intenção do
    usuário) e o recall do ensemble fica intacto. `consulta_real` deve ser
    autossuficiente (sem anafórico do histórico).
    """
    docs = retriever.base_retriever.invoke(consulta)
    consulta_rerank = consulta
    if consulta_real and consulta_real.strip() and consulta_real != consulta:
        consulta_rerank = f"{consulta} {consulta_real}"
    return retriever.base_compressor.compress_documents(docs, consulta_rerank)


def montar_cadeia_resposta(system_prompt: str, llm, com_historico: bool = False):
    """Só a síntese (prompt + stuff documents), SEM retriever.

    Quem ja buscou os docs (etapa 3 do chat) invoca direto com
    `{"input": <entrada do usuario>, "context": docs, ...}` — assim a busca
    fica livre para usar a pergunta reformulada enquanto a síntese responde a
    entrada REAL do usuario (formatos: 'liste em 3 colunas' etc.).

    `system_prompt` entra intacto (Regra anti-alucinação). O histórico, quando
    existe, vira apenas mensagens intermediárias para o tom do diálogo — nunca
    substitui nem altera o SYSTEM_PROMPT, nem injeta `{context}`.
    """
    mensagens = [("system", system_prompt)]
    if com_historico:
        mensagens.append(("placeholder", "{chat_history}"))
    mensagens.append(("human", "{input}"))

    prompt = ChatPromptTemplate.from_messages(mensagens)
    return create_stuff_documents_chain(llm, prompt)


def montar_rag_chain(retriever, system_prompt: str, llm, com_historico: bool = False):
    """Encadeia o retriever ao chain de resposta final.

    Usado pelo avaliar.py (one-shot: a MESMA pergunta alimenta busca e
    síntese). O chat (meu_primeiro_rag.py) usa montar_cadeia_resposta.
    """
    cadeia = montar_cadeia_resposta(system_prompt, llm, com_historico)
    return create_retrieval_chain(retriever, cadeia)


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
class ChatComFallback(BaseChatModel):
    """Um unico objeto LLM com tres bases: NVIDIA, Groq e OpenRouter, em ordem.

    `trocar_modelo()` so troca o campo `model_name`; quem escolhe a base/chave e
    o provedor dono daquele modelo. Assim quem ja segura o objeto (cadeias ja
    montadas: `PROMPT | llm`, `rag_chain`) continua valido sem remontar nada.
    """

    model_name: str = MODELOS_GRATUITOS[0]
    temperature: float = 0

    _ultimo_provedor: str | None = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        return "com-fallback"

    @property
    def provedor(self) -> str:
        return PROVEDOR_DO_MODELO.get(self.model_name, "openrouter")

    def _cliente(self) -> ChatOpenAI:
        provedor = self.provedor
        if provedor != self._ultimo_provedor:
            if self._ultimo_provedor is not None:
                print(f"  🔁 LLM trocando de provedor: "
                      f"{self._ultimo_provedor} -> {provedor} ({self.model_name})")
            self._ultimo_provedor = provedor

        if provedor == "nvidia":
            variavel, base = "NVIDIA_API_KEY", URL_NVIDIA
        elif provedor == "groq":
            variavel, base = "GROQ_API_KEY", URL_GROQ
        else:
            variavel, base = "OPENROUTER_API_KEY", URL_OPENROUTER

        chave = os.environ.get(variavel, "").strip()
        if not chave:
            raise RuntimeError(f"{variavel} ausente (veja o .env)")
        extra: dict = {}
        if provedor == "nvidia":
            # Pensar na NVIDIA gera ~1.800 tokens de reasoning antes da
            # resposta e estourava o timeout em contexto grande; desligado,
            # responde em segundos com o content ja final.
            extra = {"extra_body": {"chat_template_kwargs": {"thinking": False}}}
        elif provedor == "groq" and self.model_name == "openai/gpt-oss-20b":
            # Sem isso o reasoning padrao estoura o cap de 2048 tokens de
            # saida do Groq e o content volta VAZIO (finish=length) — falha
            # silenciosa no RAG. low responde em ~0,3s com content final.
            extra = {"extra_body": {"reasoning_effort": "low"}}
        elif provedor == "groq" and self.model_name == "qwen/qwen3.8-27b":
            # OTPM do qwen no Free tier e ~1K tokens/min: sem teto proprio o
            # Groq avalia o output esperado e pode mandar 429 "Request too
            # large ... reduce max_tokens". 900 cabe na janela e ainda e
            # folga pra uma sintese em tabela/topicos.
            extra = {"max_tokens": 900}
        return ChatOpenAI(
            model_name=self.model_name,
            temperature=self.temperature,
            openai_api_base=base,
            openai_api_key=chave,
            # Free tier chega a travar >90s em modelo pesado; 120s cobre o
            # reasoning dos demais sem prender o fallback por muito tempo.
            request_timeout=120,
            max_retries=0,
            **extra,
        )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        # Cliente interno chamado SEM callbacks: o run externo ja e reportado
        # pelo proprio BaseChatModel e aninhar handlers duplicaria a contagem
        # de tokens no get_openai_callback (2x em cada chamada).
        return self._cliente()._generate(messages, stop=stop, **kwargs)


def criar_llm() -> ChatComFallback:
    """NVIDIA primeiro; se a cota/key falhar, a lista cai no Groq e depois no OpenRouter."""
    return ChatComFallback(model_name=MODELOS_GRATUITOS[0], temperature=0)


def trocar_modelo(llm, modelo: str) -> None:
    campo = "model" if "model" in type(llm).model_fields else "model_name"
    setattr(llm, campo, modelo)


def reformular_pergunta(query_atual: str, chat_history: list, llm=None) -> str:
    """Reescreve a pergunta usando o diálogo, para a busca não depender de contexto.

    Sem histórico devolve a própria pergunta — zero chamadas de LLM, o que deixa
    o caminho do avaliar.py (one-shot) identico ao do chat.
    Qualquer falha devolve a pergunta original: é melhor buscar com a pergunta
    crua do que derrubar a sessão.
    """
    if not chat_history:
        return query_atual

    llm = llm or criar_llm()
    cadeia = PROMPT_REFORMULACAO | llm

    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                reescrita = cadeia.invoke({
                    "chat_history": chat_history,
                    "input": query_atual,
                }).content.strip()
                return reescrita or query_atual
            except Exception as e:
                if e_cota_esgotada(e):
                    break
                elif e_transitorio(e):
                    time.sleep(5)
                elif e_modelo_indisponivel(e):
                    break
                else:
                    print(f"  Reformulação falhou ({type(e).__name__}): usando pergunta original")
                    return query_atual
    return query_atual


# ---------------------------------------------------------------------------
# Memoria de longo prazo: arquivamento de sessoes de campanha
# ---------------------------------------------------------------------------
def _formatar_historico(chat_history: list) -> str:
    """Pares Human/AIMessage viram linhas 'Usuário/Assistente:' pro arquivista."""
    linhas = []
    for m in chat_history:
        quem = "Usuário" if getattr(m, "type", "") == "human" else "Assistente"
        linhas.append(f"{quem}: {getattr(m, 'content', '')}")
    return "\n".join(linhas) or "(histórico vazio)"


def _como_lista(valor) -> list:
    """Coage o campo do JSON para list[str] sem inventar conteúdo."""
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor if str(v).strip()]
    if valor:
        return [str(valor).strip()]
    return []


def salvar_sessao_campanha(
    chat_history: list,
    relato_final: str,
    llm,
    embeddings,
    client_qdrant,
    origem: str = "auto",
) -> dict | None:
    """Resume a sessão (PROMPT_RESUMO_SESSAO) e arquiva na coleção de histórico.

    Nunca derruba a sessão: falha de LLM, JSON inválido ou Qdrant indisponível
    imprime o aviso e devolve None. `origem` fica na metadata p/ auditoria
    ("auto" no gatilho de fim de sessão, "manual" no /salvar).
    """
    cadeia = PROMPT_RESUMO_SESSAO | llm
    historico = _formatar_historico(chat_history)

    conteudo = ""
    for modelo in MODELOS_GRATUITOS:
        trocar_modelo(llm, modelo)
        for _ in range(2):
            try:
                conteudo = cadeia.invoke({
                    "historico": historico,
                    "relato": relato_final,
                }).content.strip()
                if e_recusa(conteudo):
                    raise RecusaTraducao(conteudo[:60])
                break
            except (RecusaTraducao, APIError, ConnectionError, TimeoutError,
                    ValueError, TypeError, KeyError) as e:
                if e_cota_esgotada(e) or e_modelo_indisponivel(e) or isinstance(e, RecusaTraducao):
                    break
                if e_transitorio(e):
                    time.sleep(5)
                    continue
                break
        if conteudo:
            break
    if not conteudo:
        print("   ⚠️  nenhum modelo gerou o resumo da sessão — arquivamento cancelado")
        return None

    # Aceita JSON puro, com cercas ```json ou embutido em texto — nunca assume.
    bruto = conteudo.strip()
    bruto = re.sub(r"^```(?:json)?\s*|\s*```$", "", bruto)
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    if inicio >= 0 and fim > inicio:
        bruto = bruto[inicio:fim + 1]
    try:
        resumo = json.loads(bruto)
    except (ValueError, TypeError):
        print(f"   ⚠️  resumo fora de JSON válido ({bruto[:60]!r}) — arquivamento cancelado")
        return None

    campanha = str(resumo.get("campanha") or "").strip() or "(não informada)"
    desfecho = str(resumo.get("desfecho") or "").strip() or relato_final.strip()
    personagens = _como_lista(resumo.get("personagens"))
    assuntos = _como_lista(resumo.get("assuntos_tratados"))

    doc = Document(
        page_content=json.dumps(resumo, ensure_ascii=False, indent=2),
        metadata={
            "tipo": "sessao_campanha",
            "data": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "origem": origem,
            "campanha": campanha,
            "personagens": personagens,
            "assuntos_tratados": assuntos,
            "desfecho": desfecho,
        },
    )
    try:
        store = QdrantVectorStore(
            client=client_qdrant,
            collection_name=COLECAO_HISTORICO,
            embedding=embeddings,
        )
        store.add_documents([doc])
    except (APIError, ConnectionError, TimeoutError, ValueError, KeyError,
            TypeError, UnexpectedResponse) as e:
        print(f"   ⚠️  falha ao gravar no Qdrant ({type(e).__name__}) — sessão não arquivada")
        return None

    print(f"   📎 sessão arquivada em '{COLECAO_HISTORICO}' — campanha: {campanha[:70]!r}")
    return {
        "campanha": campanha,
        "personagens": personagens,
        "assuntos_tratados": assuntos,
        "desfecho": desfecho,
    }
