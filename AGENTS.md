# AGENTS — Software Factory

## DELEGATION
- ALL tasks → sub-agents via `opencode serve` + MiniMax M2.7
- `opencode serve --port 4567 &` — start once per session
- Multi-task → parallel background, then wait

## 324 AGENTS (key roles)
| Role | Count | Tools |
|------|-------|-------|
| dev | 35+ | code_read/write/edit, list_files, run_tests |
| qa | 18+ | test_automation, fixture_gen, playwright |
| security | 14+ | sast_tools, pentest_tools, trivy |
| product | 10+ | create_feature, create_story, web_search |
| architect | 7+ | adr_writer, iac_engineer |
| devops | 8+ | docker, deploy, monitoring, backup |
| safe | 6+ | rte, epic_owner, lean_portfolio_manager |
| doc | 3 | doc_writer, changelog_gen |

## TOOL FLOOR (role-based)
- developer: ~60 tools (code_*, git_*, docker_*, platform_*)
- qa: tests, fixtures, browser, performance
- security: sast, pentest, trivy, license_scan
- Floor tools merged with agent specialization tools

## PROMPT PATTERNS
- implementer: TDD + DONE/NEEDS_CONTEXT/BLOCKED
- spec_reviewer: APPROVED/REJECTED + MISSING/WRONG/EXTRA
- code_quality_reviewer: Critical/Important/Minor
- finish: Merge/PR/Keep/Discard

## SKILLS
- 2389 skills in YAML + GitHub cache
- Selection: Thompson Sampling Beta(α=wins, β=losses)
- 3-tier: context-pattern → declared → trigger-matched

## ADVERSARIAL (L0+L1)
- L0: deterministic checks (25 rules, 0ms)
- L1: LLM semantic review
- VETO if score <60 on critical dims
- Multi-vendor: Brain=Opus, Worker=MiniMax, Security=GLM
