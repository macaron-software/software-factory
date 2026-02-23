#!/usr/bin/env bash
# =============================================================================
# Install Development Dependencies for Quality Pipeline
# =============================================================================
# Usage:
#   ./scripts/quality/install_dependencies.sh [--js] [--security] [--all]
#
# Options:
#   --js        Install JavaScript linting tools (ESLint, Prettier, Jest)
#   --security  Install security scanning tools (Trivy, git-secrets)
#   --all       Install everything
#   (no args)   Interactive mode - ask what to install
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# =============================================================================
# Helper functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

# =============================================================================
# Installation functions
# =============================================================================

install_python_tools() {
    log_info "Installing Python quality tools..."
    
    if ! check_command pip3 && ! check_command pip; then
        log_error "pip not found. Please install Python 3 first."
        return 1
    fi
    
    local pip_cmd="pip3"
    check_command pip3 || pip_cmd="pip"
    
    # Check if we need --user flag (externally-managed Python)
    local pip_flags=""
    if ! $pip_cmd install --dry-run black 2>&1 | grep -q "externally-managed"; then
        :  # No --user needed
    else
        log_warn "Python is externally-managed, using --user flag"
        pip_flags="--user"
    fi
    
    $pip_cmd install $pip_flags -r "$PROJECT_ROOT/requirements-dev.txt"
    log_info "✓ Python tools installed"
}

install_js_tools() {
    log_info "Installing JavaScript quality tools..."
    
    if ! check_command npm; then
        log_error "npm not found. Please install Node.js first: https://nodejs.org/"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    
    # Check if package.json exists
    if [ ! -f "package.json" ]; then
        log_info "Creating package.json..."
        npm init -y
    fi
    
    # Install dev dependencies
    log_info "Installing ESLint, Prettier, Jest..."
    npm install --save-dev \
        eslint \
        @typescript-eslint/parser \
        @typescript-eslint/eslint-plugin \
        eslint-plugin-react \
        eslint-plugin-react-hooks \
        prettier \
        jest \
        @types/jest \
        ts-jest
    
    # Add scripts to package.json if not present
    if ! grep -q '"lint":' package.json; then
        log_info "Adding npm scripts to package.json..."
        npm pkg set scripts.lint="eslint ."
        npm pkg set scripts.format="prettier --write ."
        npm pkg set scripts.test="jest"
    fi
    
    log_info "✓ JavaScript tools installed"
}

install_security_tools() {
    log_info "Installing security scanning tools..."
    
    local installed_any=false
    
    # Install detect-secrets (Python)
    if check_command pip3 || check_command pip; then
        local pip_cmd="pip3"
        check_command pip3 || pip_cmd="pip"
        
        local pip_flags=""
        if $pip_cmd install --dry-run detect-secrets 2>&1 | grep -q "externally-managed"; then
            pip_flags="--user"
        fi
        
        log_info "Installing detect-secrets..."
        $pip_cmd install $pip_flags detect-secrets
        
        # Create baseline
        if [ ! -f "$PROJECT_ROOT/.secrets.baseline" ]; then
            log_info "Creating .secrets.baseline..."
            cd "$PROJECT_ROOT"
            detect-secrets scan > .secrets.baseline 2>/dev/null || true
        fi
        
        installed_any=true
    fi
    
    # Install Trivy
    if check_command brew; then
        log_info "Installing Trivy via Homebrew..."
        brew install trivy
        installed_any=true
    elif check_command apt-get; then
        log_info "Installing Trivy via apt..."
        sudo apt-get update
        sudo apt-get install -y wget apt-transport-https gnupg lsb-release
        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
        sudo apt-get update
        sudo apt-get install -y trivy
        installed_any=true
    else
        log_warn "Could not install Trivy automatically. Please install manually:"
        log_warn "  macOS: brew install trivy"
        log_warn "  Linux: See https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
    fi
    
    # Install git-secrets
    if check_command brew; then
        log_info "Installing git-secrets via Homebrew..."
        brew install git-secrets
        installed_any=true
    elif check_command apt-get; then
        log_info "Installing git-secrets from source..."
        cd /tmp
        git clone https://github.com/awslabs/git-secrets.git
        cd git-secrets
        sudo make install
        cd "$PROJECT_ROOT"
        rm -rf /tmp/git-secrets
        installed_any=true
    else
        log_warn "Could not install git-secrets automatically. Please install manually:"
        log_warn "  See https://github.com/awslabs/git-secrets"
    fi
    
    if $installed_any; then
        log_info "✓ Security tools installed"
    else
        log_warn "No security tools were installed"
    fi
}

# =============================================================================
# Interactive mode
# =============================================================================

interactive_install() {
    log_info "Interactive installation mode"
    echo ""
    echo "What would you like to install?"
    echo ""
    echo "1) Python quality tools (Ruff, Black, Pytest, Bandit)"
    echo "2) JavaScript quality tools (ESLint, Prettier, Jest)"
    echo "3) Security scanning tools (Trivy, detect-secrets, git-secrets)"
    echo "4) Everything"
    echo "5) Exit"
    echo ""
    read -p "Enter choice [1-5]: " choice
    
    case $choice in
        1)
            install_python_tools
            ;;
        2)
            install_js_tools
            ;;
        3)
            install_security_tools
            ;;
        4)
            install_python_tools
            install_js_tools
            install_security_tools
            ;;
        5)
            log_info "Exiting"
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

# =============================================================================
# Main
# =============================================================================

main() {
    log_info "Development Dependencies Installer"
    log_info "Project: $PROJECT_ROOT"
    echo ""
    
    # Parse arguments
    if [ $# -eq 0 ]; then
        interactive_install
    else
        for arg in "$@"; do
            case $arg in
                --js)
                    install_js_tools
                    ;;
                --security)
                    install_security_tools
                    ;;
                --python)
                    install_python_tools
                    ;;
                --all)
                    install_python_tools
                    install_js_tools
                    install_security_tools
                    ;;
                --help|-h)
                    echo "Usage: $0 [OPTIONS]"
                    echo ""
                    echo "Options:"
                    echo "  --python     Install Python quality tools"
                    echo "  --js         Install JavaScript quality tools"
                    echo "  --security   Install security scanning tools"
                    echo "  --all        Install everything"
                    echo "  (no args)    Interactive mode"
                    exit 0
                    ;;
                *)
                    log_error "Unknown option: $arg"
                    echo "Use --help for usage information"
                    exit 1
                    ;;
            esac
        done
    fi
    
    echo ""
    log_info "Installation complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Run: make install-hooks"
    echo "  2. Read: cat CONTRIBUTING.md"
    echo "  3. Commit something to test the hooks!"
}

main "$@"
