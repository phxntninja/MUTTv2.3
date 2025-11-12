#!/bin/bash
# =====================================================================
# muttdev CLI Installation Script
# =====================================================================
# This script installs the muttdev CLI tool for MUTT developers.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/your-org/mutt/main/scripts/install_muttdev.sh | bash
#   # OR
#   ./scripts/install_muttdev.sh
#
# What this does:
#   1. Checks for required dependencies
#   2. Creates symlink to muttdev in /usr/local/bin
#   3. Makes muttdev executable
#   4. Verifies installation
# =====================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =====================================================================
# Helper Functions
# =====================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =====================================================================
# Dependency Checks
# =====================================================================

check_dependencies() {
    log_info "Checking dependencies..."

    local missing=()

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    else
        python_version=$(python3 --version | cut -d' ' -f2)
        log_info "  ✓ Python ${python_version} found"
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        missing+=("pip3")
    else
        log_info "  ✓ pip3 found"
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        echo ""
        echo "Please install:"
        echo "  macOS:   brew install python3"
        echo "  Ubuntu:  sudo apt install python3 python3-pip"
        echo "  RHEL:    sudo yum install python3 python3-pip"
        exit 1
    fi
}

# =====================================================================
# Installation
# =====================================================================

install_muttdev() {
    log_info "Installing muttdev CLI..."

    # Determine MUTT project root
    if [ -f "cli/muttdev" ]; then
        PROJECT_ROOT=$(pwd)
    elif [ -f "../cli/muttdev" ]; then
        PROJECT_ROOT=$(cd .. && pwd)
    else
        log_error "Could not find muttdev CLI script"
        log_error "Please run this script from the MUTT project root or scripts/ directory"
        exit 1
    fi

    MUTTDEV_SCRIPT="${PROJECT_ROOT}/cli/muttdev"

    # Make executable
    chmod +x "${MUTTDEV_SCRIPT}"
    log_info "  ✓ Made muttdev executable"

    # Create symlink in /usr/local/bin
    if [ -w /usr/local/bin ]; then
        ln -sf "${MUTTDEV_SCRIPT}" /usr/local/bin/muttdev
        log_info "  ✓ Created symlink: /usr/local/bin/muttdev -> ${MUTTDEV_SCRIPT}"
    else
        log_warn "  No write permission to /usr/local/bin"
        log_info "  Creating symlink with sudo..."
        sudo ln -sf "${MUTTDEV_SCRIPT}" /usr/local/bin/muttdev
        log_info "  ✓ Created symlink: /usr/local/bin/muttdev"
    fi

    # Install Python dependencies
    log_info "Installing Python dependencies..."

    if [ -f "${PROJECT_ROOT}/requirements.txt" ]; then
        pip3 install -q -r "${PROJECT_ROOT}/requirements.txt"
        log_info "  ✓ Python dependencies installed"
    else
        log_warn "  No requirements.txt found, skipping"
    fi
}

# =====================================================================
# Verification
# =====================================================================

verify_installation() {
    log_info "Verifying installation..."

    if ! command -v muttdev &> /dev/null; then
        log_error "muttdev command not found in PATH"
        echo ""
        echo "Please add /usr/local/bin to your PATH:"
        echo "  export PATH=\"/usr/local/bin:\$PATH\""
        exit 1
    fi

    # Test command
    if muttdev --version &> /dev/null; then
        version=$(muttdev --version 2>&1)
        log_info "  ✓ ${version}"
    else
        log_error "muttdev command failed"
        exit 1
    fi
}

# =====================================================================
# Main
# =====================================================================

main() {
    echo "=========================================="
    echo "muttdev CLI Installation"
    echo "=========================================="
    echo ""

    check_dependencies
    install_muttdev
    verify_installation

    echo ""
    echo "=========================================="
    log_info "Installation complete!"
    echo "=========================================="
    echo ""
    echo "Try it out:"
    echo "  muttdev --help"
    echo "  muttdev setup"
    echo "  muttdev status"
    echo ""
}

main "$@"
