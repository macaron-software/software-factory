"""
Skill Broker — auto-detects tech stack and injects relevant tech skills.

Option A: loads pre-built skills from skills/tech/{tech}.yaml
Option B: tech-specialized agent defs live in skills/definitions/dev-{tech}.yaml
Option C: generate_dynamic_context() — inline ephemeral block, no files needed

Called from patterns/engine.py _build_node_context() for dev/qa/lead roles.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_TECH_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "tech"

# Detection rules: tech_name → {files, keywords}
_RULES: dict[str, dict] = {
    "rust": {
        "files": ["Cargo.toml"],
        "keywords": ["axum", "actix-web", "tokio", "cargo", "rustc", "warp", "tonic",
                     "macroquad", "bevy", "ggez", "wgpu", "winit"],
    },
    "react": {
        "files": ["package.json"],
        "keywords": [
            '"react"',
            "react-dom",
            "jsx",
            "tsx",
            "create-react-app",
            "vite+react",
        ],
    },
    "angular": {
        "files": ["angular.json"],
        "keywords": ["@angular/core", "angular", "ng build", "ng test"],
    },
    "nextjs": {
        "files": ["next.config.js", "next.config.ts", "next.config.mjs"],
        "keywords": ["next.js", "nextjs", "next/app", "next/router", '"next"'],
    },
    "python-fastapi": {
        "files": ["requirements.txt", "pyproject.toml"],
        "keywords": ["fastapi", "uvicorn", "pydantic", "starlette"],
    },
    "python-django": {
        "files": ["manage.py"],
        "keywords": ["django", "wsgi", "INSTALLED_APPS", "django.db"],
    },
    "java-spring": {
        "files": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "keywords": [
            "spring-boot",
            "spring boot",
            "@RestController",
            "@SpringBootApplication",
            "SpringApplication",
        ],
    },
    "go": {
        "files": ["go.mod"],
        "keywords": ['"gin-gonic"', '"fiber"', '"echo"', "go 1.", "package main"],
    },
    "flutter": {
        "files": ["pubspec.yaml"],
        "keywords": ["flutter:", "dart:", "Widget", "StatefulWidget", "flutter sdk"],
    },
    "kotlin-android": {
        "files": ["AndroidManifest.xml"],
        "keywords": ["kotlin", "android", "jetpack compose", "androidx", "viewmodel"],
    },
    "vue": {
        "files": ["vue.config.js", "vite.config.ts"],
        "keywords": ['"vue"', "vuex", "pinia", "@vue/", "defineComponent"],
    },
    "svelte": {
        "files": ["svelte.config.js", "svelte.config.ts"],
        "keywords": ["svelte", "sveltekit", "$app/"],
    },
}

# Inline hints — fallback when no tech YAML file exists (Option C)
_INLINE_HINTS: dict[str, str] = {
    "rust": (
        "Build: `cargo check` (fast) / `cargo build --release` (optimized). Test: `cargo test`. "
        "Lint: `cargo clippy -- -D warnings`. Fmt: `cargo fmt`. "
        "Use `?` operator (never `.unwrap()` in prod). Error: `anyhow::Result` or `thiserror`. "
        "GAMEDEV: macroquad re-exports rand — do NOT add `rand` crate to Cargo.toml. "
        "Use `macroquad::rand::gen_range()`. Game loop: `#[macroquad::main('Title')] async fn main() { loop { next_frame().await } }`. "
        "draw_texture/draw_rectangle are FREE FUNCTIONS, not methods."
    ),
    "react": (
        "Build: `npm run build`. Test: `npm test -- --run` (vitest) or `npm test` (Jest). "
        "Lint: `npm run lint`. Prefer hooks + functional components. "
        "State: useState/useReducer for local, zustand/jotai for global. "
        "Never mutate state directly. Key on stable IDs in lists."
    ),
    "angular": (
        "Build: `ng build`. Test: `ng test --no-watch`. E2E: `ng e2e`. Lint: `ng lint`. "
        "Signals (v17+) preferred over BehaviorSubject. Standalone components (no NgModule). "
        "inject() over constructor injection. OnPush change detection for perf."
    ),
    "nextjs": (
        "Build: `next build`. Dev: `next dev`. Test: `vitest` or `jest`. "
        "App Router: app/ dir. Server Components by default — add 'use client' only when needed. "
        "Data: fetch() in server components, SWR/React Query in client. "
        "API: app/api/route.ts with GET/POST handlers."
    ),
    "python-fastapi": (
        "Run: `uvicorn app.main:app --reload`. Test: `pytest -x`. Lint: `ruff check .`. "
        "Pydantic v2: `model_config = ConfigDict(...)`. Async endpoints with `async def`. "
        "Alembic for migrations: `alembic upgrade head`. Dependency injection via `Depends()`."
    ),
    "python-django": (
        "Run: `python manage.py runserver`. Test: `python manage.py test` or `pytest --ds=config.settings`. "
        "Migrate: `python manage.py makemigrations && python manage.py migrate`. "
        "DRF: `@api_view` or `ViewSet`. Custom auth: override `authentication_classes`."
    ),
    "java-spring": (
        "Build+test: `./mvnw test` or `./gradlew test`. "
        "Spring Boot 3+: @SpringBootApplication, auto-configuration. "
        "@RestController + @GetMapping/@PostMapping. Spring Data JPA: extends JpaRepository<E,ID>. "
        "@Service for business logic, @Repository for data. Lombok: @Data @Builder. "
        "Tests: @SpringBootTest (integration), @WebMvcTest (slice), @DataJpaTest (repo)."
    ),
    "go": (
        "Build: `go build ./...`. Test: `go test ./... -v`. Lint: `golangci-lint run`. "
        "Wrap errors: `fmt.Errorf('context: %w', err)`. Use `errors.Is()` / `errors.As()`. "
        "Prefer stdlib net/http over frameworks for simple services. "
        "Goroutines: always use context for cancellation. Close channels from sender only."
    ),
    "flutter": (
        "Test: `flutter test`. Run: `flutter run`. Build APK: `flutter build apk`. "
        "State: Riverpod (recommended) or Bloc. Widget tests: `testWidgets()`. "
        "`const` constructors everywhere possible. `async/await` with proper error handling. "
        "Golden tests: `flutter test --update-goldens`."
    ),
    "kotlin-android": (
        "Test: `./gradlew test`. UI test: `./gradlew connectedAndroidTest`. "
        "Jetpack Compose: `@Composable` functions, `remember {}`, `LaunchedEffect`. "
        "ViewModel + StateFlow/SharedFlow. Hilt for DI. Coroutines for async. "
        "Navigation: NavController + NavHost. Room for local DB."
    ),
    "vue": (
        "Build: `npm run build`. Test: `npm run test:unit` (vitest). "
        "Composition API with `<script setup>`. Pinia for state. Vue Router 4. "
        "`defineProps()`, `defineEmits()`, `ref()`, `computed()`, `watch()`. "
        "Never mutate props — emit events upward."
    ),
    "svelte": (
        "Build: `npm run build`. Test: `npm run test`. Dev: `npm run dev`. "
        "SvelteKit: +page.svelte, +layout.svelte, +page.server.ts (load fn). "
        "Stores: `writable()`, `readable()`, `derived()`. Two-way: `bind:value`. "
        "Transitions: `transition:fade`, `animate:flip`."
    ),
}


def detect_stack(project_path: str = "", specs_text: str = "") -> list[str]:
    """Detect tech stack from project files + text.
    Returns sorted list of tech names (e.g. ['react', 'python-fastapi']).
    """
    techs: set[str] = set()

    if project_path:
        p = Path(project_path)
        for tech, rules in _RULES.items():
            for fname in rules.get("files", []):
                if (p / fname).exists():
                    techs.add(tech)
                    break
                # shallow glob (2 levels)
                if list(p.glob(f"*/{fname}")) or list(p.glob(f"**/{fname}")):
                    techs.add(tech)
                    break

    if specs_text:
        text_lower = specs_text.lower()
        for tech, rules in _RULES.items():
            if tech in techs:
                continue
            for kw in rules.get("keywords", []):
                if kw.lower() in text_lower:
                    techs.add(tech)
                    break

    return sorted(techs)


def load_tech_skills(techs: list[str], max_chars: int = 3000) -> str:
    """Load tech skill content from skills/tech/{tech}.yaml (Option A).
    Falls back to inline hints if file missing (Option C).
    Returns compiled prompt string.
    """
    parts: list[str] = []
    total = 0

    for tech in techs:
        if total >= max_chars:
            break

        content = ""
        name = tech

        # Try YAML file first (Option A)
        skill_file = _TECH_SKILLS_DIR / f"{tech}.yaml"
        if skill_file.exists():
            try:
                data = yaml.safe_load(skill_file.read_text()) or {}
                content = data.get("content", "")
                name = data.get("name", tech)
            except Exception:
                pass

        # Fallback: inline hint (Option C)
        if not content:
            content = _INLINE_HINTS.get(tech, "")

        if content:
            chunk = content[: min(1500, max_chars - total)]
            parts.append(f"### {name}\n{chunk}")
            total += len(chunk)

    return "\n\n".join(parts)


def generate_dynamic_context(techs: list[str]) -> str:
    """Option C: Compact ephemeral block — no files required.
    Returns 1-2 line per tech with build/test commands + key idioms.
    """
    if not techs:
        return ""

    lines = [f"## Detected Tech Stack: {', '.join(techs)}"]
    for tech in techs:
        hint = _INLINE_HINTS.get(tech)
        if hint:
            lines.append(f"- **{tech}**: {hint}")

    return "\n".join(lines)


# Roles that benefit from tech skill injection
_DEV_ROLES = frozenset(
    [
        "dev",
        "backend",
        "frontend",
        "fullstack",
        "mobile",
        "qa",
        "test",
        "lead",
        "architect",
    ]
)


def should_inject(role: str) -> bool:
    """Returns True if this agent role should receive tech skill injection."""
    role_l = (role or "").lower()
    return any(r in role_l for r in _DEV_ROLES)
