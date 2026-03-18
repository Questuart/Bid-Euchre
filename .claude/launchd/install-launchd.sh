#!/bin/bash
# Install the steward session launchd agent for macOS.
#
# Usage:
#   .claude/launchd/install-launchd.sh           # Install
#   .claude/launchd/install-launchd.sh --dry-run  # Preview without installing
#   .claude/launchd/install-launchd.sh --uninstall # Remove the agent
#
# What it does:
#   1. Substitutes __REPO_PATH__ in the plist template with the actual repo path.
#   2. Copies the rendered plist to ~/Library/LaunchAgents/.
#   3. Loads the agent with launchctl.
#
# After installation, the agent runs at login and ensures the steward tmux
# session is present. See ensure-steward-session.plist for behavior details.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PLIST_TEMPLATE="${SCRIPT_DIR}/ensure-steward-session.plist"
PLIST_NAME="com.bid-euchre.steward-session.plist"
INSTALL_DIR="${HOME}/Library/LaunchAgents"
INSTALL_PATH="${INSTALL_DIR}/${PLIST_NAME}"

DRY_RUN=0
UNINSTALL=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--uninstall]"
            echo ""
            echo "  --dry-run    Preview the rendered plist without installing"
            echo "  --uninstall  Unload and remove the installed agent"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--dry-run] [--uninstall]"
            exit 1
            ;;
    esac
done

# --- uninstall ---------------------------------------------------------------

if [ "$UNINSTALL" = 1 ]; then
    if [ -f "$INSTALL_PATH" ]; then
        echo "Unloading agent..."
        launchctl unload "$INSTALL_PATH" 2>/dev/null || true
        echo "Removing ${INSTALL_PATH}..."
        rm "$INSTALL_PATH"
        echo "Done. Agent uninstalled."
    else
        echo "Agent not installed at ${INSTALL_PATH}. Nothing to do."
    fi
    exit 0
fi

# --- preflight ---------------------------------------------------------------

if [ "$(uname)" != "Darwin" ]; then
    echo "Error: This script is macOS-only (uses launchd)."
    echo "On Linux, use systemd or cron instead."
    exit 1
fi

if [ ! -f "$PLIST_TEMPLATE" ]; then
    echo "Error: Template not found at ${PLIST_TEMPLATE}"
    exit 1
fi

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: ${REPO_DIR} does not appear to be a git repository."
    exit 1
fi

# --- render ------------------------------------------------------------------

RENDERED="$(sed "s|__REPO_PATH__|${REPO_DIR}|g" "$PLIST_TEMPLATE")"

if [ "$DRY_RUN" = 1 ]; then
    echo "=== Dry run: rendered plist ==="
    echo ""
    echo "$RENDERED"
    echo ""
    echo "=== Would install to: ${INSTALL_PATH} ==="
    echo "=== Repo path: ${REPO_DIR} ==="
    exit 0
fi

# --- install -----------------------------------------------------------------

mkdir -p "$INSTALL_DIR"

# Unload existing agent if present
if [ -f "$INSTALL_PATH" ]; then
    echo "Unloading existing agent..."
    launchctl unload "$INSTALL_PATH" 2>/dev/null || true
fi

echo "Installing to ${INSTALL_PATH}..."
echo "$RENDERED" > "$INSTALL_PATH"

# Validate the plist
if ! plutil -lint "$INSTALL_PATH" >/dev/null 2>&1; then
    echo "Error: Generated plist is invalid. Removing."
    rm "$INSTALL_PATH"
    exit 1
fi

echo "Loading agent..."
launchctl load "$INSTALL_PATH"

echo ""
echo "Done! The steward session agent is now installed."
echo ""
echo "  Repo:     ${REPO_DIR}"
echo "  Plist:    ${INSTALL_PATH}"
echo "  Log:      /tmp/bid-euchre-steward-session.log"
echo "  Errors:   /tmp/bid-euchre-steward-session.err"
echo ""
echo "The agent will ensure the steward tmux session is running on login."
echo ""
echo "To uninstall:"
echo "  $0 --uninstall"
