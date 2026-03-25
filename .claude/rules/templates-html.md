---
description: Jinja2/HTMX templates — dark theme, HTMX patterns, no emoji
globs: platform/web/templates/**/*.html
---

- HTMX: use `hx-get="/partial/X"` + `hx-trigger="load"` for dynamic content.
- CSS: custom-property tokens only. Dark-first with `[data-theme]`. No inline styles with hardcoded hex.
- No emoji, no gradient, no FontAwesome. Feather SVG icons only.
- No fake/mock data. All data from live PG queries.
- Markdown rendering: use `md()` function for agent content. Never inject raw markdown.
- Skeleton loading: every data-dependent component needs a skeleton variant with `aria-busy="true"`.
- i18n: 40 locales supported. Use `{{ _('key') }}` for all user-facing strings.
- RTL support: use CSS logical properties (`margin-inline-start`, not `margin-left`).
- readyState check for HTMX (not DOMContentLoaded).
