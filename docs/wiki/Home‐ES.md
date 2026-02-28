# Software Factory — Wiki

**Macaron Software Factory** es una plataforma de orquestación de agentes IA para equipos de desarrollo de software. Coordina 181 agentes especializados a través de 42 workflows con metodología SAFe.

## Navegación

| Sección | Descripción |
|---------|-------------|
| [Arquitectura](Architecture) | Arquitectura, componentes, flujo de datos |
| [Guía de despliegue](Deployment-Guide) | 3 entornos: Azure, OVH, Local |
| [Referencia API](API-Reference) | Endpoints REST, autenticación |
| [Agentes](Agents) | 181 agentes en 9 dominios |
| [Workflows](Workflows) | 42 workflows integrados |
| [Patrones](Patterns) | 15 patrones de orquestación |
| [Seguridad](Security) | Auth, validación adversarial, secretos |
| [Configuración LLM](LLM-Configuration) | Configuración multi-proveedor LLM |

## Traducciones

🇬🇧 [English](Home) · 🇫🇷 [Français](Home‐FR) · 🇩🇪 [Deutsch](Home‐DE) · 🇮🇹 [Italiano](Home‐IT) · 🇧🇷 [Português](Home‐PT) · 🇨🇳 [中文](Home‐ZH) · 🇯🇵 [日本語](Home‐JA)

## Inicio rápido

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup && make run
# → http://localhost:8090
```

## Repositorios

| Repo | Propósito | Contenido |
|------|-----------|-----------|
| **GitHub** (macaron-software/software-factory) | Público, plataforma completa | Todo el código. Sanitizado: 0 datos de proyecto, 0 info personal |
| **GitLab La Poste** (gitlab.azure.innovation-laposte.io) | Esqueleto interno | Estructura, sin misiones, sin skills, integración CI/CD |

## Licencia

AGPL-3.0
