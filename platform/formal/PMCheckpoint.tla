----------------------------- MODULE PMCheckpoint -----------------------------
(*
 * Formal model of the PM v2 decision loop.
 *
 * The PM agent iterates over a phase queue, making decisions:
 *   next  - advance to next phase
 *   loop  - repeat current phase
 *   skip  - skip current phase
 *   done  - finish workflow (requires all gates passed)
 *   phase - inject a dynamic phase and reset loop tracker
 *
 * Safety: total decisions bounded, consecutive loops bounded,
 *         phase_queue monotonically consumed (no infinite insertion).
 * Liveness: workflow always terminates.
 *)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS MAX_DECISIONS,       \* hard cap on total decisions (default 20)
          MAX_CONSECUTIVE,     \* max consecutive loops of same phase (default 2)
          NUM_PHASES           \* initial number of phases in queue

VARIABLES phase_idx,           \* current index into phase queue (1-based)
          phase_len,           \* current length of phase queue
          decisions,           \* total decision counter
          consec_loops,        \* consecutive loop count for current phase
          gates_passed,        \* set of phase indices whose gate is passed
          done,                \* workflow finished flag
          dynamic_added        \* count of dynamically added phases

vars == <<phase_idx, phase_len, decisions, consec_loops,
          gates_passed, done, dynamic_added>>

-----------------------------------------------------------------------------
Init ==
    /\ phase_idx     = 1
    /\ phase_len     = NUM_PHASES
    /\ decisions     = 0
    /\ consec_loops  = 0
    /\ gates_passed  = {}
    /\ done          = FALSE
    /\ dynamic_added = 0

-----------------------------------------------------------------------------
(* Helper: can we still make decisions? *)
CanDecide == decisions < MAX_DECISIONS /\ ~done

(* Decision: next -- advance to the following phase *)
DecideNext ==
    /\ CanDecide
    /\ phase_idx <= phase_len
    /\ gates_passed' = gates_passed \union {phase_idx}
    /\ phase_idx'    = phase_idx + 1
    /\ consec_loops' = 0
    /\ decisions'    = decisions + 1
    /\ UNCHANGED <<phase_len, done, dynamic_added>>

(* Decision: loop -- repeat the current phase *)
DecideLoop ==
    /\ CanDecide
    /\ phase_idx <= phase_len
    /\ consec_loops < MAX_CONSECUTIVE
    /\ consec_loops' = consec_loops + 1
    /\ decisions'    = decisions + 1
    /\ UNCHANGED <<phase_idx, phase_len, gates_passed, done, dynamic_added>>

(* Decision: skip -- skip the current phase without passing its gate *)
DecideSkip ==
    /\ CanDecide
    /\ phase_idx <= phase_len
    /\ phase_idx'    = phase_idx + 1
    /\ consec_loops' = 0
    /\ decisions'    = decisions + 1
    /\ UNCHANGED <<phase_len, gates_passed, done, dynamic_added>>

(* Decision: phase -- create a dynamic phase, insert after current *)
DecidePhase ==
    /\ CanDecide
    /\ phase_idx <= phase_len
    /\ dynamic_added < NUM_PHASES  \* bound dynamic insertions
    /\ phase_len'     = phase_len + 1
    /\ dynamic_added' = dynamic_added + 1
    /\ consec_loops'  = 0
    /\ decisions'     = decisions + 1
    \* Current phase gate is passed; new phase inserted at phase_idx + 1
    /\ gates_passed'  = gates_passed \union {phase_idx}
    /\ phase_idx'     = phase_idx + 1
    /\ UNCHANGED done

(* Decision: done -- finish workflow (only if all phases consumed) *)
DecideDone ==
    /\ CanDecide
    /\ phase_idx > phase_len
    /\ done'      = TRUE
    /\ decisions' = decisions + 1
    /\ UNCHANGED <<phase_idx, phase_len, consec_loops, gates_passed, dynamic_added>>

(* Forced advance: if consecutive loops exhausted, auto-advance *)
ForcedAdvance ==
    /\ CanDecide
    /\ phase_idx <= phase_len
    /\ consec_loops >= MAX_CONSECUTIVE
    /\ phase_idx'    = phase_idx + 1
    /\ consec_loops' = 0
    /\ decisions'    = decisions + 1
    /\ gates_passed' = gates_passed \union {phase_idx}
    /\ UNCHANGED <<phase_len, done, dynamic_added>>

(* Timeout: decision budget exhausted, force done *)
BudgetExhausted ==
    /\ decisions >= MAX_DECISIONS
    /\ ~done
    /\ done' = TRUE
    /\ UNCHANGED <<phase_idx, phase_len, decisions, consec_loops,
                   gates_passed, dynamic_added>>

-----------------------------------------------------------------------------
Next ==
    \/ DecideNext
    \/ DecideLoop
    \/ DecideSkip
    \/ DecidePhase
    \/ DecideDone
    \/ ForcedAdvance
    \/ BudgetExhausted

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

-----------------------------------------------------------------------------
(* INVARIANTS *)

TypeOK ==
    /\ phase_idx    \in 1..(phase_len + 1)
    /\ phase_len    \in NUM_PHASES..(NUM_PHASES + NUM_PHASES)
    /\ decisions    \in 0..MAX_DECISIONS
    /\ consec_loops \in 0..MAX_CONSECUTIVE
    /\ done         \in BOOLEAN

\* Decision count never exceeds budget.
DecisionBounded ==
    decisions <= MAX_DECISIONS

\* Consecutive loops per phase are bounded.
LoopBounded ==
    consec_loops <= MAX_CONSECUTIVE

\* Dynamic insertions are bounded (no infinite queue growth).
PhaseQueueBounded ==
    dynamic_added <= NUM_PHASES

\* Liveness: workflow eventually terminates.
EventuallyDone == <>(done = TRUE)

=============================================================================
