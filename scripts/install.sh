#!/bin/bash
# SSH Manager Linux/macOS install/uninstall script
# Features: auto-download, rename, add to PATH, and uninstall
# 
# Usage:
#   Online install:curl -fsSL https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.sh | bash
#   Local install: bash install.sh
#   Online uninstall:curl -fsSL https://raw.githubusercontent.com/Eavelabs/sshm/main/scripts/install.sh | bash -s -- --uninstall
#   Local uninstall: bash install.sh --uninstall

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Output helpers
info() { echo -e "${CYAN}$1${NC}"; }
success() { echo -e "${GREEN}$1${NC}"; }
warning() { echo -e "${YELLOW}$1${NC}"; }
error() { echo -e "${RED}$1${NC}"; exit 1; }

# Argument parsing
VERSION="latest"
INSTALL_DIR="/usr/local/bin"
NO_ADD_PATH=false
UNINSTALL=false
CLEAN_PATH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --no-add-path)
            NO_ADD_PATH=true
            shift
            ;;
        --clean-path)
            CLEAN_PATH=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Uninstall function
uninstall_sshm() {
    info "================================="
    info "SSH Manager Uninstaller"
    info "================================="
    echo ""
    
    # Files to remove (cover all possible platform binary names)
    FILES_TO_REMOVE=(
        "$INSTALL_DIR/sshm"
        "$INSTALL_DIR/sshm-linux-amd64"
        "$INSTALL_DIR/sshm-macos-amd64"
    )
    
    SUMMARY_DELETED=0
    
    for FILE in "${FILES_TO_REMOVE[@]}"; do
        if [ -f "$FILE" ]; then
            if [ -w "$INSTALL_DIR" ]; then
                rm -f "$FILE"
                success "Deleted: $FILE"
            else
                sudo rm -f "$FILE"
                success "Deleted: $FILE (requires sudo)"
            fi
            SUMMARY_DELETED=$((SUMMARY_DELETED + 1))
        fi
    done
    
    if [ $SUMMARY_DELETED -eq 0 ]; then
        warning "No SSH Manager files found in $INSTALL_DIR"
    fi
    
    echo ""
    success "Uninstall complete!"
    exit 0
}

# Uninstall mode
if [ "$UNINSTALL" = true ]; then
    uninstall_sshm
fi

# Clean stale sshm PATH entries from shell rc files (keep current install dir)
clean_stale_sshm_path() {
    info "Cleaning stale sshm PATH entries..."
    local keep="$INSTALL_DIR"
    local removed=0
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.config/fish/config.fish"; do
        [ -f "$rc" ] || continue
        local tmp="${rc}.sshm_tmp"
        : > "$tmp"
        local changed=0
        while IFS= read -r line || [ -n "$line" ]; do
            # line is an export PATH containing sshm
            if echo "$line" | grep -q "export PATH=" && echo "$line" | grep -q "sshm"; then
                # keep if it points to the current install dir, otherwise stale
                if echo "$line" | grep -qF "$keep"; then
                    echo "$line" >> "$tmp"
                else
                    removed=$((removed + 1))
                    changed=1
                    warning "  Removed: $line"
                    continue
                fi
            else
                echo "$line" >> "$tmp"
            fi
        done < "$rc"
        if [ "$changed" = "1" ]; then
            mv "$tmp" "$rc"
        else
            rm -f "$tmp"
        fi
    done
    info "Cleanup done (removed $removed stale entries)"
}

# Main install flow
info "================================="
info "SSH Manager Installer"
info "================================="
echo ""

# Detect platform
OS="$(uname -s)"
case "$OS" in
    Linux*)     
        PLATFORM="linux"
        ASSET_NAME="sshm-linux-amd64"
        ;;
    Darwin*)    
        PLATFORM="macos"
        ASSET_NAME="sshm-macos-amd64"
        ;;
    *)          
        error "Unsupported platform: $OS"
        ;;
esac

info "Detected platform: $PLATFORM"
echo ""

# Get version info
REPO="Eavelabs/sshm"
info "Getting version info..."

if [ "$VERSION" = "latest" ]; then
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
else
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/tags/$VERSION"
fi

if ! RELEASE_INFO=$(curl -fsSL "$RELEASE_URL"); then
    error "Failed to get version info, check network connection"
fi

VERSION=$(echo "$RELEASE_INFO" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/$ASSET_NAME"

if [ -z "$VERSION" ]; then
    error "Failed to parse version info"
fi

success "Found version: $VERSION"
info "Download URL: $DOWNLOAD_URL"
echo ""

# Show install info
info "Install location: $INSTALL_DIR/sshm"
echo ""

# Confirm installation (non-silent)
if [ -t 0 ]; then
    read -p "Continue installation? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        warning "Installation cancelled"
        exit 0
    fi
fi

# Check permissions
if [ ! -w "$INSTALL_DIR" ]; then
    warning "sudo required to install to $INSTALL_DIR"
    SUDO="sudo"
else
    SUDO=""
fi

# Download file
TMP_FILE="/tmp/$ASSET_NAME"
echo ""
info "Downloading $VERSION..."

if ! curl -L --progress-bar "$DOWNLOAD_URL" -o "$TMP_FILE"; then
    error "Download failed"
fi

success "Download complete"

# Set execute permission
chmod +x "$TMP_FILE"

# Install (renamed to sshm)
info "Installing to $INSTALL_DIR/sshm..."
if ! $SUDO mv "$TMP_FILE" "$INSTALL_DIR/sshm"; then
    error "Install failed"
fi

success "Installed: $INSTALL_DIR/sshm"

# Verify installation
echo ""
info "Verifying installation..."
if sshm --help >/dev/null 2>&1; then
    success "Verification passed!"
else
    warning "Verification failed, but file installed"
fi

# Installation complete
echo ""
info "================================="
success "Installation complete!"
info "================================="
echo ""
info "Install location: $INSTALL_DIR/sshm"
info "Version: $VERSION"
echo ""

# Check PATH
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
    info "Usage:"
    echo -e "  ${YELLOW}sshm list${NC}"
    echo -e "  ${YELLOW}sshm --help${NC}"
else
    warning "$INSTALL_DIR is not in PATH"
    info "Usage:"
    echo "  Option 1: run with full path"
    echo -e "    ${YELLOW}$INSTALL_DIR/sshm list${NC}"
    echo ""
    echo "  Option 2: add to PATH (add to ~/.bashrc or ~/.zshrc)"
    echo -e "    ${YELLOW}export PATH=\"\$PATH:$INSTALL_DIR\"${NC}"
fi

# Clean stale sshm PATH entries (--clean-path)
if [ "$CLEAN_PATH" = true ]; then
    echo ""
    clean_stale_sshm_path
fi

echo ""
info "More help:"
echo "  sshm --help"
echo "  https://github.com/$REPO"
echo ""

# Uninstall hint
echo -e "${BLUE}Uninstall:${NC}"
echo -e "  ${BLUE}bash install.sh --uninstall${NC}"
echo ""
