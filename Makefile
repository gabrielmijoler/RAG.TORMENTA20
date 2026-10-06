# Comandos do projeto RAG-Tormenta20. Rode `make` (ou `make help`) para listar tudo.
.DEFAULT_GOAL := help

PY   := .venv/bin/python
PIP  := .venv/bin/pip
RUNTIME := docker
ETAPA ?= baseline
ARGS  ?=

# pip descompacta wheels em TMPDIR; a wheel do torch+CUDA passa de 1,5 GB e o
# /tmp desta máquina é um tmpfs minúsculo (ENOSPC na instalação). O .pip-tmp
# fica no mesmo volume do projeto, com 900 GB livres.
export TMPDIR := $(CURDIR)/.pip-tmp

.PHONY: help install dev qdrant-up qdrant-down qdrant-status chat avaliar lint fmt test check

help: ## lista os comandos disponíveis
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## cria o .venv (se preciso) e instala o projeto (comandos rag-*)
	@test -x $(PY) || python3 -m venv .venv
	@mkdir -p $(TMPDIR)
	$(PIP) install -e .

dev: ## cria o .venv (se preciso) e instala as ferramentas de dev (ruff, pytest)
	@test -x $(PY) || python3 -m venv .venv
	@mkdir -p $(TMPDIR)
	$(PIP) install ruff pytest

qdrant-up: ## sobe o Qdrant via compose (porta 6335, não conflita com o MTC)
	$(RUNTIME) compose up -d

qdrant-down: ## para o Qdrant
	$(RUNTIME) compose down

qdrant-status: ## verifica se o Qdrant está respondendo (porta 6335)
	@curl -sf http://localhost:6335/readyz >/dev/null && echo "QDRANT OK" || echo "QDRANT FORA DO AR"

chat: ## chat interativo do RAG
	$(PY) index.py

avaliar: ## roda a suite de avaliação (ETAPA=nome -- ARGS="--estrategia hyde --limiar 0.7 --juiz")
	$(PY) avaliar.py --etapa $(ETAPA) $(ARGS)

lint: ## analisa o código com ruff (make dev primeiro)
	$(PY) -m ruff check .

fmt: ## formata o código com ruff (make dev primeiro)
	$(PY) -m ruff format .

test: ## roda os testes (make dev primeiro)
	$(PY) -m pytest

check: lint test ## lint + testes
