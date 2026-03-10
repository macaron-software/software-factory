<p align="center">
  <a href="CONTRIBUTING.md">English</a> |
  <a href="CONTRIBUTING.fr.md">Français</a> |
  <a href="CONTRIBUTING.zh-CN.md">中文</a> |
  <a href="CONTRIBUTING.es.md">Español</a> |
  <a href="CONTRIBUTING.ja.md">日本語</a> |
  <a href="CONTRIBUTING.pt.md">Português</a> |
  <a href="CONTRIBUTING.de.md">Deutsch</a> |
  <a href="CONTRIBUTING.ko.md">한국어</a>
</p>

# Contribuindo para o Software Factory

Obrigado pelo seu interesse em contribuir para o Software Factory! Este documento fornece diretrizes e instrucoes para contribuir.

## Codigo de Conduta

Ao participar, voce concorda em respeitar nosso [Codigo de Conduta](CODE_OF_CONDUCT.pt.md).

## Como Contribuir

### Reportar Bugs

1. Verifique as [issues existentes](https://github.com/macaron-software/software-factory/issues) para evitar duplicatas
2. Use o [modelo de relatorio de bug](.github/ISSUE_TEMPLATE/bug_report.md)
3. Inclua: passos para reproduzir, comportamento esperado vs real, detalhes do ambiente

### Sugerir Funcionalidades

1. Abra uma issue com o [modelo de solicitacao de funcionalidade](.github/ISSUE_TEMPLATE/feature_request.md)
2. Descreva o caso de uso e o comportamento esperado
3. Explique por que isso seria util para outros usuarios

### Pull Requests

1. Faca fork do repositorio
2. Crie uma branch: `git checkout -b feature/minha-funcionalidade`
3. Faca suas alteracoes seguindo os padroes abaixo
4. Escreva ou atualize os testes
5. Execute os testes: `make test`
6. Faca commit com mensagens claras (veja convencoes abaixo)
7. Faca push e abra uma Pull Request

## Configuracao de Desenvolvimento

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## Padroes de Codigo

### Python

- **Estilo**: PEP 8, aplicado pelo `ruff`
- **Type hints**: obrigatorios para APIs publicas
- **Docstrings**: estilo Google para modulos, classes, funcoes publicas
- **Imports**: `from __future__ import annotations` em todos os arquivos

### Mensagens de Commit

Siga [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: adicionar canal WebSocket em tempo real
fix: corrigir ordem de rotas na API de missoes
refactor: dividir api.py em sub-modulos
docs: atualizar diagramas de arquitetura
test: adicionar testes de fila de trabalhos
```

### Testes

- Testes unitarios em `tests/` com `pytest`
- Testes assincronos com `pytest-asyncio`
- Testes E2E em `platform/tests/e2e/` com Playwright
- Toda nova funcionalidade deve ter testes

### Regras de Arquitetura

- **LLM gera, ferramentas deterministicas validam** — IA para tarefas criativas, scripts/compiladores para validacao
- **Sem arquivos monoliticos** — dividir modulos com mais de 500 linhas em sub-pacotes
- **SQLite para persistencia** — sem dependencias de banco de dados externo
- **LLM multi-provedor** — nunca codificar um unico provedor
- **Retrocompativel** — novas funcionalidades nao devem quebrar APIs existentes

## Licenca

Ao contribuir, voce concorda que suas contribuicoes serao licenciadas sob a [Licenca AGPL v3](LICENSE).
