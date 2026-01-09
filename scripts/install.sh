#!/bin/bash
# SSH Manager Linux/macOS 安装/卸载脚本
# 功能：自动下载、重命名、添加到 PATH，也可用于卸载
# 
# 使用方法: 
#   在线安装: curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash
#   本地安装: bash install.sh
#   在线卸载: curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash -s -- --uninstall
#   本地卸载: bash install.sh --uninstall

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 输出函数
info() { echo -e "${CYAN}$1${NC}"; }
success() { echo -e "${GREEN}$1${NC}"; }
warning() { echo -e "${YELLOW}$1${NC}"; }
error() { echo -e "${RED}$1${NC}"; exit 1; }

# 参数解析
VERSION="latest"
INSTALL_DIR="/usr/local/bin"
NO_ADD_PATH=false
UNINSTALL=false

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
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 卸载函数
uninstall_sshm() {
    info "================================="
    info "SSH Manager 卸载程序"
    info "================================="
    echo ""
    
    SSHM_PATH="$INSTALL_DIR/sshm"
    PLATFORM_FILE=""
    
    # 检测平台
    OS="$(uname -s)"
    case "$OS" in
        Linux*)     PLATFORM_FILE="$INSTALL_DIR/sshm-linux-amd64";;
        Darwin*)    PLATFORM_FILE="$INSTALL_DIR/sshm-macos-amd64";;
    esac
    
    # 删除文件
    if [ -f "$SSHM_PATH" ]; then
        if [ -w "$INSTALL_DIR" ]; then
            rm -f "$SSHM_PATH"
            success "✅ 已删除: $SSHM_PATH"
        else
            sudo rm -f "$SSHM_PATH"
            success "✅ 已删除: $SSHM_PATH (需要 sudo)"
        fi
    else
        warning "⚠️  未找到: $SSHM_PATH"
    fi
    
    # 删除平台标识文件（如果存在）
    if [ -f "$PLATFORM_FILE" ]; then
        if [ -w "$INSTALL_DIR" ]; then
            rm -f "$PLATFORM_FILE"
            success "✅ 已删除: $PLATFORM_FILE"
        else
            sudo rm -f "$PLATFORM_FILE"
            success "✅ 已删除: $PLATFORM_FILE (需要 sudo)"
        fi
    fi
    
    echo ""
    success "卸载完成！"
    exit 0
}

# 检查是否为卸载模式
if [ "$UNINSTALL" = true ]; then
    uninstall_sshm
fi

# 主安装流程
info "================================="
info "SSH Manager 安装程序"
info "================================="
echo ""

# 检测平台
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
        error "❌ 不支持的平台: $OS"
        ;;
esac

info "🖥️  检测到平台: $PLATFORM"
echo ""

# 获取版本信息
REPO="365tools/SSHKeyManager"
info "📦 正在获取版本信息..."

if [ "$VERSION" = "latest" ]; then
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
else
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/tags/$VERSION"
fi

if ! RELEASE_INFO=$(curl -fsSL "$RELEASE_URL"); then
    error "❌ 无法获取版本信息，请检查网络连接"
fi

VERSION=$(echo "$RELEASE_INFO" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/$ASSET_NAME"

if [ -z "$VERSION" ]; then
    error "❌ 解析版本信息失败"
fi

success "✅ 找到版本: $VERSION"
info "🔗 下载地址: $DOWNLOAD_URL"
echo ""

# 显示安装信息
info "📂 安装位置: $INSTALL_DIR/sshm"
echo ""

# 确认安装（非静默模式）
if [ -t 0 ]; then
    read -p "是否继续安装? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        warning "❌ 安装已取消"
        exit 0
    fi
fi

# 检查权限
if [ ! -w "$INSTALL_DIR" ]; then
    warning "⚠️  需要 sudo 权限安装到 $INSTALL_DIR"
    SUDO="sudo"
else
    SUDO=""
fi

# 下载文件
TMP_FILE="/tmp/$ASSET_NAME"
echo ""
info "⬇️  正在下载 $VERSION..."

if ! curl -L --progress-bar "$DOWNLOAD_URL" -o "$TMP_FILE"; then
    error "❌ 下载失败"
fi

success "✅ 下载完成"

# 赋予执行权限
chmod +x "$TMP_FILE"

# 安装（重命名为 sshm）
info "📝 安装到 $INSTALL_DIR/sshm..."
if ! $SUDO mv "$TMP_FILE" "$INSTALL_DIR/sshm"; then
    error "❌ 安装失败"
fi

success "✅ 安装成功: $INSTALL_DIR/sshm"

# 验证安装
echo ""
info "🧪 验证安装..."
if sshm --help >/dev/null 2>&1; then
    success "✅ 安装验证成功！"
else
    warning "⚠️  验证失败，但文件已安装"
fi

# 安装完成
echo ""
info "================================="
success "✅ 安装完成！"
info "================================="
echo ""
info "📍 安装位置: $INSTALL_DIR/sshm"
info "📌 版本: $VERSION"
echo ""

# 检查 PATH
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
    info "使用方法:"
    echo -e "  ${YELLOW}sshm list${NC}"
    echo -e "  ${YELLOW}sshm --help${NC}"
else
    warning "⚠️  $INSTALL_DIR 不在 PATH 中"
    info "使用方法:"
    echo "  方式 1: 完整路径运行"
    echo -e "    ${YELLOW}$INSTALL_DIR/sshm list${NC}"
    echo ""
    echo "  方式 2: 添加到 PATH (添加到 ~/.bashrc 或 ~/.zshrc)"
    echo -e "    ${YELLOW}export PATH=\"\$PATH:$INSTALL_DIR\"${NC}"
fi

echo ""
info "更多帮助:"
echo "  sshm --help"
echo "  https://github.com/$REPO"
echo ""

# 提示如何卸载
echo -e "${BLUE}卸载方法:${NC}"
echo -e "  ${BLUE}bash install.sh --uninstall${NC}"
echo ""
