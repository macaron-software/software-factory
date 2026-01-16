#!/bin/bash
#
# Wiggum Batch TDD Runner - Run TDD agent on FAILED tasks
# Usage: ./wiggum_batch_tdd.sh [iterations] [parallel_workers]
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS_DIR="$SCRIPT_DIR/status"
TASKS_DIR="$SCRIPT_DIR/tasks"
LOGS_DIR="$SCRIPT_DIR/logs"

ITERATIONS=${1:-10}
PARALLEL_WORKERS=${2:-4}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$LOGS_DIR"

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       WIGGUM BATCH TDD RUNNER - Ralph Wiggum Style          ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Iterations: $ITERATIONS  |  Parallel Workers: $PARALLEL_WORKERS               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"

# Get list of FAILED tasks
FAILED_TASKS=()
for status_file in "$STATUS_DIR"/T*.status; do
    if [[ -f "$status_file" ]]; then
        status=$(head -1 "$status_file")
        if [[ "$status" == "FAILED" ]]; then
            task_id=$(basename "$status_file" .status)
            if [[ -f "$TASKS_DIR/${task_id}.md" ]]; then
                FAILED_TASKS+=("$task_id")
            fi
        fi
    fi
done

echo -e "${YELLOW}Found ${#FAILED_TASKS[@]} FAILED tasks to process${NC}"
echo ""

if [[ ${#FAILED_TASKS[@]} -eq 0 ]]; then
    echo -e "${GREEN}No FAILED tasks found! All done.${NC}"
    exit 0
fi

# Display tasks
echo -e "${BLUE}Tasks to process:${NC}"
for task in "${FAILED_TASKS[@]}"; do
    echo "  - $task"
done
echo ""

# Function to run agent on a task
run_agent() {
    local task_id=$1
    local iteration=$2
    local log_file="$LOGS_DIR/${task_id}_iter${iteration}.log"

    echo -e "${BLUE}[ITER $iteration] Starting $task_id${NC}"

    # Mark as IN_PROGRESS
    echo "IN_PROGRESS" > "$STATUS_DIR/${task_id}.status"

    # Run the real agent
    cd "$SCRIPT_DIR"
    python3 real_agent.py "tasks/${task_id}.md" tdd > "$log_file" 2>&1
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        echo "COMPLETE" > "$STATUS_DIR/${task_id}.status"
        echo -e "${GREEN}[ITER $iteration] $task_id COMPLETE${NC}"
        return 0
    else
        echo "FAILED" > "$STATUS_DIR/${task_id}.status"
        echo -e "${RED}[ITER $iteration] $task_id FAILED${NC}"
        return 1
    fi
}

# Run iterations
for iter in $(seq 1 "$ITERATIONS"); do
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                    ITERATION $iter / $ITERATIONS${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"

    # Refresh FAILED tasks list
    CURRENT_FAILED=()
    for status_file in "$STATUS_DIR"/T*.status; do
        if [[ -f "$status_file" ]]; then
            status=$(head -1 "$status_file")
            if [[ "$status" == "FAILED" ]]; then
                task_id=$(basename "$status_file" .status)
                if [[ -f "$TASKS_DIR/${task_id}.md" ]]; then
                    CURRENT_FAILED+=("$task_id")
                fi
            fi
        fi
    done

    if [[ ${#CURRENT_FAILED[@]} -eq 0 ]]; then
        echo -e "${GREEN}All tasks COMPLETE! Stopping early.${NC}"
        break
    fi

    echo -e "${YELLOW}${#CURRENT_FAILED[@]} FAILED tasks remaining${NC}"

    # Process tasks in parallel batches
    running_pids=()
    for task in "${CURRENT_FAILED[@]}"; do
        # Wait if we have too many parallel workers
        while [[ ${#running_pids[@]} -ge $PARALLEL_WORKERS ]]; do
            # Wait for any child to finish
            for pid_idx in "${!running_pids[@]}"; do
                if ! kill -0 "${running_pids[$pid_idx]}" 2>/dev/null; then
                    unset 'running_pids[$pid_idx]'
                fi
            done
            # Compact array
            running_pids=("${running_pids[@]}")
            sleep 1
        done

        # Start agent in background
        run_agent "$task" "$iter" &
        running_pids+=($!)
    done

    # Wait for all to complete
    for pid in "${running_pids[@]}"; do
        wait "$pid" 2>/dev/null
    done

    # Summary for this iteration
    completed=$(grep -l "^COMPLETE" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')
    failed=$(grep -l "^FAILED" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')
    echo ""
    echo -e "${BLUE}Iteration $iter Summary: COMPLETE=$completed, FAILED=$failed${NC}"

    # Brief pause between iterations
    sleep 2
done

# Final summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    FINAL SUMMARY                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"

final_complete=$(grep -l "^COMPLETE" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')
final_failed=$(grep -l "^FAILED" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')
final_pending=$(grep -l "^PENDING" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')
final_progress=$(grep -l "^IN_PROGRESS" "$STATUS_DIR"/T*.status 2>/dev/null | wc -l | tr -d ' ')

echo -e "  COMPLETE:    ${GREEN}$final_complete${NC}"
echo -e "  FAILED:      ${RED}$final_failed${NC}"
echo -e "  PENDING:     ${YELLOW}$final_pending${NC}"
echo -e "  IN_PROGRESS: ${BLUE}$final_progress${NC}"
echo ""
echo -e "${GREEN}Logs saved to: $LOGS_DIR${NC}"
