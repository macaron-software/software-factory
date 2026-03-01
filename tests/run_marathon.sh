#!/usr/bin/env bash
# run_marathon.sh — SF Endurance Marathon Runner
#
# Usage:
#   ./tests/run_marathon.sh              # 12h, all envs
#   MARATHON_HOURS=24 ./tests/run_marathon.sh
#   MARATHON_HOURS=36 MARATHON_ENV=azure ./tests/run_marathon.sh
#
# Output: tests/marathon_results_*.json + tests/ENDURANCE_REPORT.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

MARATHON_HOURS="${MARATHON_HOURS:-12}"
MARATHON_ENV="${MARATHON_ENV:-all}"
AZURE_PASS="${AZURE_PASS:-MacaronAz2026!}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   SF ENDURANCE MARATHON — ${MARATHON_HOURS}h — ENV: ${MARATHON_ENV}"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Project: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

# ── Pre-flight checks ──────────────────────────────────────────────
echo "── Pre-flight checks ──"

check_env() {
    local name="$1"
    local url="$2"
    local auth="$3"

    if [ -n "$auth" ]; then
        status=$(curl -sk --max-time 10 -u "$auth" "$url/api/health" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    else
        status=$(curl -sk --max-time 10 "$url/api/health" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
    fi

    if [ "$status" = "200" ]; then
        echo "  ✅ $name ($url) — HTTP 200"
    else
        echo "  ⚠️  $name ($url) — HTTP $status (will skip)"
    fi
}

check_env "Local"       "http://localhost:8099"          ""
check_env "Azure Prod"  "https://sf.macaron-software.com" "admin:${AZURE_PASS}"
check_env "OVH Demo"    "http://54.36.183.124:8090"       ""

echo ""

# ── Run deliverable quality check first ───────────────────────────
echo "── Phase 1: Deliverable quality check ──"
python3 -m pytest tests/test_deliverable_quality.py -v --tb=short 2>&1 | tee /tmp/deliverable_report.txt
echo ""

# ── Run Playwright smoke on available envs ────────────────────────
echo "── Phase 2: Playwright smoke tests ──"
if command -v npx &>/dev/null && [ -d "platform/tests/e2e/node_modules" ]; then
    cd platform/tests/e2e

    for ENV_NAME in local azure ovh; do
        case "$ENV_NAME" in
            local)  ENV_URL="http://localhost:8099" ; AUTH="" ;;
            azure)  ENV_URL="https://sf.macaron-software.com" ; AUTH="" ;;
            ovh)    ENV_URL="http://54.36.183.124:8090" ; AUTH="" ;;
        esac

        status=$(curl -sk --max-time 8 "$ENV_URL/api/health" -o /dev/null -w "%{http_code}" 2>/dev/null || echo "000")
        if [ "$status" = "200" ]; then
            echo "  Running smoke on $ENV_NAME..."
            BASE_URL="$ENV_URL" npx playwright test pages.spec.ts portfolio.spec.ts endurance.spec.ts \
                --timeout 60000 2>&1 | tail -10 || true
        else
            echo "  ⚠️  Skipping $ENV_NAME (HTTP $status)"
        fi
    done

    cd "$PROJECT_DIR"
else
    echo "  ⚠️  Playwright not available (skipping)"
fi
echo ""

# ── Run stability tests ───────────────────────────────────────────
echo "── Phase 3: Stability tests ──"
STABILITY_TESTS=1 python3 -m pytest tests/test_stability.py -v --tb=short -x 2>&1 | tee /tmp/stability_report.txt || true
echo ""

# ── Launch the marathon ───────────────────────────────────────────
echo "── Phase 4: Marathon endurance (${MARATHON_HOURS}h) ──"
echo "  This will run for ${MARATHON_HOURS} hours. Use Ctrl+C to stop early."
echo "  Results will be saved to tests/marathon_results_*.json"
echo ""

MARATHON_HOURS="$MARATHON_HOURS" \
MARATHON_ENV="$MARATHON_ENV" \
AZURE_PASS="$AZURE_PASS" \
python3 tests/test_endurance_marathon.py --hours "$MARATHON_HOURS" --env "$MARATHON_ENV" 2>&1 | tee /tmp/marathon_output.txt

# ── Generate final report ─────────────────────────────────────────
echo ""
echo "── Phase 5: Generating consolidated report ──"

python3 - <<'PYEOF'
import json
import glob
import datetime
from pathlib import Path

report_dir = Path("tests")
results_files = sorted(glob.glob(str(report_dir / "marathon_results_*.json")))

lines = [
    "# SF Endurance Report",
    f"Generated: {datetime.datetime.now().isoformat()}",
    "",
    "## Marathon Results (uptime, latency, missions)",
    "| Env | Hours | Uptime % | Avg Latency | P99 Latency | Missions +done | Zombies | Alerts |",
    "|-----|-------|----------|-------------|-------------|----------------|---------|--------|",
]

for f in results_files:
    try:
        d = json.loads(Path(f).read_text())
        row = (
            f"| {d.get('env','?')} "
            f"| {d.get('hours','?')}h "
            f"| {d.get('uptime_pct',0):.1f}% "
            f"| {d.get('avg_latency_ms',0):.0f}ms "
            f"| {d.get('p99_latency_ms',0):.0f}ms "
            f"| +{d.get('missions_completed',0)} "
            f"| {d.get('zombie_incidents',0)} "
            f"| {len(d.get('alerts',[]))} |"
        )
        lines.append(row)
    except Exception as e:
        lines.append(f"| error reading {f}: {e} ||||||||")

lines += [
    "",
    "## Overall Assessment",
]

for f in results_files:
    try:
        d = json.loads(Path(f).read_text())
        uptime = d.get('uptime_pct', 0)
        icon = "✅" if uptime >= 99.0 else "⚠️" if uptime >= 95.0 else "❌"
        lines.append(f"- {icon} **{d['env']}**: uptime={uptime:.1f}% p99={d.get('p99_latency_ms',0):.0f}ms zombies={d.get('zombie_incidents',0)}")
        for alert in d.get('alerts', [])[:5]:
            lines.append(f"  - ⚠️ {alert}")
    except Exception:
        pass

# Append deliverable report if exists
deliv = Path("tests/DELIVERABLE_QUALITY_REPORT.md")
if deliv.exists():
    lines += ["", "---", "", deliv.read_text()]

report_text = "\n".join(lines)
report_path = Path("tests/ENDURANCE_REPORT.md")
report_path.write_text(report_text)
print(f"\nReport saved: {report_path}")
print(report_text[:2000])
PYEOF

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   MARATHON COMPLETE — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  Report: tests/ENDURANCE_REPORT.md"
echo "  Results: tests/marathon_results_*.json"
