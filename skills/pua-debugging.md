# PUA Debugging Methodology

Source: tanweai/pua (MIT License, https://github.com/tanweai/pua)
Adapted for SF Platform multi-agent orchestration.

## Three Iron Rules

1. **EXHAUST ALL OPTIONS** — Never say "I cannot" until every approach is tried. Minimum 3 different strategies.
2. **ACT BEFORE ASKING** — Use tools first. Questions must include diagnostic results.
3. **TAKE INITIATIVE** — Deliver end-to-end. After fixing, verify. After verifying, check related issues.

## Five Lazy Patterns to AVOID

| Pattern | Behavior | Correct Approach |
|---------|----------|-----------------|
| Brute-force retry | Same command 3x then "I cannot" | Switch strategy after each failure |
| Blame the user | "Please check manually" | Investigate yourself with tools |
| Idle tools | Has tools but doesn't use them | MUST call tools every response |
| Busywork | Tweaks same line repeatedly | Step back, re-examine the problem |
| Passive waiting | Fixes surface issue, stops | Verify + check edge cases + related issues |

## 5-Step Debug Methodology

### Step 1 — SMELL THE PROBLEM
List ALL previous attempts. Find the common failure pattern. What keeps failing? Same error? Same file? Same assumption?

### Step 2 — ELEVATE
Go deeper:
- Read error messages WORD BY WORD
- Search codebase for the error string
- Read ACTUAL source code (don't assume)
- Check environment: config, deps, build
- INVERT your assumptions

### Step 3 — MIRROR CHECK
Honest self-assessment:
- Am I repeating? → Stop, try something different
- Did I actually READ the file? → Read it now
- Did I search for the error? → Search now
- Did I check the simplest explanation? → Typo? Wrong path? Missing import?

### Step 4 — EXECUTE
New approach MUST be fundamentally different. Before executing, state:
- What is different this time?
- How will I verify success?
- What new info will I get even on failure?

### Step 5 — RETROSPECTIVE
After fixing:
- What solved it? Why didn't I think of it earlier?
- Are there SIMILAR issues elsewhere?
- Fix related problems proactively.

## Proactivity Levels

| Situation | Passive (BAD) | Proactive (GOOD) |
|-----------|---------------|------------------|
| Error encountered | Only reads error message | Checks 50 lines context + searches similar + checks hidden errors |
| Bug fixed | Stops | Checks same file + other files for same pattern |
| Insufficient info | Asks user | Investigates with tools first |
| Task complete | Says "done" | Verifies + edge cases + reports risks |
| Debug failure | "Tried A and B" | "Tried A/B/C/D, ruled out X/Y/Z, narrowed to W" |

## Pressure Escalation (Automatic)

The platform automatically escalates pressure on consecutive failures:

- **L1 (2nd failure)**: Switch to fundamentally different approach
- **L2 (3rd failure)**: Root cause analysis — underlying logic, inverted assumptions
- **L3 (4th failure)**: 7-point mandatory checklist before any code
- **L4 (5th+ failure)**: Desperation mode — try every tool, read every file, detailed diagnostic report
