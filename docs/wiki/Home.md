# 🏭 Software Factory — Wiki

**Macaron Software Factory** is an AI-powered agent orchestration platform for software engineering teams. It coordinates 156 specialized agents through 36 workflows using SAFe methodology.

## Navigation

| Section | Description |
|---------|-------------|
| [Architecture](Architecture) | Platform architecture, components, data flow |
| [Deployment Guide](Deployment-Guide) | 3 environments: Azure, OVH, Local |
| [API Reference](API-Reference) | REST API endpoints, authentication |
| [Agents](Agents) | 156 agents across 9 domains |
| [Workflows](Workflows) | 36 built-in workflows |
| [Patterns](Patterns) | 15 orchestration patterns |
| [Security](Security) | Auth, adversarial validation, secrets |
| [LLM Configuration](LLM-Configuration) | Multi-provider LLM setup |

## Translations

🇫🇷 [Français](Home‐FR) · 🇪🇸 [Español](Home‐ES) · 🇩🇪 [Deutsch](Home‐DE) · 🇮🇹 [Italiano](Home‐IT) · 🇧🇷 [Português](Home‐PT) · 🇨🇳 [中文](Home‐ZH) · 🇯🇵 [日本語](Home‐JA)

## Quick Start

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup
make run
# → http://localhost:8090
```

## Repositories

| Repo | Purpose | Content |
|------|---------|---------|
| **GitHub** (macaron-software/software-factory) | Public, full platform | All code, agents, workflows. Sanitized: 0 project data, 0 personal info |
| **GitLab La Poste** (gitlab.azure.<gitlab-laposte>) | Internal skeleton | Platform structure, no missions, no agent skills, CI/CD integration |

## License

AGPL-3.0 — See [LICENSE](https://github.com/macaron-software/software-factory/blob/main/LICENSE)
