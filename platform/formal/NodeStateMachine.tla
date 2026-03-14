--------------------------- MODULE NodeStateMachine ---------------------------
(*
 * Formal model of the SF node execution state machine.
 *
 * States: PENDING, RUNNING, COMPLETED, VETOED, FAILED
 * Transitions are monotonic (no backward moves).
 * An adversarial retry guard allows up to MAX_RETRIES attempts when
 * the quality score is >= RETRY_THRESHOLD.
 *)
EXTENDS Naturals, FiniteSets

CONSTANTS MAX_RETRIES,     \* max retry attempts (default 2)
          RETRY_THRESHOLD  \* score >= this triggers retry (default 7)

VARIABLES state,           \* current node state
          retries,         \* retry counter
          score            \* last observed quality score (0..99)

vars == <<state, retries, score>>

States == {"PENDING", "RUNNING", "COMPLETED", "VETOED", "FAILED"}
TerminalStates == {"COMPLETED", "VETOED", "FAILED"}

-----------------------------------------------------------------------------
(* Initial state *)
Init ==
    /\ state   = "PENDING"
    /\ retries = 0
    /\ score   = 0

-----------------------------------------------------------------------------
(* PENDING -> RUNNING *)
Start ==
    /\ state = "PENDING"
    /\ state' = "RUNNING"
    /\ UNCHANGED <<retries, score>>

(* RUNNING -> COMPLETED  (score <= 6 means pass) *)
Complete ==
    /\ state = "RUNNING"
    /\ \E s \in 0..6 :
        /\ score' = s
        /\ state' = "COMPLETED"
    /\ UNCHANGED retries

(* RUNNING -> VETOED *)
Veto ==
    /\ state = "RUNNING"
    /\ state' = "VETOED"
    /\ UNCHANGED <<retries, score>>

(* RUNNING -> retry path: score >= RETRY_THRESHOLD and retries left *)
RetryReject ==
    /\ state = "RUNNING"
    /\ retries < MAX_RETRIES
    /\ \E s \in RETRY_THRESHOLD..99 :
        /\ score' = s
        \* Stay RUNNING for another attempt; bump retry counter
        /\ state' = "RUNNING"
    /\ retries' = retries + 1

(* RUNNING -> FAILED: retries exhausted or unrecoverable *)
Fail ==
    /\ state = "RUNNING"
    /\ \/ retries >= MAX_RETRIES  \* no more retries
       \/ \E s \in RETRY_THRESHOLD..99 :
            /\ score' = s
            /\ retries >= MAX_RETRIES
    /\ state' = "FAILED"
    /\ UNCHANGED retries

(* Direct fail without retry (e.g., crash) *)
DirectFail ==
    /\ state = "RUNNING"
    /\ state' = "FAILED"
    /\ UNCHANGED <<retries, score>>

-----------------------------------------------------------------------------
Next ==
    \/ Start
    \/ Complete
    \/ Veto
    \/ RetryReject
    \/ Fail
    \/ DirectFail

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

-----------------------------------------------------------------------------
(* INVARIANTS *)

\* A node is in exactly one state (trivially true for a single variable,
\* but documents the contract for multi-node extensions).
TypeOK ==
    /\ state \in States
    /\ retries \in 0..MAX_RETRIES
    /\ score \in 0..99

\* Monotonicity: once terminal, state never changes.
MonotonicTerminal ==
    state \in TerminalStates => state' \in TerminalStates \/ UNCHANGED state

\* Retry count is bounded.
RetryBounded ==
    retries <= MAX_RETRIES

\* Liveness: every node eventually reaches a terminal state.
EventuallyTerminal == <>(state \in TerminalStates)

=============================================================================
