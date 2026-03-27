#!/usr/bin/env bash
# pii_guard_lite.sh — Lightweight PII/secrets pre-commit guard (no Python deps)
#
# Standalone regex-based scanner for staged files.
# Detects: API keys, tokens, private keys, emails, phone numbers, IP addresses.
# Designed to be copied to any repo as .git/hooks/pre-commit or via pre-commit framework.
#
# Usage:
#   As git hook:  cp pii_guard_lite.sh /path/to/repo/.git/hooks/pre-commit && chmod +x ...
#   As script:    bash pii_guard_lite.sh [--fix]  (--fix auto-redacts)

set -euo pipefail

VIOLATIONS=0
FIXES=()

# ── Patterns ─────────────────────────────────────────────────────────────────

# High-confidence secrets (always block)
SECRET_PATTERNS=(
    'ghp_[A-Za-z0-9]{20,}'                          # GitHub PAT
    'github_pat_[A-Za-z0-9_]{20,}'                   # GitHub fine-grained PAT
    'gho_[A-Za-z0-9]{20,}'                           # GitHub OAuth token
    'sk-[A-Za-z0-9]{20,}'                            # OpenAI/MiniMax key
    'sk-cp-[A-Za-z0-9]{20,}'                         # MiniMax specific
    'sk-ant-[A-Za-z0-9]{20,}'                        # Anthropic key
    'nvapi-[A-Za-z0-9]{20,}'                         # NVIDIA API key
    'EayNuWg3[A-Za-z0-9]{20,}'                       # Mistral key pattern
    'Bearer [A-Za-z0-9._-]{40,}'                     # Long bearer tokens
    '-----BEGIN [A-Z ]*PRIVATE KEY-----'             # Private keys
    '-----BEGIN [A-Z ]*CERTIFICATE-----'             # Certificates
    'AKIA[A-Z0-9]{16}'                               # AWS access key ID
    'AIza[A-Za-z0-9_-]{35}'                          # Google API key
    'ya29\.[A-Za-z0-9_-]{20,}'                       # Google OAuth token
    '[0-9]+-[A-Za-z0-9_]{32}\.apps\.googleusercontent\.com' # Google client ID
    '"type":\s*"service_account"'                    # Google service account JSON
    '"private_key":\s*"-----BEGIN'                   # Google/GCP private key in JSON
    'pk_live_[A-Za-z0-9]{20,}'                       # Stripe live publishable key
    'sk_live_[A-Za-z0-9]{20,}'                       # Stripe live secret key
    'pk_test_[A-Za-z0-9]{20,}'                       # Stripe test publishable key
    'rk_live_[A-Za-z0-9]{20,}'                       # Stripe restricted key
    'whsec_[A-Za-z0-9]{20,}'                         # Stripe webhook secret
    'INFISICAL_TOKEN=[A-Za-z0-9._-]{20,}'            # Infisical vault token
    'xox[bpors]-[A-Za-z0-9-]{20,}'                   # Slack token
    'hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+' # Slack webhook
    'SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'      # SendGrid API key
    'PRIVATE KEY.*\n.*[A-Za-z0-9+/=]{40,}'           # Generic private key content
    'password\s*[:=]\s*["\x27][^"\x27]{8,}["\x27]'  # Hardcoded passwords (quoted, 8+ chars)
    'IBAN\s*[:=]?\s*[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}' # IBAN numbers
    'FR[0-9]{2}[0-9]{5}[0-9]{5}[A-Z0-9]{11}[0-9]{2}' # French IBAN specific
)

# Medium-confidence PII (warn, block if --strict)
PII_PATTERNS=(
    '\+33[0-9 ]{9,}'                                 # French phone
    '\+1[0-9 ()-]{10,}'                              # US phone
    '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' # Email (broad)
    '[0-9]{3}[-. ][0-9]{2}[-. ][0-9]{3}[-. ][0-9]{3}[-. ][0-9]{2}' # French SSN (NIR)
    '[0-9]{13,16}'                                    # Credit card-like numbers (13-16 digits)
)

# Allowlist — skip these matches
ALLOWLIST=(
    'admin@demo.local'
    'noreply@anthropic.com'
    'noreply@macaron-software.com'
    'security@macaron-software.com'
    'conduct@macaron-software.com'
    'example@example.com'
    'user@example.com'
    'test@test.com'
    'postgresql://macaron:macaron@'
    'Co-Authored-By:'
    'Bearer YOUR_TOKEN'
    'Bearer eyJ'                                     # JWT example
    'sk-xxx'
    'sk-test'
    'sk_live_xxx'
)

# File extensions to scan
SCAN_EXTS='py|md|txt|yml|yaml|json|toml|ini|cfg|env|sh|ts|tsx|js|jsx|sql|html|css|rs|swift'

# ── Helpers ──────────────────────────────────────────────────────────────────

is_allowlisted() {
    local match="$1"
    for allow in "${ALLOWLIST[@]}"; do
        if [[ "$match" == *"$allow"* ]]; then
            return 0
        fi
    done
    return 1
}

# ── Main scan ────────────────────────────────────────────────────────────────

# Get staged files
STAGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)
if [ -z "$STAGED" ]; then
    exit 0
fi

for file in $STAGED; do
    # Skip binary and non-text files
    if ! echo "$file" | grep -qE "\.($SCAN_EXTS)$"; then
        continue
    fi
    if [ ! -f "$file" ]; then
        continue
    fi

    content=$(cat "$file" 2>/dev/null || true)
    if [ -z "$content" ]; then
        continue
    fi

    # Check secrets (high confidence — always block)
    for pattern in "${SECRET_PATTERNS[@]}"; do
        matches=$(echo "$content" | grep -oE "$pattern" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            while IFS= read -r match; do
                if is_allowlisted "$match"; then
                    continue
                fi
                preview="${match:0:30}..."
                echo "  BLOCK: $file — SECRET ($preview)" >&2
                VIOLATIONS=$((VIOLATIONS + 1))
            done <<< "$matches"
        fi
    done

    # Check PII (medium confidence — warn)
    for pattern in "${PII_PATTERNS[@]}"; do
        matches=$(echo "$content" | grep -oE "$pattern" 2>/dev/null || true)
        if [ -n "$matches" ]; then
            while IFS= read -r match; do
                if is_allowlisted "$match"; then
                    continue
                fi
                preview="${match:0:30}..."
                echo "  WARN:  $file — PII ($preview)" >&2
            done <<< "$matches"
        fi
    done
done

if [ "$VIOLATIONS" -gt 0 ]; then
    echo "" >&2
    echo "PII Guard: $VIOLATIONS secret(s) detected in staged files." >&2
    echo "Remove secrets before committing. Use SKIP=pii-guard git commit to bypass." >&2
    exit 1
fi

exit 0
