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

# Contribuir a Software Factory

Gracias por su interes en contribuir a Software Factory. Este documento proporciona las directrices e instrucciones para contribuir.

## Codigo de Conducta

Al participar, acepta respetar nuestro [Codigo de Conducta](CODE_OF_CONDUCT.es.md).

## Como Contribuir

### Reportar Errores

1. Verifique las [issues existentes](https://github.com/macaron-software/software-factory/issues) para evitar duplicados
2. Use la [plantilla de reporte de errores](.github/ISSUE_TEMPLATE/bug_report.md)
3. Incluya: pasos para reproducir, comportamiento esperado vs real, detalles del entorno

### Sugerir Funcionalidades

1. Abra una issue con la [plantilla de solicitud de funcionalidad](.github/ISSUE_TEMPLATE/feature_request.md)
2. Describa el caso de uso y el comportamiento esperado
3. Explique por que seria util para otros usuarios

### Pull Requests

1. Haga fork del repositorio
2. Cree una rama: `git checkout -b feature/mi-funcionalidad`
3. Realice sus cambios siguiendo los estandares a continuacion
4. Escriba o actualice las pruebas
5. Ejecute las pruebas: `make test`
6. Haga commit con mensajes claros (ver convenciones a continuacion)
7. Haga push y abra una Pull Request

## Configuracion de Desarrollo

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## Estandares de Codigo

### Python

- **Estilo**: PEP 8, aplicado por `ruff`
- **Type hints**: requeridos para APIs publicas
- **Docstrings**: estilo Google para modulos, clases, funciones publicas
- **Imports**: `from __future__ import annotations` en todos los archivos

### Mensajes de Commit

Siga [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: agregar canal WebSocket en tiempo real
fix: corregir orden de rutas en API de misiones
refactor: dividir api.py en sub-modulos
docs: actualizar diagramas de arquitectura
test: agregar pruebas de cola de trabajos
```

### Pruebas

- Pruebas unitarias en `tests/` con `pytest`
- Pruebas asincronas con `pytest-asyncio`
- Pruebas E2E en `platform/tests/e2e/` con Playwright
- Toda nueva funcionalidad debe tener pruebas

### Reglas de Arquitectura

- **El LLM genera, las herramientas deterministas validan** — IA para tareas creativas, scripts/compiladores para validacion
- **Sin archivos monoliticos** — dividir modulos de mas de 500 lineas en sub-paquetes
- **SQLite para persistencia** — sin dependencias de bases de datos externas
- **LLM multi-proveedor** — nunca codificar un solo proveedor
- **Retrocompatible** — las nuevas funcionalidades no deben romper las APIs existentes

## Licencia

Al contribuir, acepta que sus contribuciones seran licenciadas bajo la [Licencia AGPL v3](LICENSE).
