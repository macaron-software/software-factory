# RTK Integration for Claude, Copilot & OpenCode

## Status

✅ **Claude Code**: Hook-based (automatic via `~/.claude/hooks/rtk-rewrite.sh`)
✅ **Copilot CLI**: Shell functions (automatic via `~/.config/rtk/shell-integration.sh`)
✅ **OpenCode**: Shell functions (automatic via `~/.config/rtk/shell-integration.sh`)

## How It Works

### Claude Code
Uses PreToolUse hook that rewrites commands before execution.
- Config: `~/.claude/settings.json`
- Hook: `~/.claude/hooks/rtk-rewrite.sh`

### Copilot & OpenCode
Uses shell function overrides that intercept commands.
- Config: `~/.zshrc` (or `~/.bashrc`)
- Integration: `~/.config/rtk/shell-integration.sh`

## Verify It's Working

```bash
# Run test script
test-rtk-integration

# Check manually
type git  # Should say "shell function"
git status  # Should show compact output with 📌 emoji
ls  # Should show compact output with 📊 emoji
```

## Commands Auto-Wrapped

- `git` → `rtk git`
- `ls` → `rtk ls`
- `cat` → `rtk read`
- `grep` → `rtk grep`
- `find` → `rtk find`
- `pytest` → `rtk pytest`
- `cargo` → `rtk cargo`

## Check Savings

```bash
rtk gain              # Summary
rtk gain --graph      # With graph
rtk gain --history    # Recent commands
```

## Current Stats

As of setup (Mar 5, 2026):
- Total commands: 2180
- Tokens saved: 19.2M (93.5%)
- Top savings: curl (5.7M), read (755K)

## Troubleshooting

### Commands not using rtk?

1. Check shell integration is loaded:
   ```bash
   type git  # Should say "function"
   ```

2. Reload shell:
   ```bash
   source ~/.zshrc
   ```

3. For new terminals: close and reopen

### Want to disable?

Comment out in `~/.zshrc`:
```bash
# export RTK_ENABLED=auto
# [[ -f ~/.config/rtk/shell-integration.sh ]] && source ~/.config/rtk/shell-integration.sh
```

### Want more commands wrapped?

Edit `~/.config/rtk/shell-integration.sh` and uncomment:
```bash
npm() { _rtk_wrap npm "$@"; }
docker() { _rtk_wrap docker "$@"; }
gh() { _rtk_wrap gh "$@"; }
```
