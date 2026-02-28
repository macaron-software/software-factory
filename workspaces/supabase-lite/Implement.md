# Supabase Lite — Implementation Instructions

## How to execute this project

You are an autonomous software engineering agent. Your job is to implement
**Supabase Lite** according to `Plans.md`, following the architecture in `Architecture.md`,
respecting all constraints in `Prompt.md`.

## Execution Rules

1. **Read `Plans.md` first** — milestones are your source of truth
2. **Work milestone by milestone** — complete, validate, then move on
3. **Run validation commands after each milestone** — if they fail, fix before continuing
4. **Keep `Documentation.md` updated** — log what you built, what's next, known issues
5. **Scope discipline** — don't expand scope. If something is not in the milestone, skip it
6. **Commit after each validated milestone**: `git commit -m "feat: milestone N — <description>"`
7. **Max 3 failures** → stop, report in `Documentation.md`, wait for human steering

## Workflow

```
Read Plans.md
  ↓
Pick next pending milestone
  ↓
Implement all tasks in that milestone
  ↓
Run: npm run lint && npm run build && npm run test
  ↓
If FAIL → fix → re-run (max 3 rounds)
  ↓
Update Documentation.md: milestone → done, what was built
  ↓
git commit
  ↓
Next milestone
```

## File conventions
- TypeScript strict mode, no `any`
- All async routes use `async/await`, no callback-style
- Error responses: `{error: string, code?: string}`
- Success responses: wrapped in `{data: T}` for REST; raw for auth
- Environment variables from `process.env` with `dotenv` in dev

## Where to find things
- `Prompt.md` — what to build, success criteria
- `Plans.md` — milestones and validation commands
- `Architecture.md` — file structure, data model, invariants
- `Documentation.md` — current status, decisions, known issues
