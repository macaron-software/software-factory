# UX Laws — Deep Skill
# Source: lawsofux.com (Jon Yablonski) — 30 laws

## WHEN TO ACTIVATE
Designing UI, reviewing mockups, evaluating user flows, creating wireframes,
writing acceptance criteria for user-facing features, or any IHM work.

## CORE PRINCIPLES

### Perception & Gestalt
1. **Aesthetic-Usability Effect** — Beautiful design perceived as more usable.
   Users tolerate minor issues if visually pleasing. Can mask usability problems in testing.
   APPLY: Invest in visual polish. TEST: Usability test with both polished and wireframe versions.

2. **Law of Common Region** — Elements sharing a bounded area are grouped.
   APPLY: Use cards, borders, backgrounds to group related content. CSS: border, background-color, padding.

3. **Law of Proximity** — Near objects perceived as related.
   APPLY: Space related items close (8-16px), separate unrelated (24-48px). Use spacing tokens consistently.

4. **Law of Pragnanz** — People perceive simplest form possible.
   APPLY: Reduce visual complexity. Simple shapes. Clear hierarchy. Avoid decorative noise.

5. **Law of Similarity** — Similar elements perceived as group.
   APPLY: Consistent styling for same-type elements. Color-code categories. Typography consistency.

6. **Law of Uniform Connectedness** — Visually connected = more related.
   APPLY: Use lines, arrows, shared colors to show relationships. Flow diagrams, step indicators.

### Cognition & Memory
7. **Cognitive Load** — Mental resources needed for UI interaction.
   3 types: intrinsic (task complexity), extraneous (bad design), germane (learning).
   APPLY: Minimize extraneous. Progressive disclosure. Reduce decisions per screen.

8. **Cognitive Bias** — Systematic thinking errors affect decisions.
   Key biases: anchoring (first price seen), framing (how options presented), confirmation.
   APPLY: Use defaults wisely. Frame options carefully. Be aware of anchoring in pricing/settings.

9. **Chunking** — Break info into meaningful groups.
   APPLY: Phone numbers (XXX-XXX-XXXX), card numbers (4 groups of 4), form sections, nav groups.
   Rule: Max 5-9 items per chunk (Miller's Law).

10. **Miller's Law** — Working memory holds 7 plus/minus 2 items.
    APPLY: Limit nav items to 5-9. Chunk long lists. Don't force users to remember across screens.

11. **Mental Model** — User's compressed understanding of how system works.
    APPLY: Match user expectations. Use familiar patterns. Consistent behavior across app.
    TEST: "Where would you expect to find X?" questions in user testing.

12. **Working Memory** — Temporary cognitive storage for active tasks.
    APPLY: Show context persistently. Don't make users remember info from previous screens.
    Breadcrumbs, progress indicators, persistent state displays.

### Decision & Interaction
13. **Hick's Law** — Decision time = log2(n+1) choices.
    APPLY: Minimize choices when speed matters. Break complex tasks into steps.
    Highlight recommended. Progressive onboarding. Don't over-simplify to abstraction.
    EXAMPLE: Google homepage (one input), Apple TV remote (minimal buttons), Slack progressive onboarding.

14. **Fitts's Law** — Time to target = f(distance, size).
    APPLY: Touch targets min 44x44px (WCAG 2.5.5). Ample spacing between targets.
    Place frequently-used actions near attention area. Edge/corner targets are fastest (infinite depth).

15. **Choice Overload** — Users overwhelmed by too many options.
    APPLY: Limit to 3-5 options. Use filters for large sets. Default selections. Progressive disclosure.

16. **Selective Attention** — Focus on stimuli related to goals.
    APPLY: Highlight primary CTA. Reduce visual noise. Guide attention with contrast, size, motion.
    Don't rely on users noticing secondary info without explicit visual cues.

### Behavior & Motivation
17. **Flow** — Full immersion with energized focus.
    Requirements: Clear goals, immediate feedback, challenge-skill balance, minimal interruptions.
    APPLY: Reduce friction. Instant feedback on actions. Don't break user concentration with popups.

18. **Goal-Gradient Effect** — Effort increases near goal completion.
    APPLY: Show progress bars. Reward near-completion. Break into milestones.
    Pre-fill progress (start at 20% not 0%).

19. **Paradox of Active User** — Users skip manuals, learn by doing.
    APPLY: Design for exploration. Undo/recover from errors. Contextual help, not manuals.
    Empty states with clear CTAs. Inline tooltips, not docs links.

20. **Zeigarnik Effect** — Incomplete tasks remembered better.
    APPLY: Show incomplete items prominently. Save drafts automatically.
    Gamify completion (streaks, checklists, badges).

21. **Parkinson's Law** — Task inflates to fill time.
    APPLY: Set clear constraints. Time-box. Show urgency cues. Default deadlines.

### Experience & Strategy
22. **Peak-End Rule** — Experience judged by peak + end moments.
    APPLY: End on positive note (success animation, thank you). Fix worst pain points first.
    Celebrate completion. Last impression matters most.

23. **Postel's Law** — Liberal input, conservative output.
    APPLY: Accept varied formats (dates, phone numbers). Auto-format. Forgiving search.
    Validate gracefully, suggest corrections. Output consistently formatted.

24. **Serial Position Effect** — Best remember first and last items.
    APPLY: Key items at start and end of lists/menus. CTA at end. Most important nav items first/last.

25. **Von Restorff Effect** — Different item most remembered.
    APPLY: Make CTAs visually distinct. Highlight key info with contrast.
    Use color, size, shape strategically. Don't make everything "special."

26. **Pareto Principle** — 80% effects from 20% causes.
    APPLY: Focus dev on top-used features. Optimize critical user paths.
    Analytics: identify the 20% of features used 80% of the time.

### System Design
27. **Doherty Threshold** — Productivity soars when response <400ms.
    APPLY: Target <400ms for all interactions. Use skeleton loading for longer.
    Progress indicators for >1s. Optimistic UI updates. Perceived performance matters.

28. **Jakob's Law** — Users prefer familiar patterns.
    APPLY: Don't reinvent standard UI patterns. Follow platform conventions.
    Navigation, forms, modals should work as users expect from other apps.

29. **Tesler's Law** — Irreducible complexity exists.
    APPLY: Don't hide essential complexity behind oversimplified UI.
    Move complexity from user to system. Accept that some tasks are inherently complex.

30. **Occam's Razor** — Simplest solution preferred.
    APPLY: Remove unnecessary elements. Reduce steps. Avoid feature creep.
    Every element should earn its place. If in doubt, leave it out.

## CHECKLIST FOR EVERY IHM
- [ ] Cognitive load: Is this screen overloaded? Can we chunk/progressively disclose?
- [ ] Hick's Law: How many decisions? Can we reduce or recommend?
- [ ] Fitts's Law: Touch targets >= 44px? Frequently-used actions accessible?
- [ ] Doherty: Response < 400ms? Skeleton/spinner for longer?
- [ ] Jakob's Law: Using familiar patterns? Not reinventing standard UI?
- [ ] Peak-End: Positive completion experience? Worst pain points addressed?
- [ ] Postel: Forgiving input? Consistent output?
- [ ] Gestalt: Clear grouping via proximity, similarity, region?
- [ ] Flow: No unnecessary interruptions? Immediate feedback?
- [ ] A11Y: Keyboard navigable? Screen reader compatible? Contrast OK?

## ANTI-PATTERNS
- **Feature soup**: Every feature visible at once (violates Hick's, cognitive load)
- **Mystery meat navigation**: Icons without labels (violates mental model)
- **Modal hell**: Modals spawning modals (violates flow, cognitive load)
- **Infinite scroll without position**: No way to know progress (violates goal-gradient)
- **Destructive actions without confirmation**: No undo (violates paradox of active user)
- **Tiny touch targets**: Below 44px (violates Fitts's Law)
- **Wall of text**: No chunking, no hierarchy (violates Miller's, chunking)
