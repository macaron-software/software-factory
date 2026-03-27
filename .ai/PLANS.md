# Plans — Software Factory

## ACTIVE
No active milestones.

## BACKLOG
- [ ] iOS/Android mobile clients (SwiftUI + Kotlin)
- [ ] Rust/gRPC services (popinz-v2-rust)
- [ ] Mes Aides: 71 aids + datagouv MCP

## STACK
- Py/FastAPI+HTMX (SF) · Rust/Axum+React (PSY)
- Rust+WASM+SwiftUI+Kotlin (MesAides)

## ENVIRONMENTS
| Env | URL | LLM |
|-----|-----|-----|
| Local dev | localhost:8099 | local-mlx |
| OVH demo | $OVH_IP | minimax |
| Azure prod | $SF_NODE1_IP | azure-openai |

## QUALITY
- 17 gates: guardrails · veto · prompt_inject · tool_acl · adv-L0 · AC-reward · RBAC · CI
- Thompson Sampling for skill selection
- Darwin GA for team evolution
