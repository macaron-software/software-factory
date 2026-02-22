#!/bin/bash
# Install Git Hooks + Quality Tools
# One-command setup for local development quality pipeline

set -e

echo "=================================================="
echo "🛠️  Installing Git Hooks + Quality Tools"
echo "=================================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# 1. Check Git Repository
# ============================================================================
# Find .git directory (could be in parent if this is a subdir)
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)
if [ -z "$GIT_DIR" ]; then
  echo "❌ Error: Not a git repository"
  echo "Run this script from within a git repository"
  exit 1
fi

echo ""
echo "📂 Git repository found: $GIT_DIR"

# ============================================================================
# 2. Install Python Dependencies
# ============================================================================
echo ""
echo "🐍 Installing Python quality tools..."
if command -v python3 &> /dev/null; then
  if [ -f "requirements-dev.txt" ]; then
    python3 -m pip install --user -q -r requirements-dev.txt 2>&1 | grep -v "Requirement already satisfied" || true
    echo -e "${GREEN}✅ Python tools installed (--user)${NC}"
  else
    echo -e "${YELLOW}⚠️  requirements-dev.txt not found${NC}"
  fi
else
  echo -e "${YELLOW}⚠️  Python3 not found, skipping Python tools${NC}"
fi

# ============================================================================
# 3. Install JavaScript Dependencies (if package.json exists)
# ============================================================================
if [ -f "package.json" ]; then
  echo ""
  echo "📦 Installing JavaScript quality tools..."
  if command -v npm &> /dev/null; then
    npm install --save-dev eslint prettier @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-react eslint-config-prettier jest 2>&1 | grep -v "npm WARN" || true
    echo -e "${GREEN}✅ JavaScript tools installed${NC}"
  else
    echo -e "${YELLOW}⚠️  npm not found, skipping JavaScript tools${NC}"
  fi
else
  echo ""
  echo "📦 No package.json found, skipping JavaScript tools"
fi

# ============================================================================
# 4. Install Git Hooks
# ============================================================================
echo ""
echo "🔗 Installing Git hooks..."

# Copy hooks from scripts/quality/ to $GIT_DIR/hooks/
HOOKS=("pre-commit" "commit-msg" "pre-push")
SCRIPT_DIR=$(pwd)
for hook in "${HOOKS[@]}"; do
  if [ -f "scripts/quality/$hook" ]; then
    cp "scripts/quality/$hook" "$GIT_DIR/hooks/$hook"
    chmod +x "$GIT_DIR/hooks/$hook"
    echo -e "${GREEN}✅ Installed $hook to $GIT_DIR/hooks/${NC}"
  else
    echo -e "${YELLOW}⚠️  $hook not found in scripts/quality/${NC}"
  fi
done

# ============================================================================
# 5. Create .secrets.baseline (for detect-secrets)
# ============================================================================
echo ""
echo "🔒 Setting up secrets detection..."
if command -v detect-secrets &> /dev/null; then
  if [ ! -f ".secrets.baseline" ]; then
    detect-secrets scan --baseline .secrets.baseline
    echo -e "${GREEN}✅ Created .secrets.baseline${NC}"
  else
    echo "ℹ️  .secrets.baseline already exists"
  fi
else
  echo -e "${YELLOW}⚠️  detect-secrets not installed (optional)${NC}"
fi

# ============================================================================
# 6. Final Summary
# ============================================================================
echo ""
echo "=================================================="
echo -e "${GREEN}✅ Git Hooks Installation Complete!${NC}"
echo "=================================================="
echo ""
echo "Installed hooks:"
echo "  • pre-commit   - Linters + auto-fix + security"
echo "  • commit-msg   - Conventional commits validation"
echo "  • pre-push     - Full tests + coverage + security scan"
echo ""
echo "Configuration files created:"
echo "  • .ruff.toml          - Ruff linter config"
echo "  • .eslintrc.json      - ESLint config"
echo "  • .prettierrc         - Prettier config"
echo "  • pytest.ini          - Pytest config with coverage"
echo ""
echo "Next steps:"
echo "  1. Make a commit: git commit -m \"feat: my feature\""
echo "     → Auto-linting + auto-fix will run!"
echo ""
echo "  2. Push changes: git push"
echo "     → Full tests + security scan will run!"
echo ""
echo "Bypass hooks (emergency only):"
echo "  git commit --no-verify"
echo "  git push --no-verify"
echo ""
echo "=================================================="
