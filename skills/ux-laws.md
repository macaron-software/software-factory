---
name: ux-laws
version: "2.0.0"
description: >
  Applies the 30 Laws of UX (Jon Yablonski — https://lawsofux.com) to user story
  writing, UX audit, design critique, and mobile/offline resilience patterns.
  Full origins, real product examples, cross-law relationships, and 4 application contexts.
metadata:
  category: design
  source: "https://lawsofux.com — Jon Yablonski (MIT)"
  integrated_by: "macaron-software/software-factory"
  integration_rationale: >
    Evidence-based cognitive laws reduce the subjective gap in UX review.
    Applied in 4 contexts: (1) US acceptance criteria — measurable cognitive constraints;
    (2) UX audit — 30-law checklist; (3) design critique — explain WHY not just THAT;
    (4) mobile/offline UX — network resilience with empathic messaging.
  triggers:
    - "when writing user stories or acceptance criteria"
    - "when reviewing or auditing a UI/UX"
    - "when critiquing a design proposal"
    - "when doing a UX heuristic evaluation"
    - "when discussing cognitive load or user mental models"
    - "when agent must evaluate if a UI is too complex"
    - "when defining performance SLAs for user-facing interactions"
    - "when designing mobile or offline-capable features"
    - "when handling network errors, retries, or disconnection states"
---

# Laws of UX v2 — Agent Application Guide

Source: https://lawsofux.com (Jon Yablonski, MIT License)
All 30 laws with origins, real product examples, cross-law relations, and 4 application contexts.

---

## THE 30 LAWS — Full Reference

### 1. Aesthetic-Usability Effect
*Users often perceive aesthetically pleasing design as design that's more usable.*
**Origin**: Kurosu & Kashimura, Hitachi Design Center, 1995. Tested 26 ATM UI variations with 252 participants — stronger correlation between aesthetic appeal and *perceived* ease of use than actual ease of use.
**Key insight**: Beautiful design masks usability problems — it can hide issues during testing too.
**Takeaways**:
1. Aesthetically pleasing design creates positive brain response → users believe it works better.
2. Users tolerate minor usability issues more in beautiful designs.
3. ⚠️ Visually pleasing design can hide usability problems in usability testing.
**AC pattern**: "The visual design score (System Usability Scale aesthetic subscale) is ≥70"

### 2. Choice Overload
*People get overwhelmed when presented with too many options.*
**Origin**: Alvin Toffler coined "overchoice" in *Future Shock* (1970). Related to → **Hick's Law**.
**Takeaways**:
1. Too many options hurt decision-making quality and overall experience perception.
2. Enable side-by-side comparison of related items when comparison is necessary (e.g. pricing tiers).
3. Prioritize content shown at any moment (featured product); provide narrowing tools (search, filter).
**AC pattern**: "Primary selection has ≤7 options; all others are behind filter/search"

### 3. Chunking
*Individual pieces of information are broken down and grouped into meaningful wholes.*
**Origin**: George A. Miller's 1956 paper "The Magical Number Seven, Plus or Minus Two". Related to → **Miller's Law**.
**Takeaways**:
1. Chunking enables scanning — users identify goal-relevant information faster.
2. Visually distinct groups with clear hierarchy align with how people evaluate digital content.
3. Use modules, separators, and hierarchy to show underlying relationships.
**AC pattern**: "Content is organized into ≤7 named groups per screen level"

### 4. Cognitive Bias
*Systematic errors in thinking that influence perception and decision-making.*
**Origin**: Amos Tversky & Daniel Kahneman, 1972. Demonstrated human judgment deviates from rational choice theory via heuristics — mental shortcuts that introduce systematic errors.
**Takeaways**:
1. Mental shortcuts (heuristics) increase efficiency but introduce biases without our awareness.
2. Understanding biases (confirmation bias, anchoring, availability heuristic) helps design against dark patterns.
3. ⚠️ Never exploit cognitive biases for conversion — design ethically. Related to → **Peak-End Rule**.
**Design alert**: Identify dark patterns (false scarcity, misleading defaults, roach motel) — refuse to implement.

### 5. Cognitive Load
*The amount of mental resources needed to understand and interact with an interface.*
**Origin**: John Sweller, late 1980s, expanding on Miller's information processing theories. Published "Cognitive Load Theory, Learning Difficulty, and Instructional Design" (1988). Related to → **Miller's Law**, **Working Memory**.
**Types**:
- **Intrinsic**: effort to carry info relevant to the goal (unavoidable)
- **Extraneous**: mental processing from distracting/unnecessary design elements (reducible)
**Takeaways**:
1. When information exceeds working space → tasks harder, details missed, user overwhelmed.
2. Remove extraneous cognitive load: unnecessary elements, ambiguous labels, redundant choices.
3. Design each screen to do ONE thing.
**AC pattern**: "Each screen has exactly one primary action; secondary actions are collapsed"

### 6. Doherty Threshold
*Productivity soars when computer and user interact at a pace (<400ms) where neither waits.*
**Origin**: Walter J. Doherty & Ahrvind J. Thadani, IBM Systems Journal, 1982. Previous standard was 2000ms; they established 400ms as the threshold for "addicting" interaction.
**Takeaways**:
1. System feedback within **400ms** keeps user attention and increases productivity.
2. Use *perceived* performance: skeleton screens, optimistic updates, instant visual response.
3. Animations engage visually while loading happens in background.
4. Progress bars make waits tolerable — even if inaccurate.
5. ⚠️ Intentional artificial delay can *increase* perceived value and trust (e.g. "Calculating..." for 800ms).
**SLA standard**: 0–100ms=instant | 100–400ms=fast | 400ms–1s=acceptable+indicator | >1s=loading state required | >10s=background task+notification

### 7. Fitts's Law
*The time to acquire a target is a function of distance to and size of the target.*
**Origin**: Paul Fitts, 1954. MT = a + b × log₂(2D/W). Fast movements + small targets = higher error rate.
**Takeaways**:
1. Touch targets must be large enough for accurate selection.
2. Adequate spacing between touch targets (min 8px; 16px preferred).
3. Place targets near user's natural task area (e.g. Submit near last field, not top-right).
**Minimums**: Touch target ≥44×44px (Apple HIG) | ≥48×48dp (Material) | ≥24×24px (WCAG 2.5.5 AAA)
**AC pattern**: "All interactive targets have a minimum touch area of 44×44px"

### 8. Flow
*Mental state of full immersion in an activity — energized focus, control, enjoyment.*
**Origin**: Mihály Csíkszentmihályi, 1975. The balance point between challenge and skill.
**Takeaways**:
1. Flow = balance between task difficulty and user skill level.
2. Too hard → frustration; too easy → boredom. Match challenge to skill.
3. Provide feedback so users know what was done and what was accomplished.
4. Remove friction: optimize efficiency, make content discoverable.
**Anti-patterns**: Interrupt-driven confirmations, mode errors, unexpected navigation, modal dialogs mid-task.
**AC pattern**: "The primary user flow contains 0 forced interruptions (modals, required redirects)"

### 9. Goal-Gradient Effect
*The tendency to approach a goal increases with proximity to the goal.*
**Origin**: Clark Hull, 1932 (behaviorist). Rats in a straight alley ran faster as they approached food. Implications for human reward programs were understudied until Kivetz et al. (2006). Related to → **Zeigarnik Effect**.
**Takeaways**:
1. The closer users are to completing a task, the faster they work toward it.
2. Artificial progress toward a goal increases motivation to complete.
3. Always show how close users are to completion.
**AC pattern**: "Multi-step flows display a progress indicator showing current step / total steps"
**Tactic**: Pre-fill loyalty cards (coffee stamp 2/10 perceived as more motivating than 0/8 even with more stamps needed)

### 10. Hick's Law
*The time to make a decision increases with the number and complexity of choices.*
**Origin**: William Edmund Hick & Ray Hyman, 1952. RT = b × log₂(n + 1).
**Examples**: Google homepage (1 action), Apple TV remote (transfers complexity to TV interface), Slack progressive onboarding (hide all features except messaging input initially).
**Takeaways**:
1. Minimize choices when response time is critical.
2. Break complex tasks into smaller steps.
3. Highlight recommended options (reduce perceived complexity).
4. Progressive onboarding for new users.
5. ⚠️ Don't oversimplify to abstraction — removing too much removes capability.
**AC pattern**: "Primary navigation has ≤7 items; recommended option is visually highlighted"

### 11. Jakob's Law
*Users spend most time on other sites — they prefer your site works the same way.*
**Origin**: Jakob Nielsen, Nielsen Norman Group.
**Example**: YouTube 2017 redesign — allowed users to preview new Material Design UI, revert to old version, submit feedback. Managed mental model transition without friction.
**Takeaways**:
1. Users transfer expectations from familiar products to new ones that appear similar.
2. Leverage existing mental models → users focus on tasks, not on learning new models.
3. When redesigning: give users time with the old version before forcing the new one.
**Related**: → **Mental Model**
**AC pattern**: "All standard patterns (form save, navigation breadcrumbs, back button) follow established web conventions"

### 12. Law of Common Region
*Elements tend to be perceived as groups if they share an area with a clearly defined boundary.*
**Origin**: Gestalt psychology principles (Prägnanz). One of 5 grouping categories.
**Takeaways**:
1. Common region creates clear structure for quickly understanding element relationships.
2. Border around elements = easy way to create common region.
3. Background color behind a group = alternative way to create common region.
**Related**: → **Law of Proximity**, **Law of Prägnanz**

### 13. Law of Proximity
*Objects that are near each other tend to be grouped together.*
**Origin**: Gestalt psychology.
**Example**: Google search results — spacing between results groups each result as a related cluster.
**Takeaways**:
1. Proximity establishes relationship between nearby objects.
2. Elements in close proximity are perceived to share similar functionality or traits.
3. Proximity helps users organize information faster.
**Rule**: Form labels must be closer to their input than to adjacent inputs.

### 14. Law of Prägnanz (Law of Good Figure)
*People perceive ambiguous/complex images as the simplest form possible.*
**Origin**: Max Wertheimer, 1910. Observation at a railroad crossing — lights appearing as single moving light (phi phenomenon). Foundation of Gestalt psychology.
**Takeaways**:
1. Human eye finds simplicity and order in complex shapes — prevents information overload.
2. Simple figures are processed and remembered better than complex ones.
3. The eye simplifies complex shapes into unified forms.
**Design rule**: Icons must be reducible to their simplest geometric form and still recognizable.

### 15. Law of Similarity
*The human eye perceives similar elements as a group, even if separated.*
**Origin**: Gestalt psychology. Similarity via color, shape, size, orientation, movement.
**Takeaways**:
1. Visually similar elements will be perceived as related.
2. Color, shape, size, orientation, movement signal group membership and shared meaning.
3. Links and navigation must be visually differentiated from regular text.
**AC pattern**: "All clickable elements use the same visual treatment (color + underline/hover state)"

### 16. Law of Uniform Connectedness
*Visually connected elements are perceived as more related than unconnected ones.*
**Origin**: Gestalt psychology.
**Example**: Google search results — borders around featured snippets/videos create visual connection and priority.
**Takeaways**:
1. Group similar functions with shared visual connection: colors, lines, frames, shapes.
2. Tangible connecting references (lines, arrows) create visual connection between sequential elements.
3. Use uniform connectedness to show context or emphasize relationships.

### 17. Mental Model
*A compressed model of what we think we know about a system and how it works.*
**Origin**: Kenneth Craik, *The Nature of Explanation* (1943). Related to → **Jakob's Law**.
**Takeaways**:
1. We form working models about systems and apply them to similar new situations.
2. Match designs to users' mental models → they focus on tasks, not on learning.
3. E-commerce conventions (product cards, carts, checkout) exist precisely because they match mental models.
4. Shrinking the gap between designer mental models and user mental models is UX's biggest challenge.
**Methods**: user interviews, personas, journey maps, empathy maps, card sorting.

### 18. Miller's Law
*The average person can only keep 7 (±2) items in working memory.*
**Origin**: George Miller, 1956, "The Magical Number Seven, Plus or Minus Two". Applied to short-term memory capacity and channel capacity.
**Example**: Phone numbers chunked as (XXX) XXX-XXXX — 10 digits in 3 chunks.
**Takeaways**:
1. ⚠️ Don't use "7" to justify artificial design limitations — use chunking instead.
2. Organize content into smaller chunks.
3. Short-term memory capacity varies per individual and context.
**Related**: → **Chunking**, **Cognitive Load**, **Working Memory**

### 19. Occam's Razor
*Among equally good solutions, prefer the one with fewest assumptions.*
**Origin**: William of Ockham (c.1287–1347), "lex parsimoniae" — law of parsimony.
**Takeaways**:
1. The best way to reduce complexity is to not create it in the first place.
2. Analyze each element — remove as many as possible without compromising function.
3. "Done" = when nothing more can be removed, not when nothing more can be added.
**Design test**: "Can this feature/field/step be removed? What breaks?"

### 20. Paradox of the Active User
*Users never read manuals — they start using software immediately.*
**Origin**: Mary Beth Rosson & John Carroll, 1987. New users skipped manuals, hit roadblocks, but still refused to read documentation.
**Takeaways**:
1. Users are motivated to complete *immediate* tasks — they won't invest in upfront learning.
2. They'd save time long-term by learning the system, but they don't — this is the paradox.
3. Make guidance *contextual and inline* — tooltips, coach marks, empty states — not separate docs.
**AC pattern**: "The primary action is discoverable within 10 seconds without documentation"

### 21. Pareto Principle (80/20 Rule)
*Roughly 80% of effects come from 20% of causes.*
**Origin**: Vilfredo Pareto observed 80% of Italy's land owned by 20% of population.
**Takeaways**:
1. Inputs and outputs are not evenly distributed.
2. A large group may have only a few meaningful contributors.
3. Focus majority of effort on areas that bring largest benefits to most users.
**Application**: Identify the 20% of features used 80% of the time → make those prominent. Deprioritize the rest.

### 22. Parkinson's Law
*Any task inflates to fill all available time.*
**Origin**: Cyril Northcote Parkinson, *The Economist*, 1955.
**Takeaways**:
1. Limit task time to what users expect it'll take.
2. Reducing actual duration below expected duration improves UX.
3. Autofill, saved info, smart defaults prevent task inflation (checkout, booking forms).
**AC pattern**: "The checkout form pre-fills all available data from user profile; only unknowns require input"

### 23. Peak-End Rule
*People judge experiences based on peak and end, not on average.*
**Origin**: Kahneman, Fredrickson, Schreiber & Redelmeier, 1993 "When More Pain Is Preferred to Less: Adding a Better End." Cold water hand experiment — 14°C for 60s vs 14°C for 60s + 15°C for 30s: participants preferred the longer trial. Related to → **Cognitive Bias**.
**Examples**:
- Mailchimp's high-five illustration after sending a campaign (peak delight moment)
- Uber showing driver location immediately after request to reduce perceived wait (avoiding negative peak)
**Takeaways**:
1. Pay close attention to most intense points AND final moments of the user journey.
2. Design to delight at the most helpful/entertaining moment.
3. ⚠️ People recall negative experiences more vividly than positive ones.
**AC pattern**: "On task completion, user receives a clear confirmation with positive reinforcement and explicit next step"

### 24. Postel's Law (Robustness Principle)
*Be liberal in what you accept, and conservative in what you send.*
**Origin**: Jon Postel, TCP specification. "Be conservative in what you do, be liberal in what you accept from others."
**Takeaways**:
1. Be empathetic, flexible, and tolerant of various user inputs.
2. Anticipate any input format, access method, or capability.
3. More anticipation = more resilient design.
4. Accept variable input (e.g. phone: accept +33 6 12, 0612, 06-12-34, 06 12 34 56) → normalize internally → output consistently.
**AC pattern**: "Phone/date/postal code fields accept all common format variants and normalize on blur"

### 25. Selective Attention
*We focus attention only on the subset of stimuli related to our goals.*
**Origin**: Multiple theories from 1950s–1970s: Broadbent Filter Theory (1958), Cherry's Cocktail Party Effect (1953), Treisman's Attenuation Model (1960). Related to → **Von Restorff Effect**.
**Key phenomena**:
- **Banner Blindness**: users ignore ad-like content even when it contains important info
- **Change Blindness**: significant interface changes go unnoticed without strong cues
**Takeaways**:
1. Users filter out irrelevant information — designers must guide attention, prevent overwhelm.
2. Never style important content to look like ads; never place content where ads typically appear.
3. Signal important changes with strong visual cues (animation, color change, toast notifications).
**AC pattern**: "No critical action or status message is placed in a location typically used for ads"

### 26. Serial Position Effect
*Users best remember first and last items in a series.*
**Origin**: Herman Ebbinghaus. Primacy effect (beginning recalled via long-term memory) + Recency effect (end recalled via working memory).
**Takeaways**:
1. Place least important items in the middle of lists.
2. Place key actions at far left/right within navigation elements.
3. Most critical CTA in primary (first) or final (last) position in a group.
**AC pattern**: "Primary CTA is positioned first or last in its action group; destructive actions are in the middle"

### 27. Tesler's Law (Law of Conservation of Complexity)
*For any system, there is a certain amount of complexity that cannot be reduced.*
**Origin**: Larry Tesler, Xerox PARC, mid-1980s. "An engineer should spend an extra week reducing complexity vs making millions of users spend an extra minute."
**Takeaways**:
1. All processes have irreducible complexity — it must be assumed by system OR user.
2. Always move complexity to the system (defaults, validation, automation), not the user.
3. ⚠️ Tognazzini's caveat: when you simplify, users attempt more complex tasks — new complexity appears.
4. Design for real users, not idealized rational ones.
**AC pattern**: "Every required input field has a smart default or can be pre-filled from available context"

### 28. Von Restorff Effect (Isolation Effect)
*When multiple similar objects are present, the one that differs is most likely remembered.*
**Origin**: Hedwig von Restorff (1906–1962), 1933 study on categorically similar item lists with one isolated item.
**Takeaways**:
1. Make important information and key actions visually distinctive.
2. ⚠️ Use restraint — too many "distinctive" elements compete and none stand out (crying wolf).
3. ⚠️ Don't rely exclusively on color for contrast (color blindness).
4. ⚠️ Consider motion sensitivity when using animation for contrast.
**AC pattern**: "Exactly one primary CTA per screen; all others are visually secondary"

### 29. Working Memory
*Cognitive system that temporarily holds and manipulates information needed for tasks.*
**Origin**: Term coined by Miller, Galanter & Pribram; formalized by Atkinson & Shiffrin (1968). Capacity: 4–7 chunks, fades after 20–30 seconds.
**Key insight**: Brains excel at *recognition* (seen before?) but struggle at *recall* (what was on previous screen?). Related to → **Cognitive Load**.
**Takeaways**:
1. Design with working memory limit in mind — show only necessary and relevant information.
2. Support recognition over recall: differentiate visited links, show breadcrumbs, display what was selected.
3. Carry critical info across screens (comparison tables, persistent summary bars in checkout).
**AC pattern**: "Users never need to remember information from one screen to complete an action on another"

### 30. Zeigarnik Effect
*People remember uncompleted or interrupted tasks better than completed tasks.*
**Origin**: Bluma Zeigarnik (1900–1988), Soviet psychologist, Berlin School. Memory study in 1920s comparing incomplete vs complete tasks. Related to → **Goal-Gradient Effect**.
**Takeaways**:
1. Provide clear signifiers of additional/available content (invite discovery).
2. Artificial progress toward a goal increases motivation to complete.
3. Show clear progress indicators.
**Tactic**: Multi-step forms: save progress, show "Continue where you left off" on return. The unfinished task will stay on the user's mind.
**AC pattern**: "If a user abandons a multi-step flow, their progress is saved and highlighted on next visit"

---

## CROSS-LAW RELATIONSHIP MAP

| Law | Closely Related To |
|-----|--------------------|
| Choice Overload | Hick's Law |
| Chunking | Miller's Law |
| Cognitive Load | Miller's Law, Working Memory |
| Cognitive Bias | Peak-End Rule |
| Goal-Gradient Effect | Zeigarnik Effect |
| Jakob's Law | Mental Model |
| Law of Common Region | Law of Proximity, Law of Prägnanz |
| Mental Model | Jakob's Law |
| Miller's Law | Chunking, Cognitive Load, Working Memory |
| Peak-End Rule | Cognitive Bias |
| Selective Attention | Von Restorff Effect |
| Working Memory | Cognitive Load |
| Zeigarnik Effect | Goal-Gradient Effect |

---

## CONTEXT A — Writing User Stories and Acceptance Criteria

When writing US, use these laws to make acceptance criteria **measurable and cognitive-science-backed**.

### Hick's Law
- **AC pattern**: "Given N choices are presented, the user reaches a decision in under X seconds"
- **Rule**: max 5–7 primary actions per screen; progressively disclose the rest
- **Violation**: "User can configure 15 settings on the first screen" → violates Hick's

### Miller's Law
- **AC pattern**: "No single view presents more than 7 items without pagination or grouping"
- **Rule**: chunk related items; use progressive disclosure beyond 7

### Cognitive Load
- **AC pattern**: "The feature does not add a new required input field to an existing flow"
- **Question**: "What decision or memory burden does this remove from the user?"

### Doherty Threshold
- **AC pattern**: "The page responds to user action within 400ms (visual feedback or result)"
- **Rule**: if backend takes >400ms, show immediate optimistic feedback or skeleton screen

### Goal-Gradient Effect
- **AC pattern**: "A progress indicator shows the user's position in the X-step flow"

### Peak-End Rule
- **AC pattern**: "On form submission, user sees clear success confirmation with next step"
- **Violation**: 8-step form ending with "Your request was submitted" (flat, emotionless ending)

### Pareto Principle (80/20)
- **Use as scoping filter**: identify the 20% of features delivering 80% of user value → build those first

### Tesler's Law
- **Question**: "Which side — user or system — is better equipped to handle this complexity?"
- **Rule**: move complexity to system; expose simple surface to user

### Occam's Razor
- **AC pattern**: "The feature can be used without reading documentation"
- **Test**: "Can any element be removed without breaking the feature?"

### Parkinson's Law
- **Rule**: constrain story scope explicitly. Add explicit exclusion lines to US: "OUT OF SCOPE: X, Y, Z"

### Zeigarnik Effect
- **AC pattern**: "If the user leaves a multi-step flow, their progress is saved and a reminder is shown on return"

### Postel's Law
- **AC pattern**: "Phone/date/postal fields accept all common formats; normalized on blur/submit"

---

## CONTEXT B — UX Audit Checklist (30 Laws)

Report format per law: **Law | Status (✅/❌/⚠️/N/A) | Evidence | Recommendation**

### PERCEPTION & GROUPING (Gestalt)
| Law | What to check |
|-----|--------------|
| Law of Proximity | Related items visually close; unrelated items have whitespace separation |
| Law of Common Region | Related items share a container/border/background |
| Law of Similarity | Items with similar function look similar (color, shape, size) |
| Law of Uniform Connectedness | Connected items (lines, borders) imply relationship |
| Law of Prägnanz | Complex graphics reduce to their most readable, simplest form |

### ATTENTION & MEMORY
| Law | What to check |
|-----|--------------|
| Miller's Law | No list/menu/set exceeds 7 (±2) ungrouped items |
| Von Restorff Effect | Primary CTA is visually distinct from secondary actions (exactly 1 standout) |
| Serial Position Effect | Most important items are first or last in lists/navs |
| Selective Attention | Non-critical content doesn't compete with main task; nothing looks like an ad |
| Working Memory | Users never need to remember info from screen A to act on screen B |
| Mental Model | UI matches what users know from other apps (Jakob's Law conventions) |

### DECISION & INTERACTION
| Law | What to check |
|-----|--------------|
| Hick's Law | Primary options ≤7; secondary options hidden until needed; recommended option highlighted |
| Fitts's Law | Click/touch targets ≥44×44px, close to natural cursor/thumb path, adequate spacing |
| Cognitive Load | Each page asks user to do exactly one thing |
| Choice Overload | Dropdowns/filters have sensible defaults; visible options ≤10; comparison available |
| Flow | Interaction sequence uninterrupted; 0 forced modals mid-task; no dead-ends |

### TIME & PERFORMANCE
| Law | What to check |
|-----|--------------|
| Doherty Threshold | Every user action gets visual feedback in <400ms |
| Goal-Gradient Effect | Progress indicator in multi-step flows; current step shown |
| Peak-End Rule | Key moment (peak) and closing confirmation (end) are well-designed |
| Zeigarnik Effect | Long/async tasks show saved state on return |
| Parkinson's Law | Form pre-fills available data; autofill leveraged for completion |

### COGNITIVE PRINCIPLES
| Law | What to check |
|-----|--------------|
| Aesthetic-Usability Effect | UI is visually clean and consistent (users perceive prettier = more usable) |
| Chunking | Information grouped into meaningful units (≤7 per group) |
| Cognitive Bias | No dark patterns exploiting anchoring, scarcity, urgency, or social proof |
| Paradox of Active User | Core actions discoverable <10 seconds without documentation |
| Postel's Law | Input: liberal (multiple formats accepted); Output: consistent and normalized |
| Tesler's Law | Complexity absorbed by system (defaults, validation, automation), not user |

### STRATEGY & STRUCTURE
| Law | What to check |
|-----|--------------|
| Jakob's Law | Conventions from other apps respected (save, back, nav patterns) |
| Occam's Razor | No feature/field exists without a clear user need |
| Pareto Principle | The 20% of features used most are most prominent and optimized |

---

## CONTEXT C — Design Critique Template

```
## UX Laws Critique — [Feature Name]

### Violations (must fix before ship)
- **[Law Name]**: [What is violated] → [Recommended fix]

### Warnings (should fix in next iteration)
- **[Law Name]**: [Potential issue] → [Suggested improvement]

### Compliant (notable strengths)
- **[Law Name]**: [What the design does right]

### Net Assessment
Cognitive load: [Low/Medium/High]
Decision complexity: [Low/Medium/High — Hick's score: N options at primary level]
Memory demand: [Low/Medium/High — Miller's score: N ungrouped items max]
Peak moment: [Identified / Not designed]
End moment: [Designed / Generic]
```

---

## CONTEXT D — Mobile & Network Resilience UX

*Apply when designing web async, native mobile apps, or any feature with network dependency.*

### Doherty Threshold → Network States
Map response time to UX treatment:

| Latency | Treatment |
|---------|-----------|
| 0–100ms | No indicator needed — instant |
| 100–400ms | Subtle spinner (don't interrupt flow) |
| 400ms–1s | Progress indicator + context label |
| 1s–3s | Skeleton screen (content shape placeholder) |
| 3s–10s | Progress bar + estimated time + cancel option |
| >10s | Background task + "We'll notify you" + dismissable |

### Offline / Network Loss States
**Empathic messaging patterns** (not technical error messages):

```
❌ BAD:  "ERR_NETWORK_CHANGED"
❌ BAD:  "Request failed with status 0"
❌ BAD:  "No internet connection."

✅ GOOD (empathic): 
- "You're offline — don't worry, your work is saved."
- "Lost connection. We'll keep trying and sync when you're back online."
- "Slow connection — this might take a moment. Your data is safe."
- "Back online! Syncing your changes now..."
```

**Required states to design**:
1. **Offline detected**: empathic message, show cached data if available, queue pending actions
2. **Partial connectivity** (high latency): degraded mode indicator, disable non-critical features
3. **Reconnected**: auto-retry pending actions, sync notification, success confirmation
4. **Conflict** (offline edit + server edit): clear merge UI, never silently overwrite

### Retry UX (Zeigarnik + Goal-Gradient)
```
- Show retry attempt count: "Retrying... (attempt 2/3)"
- Exponential backoff indicator: "Next retry in 10s"
- Manual override: "Retry now" button always visible
- Clear failure state: "Failed after 3 attempts — save locally or try later"
- Never loop silently — user must know something is happening
```

### Optimistic Updates (Doherty + Peak-End Rule)
```
- Apply state change instantly in UI (optimistic)
- Queue action for when network available
- On failure: roll back gracefully with clear explanation
- Pattern: Action → Instant feedback → Background confirm → (if fail) Friendly rollback message
```

### Progressive Loading (Chunking + Working Memory)
```
- Load critical content first (above fold)
- Lazy load below-fold content
- Skeleton screens: match actual content shape (not generic spinner)
- Preserve user position on reload (scroll restoration)
```

### Mobile-Specific Fitts's Law Targets

| Context | Minimum size |
|---------|-------------|
| Primary CTA | 48×48dp / 44×44pt |
| Navigation item | 44×44dp |
| Close/Back button | 44×44dp, positioned reachably (bottom sheet) |
| Form input height | 48dp / 44pt |
| Touch target spacing | 8dp minimum between adjacent targets |
| Thumb zone (phone) | Bottom 60% of screen — put primary actions there |

### Offline-First AC Pattern
```
Given the user is offline
When they perform [action]
Then the UI responds within 100ms (local state update)
And shows "Saved offline — will sync when connected"
And the action is queued and retried automatically when connection resumes
And on successful sync, user receives a subtle confirmation toast
```

---

## QUICK REFERENCE — Law to Category

| Category | Laws |
|----------|------|
| **Scope / Prioritization** | Pareto, Occam's Razor, Parkinson's Law, Tesler's |
| **Decision UX** | Hick's, Choice Overload, Cognitive Load |
| **Memory** | Miller's, Working Memory, Chunking, Zeigarnik |
| **Perception (Gestalt)** | Proximity, Common Region, Similarity, Uniform Connectedness, Prägnanz |
| **Interaction** | Fitts's, Doherty Threshold, Flow |
| **Emotional / Narrative** | Peak-End Rule, Aesthetic-Usability Effect, Goal-Gradient, Von Restorff |
| **Mental Models** | Jakob's Law, Mental Model, Paradox of Active User |
| **System Design** | Postel's Law, Tesler's Law |
| **Attention** | Selective Attention, Cognitive Bias |
| **Mobile / Network** | Doherty, Fitts's, Postel's, Zeigarnik, Goal-Gradient |

