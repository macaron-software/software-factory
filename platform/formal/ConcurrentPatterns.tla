-------------------------- MODULE ConcurrentPatterns --------------------------
(*
 * Formal model of concurrent execution patterns in the SF platform.
 *
 * Pattern 1 -- Barrier: N workers execute in parallel; an aggregator
 * runs only after ALL workers complete (or fail).
 *
 * Pattern 2 -- Wave: workers are ordered in waves by a dependency DAG.
 * A worker in wave W cannot start until all workers in wave W-1 are done.
 *
 * Invariants:
 *   - Aggregator never runs before all workers complete.
 *   - Wave ordering is respected (acyclic dependency).
 *)
EXTENDS Naturals, FiniteSets

CONSTANTS N,              \* number of workers
          NUM_WAVES        \* number of dependency waves (>= 1)

ASSUME N \in Nat /\ N >= 1
ASSUME NUM_WAVES \in Nat /\ NUM_WAVES >= 1

Workers == 1..N

VARIABLES worker_state,    \* function: worker -> state
          aggregator,      \* aggregator state: "IDLE" | "RUNNING" | "DONE"
          wave_done,       \* set of completed wave numbers
          worker_wave      \* function: worker -> wave assignment (1..NUM_WAVES)

vars == <<worker_state, aggregator, wave_done, worker_wave>>

WorkerStates == {"PENDING", "RUNNING", "COMPLETED", "FAILED"}

-----------------------------------------------------------------------------
(* Assign workers to waves deterministically: worker i -> ((i-1) % NUM_WAVES) + 1 *)
WaveOf(i) == ((i - 1) % NUM_WAVES) + 1

Init ==
    /\ worker_state = [w \in Workers |-> "PENDING"]
    /\ aggregator   = "IDLE"
    /\ wave_done    = {}
    /\ worker_wave  = [w \in Workers |-> WaveOf(w)]

-----------------------------------------------------------------------------
(* A worker can start if its wave's predecessors are all done. *)
WavePredsDone(w) ==
    LET wv == worker_wave[w]
    IN  wv = 1 \/ (wv - 1) \in wave_done

(* Start a worker *)
StartWorker(w) ==
    /\ worker_state[w] = "PENDING"
    /\ WavePredsDone(w)
    /\ worker_state' = [worker_state EXCEPT ![w] = "RUNNING"]
    /\ UNCHANGED <<aggregator, wave_done, worker_wave>>

(* Worker completes successfully *)
CompleteWorker(w) ==
    /\ worker_state[w] = "RUNNING"
    /\ worker_state' = [worker_state EXCEPT ![w] = "COMPLETED"]
    \* Check if this wave is now fully done
    /\ LET wv == worker_wave[w]
           waveWorkers == {x \in Workers : worker_wave[x] = wv}
           othersInWave == waveWorkers \ {w}
           allOthersDone == \A x \in othersInWave :
               worker_state[x] \in {"COMPLETED", "FAILED"}
       IN  IF allOthersDone
           THEN wave_done' = wave_done \union {wv}
           ELSE UNCHANGED wave_done
    /\ UNCHANGED <<aggregator, worker_wave>>

(* Worker fails *)
FailWorker(w) ==
    /\ worker_state[w] = "RUNNING"
    /\ worker_state' = [worker_state EXCEPT ![w] = "FAILED"]
    /\ LET wv == worker_wave[w]
           waveWorkers == {x \in Workers : worker_wave[x] = wv}
           othersInWave == waveWorkers \ {w}
           allOthersDone == \A x \in othersInWave :
               worker_state[x] \in {"COMPLETED", "FAILED"}
       IN  IF allOthersDone
           THEN wave_done' = wave_done \union {wv}
           ELSE UNCHANGED wave_done
    /\ UNCHANGED <<aggregator, worker_wave>>

(* All workers finished (completed or failed) *)
AllWorkersFinished ==
    \A w \in Workers : worker_state[w] \in {"COMPLETED", "FAILED"}

(* Aggregator starts -- only when all workers are done *)
StartAggregator ==
    /\ aggregator = "IDLE"
    /\ AllWorkersFinished
    /\ aggregator' = "RUNNING"
    /\ UNCHANGED <<worker_state, wave_done, worker_wave>>

(* Aggregator completes *)
CompleteAggregator ==
    /\ aggregator = "RUNNING"
    /\ aggregator' = "DONE"
    /\ UNCHANGED <<worker_state, wave_done, worker_wave>>

-----------------------------------------------------------------------------
Next ==
    \/ \E w \in Workers : StartWorker(w)
    \/ \E w \in Workers : CompleteWorker(w)
    \/ \E w \in Workers : FailWorker(w)
    \/ StartAggregator
    \/ CompleteAggregator

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

-----------------------------------------------------------------------------
(* INVARIANTS *)

TypeOK ==
    /\ \A w \in Workers : worker_state[w] \in WorkerStates
    /\ aggregator \in {"IDLE", "RUNNING", "DONE"}

\* The aggregator never runs before all workers are finished.
AggregatorSafety ==
    aggregator \in {"RUNNING", "DONE"} => AllWorkersFinished

\* Wave ordering: no worker in wave W is RUNNING or beyond unless wave W-1
\* is fully done.
WaveOrderRespected ==
    \A w \in Workers :
        worker_state[w] \in {"RUNNING", "COMPLETED", "FAILED"}
        => WavePredsDone(w)

\* Liveness: aggregator eventually completes.
EventuallyAggregated == <>(aggregator = "DONE")

=============================================================================
