# MACARON AGENT PLATFORM — SPECIFICATIONS v1.0

> **Vision** : Une plateforme web locale permettant de créer, orchestrer et piloter des équipes d'agents IA collaboratifs sur des projets logiciels, avec mémoire persistante, outils MCP, et conversation temps réel style WhatsApp.

---

## 1. CONCEPTS FONDAMENTAUX

### 1.1 Projet = Unité de base

Tout commence par un **Projet**. Un projet est un espace de travail complet :

```
PROJET
├── Identity     → nom, description, avatar, couleur
├── Vision       → document de vision produit (VISION.md)
├── Values       → principes Lean/Agile du projet (valeurs)
├── Git          → répertoire local, historique, branches
├── Agent Lead   → agent LLM par défaut (interlocuteur humain)
├── Agents       → pool d'agents disponibles pour ce projet
├── Patterns     → assemblages d'agents (workflows)
├── Workflows    → chaînes de patterns (pipelines)
├── Memory       → mémoire projet persistante (FTS5)
├── Tools        → outils MCP connectés
├── Sessions     → conversations/exécutions en cours
└── Artifacts    → fichiers produits (code, specs, tests, docs)
```

**Règle** : L'humain dialogue TOUJOURS avec l'Agent Lead du projet. C'est l'Agent Lead qui délègue aux sous-agents si nécessaire, et qui rend compte à l'humain.

### 1.2 Pilotage par la Vision

Chaque projet a un document **VISION.md** qui définit :

- La roadmap produit (features, milestones)
- Les objectifs business (KPI, OKR)
- Les contraintes (AO, compliance, deadline)
- Les priorités (WSJF ordering)

L'Agent Lead et le Brain s'appuient sur la Vision pour :

- Décider quoi faire ensuite (priorisation)
- Valider que le travail produit est aligné (pas de SLOP)
- Mesurer l'avancement (% vision réalisée)

### 1.3 Valeurs Lean du Projet

Chaque projet porte des **valeurs** configurables :

| Valeur                    | Description                    | Impact sur agents                      |
| ------------------------- | ------------------------------ | -------------------------------------- |
| **Qualité > Vitesse**     | Adversarial review obligatoire | Veto activé, review systématique       |
| **Feedback rapide**       | Loops courtes, fail fast       | Itérations max, convergence check      |
| **Éliminer le waste**     | Pas de code inutile, KISS      | Brain filtre, adversarial rejette SLOP |
| **Respect des personnes** | Collaboration, pas compétition | Négociation > Veto quand possible      |
| **Amélioration continue** | Retrospective auto             | XP Agent analyse, factory s'améliore   |
| **Flux continu**          | WIP limits, pas de blocage     | Queue management, timeouts             |

---

## 2. AGENTS

### 2.1 Définition d'un Agent

Un agent est une entité autonome avec :

```yaml
Agent:
  # Identité
  id: string # Unique (slug)
  name: string # Nom affiché
  avatar: string # URL image ou emoji/SVG
  profile_image: string # Photo de profil (optionnel)
  color: string # Couleur thème (#hex)
  description: string # Bio courte

  # Cerveau
  llm:
    provider: string # azure-foundry | anthropic | minimax | glm
    model: string # gpt-4o | claude-opus-4.5 | etc.
    temperature: float # 0.0 - 1.0
    max_tokens: int # Limite de sortie
    fallback_model: string # Si rate-limited ou timeout

  # Compétences
  skills: list[Skill] # Skills chargées (prompts spécialisés)
  tools: list[Tool] # Outils MCP disponibles
  mcps: list[MCP] # Serveurs MCP connectés

  # Persona
  system_prompt: string # Instruction système complète
  persona_traits: list[string] # ["rigoureux", "pragmatique", ...]

  # Permissions
  permissions:
    can_veto: bool # Peut bloquer un résultat
    veto_level: absolute|strong|advisory
    can_delegate: bool # Peut assigner du travail
    can_approve: bool # Peut valider un résultat
    can_spawn_agents: bool # Peut créer des sous-agents
    can_modify_memory: bool # Peut écrire en mémoire projet
    escalation_to: string # Agent d'escalade (lead, humain)
    require_human_approval: list[string] # Actions nécessitant validation humaine

  # Communication
  communication:
    responds_to: list[string] # Agents qui peuvent le contacter
    can_contact: list[string] # Agents qu'il peut contacter
    broadcast_channels: list[string] # Canaux de diffusion

  # Mémoire
  memory:
    type: session|project|global|vector # Portée de la mémoire
    context_window: int # Nombre de messages en contexte
    long_term_enabled: bool # FTS5 / RAG
    shared_with: list[string] # Agents avec qui partager
```

### 2.2 Agents Prédéfinis

| ID            | Nom                 | Rôle                      | LLM par défaut  | Veto         | Spécialité                                  |
| ------------- | ------------------- | ------------------------- | --------------- | ------------ | ------------------------------------------- |
| `brain`       | Brain               | Orchestrateur stratégique | claude-opus-4.5 | —            | Vision → tâches, WSJF, architecture globale |
| `lead-dev`    | Lead Développeur    | Review & architecture     | claude-sonnet-4 | Strong       | Code review, design patterns, qualité       |
| `dev`         | Développeur         | Implémentation TDD        | gpt-4o          | —            | Red-Green-Refactor, atomic commits          |
| `testeur`     | Testeur QA          | Tests & couverture        | gpt-4o-mini     | —            | E2E, smoke, regression, edge cases          |
| `securite`    | Sécurité            | Audit OWASP               | glm-4-plus      | **Absolute** | XSS, injection, secrets, RBAC               |
| `devops`      | DevOps              | Infra & CI/CD             | gpt-4o          | Strong       | Docker, deploy, monitoring, rollback        |
| `architecte`  | Architecte          | Design système            | claude-opus-4.5 | Strong       | Patterns, scalabilité, choix tech           |
| `chef-projet` | Chef de Projet      | Pilotage & délégation     | gpt-4o          | —            | Planning, suivi, arbitrage, reporting       |
| `metier`      | Expert Métier       | Requirements              | gpt-4o          | —            | User stories, acceptance criteria           |
| `ux`          | UX Designer         | Expérience utilisateur    | gpt-4o          | —            | Wireframes, flows, WCAG, accessibilité      |
| `adversarial` | Adversarial Critic  | Review contradictoire     | MiniMax-M1      | **Absolute** | SLOP, skip, bypass, quality gate            |
| `tech-writer` | Rédacteur Technique | Documentation             | gpt-4o-mini     | —            | API docs, changelog, ADR                    |

### 2.3 Agents Custom

L'utilisateur peut créer des agents personnalisés :

- Via le **formulaire Agent Builder** (UI)
- Via un **agent assembleur** qui propose un agent adapté au besoin
- Par **clonage** d'un agent existant + modifications

---

## 3. PATTERNS (Assemblages d'Agents)

### 3.1 Concept

Un **Pattern** définit comment des agents collaborent :

- Qui participe (quels agents)
- Comment ils communiquent (edges / canaux)
- Quel est le flux d'information (séquentiel, parallèle, mesh)
- Quelles règles de mémoire s'appliquent (partagée, isolée)
- Quels sont les critères de terminaison

```yaml
Pattern:
  id: string
  name: string
  description: string
  type: solo|sequential|parallel|loop|router|aggregator|hierarchical|network|human-in-loop|adversarial|pipeline

  # Agents participants
  agents:
    - id: string # Ref agent
      role_override: string # Rôle dans ce pattern (peut différer du rôle par défaut)
      config_override: {} # Surcharges LLM, permissions...

  # Connexions entre agents
  edges:
    - from: string # Agent source
      to: string # Agent destination
      type: delegate|inform|review|veto|negotiate|escalate
      label: string # Description de l'échange
      condition: string # Condition d'activation (optionnel)

  # Configuration
  config:
    max_iterations: int # Pour loops
    convergence_check: bool # Arrêter si consensus
    wip_limit: int # Agents actifs en parallèle max
    timeout_sec: int # Timeout global
    require_unanimous_approval: bool # Tous doivent approuver
    allow_negotiation: bool # Agents peuvent négocier entre eux
    human_checkpoints: list[string] # Points de validation humaine

  # Mémoire du pattern
  memory_config:
    shared_context: bool # Mémoire partagée entre agents
    isolated_agents: list[string] # Agents avec mémoire isolée (adversarial)
    persist_to_project: bool # Écrire les conclusions en mémoire projet
    summary_on_complete: bool # Résumer l'exécution à la fin
```

### 3.2 Patterns Prédéfinis

#### 3.2.1 Solo Chat

```
Humain ↔ Agent Lead
```

Dialogue direct avec un agent unique. Le plus simple.

#### 3.2.2 TDD Loop (Wiggum)

```
Brain → [Dev (RED) → Dev (GREEN) → Lead (REVIEW) → Adversarial (GATE)]
                              ↑_________________________________↓ loop
```

Boucle TDD itérative : l'agent dev écrit un test (RED), implémente (GREEN), le lead review, l'adversarial valide. Loop jusqu'à convergence.

**Config** : `max_iterations: 10`, `convergence: tests_pass AND adversarial_approve`

#### 3.2.3 Code Review Pipeline

```
Dev → Lead Dev → Sécurité → Architecte → [APPROVE | VETO]
```

Pipeline séquentiel de review. Chaque agent peut approuver ou bloquer. Veto = retour au dev avec feedback.

#### 3.2.4 Architecture Debate (Network)

```
Architecte ↔ Lead Dev ↔ DevOps ↔ Sécurité
        (full mesh, négociation)
```

Discussion ouverte entre experts. Chacun peut argumenter, proposer, contester. Convergence par consensus ou vote.

#### 3.2.5 Feature Factory (Hierarchical)

```
Chef Projet (manager)
├── Brain (décompose en tâches)
├── Dev 1 (feature A)
├── Dev 2 (feature B)
├── Testeur (valide A+B)
└── Lead Dev (intègre + review)
```

Le chef de projet délègue, le brain décompose, les devs implémentent en parallèle, le testeur valide, le lead intègre.

#### 3.2.6 Adversarial Review (Team of Rivals)

```
Dev (implémente) → Code Critic → Security Critic → Arch Critic
                         ↓ VETO           ↓ VETO        ↓ VETO
                    Feedback → Dev (fix) → retry cascade
```

Cascade de critics multi-vendor (cf. Swiss Cheese Model de la Software Factory). Chaque critic a un LLM différent pour diversité cognitive.

#### 3.2.7 Sprint Planning (Aggregator)

```
Métier + UX + Architecte → (parallèle) → Chef Projet (synthèse) → Backlog priorisé
```

Chaque expert propose ses items, le chef de projet agrège et priorise (WSJF).

#### 3.2.8 RLM Deep Analysis

```
Brain (recursive) → [Locate → Summarize → Analyze → Plan] × N fichiers
                                                               ↓
                                                     Tâches WSJF priorisées
```

Analyse récursive profonde du codebase via MCP tools (lrm_locate, lrm_summarize, etc.). Comme le Brain de la Software Factory.

#### 3.2.9 Deploy Pipeline (SF-style)

```
Build → Adversarial → Infra Check → Staging → E2E Smoke → E2E Journey → Canary → Prod
         (gate)        (CoVe)                  (Playwright)              (1%→100%)
```

Pipeline complet de déploiement avec gates de qualité à chaque étape.

#### 3.2.10 Human-in-the-Loop

```
Agent → ... → CHECKPOINT → Humain valide → ... → CHECKPOINT → Humain valide → Done
```

N'importe quel pattern avec des points de contrôle où l'humain doit valider avant de continuer.

#### 3.2.11 Delegation Chain (Chef de Projet)

```
Humain → Chef Projet → délègue à Lead Dev → délègue à Dev
                    ← rapport ← rapport ← résultat
```

Chaîne de commandement avec delegation et reporting. Le chef de projet dialogue avec les leads, qui dialoguent avec les devs. L'humain ne voit que le rapport du chef de projet + peut zoomer sur n'importe quelle conversation.

### 3.3 Patterns Custom

L'utilisateur peut :

- **Composer** un pattern via l'éditeur visuel (canvas drag & drop)
- **Demander à un agent** de proposer un pattern adapté à son besoin
- **Modifier** un pattern existant (ajouter/retirer agents, changer edges)
- **Importer/Exporter** des patterns en YAML

---

## 4. WORKFLOWS (Chaînes de Patterns)

### 4.1 Concept

Un **Workflow** est une séquence orchestrée de patterns, où la sortie d'un pattern alimente le suivant :

```yaml
Workflow:
  id: string
  name: string
  description: string
  project_id: string

  # Phases ordonnées
  phases:
    - name: string
      pattern_id: string # Pattern à exécuter
      input_from: string|null # Phase précédente (ou null = input humain)
      gate: string # Condition pour passer à la phase suivante
      on_failure: retry|skip|abort|human_decide
      config_override: {} # Surcharges pour cette phase

  # Cycle de vie
  lifecycle:
    auto_start: bool # Démarre automatiquement
    auto_loop: bool # Boucle (features → fixes → refactor → features)
    max_cycles: int # Nombre max de boucles
    schedule: string # Cron (optionnel)
```

### 4.2 Workflows Prédéfinis

#### 4.2.1 Software Factory (SF)

```
Phase 1: RLM Deep Analysis (Brain)
    ↓ tâches WSJF
Phase 2: TDD Loop (Wiggum) × N tâches en parallèle
    ↓ code_written
Phase 3: Adversarial Review (cascade)
    ↓ approved
Phase 4: Build + Deploy Pipeline
    ↓ deployed
Phase 5: E2E Validation
    ↓ verified
── LOOP → Phase 1 (next features)
```

#### 4.2.2 Migration Factory (MF)

```
Phase 1: Migration Analysis (Brain + breaking changes DB)
    ↓ migration plan
Phase 2: Transform (codemods + LLM)
    ↓ code migrated
Phase 3: Comparative Adversarial (golden diff 0%)
    ↓ iso verified
Phase 4: Canary Deploy (1% → 100%)
    ↓ deployed
── LOOP → Phase 1 (next module)
```

#### 4.2.3 Sprint Agile

```
Phase 1: Sprint Planning (aggregator: métier + UX + archi → backlog)
    ↓ backlog priorisé
Phase 2: Feature Factory (hierarchical: chef projet → devs)
    ↓ features done
Phase 3: Review + QA (sequential: lead + testeur + sécu)
    ↓ approved
Phase 4: Retrospective (XP Agent → amélioration)
    ↓ lessons learned
── LOOP → Phase 1 (next sprint)
```

#### 4.2.4 Security Audit

```
Phase 1: Code Scan (sécurité + adversarial)
    ↓ vulnérabilités
Phase 2: Fix Prioritization (WSJF)
    ↓ fix tasks
Phase 3: TDD Fix Loop
    ↓ patched
Phase 4: Re-audit (verify)
```

### 4.3 Workflows Custom

L'utilisateur peut :

- **Assembler** des phases en chaînant des patterns existants
- **Définir** les conditions de passage (gates)
- **Configurer** la politique d'erreur (retry, abort, humain)
- **Activer le mode auto-loop** (cycle continu)

---

## 5. MÉMOIRE

### 5.1 Architecture 4 couches

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: SESSION MEMORY (éphémère)                       │
│   Portée: 1 session/conversation                         │
│   Durée: session active uniquement                       │
│   Contenu: messages, contexte, décisions en cours        │
│   Accès: agents de la session                            │
│   Tech: sliding window (N derniers messages en prompt)   │
├─────────────────────────────────────────────────────────┤
│ Layer 2: PATTERN MEMORY (workflow run)                    │
│   Portée: 1 exécution de pattern                         │
│   Durée: durée du pattern run                            │
│   Contenu: contexte partagé, résultats intermédiaires    │
│   Accès: agents du pattern (configurable: shared/isolé)  │
│   Tech: key-value en DB (memory_pattern)                 │
├─────────────────────────────────────────────────────────┤
│ Layer 3: PROJECT MEMORY (persistante)                    │
│   Portée: 1 projet, cross-sessions                       │
│   Durée: permanente                                      │
│   Contenu: architecture, conventions, décisions, lessons │
│   Accès: tous les agents du projet                       │
│   Tech: SQLite + FTS5 (memory_project)                   │
│   Bridge: ProjectContext RAG de la Software Factory       │
├─────────────────────────────────────────────────────────┤
│ Layer 4: GLOBAL MEMORY (cross-projet)                    │
│   Portée: tous les projets                               │
│   Durée: permanente                                      │
│   Contenu: patterns systémiques, erreurs récurrentes     │
│   Accès: Brain, agents avec permission                   │
│   Tech: SQLite + FTS5 (memory_global)                    │
│   Bridge: meta_awareness de la Software Factory          │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Règles mémoire par pattern

| Pattern          | Session   | Pattern   | Project | Global |
| ---------------- | --------- | --------- | ------- | ------ |
| Solo Chat        | ✅ RW     | —         | ✅ R    | ❌     |
| TDD Loop         | ✅ RW     | ✅ shared | ✅ RW   | ❌     |
| Adversarial      | ✅ R only | ❌ isolé  | ✅ R    | ❌     |
| Network (debate) | ✅ RW     | ✅ shared | ✅ R    | ❌     |
| Feature Factory  | ✅ RW     | ✅ shared | ✅ RW   | ✅ R   |
| Brain RLM        | ✅ RW     | ✅ shared | ✅ RW   | ✅ RW  |

**Adversarial isolation** : L'adversarial n'a PAS accès à la mémoire du pattern pour éviter le biais de confirmation. Il juge le code sans savoir ce que les autres agents ont dit.

### 5.3 Mémoire et Vision

La mémoire projet contient automatiquement :

- Le contenu de VISION.md (catégorie `vision`)
- Les valeurs Lean du projet (catégorie `values`)
- L'historique des décisions architecturales (catégorie `decisions`)
- Les conventions de code (catégorie `conventions`)
- Les erreurs récurrentes (catégorie `errors`)

Le Brain et l'Agent Lead consultent la vision en priorité pour chaque décision.

---

## 6. OUTILS (TOOLS & MCP)

### 6.1 Outils Natifs

| Catégorie | Outil         | Description                            |
| --------- | ------------- | -------------------------------------- |
| **Code**  | `code_read`   | Lire un fichier                        |
| **Code**  | `code_write`  | Écrire un fichier                      |
| **Code**  | `code_edit`   | Modifier un fichier (search & replace) |
| **Code**  | `code_search` | Rechercher dans le code (ripgrep)      |
| **Git**   | `git_status`  | Statut du repo                         |
| **Git**   | `git_diff`    | Diff des changements                   |
| **Git**   | `git_commit`  | Créer un commit                        |
| **Git**   | `git_branch`  | Gérer les branches                     |
| **Git**   | `git_log`     | Historique des commits                 |
| **Build** | `build`       | Compiler le projet                     |
| **Build** | `test`        | Lancer les tests                       |
| **Build** | `lint`        | Lancer le linter                       |
| **Infra** | `deploy`      | Déployer                               |
| **Infra** | `monitor`     | Surveiller                             |

### 6.2 Serveurs MCP

| MCP            | Description                 | Outils exposés                                                                               |
| -------------- | --------------------------- | -------------------------------------------------------------------------------------------- |
| **LRM**        | Locate-Read-Modify codebase | `lrm_locate`, `lrm_summarize`, `lrm_conventions`, `lrm_examples`, `lrm_build`, `lrm_context` |
| **Figma**      | Design system sync          | `get_file`, `get_node`, `get_styles`, `get_selection`                                        |
| **Playwright** | Browser automation E2E      | `navigate`, `click`, `fill`, `screenshot`, `assert`                                          |
| **GitHub**     | Repo, issues, PRs           | `search_code`, `list_issues`, `create_pr`, `get_commit`                                      |
| **Filesystem** | Accès fichiers              | `read`, `write`, `list`, `search`                                                            |
| **Jira**       | Tickets, sprints            | `get_issue`, `create_issue`, `search`, `update_status`                                       |
| **Wiki**       | Documentation interne       | `search`, `get_page`, `update_page`                                                          |
| **Docker**     | Containers, images          | `ps`, `logs`, `exec`, `build`, `compose`                                                     |
| **SQLite**     | Base de données             | `query`, `execute`, `schema`                                                                 |
| **Seek/RLM**   | Recherche sémantique        | `semantic_search`, `similar_files`, `explain_code`                                           |

### 6.3 Permissions Outils par Agent

Les outils sont attribués par agent. L'Agent Lead et le Brain ont accès à tous les outils. Les autres agents ont un sous-ensemble adapté à leur rôle :

```
Dev:       code_*, git_*, build, test, lint, lrm_*
Testeur:   code_read, code_search, test, playwright_*
Sécurité:  code_read, code_search (read-only)
DevOps:    infra_*, docker_*, deploy_*, monitoring_*
Architecte: code_read, code_search, lrm_*, design_*
Chef Projet: task_*, planning_*, jira_*, wiki_*
```

---

## 7. CONVERSATIONS & DIALOGUE

### 7.1 L'humain dialogue avec l'Agent Lead

```
┌──────────────────────────────────────────────┐
│ CONVERSATION VIEW (WhatsApp-style)            │
│                                              │
│  [Humain] → message → [Agent Lead]           │
│  [Agent Lead] → "Je délègue au dev..." → ... │
│                                              │
│  -- Sous-conversation (collapsible) --       │
│  [Agent Lead] → [Dev] "Implémente X"        │
│  [Dev] → [Agent Lead] "Voici le code"        │
│  [Agent Lead] → [Adversarial] "Review ?"     │
│  [Adversarial] → VETO "skip détecté"        │
│  [Dev] → fix → [Adversarial] → APPROVE      │
│  -- Fin sous-conversation --                 │
│                                              │
│  [Agent Lead] → [Humain] "Feature X prête"   │
└──────────────────────────────────────────────┘
```

### 7.2 Visualisation des échanges inter-agents

Les échanges entre agents sont visibles en temps réel dans un panneau latéral **"Logs & Pensées"** :

- **Chaque message** est affiché avec : timestamp, agent source, agent destination, type (delegate, veto, approve, inform...)
- **Tags colorés** : Veto (rouge), Approved (vert), Delegation (bleu), Code (violet), Instruction (gris)
- **Filtrable** par agent, par type, par période
- **Expandable** : cliquer sur un échange pour voir le contenu complet

### 7.3 Conversations imbriquées

Quand l'Agent Lead délègue à un sous-agent, une **sous-conversation** est créée :

- Visible comme un fil dans la conversation principale (collapsible)
- L'humain peut **zoomer** dans n'importe quelle sous-conversation
- L'humain peut **intervenir** à tout moment (Human-in-the-Loop)
- Les sous-conversations ont leur propre mémoire de session

### 7.4 Modes de conversation

| Mode             | Description                              | Quand            |
| ---------------- | ---------------------------------------- | ---------------- |
| **Chat**         | Dialogue libre avec l'Agent Lead         | Par défaut       |
| **Instruction**  | L'humain donne un ordre, l'agent exécute | "Implémente X"   |
| **Observation**  | L'humain observe les agents travailler   | Pattern en cours |
| **Intervention** | L'humain interrompt pour corriger/guider | Si dérive        |
| **Review**       | L'humain valide un résultat              | Checkpoint       |

---

## 8. UI / UX

### 8.1 Sidebar (56px, icônes)

```
[M] Logo
─────────
[📁] Projets
[🤖] Agents
[🔗] Patterns
[📚] Skills
[🔧] MCPs
[🧠] Mémoire
[💬] Sessions
[📊] Monitoring
[⚙️] Settings
```

### 8.2 Pages principales

| Page              | Contenu                                                                            |
| ----------------- | ---------------------------------------------------------------------------------- |
| **Projets**       | Dashboard projets avec cards (nom, pattern actif, agents, status, git, vision %)   |
| **Projet Detail** | Git status, Vision, Valeurs, Agents assignés, Sessions actives, Mémoire, Artifacts |
| **Agents**        | Grid d'agents avec avatar, nom, rôle, LLM, status                                  |
| **Agent Edit**    | Formulaire complet : identité, LLM, skills, tools, memory, permissions             |
| **Patterns**      | Éditeur visuel canvas + bibliothèque de patterns                                   |
| **Skills**        | Bibliothèque de skills avec filtres, preview, assignation                          |
| **MCPs**          | Registry MCP avec status (running/stopped), tools, tokens                          |
| **Mémoire**       | Exploration FTS5, stats par couche, timeline                                       |
| **Sessions**      | Liste des sessions actives/terminées par projet                                    |
| **Conversation**  | Chat WhatsApp + panneau Logs & Pensées                                             |
| **Monitoring**    | Métriques agents : tokens, messages, vetos, success rate                           |
| **Settings**      | Config globale, LLM providers, tokens API                                          |

### 8.3 Theme

- **Palette** : Purple/Indigo dark (#0f0a1a primary, #1a1225 secondary)
- **Accents** : Purple (#bc8cff), Blue (#7c8aff), Green (#3fb950)
- **Bubbles** : Green (#1d4a2a) pour user, Dark (#1a1225) pour agents
- **Police** : System font stack, monospace pour code
- **Interactions** : HTMX pour SPA-like, SSE pour temps réel

---

## 9. ARCHITECTURE TECHNIQUE

### 9.1 Stack

```
┌─────────────────────────────────────────────┐
│ Frontend: HTML + HTMX + CSS (no framework)   │
│ Templating: Jinja2                           │
│ Real-time: SSE (Server-Sent Events)          │
├─────────────────────────────────────────────┤
│ Backend: Python + FastAPI                    │
│ Async: asyncio                               │
│ LLM: Azure Foundry (primary) + Anthropic    │
├─────────────────────────────────────────────┤
│ Database: SQLite + FTS5                      │
│ Memory: 4-layer (session/pattern/project/global) │
│ Tools: MCP Protocol (stdio + SSE)            │
├─────────────────────────────────────────────┤
│ Agent Runtime: asyncio tasks                 │
│ Message Bus: async pub/sub + dead letter     │
│ Orchestrator: pattern-based execution        │
├─────────────────────────────────────────────┤
│ Git: local repos (subprocess git)            │
│ File System: direct access                   │
│ Deploy: local dev (Mac) ou Azure VM          │
└─────────────────────────────────────────────┘
```

### 9.2 Composants existants (déjà implémentés)

| Composant                | Fichier                              | Status |
| ------------------------ | ------------------------------------ | ------ |
| Server FastAPI           | `platform/server.py`                 | ✅     |
| Config & providers       | `platform/config.py`                 | ✅     |
| DB Schema (v3)           | `platform/db/schema.sql`             | ✅     |
| Agent Store (CRUD)       | `platform/agents/store.py`           | ✅     |
| Agent Base class         | `platform/agents/base.py`            | ✅     |
| Agent Runtime            | `platform/agents/runtime.py`         | ✅     |
| Agent Registry (YAML)    | `platform/agents/registry.py`        | ✅     |
| Agent Memory             | `platform/agents/memory.py`          | ✅     |
| Pattern Store            | `platform/patterns/store.py`         | ✅     |
| Orchestration Engine     | `platform/orchestrator/engine.py`    | ✅     |
| 8 Orchestration Patterns | `platform/orchestrator/patterns.py`  | ✅     |
| Intent Router            | `platform/orchestrator/router.py`    | ✅     |
| Message Bus (A2A)        | `platform/a2a/bus.py`                | ✅     |
| Veto Manager             | `platform/a2a/veto.py`               | ✅     |
| Protocol Validator       | `platform/a2a/protocol.py`           | ✅     |
| Tool Registry            | `platform/tools/registry.py`         | ✅     |
| Tool implementations     | `platform/tools/code_tools.py`, etc. | ✅     |
| Skill Library            | `platform/skills/library.py`         | ✅     |
| Project Registry         | `platform/projects/registry.py`      | ✅     |
| Session Store            | `platform/sessions/store.py`         | ✅     |
| Web Routes (20+)         | `platform/web/routes.py`             | ✅     |
| SSE endpoint             | `platform/web/ws.py`                 | ✅     |
| All HTML templates       | `platform/web/templates/`            | ✅     |
| Purple theme CSS         | `platform/web/static/css/`           | ✅     |

### 9.3 Composants à construire

| Composant                       | Fichier                             | Description                                         |
| ------------------------------- | ----------------------------------- | --------------------------------------------------- |
| **LLM Client (Azure Foundry)**  | `platform/llm/azure_foundry.py`     | Appels LLM via Azure AI Foundry                     |
| **LLM Client (multi-provider)** | `platform/llm/client.py`            | Abstraction multi-provider avec fallback            |
| **Agent Executor**              | `platform/agents/executor.py`       | Boucle d'exécution: receive → think → act → respond |
| **Memory Manager**              | `platform/memory/manager.py`        | CRUD 4 couches + FTS5 search + bridges SF           |
| **MCP Manager**                 | `platform/mcps/manager.py`          | Start/stop MCPs, tool discovery, bridge             |
| **Project Manager**             | `platform/projects/manager.py`      | CRUD projets, vision, valeurs, agent lead           |
| **Workflow Engine**             | `platform/orchestrator/workflow.py` | Exécution de workflows (chaînes de patterns)        |
| **Conversation Manager**        | `platform/sessions/conversation.py` | Sous-conversations, threads, intervention           |
| **SSE Live Bridge**             | `platform/web/sse_bridge.py`        | Push messages + logs + events vers UI               |
| **Factory Bridge**              | `platform/factory_bridge.py`        | Pont vers SF/MF (brain, cycle, deploy)              |

---

## 10. MODÈLES LLM (Azure AI Foundry)

### 10.1 Providers disponibles

Tous les modèles proviennent d'**Azure AI Foundry** (endpoint unique, API key unique) :

| Provider      | Modèles                                                  | Usage                        |
| ------------- | -------------------------------------------------------- | ---------------------------- |
| **OpenAI**    | gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano | Workers, chef projet, devops |
| **Anthropic** | claude-opus-4.5, claude-sonnet-4, claude-haiku-4.5       | Brain, architecte, review    |
| **Google**    | gemini-2.5-pro, gemini-2.5-flash                         | Alternative, long context    |
| **Meta**      | llama-4-maverick, llama-4-scout                          | Open source, tests           |
| **Mistral**   | mistral-large-2501, mistral-small-2503, pixtral-large    | EU compliant                 |
| **Cohere**    | command-a                                                | RAG, search                  |
| **DeepSeek**  | deepseek-v3-0324                                         | Code, raisonnement           |
| **MiniMax**   | MiniMax-M1-80k                                           | Workers rapides              |

### 10.2 Configuration LLM

```yaml
# Chaque agent choisit son modèle
llm:
  provider: azure-foundry # Tous via Azure Foundry
  model: gpt-4o # Modèle spécifique
  temperature: 0.3 # Créativité
  max_tokens: 4096 # Limite sortie
  fallback_model: gpt-4o-mini # Si rate-limited
```

### 10.3 Fallback chain

```
Primary model → rate limit/timeout → fallback_model → error
```

L'agent retry automatiquement avec le modèle de fallback si le modèle principal est indisponible.

---

## 11. GIT & HISTORISATION

### 11.1 Chaque projet = repo local

Chaque projet pointe vers un répertoire git local. L'Agent Lead et les devs peuvent :

- Lire le statut (`git status`)
- Voir les diffs (`git diff`)
- Committer des changements (`git commit`)
- Créer des branches (`git branch`, `git checkout`)
- Voir l'historique (`git log`)

### 11.2 Conventions de commit

Les commits créés par les agents suivent la convention :

```
[agent-id] type(scope): message

feat(auth): add JWT refresh token rotation
fix(api): handle null pointer in user endpoint
test(e2e): add smoke test for dashboard
```

### 11.3 Branches par pattern

Les patterns créent des branches de travail :

```
pattern/tdd-loop/task-123         # Branche de travail TDD
pattern/feature-factory/sprint-5  # Branche feature factory
pattern/deploy/v2.1.0            # Branche de release
```

---

## 12. SÉCURITÉ & PERMISSIONS

### 12.1 Principe du moindre privilège

Chaque agent n'a accès qu'aux outils et mémoires nécessaires à son rôle :

- **Dev** : code + git + build (pas de deploy)
- **Sécurité** : lecture seule (pas d'écriture)
- **DevOps** : infra (pas de code applicatif)
- **Adversarial** : isolé (pas de mémoire pattern partagée)

### 12.2 Human-in-the-Loop obligatoire pour

- Deploy en production
- Suppression de fichiers critiques
- Modifications de configuration sécurité
- Accès à des tokens/secrets
- Approbation de dépenses (LLM tokens > seuil)

### 12.3 Audit trail

Toutes les actions sont tracées dans `tool_calls` et `messages` :

- Qui a fait quoi, quand, sur quel projet
- Résultat de chaque appel d'outil
- Chaîne de décision (qui a approuvé, qui a bloqué)

---

## 13. BRIDGES VERS LA SOFTWARE FACTORY

### 13.1 Bridge SF → Platform

La plateforme peut piloter la Software Factory existante :

| Fonction SF            | Mapping Platform                          |
| ---------------------- | ----------------------------------------- |
| `factory brain run`    | Pattern: RLM Deep Analysis                |
| `factory cycle start`  | Workflow: SF cycle (TDD → Build → Deploy) |
| `factory wiggum start` | Pattern: TDD Loop                         |
| `factory deploy`       | Pattern: Deploy Pipeline                  |
| `factory infra check`  | Tool: infra_check                         |
| `factory meta analyze` | Memory: Global (cross-project)            |

### 13.2 Bridge MF → Platform

| Fonction MF       | Mapping Platform                  |
| ----------------- | --------------------------------- |
| `migrate analyze` | Pattern: Migration Analysis       |
| `migrate execute` | Workflow: MF Transform            |
| `migrate status`  | Memory: Project (migration state) |

### 13.3 ProjectContext RAG

La mémoire projet est enrichie par le `ProjectContext` de la SF :

- 10 catégories : vision, architecture, structure, data_model, api_surface, conventions, dependencies, state, history, domain
- Refresh automatique (1h)
- FTS5 search

---

## 14. MONITORING & MÉTRIQUES

### 14.1 Métriques par agent

| Métrique               | Description                |
| ---------------------- | -------------------------- |
| `messages_sent`        | Nombre de messages envoyés |
| `messages_received`    | Nombre de messages reçus   |
| `tokens_used`          | Consommation LLM           |
| `tool_calls`           | Nombre d'appels d'outils   |
| `vetos_issued`         | Nombre de vetos émis       |
| `approvals_issued`     | Nombre d'approbations      |
| `avg_response_time_ms` | Temps de réponse moyen     |
| `success_rate`         | Taux de succès             |
| `error_count`          | Nombre d'erreurs           |

### 14.2 Métriques par projet

| Métrique          | Description                  |
| ----------------- | ---------------------------- |
| `vision_progress` | % de la vision réalisée      |
| `active_sessions` | Sessions en cours            |
| `total_commits`   | Commits par les agents       |
| `code_coverage`   | Couverture de tests          |
| `open_tasks`      | Tâches en attente            |
| `cycle_time`      | Temps moyen tâche → deployed |

### 14.3 Métriques globales

| Métrique               | Description                    |
| ---------------------- | ------------------------------ |
| `total_tokens_24h`     | Consommation LLM journalière   |
| `total_tool_calls_24h` | Appels d'outils journaliers    |
| `cross_project_errors` | Erreurs systémiques            |
| `factory_uptime`       | Disponibilité de la plateforme |

---

## 15. ROADMAP D'IMPLÉMENTATION

### Phase A : Foundation Refresh _(existant, à consolider)_

- [x] Server FastAPI + SQLite + FTS5
- [x] Agent Store + Pattern Store + Skill Library
- [x] Project Registry (11 projets)
- [x] Web UI avec purple theme + WhatsApp chat

### Phase B : Project-Centric Model

- [ ] Refactorer le modèle : Projet = entité centrale
- [ ] Ajouter Vision + Valeurs par projet
- [ ] Agent Lead par défaut par projet
- [ ] Page projet détaillée (vision, agents, sessions, memory)
- [ ] Création de projet (formulaire + git init)

### Phase C : LLM Runtime

- [ ] Client Azure Foundry (multi-model)
- [ ] Agent executor (receive → think → act → respond)
- [ ] Fallback chain automatique
- [ ] Token tracking et rate limiting

### Phase D : Agent Communication

- [ ] Connecter MessageBus au runtime réel
- [ ] SSE live bridge (messages → UI en temps réel)
- [ ] Sous-conversations (threads imbriqués)
- [ ] Intervention humaine à tout moment

### Phase E : Pattern Execution

- [ ] Connecter orchestrator/engine.py au runtime
- [ ] Exécution réelle des 8+ patterns
- [ ] Visual feedback dans l'UI (agent status, progress)
- [ ] Workflow engine (chaîner des patterns)

### Phase F : Memory & Tools

- [ ] Memory Manager 4 couches + bridges SF
- [ ] MCP Manager (start/stop, tool discovery)
- [ ] Tool execution avec permissions
- [ ] Audit trail complet

### Phase G : Factory Bridges

- [ ] Bridge SF (brain, cycle, deploy)
- [ ] Bridge MF (analyze, transform)
- [ ] ProjectContext RAG integration
- [ ] Meta-awareness cross-projet

### Phase H : Polish & Production

- [ ] Monitoring dashboard
- [ ] Settings page complète
- [ ] Import/export (patterns, agents, workflows)
- [ ] Documentation utilisateur
