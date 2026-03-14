--------------------------- MODULE AdversarialGuard ---------------------------
(*
 * Formal model of the adversarial guard retry mechanism.
 *
 * The guard evaluates agent output with a quality score and decides:
 *   PASS  -- score <= 6 (with warning if score > 3)
 *   REJECT -> retry with feedback (score 7..99, retries remaining)
 *   FAILED -- retries exhausted or empty output unrecoverable
 *
 * Critical flags (HALLUCINATION, STACK_MISMATCH) force retry even at
 * low scores.
 *
 * Invariants:
 *   - Every output eventually reaches PASSED or FAILED (no limbo).
 *   - Retry count is bounded by MAX_RETRIES.
 *)
EXTENDS Naturals

CONSTANTS MAX_RETRIES        \* configurable retry limit (default 2)

VARIABLES guard_state,       \* "EVALUATING" | "PASSED" | "FAILED"
          retries,           \* current retry count
          score,             \* last quality score 0..99
          is_empty,          \* TRUE if output was empty (MiniMax quirk)
          has_critical_flag, \* TRUE if HALLUCINATION or STACK_MISMATCH
          nudged             \* TRUE if empty-output nudge was already sent

vars == <<guard_state, retries, score, is_empty, has_critical_flag, nudged>>

TerminalStates == {"PASSED", "FAILED"}

-----------------------------------------------------------------------------
Init ==
    /\ guard_state       = "EVALUATING"
    /\ retries           = 0
    /\ score             = 0
    /\ is_empty          = FALSE
    /\ has_critical_flag = FALSE
    /\ nudged            = FALSE

-----------------------------------------------------------------------------
(* Receive agent output and assign a score.
   Non-deterministically models adversarial conditions. *)
Evaluate ==
    /\ guard_state = "EVALUATING"
    /\ \E s \in 0..99, empty \in BOOLEAN, crit \in BOOLEAN :
        /\ score'             = s
        /\ is_empty'          = empty
        /\ has_critical_flag' = crit
        /\ UNCHANGED <<guard_state, retries, nudged>>

(* PASS path: score <= 6 and no critical flags and not empty *)
Pass ==
    /\ guard_state = "EVALUATING"
    /\ score <= 6
    /\ ~has_critical_flag
    /\ ~is_empty
    /\ guard_state' = "PASSED"
    /\ UNCHANGED <<retries, score, is_empty, has_critical_flag, nudged>>

(* REJECT path: score >= 7 and retries remaining *)
RejectRetry ==
    /\ guard_state = "EVALUATING"
    /\ score >= 7
    /\ retries < MAX_RETRIES
    /\ retries' = retries + 1
    \* Stay EVALUATING for next attempt; score/flags reset on re-evaluation
    /\ UNCHANGED <<guard_state, score, is_empty, has_critical_flag, nudged>>

(* Critical flag forces retry regardless of score *)
CriticalRetry ==
    /\ guard_state = "EVALUATING"
    /\ has_critical_flag
    /\ ~is_empty
    /\ retries < MAX_RETRIES
    /\ retries' = retries + 1
    /\ has_critical_flag' = FALSE  \* flag consumed
    /\ UNCHANGED <<guard_state, score, is_empty, nudged>>

(* Empty output: nudge once *)
NudgeEmpty ==
    /\ guard_state = "EVALUATING"
    /\ is_empty
    /\ ~nudged
    /\ nudged'   = TRUE
    /\ is_empty' = FALSE  \* agent will re-produce output
    /\ UNCHANGED <<guard_state, retries, score, has_critical_flag>>

(* Empty output after nudge: FAILED *)
EmptyAfterNudge ==
    /\ guard_state = "EVALUATING"
    /\ is_empty
    /\ nudged
    /\ guard_state' = "FAILED"
    /\ UNCHANGED <<retries, score, is_empty, has_critical_flag, nudged>>

(* Retries exhausted with high score: FAILED *)
RetriesExhausted ==
    /\ guard_state = "EVALUATING"
    /\ score >= 7
    /\ retries >= MAX_RETRIES
    /\ guard_state' = "FAILED"
    /\ UNCHANGED <<retries, score, is_empty, has_critical_flag, nudged>>

(* Critical flag but no retries left: FAILED *)
CriticalNoRetries ==
    /\ guard_state = "EVALUATING"
    /\ has_critical_flag
    /\ retries >= MAX_RETRIES
    /\ guard_state' = "FAILED"
    /\ UNCHANGED <<retries, score, is_empty, has_critical_flag, nudged>>

-----------------------------------------------------------------------------
Next ==
    \/ Evaluate
    \/ Pass
    \/ RejectRetry
    \/ CriticalRetry
    \/ NudgeEmpty
    \/ EmptyAfterNudge
    \/ RetriesExhausted
    \/ CriticalNoRetries

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

-----------------------------------------------------------------------------
(* INVARIANTS *)

TypeOK ==
    /\ guard_state       \in {"EVALUATING", "PASSED", "FAILED"}
    /\ retries           \in 0..MAX_RETRIES
    /\ score             \in 0..99
    /\ is_empty          \in BOOLEAN
    /\ has_critical_flag \in BOOLEAN
    /\ nudged            \in BOOLEAN

\* Retry count is bounded.
RetryBounded ==
    retries <= MAX_RETRIES

\* No limbo: once evaluation is finished, state is PASSED or FAILED.
NoLimbo ==
    guard_state \in {"EVALUATING"} \union TerminalStates

\* Liveness: every evaluation eventually reaches a terminal state.
EventuallyResolved == <>(guard_state \in TerminalStates)

=============================================================================
