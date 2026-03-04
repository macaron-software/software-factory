"""
Laws of UX Scraper / LRM Provider
===================================
Populates data/ux_laws.db with the 30 Laws of UX from https://lawsofux.com

SOURCE: Jon Yablonski — https://lawsofux.com (MIT)
WHY: Evidence-based cognitive laws injected into agent context for:
  - US writing: AC templates with measurable cognitive constraints
  - UX audit: 30-law checklist replacing opinion-based review
  - Design critique: law-referenced violation explanations

Usage:
    python -m mcp_lrm.ux_laws_scraper          # populate DB
    python -m mcp_lrm.ux_laws_scraper --stats  # show DB stats
    python -m mcp_lrm.ux_laws_scraper --update # alias for populate

LRM tools:
    lrm_ux_laws_list(category?)
    lrm_ux_laws_get(law_id)
    lrm_ux_laws_for_context(context_type)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ux_laws.db"

# ---------------------------------------------------------------------------
# Static law data
# ---------------------------------------------------------------------------

LAWS: list[dict] = [
    {
        "id": "aesthetic-usability-effect",
        "name": "Aesthetic-Usability Effect",
        "category": "emotional",
        "summary": "Users often perceive aesthetically pleasing design as design that's more usable.",
        "apply_when": "When visual polish may affect perceived credibility or trust.",
        "ac_pattern": "GIVEN a visually polished UI WHEN the user first encounters it THEN they report higher usability confidence.",
        "rule": "DO invest in visual quality; aesthetic defects lower perceived usability even if function is intact.",
        "violation_example": "Functional form with inconsistent spacing and mismatched colours dismissed as 'broken' by users.",
        "url": "https://lawsofux.com/aesthetic-usability-effect/",
    },
    {
        "id": "choice-overload",
        "name": "Choice Overload",
        "category": "decision",
        "summary": "The tendency for people to get overwhelmed when presented with a large number of options.",
        "apply_when": "When designing selection screens, menus, or any multi-option UI.",
        "ac_pattern": "GIVEN more than 7 options WHEN presented without grouping THEN user abandonment rate increases.",
        "rule": "DO reduce or group options; use progressive disclosure to expose advanced choices.",
        "violation_example": "Onboarding screen with 20 uncategorised plan tiers causing decision paralysis.",
        "url": "https://lawsofux.com/choice-overload/",
    },
    {
        "id": "chunking",
        "name": "Chunking",
        "category": "memory",
        "summary": "Individual pieces of an information set are broken down and grouped together in a meaningful whole.",
        "apply_when": "When presenting complex data, forms, or long text.",
        "ac_pattern": "GIVEN a long form WHEN fields are grouped into labelled sections THEN completion rate improves.",
        "rule": "DO group related information into chunks of 3–5 items with clear visual boundaries.",
        "violation_example": "Single-page checkout with 18 ungrouped fields in one column.",
        "url": "https://lawsofux.com/chunking/",
    },
    {
        "id": "cognitive-bias",
        "name": "Cognitive Bias",
        "category": "strategy",
        "summary": "A systematic error of thinking that influences our perception and decision-making ability.",
        "apply_when": "When designing persuasive flows, defaults, or comparative displays.",
        "ac_pattern": None,
        "rule": "DO audit UI defaults and framing for unintended bias that skews user decisions.",
        "violation_example": "Pre-selected 'annual plan' default exploiting status quo bias without transparent disclosure.",
        "url": "https://lawsofux.com/cognitive-bias/",
    },
    {
        "id": "cognitive-load",
        "name": "Cognitive Load",
        "category": "decision",
        "summary": "The amount of mental resources needed to understand and interact with an interface.",
        "apply_when": "Any screen design — always relevant; especially for complex tasks.",
        "ac_pattern": "GIVEN a task flow WHEN extraneous elements are removed THEN time-on-task decreases by ≥10%.",
        "rule": "DO eliminate unnecessary elements; every added element competes for limited mental bandwidth.",
        "violation_example": "Dashboard with 12 simultaneous data visualisations, each requiring independent interpretation.",
        "url": "https://lawsofux.com/cognitive-load/",
    },
    {
        "id": "doherty-threshold",
        "name": "Doherty Threshold",
        "category": "time",
        "summary": "Productivity soars when a computer and its users interact at a pace (<400ms) that ensures that neither has to wait on the other.",
        "apply_when": "When specifying response-time SLAs for interactive features.",
        "ac_pattern": "GIVEN a user action WHEN the system responds in <400ms THEN the user remains in flow state.",
        "rule": "DO ensure all interactive feedback (loading states, transitions) completes within 400ms.",
        "violation_example": "Search results taking 1.2s with no skeleton screen, breaking user's cognitive flow.",
        "url": "https://lawsofux.com/doherty-threshold/",
    },
    {
        "id": "fittss-law",
        "name": "Fitts's Law",
        "category": "time",
        "summary": "The time to acquire a target is a function of the distance to and size of the target.",
        "apply_when": "When sizing and placing interactive controls (buttons, links, touch targets).",
        "ac_pattern": "GIVEN a primary CTA WHEN it is ≥44×44px and within thumb reach THEN tap accuracy exceeds 95%.",
        "rule": "DO make touch targets ≥44×44px and position frequent actions close to the user's natural hand position.",
        "violation_example": "16px-high text link as the sole destructive action confirmation on mobile.",
        "url": "https://lawsofux.com/fittss-law/",
    },
    {
        "id": "flow",
        "name": "Flow",
        "category": "emotional",
        "summary": "The mental state of being fully immersed in energized focus and enjoyment in an activity.",
        "apply_when": "When designing task sequences that should feel effortless (onboarding, core journeys).",
        "ac_pattern": None,
        "rule": "DO balance challenge and skill; remove interruptions and unnecessary confirmations from core flows.",
        "violation_example": "Mid-task modal ads breaking user concentration during a multi-step checkout.",
        "url": "https://lawsofux.com/flow/",
    },
    {
        "id": "goal-gradient-effect",
        "name": "Goal-Gradient Effect",
        "category": "emotional",
        "summary": "The tendency to approach a goal increases with proximity to the goal.",
        "apply_when": "When designing progress indicators, onboarding steps, or gamification.",
        "ac_pattern": "GIVEN a multi-step flow WHEN a progress bar shows ≥1 completed step THEN task completion rate increases.",
        "rule": "DO show progress clearly and give users an early win to trigger the acceleration effect.",
        "violation_example": "Onboarding with no progress indicator, making users feel stuck at the start.",
        "url": "https://lawsofux.com/goal-gradient-effect/",
    },
    {
        "id": "hicks-law",
        "name": "Hick's Law",
        "category": "decision",
        "summary": "The time it takes to make a decision increases with the number and complexity of choices.",
        "apply_when": "When designing navigation menus, CTAs, or any decision point.",
        "ac_pattern": "GIVEN a primary navigation WHEN items exceed 7 THEN decision time exceeds acceptable threshold.",
        "rule": "DO limit choices at each decision point to ≤7 items; use progressive disclosure for the rest.",
        "violation_example": "Top navigation with 14 top-level items causing analysis paralysis on first visit.",
        "url": "https://lawsofux.com/hicks-law/",
    },
    {
        "id": "jakobs-law",
        "name": "Jakob's Law",
        "category": "strategy",
        "summary": "Users spend most of their time on other sites and prefer your site to work the same way.",
        "apply_when": "When making layout or interaction pattern decisions that deviate from conventions.",
        "ac_pattern": None,
        "rule": "DO follow established conventions (logo top-left, nav top/left, search top-right) before innovating.",
        "violation_example": "Hamburger menu on desktop hiding primary navigation that users expect to be always visible.",
        "url": "https://lawsofux.com/jakobs-law/",
    },
    {
        "id": "law-of-common-region",
        "name": "Law of Common Region",
        "category": "perception",
        "summary": "Elements tend to be perceived into groups if they are sharing an area with a clearly defined boundary.",
        "apply_when": "When grouping related UI elements visually.",
        "ac_pattern": None,
        "rule": "DO use cards, panels, or borders to visually group related elements into a common region.",
        "violation_example": "Settings form where unrelated controls share a single borderless column, causing grouping confusion.",
        "url": "https://lawsofux.com/law-of-common-region/",
    },
    {
        "id": "law-of-proximity",
        "name": "Law of Proximity",
        "category": "perception",
        "summary": "Objects that are near, or proximate to each other, tend to be grouped together.",
        "apply_when": "When laying out labels, inputs, actions, or any related elements.",
        "ac_pattern": None,
        "rule": "DO place labels closer to their inputs than to adjacent inputs; group related actions spatially.",
        "violation_example": "Form labels equidistant between two input fields, causing users to misattribute labels.",
        "url": "https://lawsofux.com/law-of-proximity/",
    },
    {
        "id": "law-of-pragnanz",
        "name": "Law of Prägnanz",
        "category": "perception",
        "summary": "People will perceive and interpret ambiguous or complex images as the simplest form possible.",
        "apply_when": "When designing icons, illustrations, or data visualisations.",
        "ac_pattern": None,
        "rule": "DO simplify visual representations to their clearest, most recognisable form.",
        "violation_example": "Icon combining five distinct shapes to represent 'settings', interpreted inconsistently by users.",
        "url": "https://lawsofux.com/law-of-pragnanz/",
    },
    {
        "id": "law-of-similarity",
        "name": "Law of Similarity",
        "category": "perception",
        "summary": "The human eye tends to perceive similar elements as a complete picture, shape, or group.",
        "apply_when": "When designing component systems where visual similarity should signal functional similarity.",
        "ac_pattern": None,
        "rule": "DO make interactive elements share a consistent visual style; differentiate non-interactive elements.",
        "violation_example": "Decorative cards styled identically to clickable cards, causing false affordance.",
        "url": "https://lawsofux.com/law-of-similarity/",
    },
    {
        "id": "law-of-uniform-connectedness",
        "name": "Law of Uniform Connectedness",
        "category": "perception",
        "summary": "Elements that are visually connected are perceived as more related than elements with no connection.",
        "apply_when": "When showing relationships between data points or UI elements.",
        "ac_pattern": None,
        "rule": "DO use lines, arrows, or shared colour to explicitly connect related elements.",
        "violation_example": "Flowchart nodes with no connecting lines, forcing users to infer relationships from position alone.",
        "url": "https://lawsofux.com/law-of-uniform-connectedness/",
    },
    {
        "id": "mental-model",
        "name": "Mental Model",
        "category": "strategy",
        "summary": "A compressed model based on what we think we know about a system and how it works.",
        "apply_when": "When introducing new workflows or departing from familiar patterns.",
        "ac_pattern": None,
        "rule": "DO align UI metaphors with the user's existing mental model; explain deviations explicitly.",
        "violation_example": "'Archive' function that permanently deletes content, violating the 'archive = safe storage' mental model.",
        "url": "https://lawsofux.com/mental-model/",
    },
    {
        "id": "millers-law",
        "name": "Miller's Law",
        "category": "memory",
        "summary": "The average person can only keep 7 (plus or minus 2) items in their working memory.",
        "apply_when": "When displaying lists, navigation items, or any set of options.",
        "ac_pattern": "GIVEN a list of items WHEN count exceeds 9 THEN group or paginate to stay within 7±2.",
        "rule": "DO limit any flat list to ≤9 items; group or paginate beyond that.",
        "violation_example": "Dropdown with 25 ungrouped country codes expecting users to scan and remember position.",
        "url": "https://lawsofux.com/millers-law/",
    },
    {
        "id": "occams-razor",
        "name": "Occam's Razor",
        "category": "strategy",
        "summary": "Among competing hypotheses that predict equally well, the one with the fewest assumptions should be selected.",
        "apply_when": "When evaluating competing design solutions or feature complexity.",
        "ac_pattern": None,
        "rule": "DO choose the simpler solution; remove features that don't directly serve a validated user need.",
        "violation_example": "Multi-step wizard added to a task completable in a single form, justified by 'future flexibility'.",
        "url": "https://lawsofux.com/occams-razor/",
    },
    {
        "id": "paradox-of-the-active-user",
        "name": "Paradox of the Active User",
        "category": "strategy",
        "summary": "Users never read manuals but start using the software immediately.",
        "apply_when": "When designing onboarding or help systems.",
        "ac_pattern": None,
        "rule": "DO make the UI self-explanatory; inline guidance beats external documentation.",
        "violation_example": "Tooltip saying 'See help docs for setup instructions' on a required configuration step.",
        "url": "https://lawsofux.com/paradox-of-the-active-user/",
    },
    {
        "id": "pareto-principle",
        "name": "Pareto Principle",
        "category": "strategy",
        "summary": "For many events, roughly 80% of the effects come from 20% of the causes.",
        "apply_when": "When prioritising features, bug fixes, or UX improvements.",
        "ac_pattern": None,
        "rule": "DO identify the 20% of features/flows driving 80% of user value and optimise those first.",
        "violation_example": "Sprint focused on edge-case power-user features while core onboarding flow has 40% drop-off.",
        "url": "https://lawsofux.com/pareto-principle/",
    },
    {
        "id": "parkinsons-law",
        "name": "Parkinson's Law",
        "category": "strategy",
        "summary": "Any task will inflate until all of the available time is spent.",
        "apply_when": "When setting deadlines or scoping time-boxed user tasks.",
        "ac_pattern": None,
        "rule": "DO set explicit time constraints for tasks; impose session limits to encourage focus.",
        "violation_example": "Unlimited form input fields with no save/submit prompt, leading users to over-detail responses.",
        "url": "https://lawsofux.com/parkinsons-law/",
    },
    {
        "id": "peak-end-rule",
        "name": "Peak-End Rule",
        "category": "emotional",
        "summary": "People judge an experience largely based on how they felt at its peak and at its end.",
        "apply_when": "When designing end states (success screens, error recovery) and peak moments.",
        "ac_pattern": "GIVEN a completed flow WHEN a celebratory success state is shown THEN NPS improves.",
        "rule": "DO design memorable peak moments and positive end states; negative endings disproportionately damage recall.",
        "violation_example": "Checkout success page showing only a plain 'Order placed' text with no confirmation delight.",
        "url": "https://lawsofux.com/peak-end-rule/",
    },
    {
        "id": "postels-law",
        "name": "Postel's Law",
        "category": "strategy",
        "summary": "Be liberal in what you accept, and conservative in what you send.",
        "apply_when": "When designing form validation and data input handling.",
        "ac_pattern": None,
        "rule": "DO accept varied input formats (e.g. phone numbers with/without spaces); output in a single canonical format.",
        "violation_example": "Phone field rejecting '+1 (555) 000-0000' and only accepting '15550000000', with no format hint.",
        "url": "https://lawsofux.com/postels-law/",
    },
    {
        "id": "selective-attention",
        "name": "Selective Attention",
        "category": "memory",
        "summary": "The process of focusing attention only to a subset of stimuli in an environment.",
        "apply_when": "When designing pages with multiple competing elements.",
        "ac_pattern": None,
        "rule": "DO establish a clear visual hierarchy so users' selective attention is guided to the most important element first.",
        "violation_example": "Landing page with six equally-sized CTAs, causing users to miss the primary conversion action.",
        "url": "https://lawsofux.com/selective-attention/",
    },
    {
        "id": "serial-position-effect",
        "name": "Serial Position Effect",
        "category": "memory",
        "summary": "Users have a propensity to best remember the first and last items in a series.",
        "apply_when": "When ordering navigation items, lists, or sequences of steps.",
        "ac_pattern": None,
        "rule": "DO place the most important actions at the beginning or end of lists/menus; avoid burying key items in the middle.",
        "violation_example": "Primary 'Upgrade' CTA placed 5th of 7 in a navigation bar, consistently overlooked in user tests.",
        "url": "https://lawsofux.com/serial-position-effect/",
    },
    {
        "id": "teslers-law",
        "name": "Tesler's Law",
        "category": "strategy",
        "summary": "For any system there is a certain amount of complexity which cannot be reduced.",
        "apply_when": "When simplifying flows — to avoid shifting complexity onto users.",
        "ac_pattern": None,
        "rule": "DO absorb irreducible complexity in the system, not in the UI; hide it from users where possible.",
        "violation_example": "Requiring users to manually enter ISO currency codes instead of providing a searchable dropdown.",
        "url": "https://lawsofux.com/teslers-law/",
    },
    {
        "id": "von-restorff-effect",
        "name": "Von Restorff Effect",
        "category": "emotional",
        "summary": "When multiple similar objects are present, the one that differs from the rest is most likely to be remembered.",
        "apply_when": "When highlighting a recommended plan, priority action, or key data point.",
        "ac_pattern": "GIVEN a pricing table WHEN one plan is visually differentiated THEN it receives 2× more selections.",
        "rule": "DO visually differentiate the most important element from its peers; use it sparingly to preserve effect.",
        "violation_example": "Three pricing tiers with identical styling — recommended tier goes unnoticed.",
        "url": "https://lawsofux.com/von-restorff-effect/",
    },
    {
        "id": "working-memory",
        "name": "Working Memory",
        "category": "memory",
        "summary": "A cognitive system that temporarily holds and manipulates information needed to complete tasks.",
        "apply_when": "When designing multi-step flows that require users to retain information across steps.",
        "ac_pattern": None,
        "rule": "DO surface relevant context at each step so users don't need to remember information from previous screens.",
        "violation_example": "Checkout step 3 requiring the user to re-enter their email from step 1 due to no session persistence.",
        "url": "https://lawsofux.com/working-memory/",
    },
    {
        "id": "zeigarnik-effect",
        "name": "Zeigarnik Effect",
        "category": "memory",
        "summary": "People remember uncompleted or interrupted tasks better than completed tasks.",
        "apply_when": "When designing progress saving, notifications, or re-engagement nudges.",
        "ac_pattern": "GIVEN an incomplete profile WHEN the user returns THEN a completion nudge drives ≥15% resumption.",
        "rule": "DO surface incomplete tasks as nudges; use progress indicators to leverage natural tension toward completion.",
        "violation_example": "App that silently saves draft without showing any 'resume' prompt on next login.",
        "url": "https://lawsofux.com/zeigarnik-effect/",
    },
]

# Mapping for context-based queries
_CONTEXT_LAW_IDS: dict[str, list[str]] = {
    "us_writing": [
        "hicks-law",
        "millers-law",
        "cognitive-load",
        "doherty-threshold",
        "goal-gradient-effect",
        "peak-end-rule",
        "pareto-principle",
        "teslers-law",
        "occams-razor",
        "parkinsons-law",
        "zeigarnik-effect",
    ],
    "ux_audit": [law["id"] for law in LAWS],  # all 30
    "design_critique": [
        "aesthetic-usability-effect",
        "von-restorff-effect",
        "jakobs-law",
        "law-of-proximity",
        "law-of-common-region",
        "law-of-similarity",
        "fittss-law",
        "serial-position-effect",
        "cognitive-load",
        "millers-law",
    ],
    "prioritization": [
        "pareto-principle",
        "teslers-law",
        "occams-razor",
        "parkinsons-law",
        "cognitive-load",
    ],
}

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _ensure_data_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def _get_db():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS laws (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            category          TEXT NOT NULL,
            summary           TEXT NOT NULL,
            apply_when        TEXT NOT NULL,
            ac_pattern        TEXT,
            rule              TEXT,
            violation_example TEXT,
            url               TEXT
        )
    """)


# ---------------------------------------------------------------------------
# Populate
# ---------------------------------------------------------------------------


def populate(verbose: bool = True) -> None:
    """Insert or replace all 30 laws into the DB."""
    with _get_db() as conn:
        _ensure_schema(conn)
        for law in LAWS:
            conn.execute(
                """
                INSERT OR REPLACE INTO laws
                    (id, name, category, summary, apply_when, ac_pattern,
                     rule, violation_example, url)
                VALUES
                    (:id, :name, :category, :summary, :apply_when, :ac_pattern,
                     :rule, :violation_example, :url)
                """,
                law,
            )
            if verbose:
                print(f"  ✓ {law['name']}")
    if verbose:
        print(f"\nDB: {DB_PATH}")


def print_stats() -> None:
    with _get_db() as conn:
        _ensure_schema(conn)
        total = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
        categories = conn.execute(
            "SELECT category, COUNT(*) AS n FROM laws GROUP BY category ORDER BY category"
        ).fetchall()
    print(f"Total laws: {total}")
    for row in categories:
        print(f"  {row['category']}: {row['n']}")


# ---------------------------------------------------------------------------
# LRM tool functions
# ---------------------------------------------------------------------------


def lrm_ux_laws_list(category: str = None) -> str:
    """List all laws, optionally filtered by category.

    categories: decision, memory, perception, time, strategy, emotional
    Returns JSON list of {id, name, category, summary}.
    """
    with _get_db() as conn:
        _ensure_schema(conn)
        if category:
            rows = conn.execute(
                "SELECT id, name, category, summary FROM laws WHERE category = ? ORDER BY name",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, category, summary FROM laws ORDER BY category, name"
            ).fetchall()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False)


def lrm_ux_laws_get(law_id: str) -> str:
    """Get full details of a specific law by id (e.g. 'hicks-law').

    Returns full row as JSON, or {"error": "..."} if not found.
    """
    with _get_db() as conn:
        _ensure_schema(conn)
        row = conn.execute("SELECT * FROM laws WHERE id = ?", (law_id,)).fetchone()
    if row is None:
        return json.dumps({"error": f"Law '{law_id}' not found"})
    return json.dumps(dict(row), ensure_ascii=False)


def lrm_ux_laws_for_context(context_type: str) -> str:
    """Get laws most relevant for a given context.

    context_type: 'us_writing' | 'ux_audit' | 'design_critique' | 'prioritization'
    Returns JSON list of full law rows grouped by category (ux_audit) or
    ordered by relevance list (other contexts).
    """
    if context_type not in _CONTEXT_LAW_IDS:
        return json.dumps(
            {
                "error": f"Unknown context_type '{context_type}'",
                "valid": list(_CONTEXT_LAW_IDS.keys()),
            }
        )

    ids = _CONTEXT_LAW_IDS[context_type]

    with _get_db() as conn:
        _ensure_schema(conn)
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM laws WHERE id IN ({placeholders})", ids
        ).fetchall()

    rows_by_id = {r["id"]: dict(r) for r in rows}

    if context_type == "ux_audit":
        # Group by category for audit use
        grouped: dict[str, list] = {}
        for law_id in ids:
            if law_id in rows_by_id:
                cat = rows_by_id[law_id]["category"]
                grouped.setdefault(cat, []).append(rows_by_id[law_id])
        return json.dumps(grouped, ensure_ascii=False)

    # Preserve relevance order
    ordered = [rows_by_id[i] for i in ids if i in rows_by_id]
    return json.dumps(ordered, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Laws of UX — populate/query the ux_laws.db SQLite database"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print count of laws in DB and exit",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Populate/update the DB with all 30 laws (default action)",
    )
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        print(f"Populating {DB_PATH} with {len(LAWS)} laws …")
        populate(verbose=True)
        print(f"\nDone. {len(LAWS)} laws written.")
