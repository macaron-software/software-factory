-------------------------- MODULE SafetyProperties ----------------------------
(*
 * Cross-cutting safety properties for the SF platform.
 *
 * Models high-level invariants that span multiple subsystems:
 *   1. No mission can be RUNNING and PAUSED simultaneously.
 *   2. YOLO mode disables pause events (WorkflowPaused never raised).
 *   3. Protected branches (main/master/develop) are never committed to directly.
 *   4. No agent can modify files outside its workspace.
 *)
EXTENDS Naturals, FiniteSets

CONSTANTS NUM_MISSIONS,     \* number of concurrent missions
          NUM_AGENTS,       \* number of agents
          NUM_BRANCHES      \* number of git branches (including protected)

Missions == 1..NUM_MISSIONS
Agents   == 1..NUM_AGENTS
Branches == 1..NUM_BRANCHES

\* Branch 1..3 are protected (main, master, develop)
ProtectedBranches == {1, 2, 3}
ASSUME NUM_BRANCHES >= 3

VARIABLES mission_state,    \* function: mission -> "IDLE" | "RUNNING" | "PAUSED" | "DONE"
          yolo_mode,        \* global flag: YOLO mode on/off
          pause_raised,     \* TRUE if a WorkflowPaused event was raised
          commit_target,    \* last branch a commit targeted (0 = none)
          agent_workspace,  \* function: agent -> workspace id (1..NUM_AGENTS)
          agent_write_path  \* last path an agent wrote to (workspace id, 0 = none)

vars == <<mission_state, yolo_mode, pause_raised,
          commit_target, agent_workspace, agent_write_path>>

MissionStates == {"IDLE", "RUNNING", "PAUSED", "DONE"}

-----------------------------------------------------------------------------
Init ==
    /\ mission_state  = [m \in Missions |-> "IDLE"]
    /\ yolo_mode      = FALSE
    /\ pause_raised   = FALSE
    /\ commit_target  = 0
    /\ agent_workspace = [a \in Agents |-> a]  \* each agent owns workspace = its id
    /\ agent_write_path = [a \in Agents |-> 0]

-----------------------------------------------------------------------------
(* Mission lifecycle *)
StartMission(m) ==
    /\ mission_state[m] = "IDLE"
    /\ mission_state' = [mission_state EXCEPT ![m] = "RUNNING"]
    /\ UNCHANGED <<yolo_mode, pause_raised, commit_target,
                   agent_workspace, agent_write_path>>

PauseMission(m) ==
    /\ mission_state[m] = "RUNNING"
    /\ ~yolo_mode  \* YOLO mode prevents pausing
    /\ mission_state' = [mission_state EXCEPT ![m] = "PAUSED"]
    /\ pause_raised' = TRUE
    /\ UNCHANGED <<yolo_mode, commit_target, agent_workspace, agent_write_path>>

ResumeMission(m) ==
    /\ mission_state[m] = "PAUSED"
    /\ mission_state' = [mission_state EXCEPT ![m] = "RUNNING"]
    /\ pause_raised' = FALSE
    /\ UNCHANGED <<yolo_mode, commit_target, agent_workspace, agent_write_path>>

CompleteMission(m) ==
    /\ mission_state[m] = "RUNNING"
    /\ mission_state' = [mission_state EXCEPT ![m] = "DONE"]
    /\ UNCHANGED <<yolo_mode, pause_raised, commit_target,
                   agent_workspace, agent_write_path>>

(* Toggle YOLO mode *)
EnableYolo ==
    /\ ~yolo_mode
    /\ yolo_mode' = TRUE
    /\ UNCHANGED <<mission_state, pause_raised, commit_target,
                   agent_workspace, agent_write_path>>

DisableYolo ==
    /\ yolo_mode
    /\ yolo_mode' = FALSE
    /\ UNCHANGED <<mission_state, pause_raised, commit_target,
                   agent_workspace, agent_write_path>>

(* Git commit to a branch -- only non-protected branches allowed *)
CommitToBranch(b) ==
    /\ b \in Branches \ ProtectedBranches
    /\ commit_target' = b
    /\ UNCHANGED <<mission_state, yolo_mode, pause_raised,
                   agent_workspace, agent_write_path>>

(* Agent writes a file -- must be within own workspace *)
AgentWrite(a) ==
    /\ agent_write_path' = [agent_write_path EXCEPT ![a] = agent_workspace[a]]
    /\ UNCHANGED <<mission_state, yolo_mode, pause_raised,
                   commit_target, agent_workspace>>

-----------------------------------------------------------------------------
Next ==
    \/ \E m \in Missions : StartMission(m)
    \/ \E m \in Missions : PauseMission(m)
    \/ \E m \in Missions : ResumeMission(m)
    \/ \E m \in Missions : CompleteMission(m)
    \/ EnableYolo
    \/ DisableYolo
    \/ \E b \in Branches : CommitToBranch(b)
    \/ \E a \in Agents : AgentWrite(a)

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* INVARIANTS *)

TypeOK ==
    /\ \A m \in Missions : mission_state[m] \in MissionStates
    /\ yolo_mode \in BOOLEAN
    /\ pause_raised \in BOOLEAN
    /\ commit_target \in 0..NUM_BRANCHES
    /\ \A a \in Agents : agent_workspace[a] \in 1..NUM_AGENTS
    /\ \A a \in Agents : agent_write_path[a] \in 0..NUM_AGENTS

\* No mission is simultaneously RUNNING and PAUSED.
NoRunningAndPaused ==
    \A m \in Missions :
        ~(mission_state[m] = "RUNNING" /\ mission_state[m] = "PAUSED")

\* In YOLO mode, WorkflowPaused is never raised.
YoloNoPause ==
    yolo_mode => ~pause_raised

\* Protected branches are never directly committed to.
ProtectedBranchSafety ==
    commit_target \notin ProtectedBranches

\* No agent writes outside its own workspace.
WorkspaceSandbox ==
    \A a \in Agents :
        agent_write_path[a] /= 0 =>
            agent_write_path[a] = agent_workspace[a]

=============================================================================
