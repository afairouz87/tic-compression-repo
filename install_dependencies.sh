#!/usr/bin/env bash
#
# install_dependencies.sh
#
# Install everything needed to build and run the TIC artifact, then verify the
# result with check_environment.py.
#
#   ./install_dependencies.sh              # install, then verify
#   ./install_dependencies.sh --dry-run    # print what would be installed
#   ./install_dependencies.sh --skip-python
#   ./install_dependencies.sh --skip-system
#   ./install_dependencies.sh --no-verify
#
# Supported: Ubuntu/Debian (apt) and macOS (Homebrew). Any other OS exits 2.
#
# Separation of responsibilities:
#   install_dependencies.sh  installs system + Python dependencies   <- this file
#   requirements.txt         canonical Python dependency list
#   check_environment.py     verifies the environment
#   smoke_test.py            verifies functional correctness
#   run_*.py                 execute experiments
#
# This script installs dependencies only. It never edits shell profiles, PATH,
# or any unrelated system configuration, and it is safe to run more than once.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

DRY_RUN=0
SKIP_PYTHON=0
SKIP_SYSTEM=0
VERIFY=1

# --------------------------------------------------------------------------
# System packages.
#
# Only what the active artifact workflow actually invokes; see dependencies.py
# for the audit that produced these lists.
#
# Debian/Ubuntu:
#   build-essential  g++ and make (the C++17 toolchain)
#   gzip bzip2 grep  baseline tools; also provide zgrep and bzgrep
#   lz4              NOT preinstalled; required by every compression experiment
#   lbzip2           NOT preinstalled; required by the PARALLEL experiments only
#   python3          interpreter
#   python3-pip      to install requirements.txt
#
# macOS:
#   g++/make/gzip/bzip2/grep/python3 already ship with macOS or the Xcode
#   Command Line Tools, so they are NOT installed here. Installing Homebrew's
#   GNU gzip/grep would change which implementation the benchmarks invoke, so
#   the script deliberately leaves the system versions in place.
#   Only lz4 and lbzip2 are genuinely missing on a stock macOS system.
# --------------------------------------------------------------------------
APT_PACKAGES=(build-essential gzip bzip2 grep lz4 lbzip2 python3 python3-pip)
BREW_PACKAGES=(lz4 lbzip2)

log()  { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die()  { printf '[FAIL] %s\n' "$1" >&2; exit "${2:-1}"; }

usage() {
    sed -n '3,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --dry-run)     DRY_RUN=1 ;;
        --skip-python) SKIP_PYTHON=1 ;;
        --skip-system) SKIP_SYSTEM=1 ;;
        --no-verify)   VERIFY=0 ;;
        -h|--help)     usage ;;
        *)             die "Unknown option: $arg (try --help)" ;;
    esac
done

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN] %s\n' "$*"
    else
        "$@"
    fi
}

have() { command -v "$1" >/dev/null 2>&1; }

# --------------------------------------------------------------------------
# OS detection
# --------------------------------------------------------------------------
detect_os() {
    case "$(uname -s)" in
        Linux)
            if have apt-get; then
                echo "debian"
            else
                die "Unsupported Linux distribution: no apt-get found.
       Only Ubuntu/Debian (apt) is supported by this script.
       Install these manually, then run: python3 check_environment.py
         ${APT_PACKAGES[*]}" 2
            fi
            ;;
        Darwin) echo "macos" ;;
        *)      die "Unsupported operating system: $(uname -s).
       Supported: Ubuntu/Debian (apt) and macOS (Homebrew)." 2 ;;
    esac
}

# Privilege escalation, Linux only, and only when not already root.
sudo_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        echo ""
    elif have sudo; then
        echo "sudo"
    else
        die "Root privileges are required to install system packages, but sudo
       was not found. Re-run as root, or install manually:
         ${APT_PACKAGES[*]}"
    fi
}

# --------------------------------------------------------------------------
# Debian / Ubuntu
# --------------------------------------------------------------------------
install_debian() {
    local SUDO missing=()
    SUDO="$(sudo_cmd)"

    for pkg in "${APT_PACKAGES[@]}"; do
        if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "ok installed"; then
            log "already installed: $pkg"
        else
            missing+=("$pkg")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        log "All system packages are already installed."
        return 0
    fi

    log "Will install via apt: ${missing[*]}"
    # shellcheck disable=SC2086
    run $SUDO apt-get update
    # shellcheck disable=SC2086
    run $SUDO apt-get install -y "${missing[@]}"
}

# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------
install_macos() {
    if ! have brew; then
        die "Homebrew is required on macOS but was not found.

       This script will NOT install Homebrew for you: it modifies system
       state and must be an explicit decision. Install it yourself from
       the official instructions at https://brew.sh, then re-run:

         ./install_dependencies.sh

       Alternatively install lz4 and lbzip2 by any means you prefer and run:

         python3 check_environment.py" 2
    fi

    if ! xcode-select -p >/dev/null 2>&1; then
        warn "Xcode Command Line Tools not detected; g++ and make may be missing."
        warn "Install them with:  xcode-select --install"
    else
        log "already installed: Xcode Command Line Tools (provides g++, make)"
    fi

    local missing=()
    for pkg in "${BREW_PACKAGES[@]}"; do
        if brew list --formula "$pkg" >/dev/null 2>&1; then
            log "already installed: $pkg"
        else
            missing+=("$pkg")
        fi
    done

    log "macOS ships gzip, bzip2, grep and python3; not installing Homebrew"
    log "replacements, so the benchmarks keep using the system versions."

    if [ "${#missing[@]}" -eq 0 ]; then
        log "All Homebrew packages are already installed."
        return 0
    fi

    log "Will install via Homebrew: ${missing[*]}"
    run brew install "${missing[@]}"
}

# --------------------------------------------------------------------------
# Python packages -- always from requirements.txt, never duplicated here
# --------------------------------------------------------------------------
install_python() {
    [ -f requirements.txt ] || die "requirements.txt not found in $REPO_ROOT"

    local PY=python3
    have "$PY" || die "python3 not found. Install it first, then re-run."

    log "Will install Python packages from requirements.txt:"
    grep -vE '^\s*(#|$)' requirements.txt | sed 's/^/         /'

    run "$PY" -m pip install --upgrade pip
    run "$PY" -m pip install -r requirements.txt
}

# --------------------------------------------------------------------------
main() {
    local os
    os="$(detect_os)"

    echo "TIC artifact -- dependency installation"
    echo "======================================"
    log "Repository : $REPO_ROOT"
    log "OS         : $(uname -s) $(uname -r) ($(uname -m)) -> $os"
    [ "$DRY_RUN" -eq 1 ] && log "Mode       : DRY RUN (nothing will be installed)"
    echo

    if [ "$SKIP_SYSTEM" -eq 1 ]; then
        log "Skipping system packages (--skip-system)."
    else
        echo "System packages"
        echo "---------------"
        case "$os" in
            debian) install_debian ;;
            macos)  install_macos ;;
        esac
        echo
    fi

    if [ "$SKIP_PYTHON" -eq 1 ]; then
        log "Skipping Python packages (--skip-python)."
    else
        echo "Python packages"
        echo "---------------"
        install_python
        echo
    fi

    if [ "$VERIFY" -eq 0 ]; then
        log "Skipping verification (--no-verify). Run: python3 check_environment.py"
        return 0
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        log "Dry run complete. Verification skipped."
        log "Next: ./install_dependencies.sh   then   python3 check_environment.py"
        return 0
    fi

    echo "Verification"
    echo "------------"
    log "Running: python3 check_environment.py"
    echo

    if python3 check_environment.py; then
        echo
        log "Installation verified."
        log "Next: make && python3 smoke_test.py"
        return 0
    fi

    echo
    die "Environment verification FAILED after installation.
       The required checks above must pass before the artifact can run.
       See docs/environment.md for troubleshooting."
}

main "$@"
