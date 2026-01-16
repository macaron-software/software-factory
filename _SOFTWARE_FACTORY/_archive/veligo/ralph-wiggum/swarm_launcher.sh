#!/usr/bin/env bash
# swarm_launcher.sh - Launch N parallel TDD workers (fractal mode)
# Each worker picks a PENDING task, runs real_agent.py, repeats

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
STATUS_DIR="$SCRIPT_DIR/status"
LOCKS_DIR="$STATUS_DIR/locks"
LOGS_DIR="$SCRIPT_DIR/logs/swarm"
AGENT="$SCRIPT_DIR/real_agent.py"

# Number of parallel workers (default 50)
NUM_WORKERS="${1:-50}"
QUEUE_TYPE="${2:-tdd}"

# Create directories
mkdir -p "$STATUS_DIR" "$LOCKS_DIR" "$LOGS_DIR"

# Load .env.local
if [ -f "$SCRIPT_DIR/.env.local" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env.local" | xargs)
fi

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# Get next pending task (atomic with flock)
get_next_task() {
    local queue="$1"

    # Filter tasks by queue type
    local pattern="T*.md"
    if [ "$queue" = "deploy" ]; then
        pattern="D*.md"
    fi

    for task_file in "$TASKS_DIR"/$pattern; do
        [ -f "$task_file" ] || continue

        task_id=$(basename "$task_file" .md)
        status_file="$STATUS_DIR/${task_id}.status"
        lock_dir="$LOCKS_DIR/${task_id}.lock"

        # Check status
        if [ -f "$status_file" ]; then
            status=$(cat "$status_file" 2>/dev/null || echo "UNKNOWN")
            [ "$status" = "PENDING" ] || continue
        else
            echo "PENDING" > "$status_file"
        fi

        # Try to acquire lock (atomic via mkdir)
        if mkdir "$lock_dir" 2>/dev/null; then
            echo "$task_file"
            return 0
        fi
    done

    echo ""
    return 1
}

# Worker function
worker() {
    local worker_id="$1"
    local queue="$2"
    local log_file="$LOGS_DIR/worker_${worker_id}_$(date +%Y%m%d_%H%M%S).log"

    log "Worker $worker_id starting (queue: $queue)" >> "$log_file"

    while true; do
        # Get next task
        task_file=$(get_next_task "$queue")

        if [ -z "$task_file" ]; then
            log "Worker $worker_id: No more tasks, sleeping 30s..." >> "$log_file"
            sleep 30
            continue
        fi

        task_id=$(basename "$task_file" .md)
        lock_dir="$LOCKS_DIR/${task_id}.lock"
        status_file="$STATUS_DIR/${task_id}.status"

        log "Worker $worker_id: Processing $task_id" >> "$log_file"
        echo "IN_PROGRESS" > "$status_file"

        # Run the agent
        set +e
        python3 "$AGENT" "$task_file" "$queue" >> "$log_file" 2>&1
        exit_code=$?
        set -e

        # Update status based on exit code
        if [ $exit_code -eq 0 ]; then
            echo "COMPLETE" > "$status_file"
            log "Worker $worker_id: $task_id COMPLETE" >> "$log_file"
        else
            echo "FAILED" > "$status_file"
            log "Worker $worker_id: $task_id FAILED (exit $exit_code)" >> "$log_file"
        fi

        # Release lock
        rmdir "$lock_dir" 2>/dev/null || true

        # Small delay to avoid hammering
        sleep 2
    done
}

# Main
log "=========================================="
log "SWARM LAUNCHER - $NUM_WORKERS workers"
log "Queue: $QUEUE_TYPE"
log "=========================================="

# Count pending tasks
pending_count=$(grep -l "PENDING" "$STATUS_DIR"/*.status 2>/dev/null | wc -l | tr -d ' ')
log "Pending tasks: $pending_count"

if [ "$pending_count" -eq 0 ]; then
    log "No pending tasks! Exiting."
    exit 0
fi

# Launch workers in background
log "Launching $NUM_WORKERS workers..."

for i in $(seq 1 "$NUM_WORKERS"); do
    worker "$i" "$QUEUE_TYPE" &
    log "  Worker $i started (PID: $!)"
    sleep 0.1  # Stagger starts slightly
done

log "All workers launched. Press Ctrl+C to stop."
log "Logs: $LOGS_DIR"
log "Status: $STATUS_DIR"

# Wait for all workers
wait
