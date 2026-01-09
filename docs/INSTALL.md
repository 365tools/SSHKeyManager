# SSH Manager 安装脚本使用说明

## 快速安装

### Windows

**一键安装（推荐）**
```powershell
# 方式 1: 直接在线安装（推荐）
irm https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.ps1 | iex

# 方式 2: 下载后安装
Invoke-WebRequest -Uri https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**⚠️ 执行策略问题**

如果遇到 "禁止运行脚本" 错误：
```powershell
# 临时允许（仅当前会话）
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
powershell -File .\scripts\install.ps1

# 或者使用 -ExecutionPolicy 参数
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

**自定义安装**
```powershell
# 指定版本安装
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Version v2.1.0

# 指定版本安装
powershell -ExecutionPolicy Bypass -File install.ps1 -Version v2.1.0

# 指定安装目录
powershell -ExecutionPolicy Bypass -File .\install.ps1 -InstallDir "C:\Tools\sshm"

# 不添加到 PATH
powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoAddPath
```

### Linux / macOS

**一键安装（推荐）**
```bash
curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash
```

**自定义安装**
```bash
# 下载安装脚本
curl -O https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh
chmod +x install.sh

# 默认安装
./install.sh

# 指定版本安装
./install.sh --version v2.1.0

# 指定安装目录
./install.sh --install-dir ~/.local/bin

# 卸载
./install.sh --uninstall
```

## 功能特性

### ✅ 自动化
- ✅ 自动下载最新版本（或指定版本）
- ✅ 自动重命名为 `sshm.exe` / `sshm`
- ✅ 自动创建安装目录
- ✅ 显示下载进度

### ✅ 交互式
- ✅ 安装前确认
- ✅ 询问是否添加到 PATH
- ✅ 安装后验证

### ✅ 灵活性
- ✅ 支持指定版本
- ✅ 支持自定义安装目录
- ✅ 支持静默安装
- ✅ 支持卸载

### ✅ 安全性
- ✅ 使用 HTTPS 下载
- ✅ 安装前显示详细信息
- ✅ 安装后验证文件完整性

## 安装后验证

```bash
# 检查版本
sshm --version

# 查看帮助
sshm --help

# 列出密钥
sshm list
```

## 卸载

### Windows

**方式 1: 使用安装脚本**
```powershell
# 如果有安装脚本
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall

# 或下载卸载脚本
irm https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.ps1 | iex -Uninstall
```

**方式 2: 手动卸载（推荐）**
```powershell
# 1. 找到安装位置
where sshm
# 或
Get-Command sshm | Select-Object -ExpandProperty Source

# 2. 删除文件
Remove-Item "$env:LOCALAPPDATA\Programs\sshm\sshm.exe" -Force

# 3. 从 PATH 中移除（打开系统环境变量设置）
# Win + R → sysdm.cpl → 高级 → 环境变量
# 编辑用户变量 PATH，删除 sshm 所在目录

# 或使用 PowerShell 移除
$path = [Environment]::GetEnvironmentVariable("Path", "User")
$newPath = ($path -split ';' | Where-Object { $_ -notlike '*sshm*' }) -join ';'
[Environment]::SetEnvironmentVariable("Path", $newPath, "User")
```

### Linux / macOS

**方式 1: 使用安装脚本**
```bash
bash install.sh --uninstall
```

**方式 2: 手动卸载**
```bash
# 找到安装位置
which sshm

# 删除文件
sudo rm /usr/local/bin/sshm

# 如果保留了平台标识文件也一并删除
sudo rm /usr/local/bin/sshm-*
```

## 常见问题

### Windows

**Q: 提示 "无法运行脚本"**
```powershell
# 临时允许脚本执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

**Q: 添加到 PATH 后仍无法使用 sshm 命令**
- 需要重启终端或打开新的 PowerShell 窗口
- 或手动刷新环境变量：`$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`

### Linux / macOS

**Q: 提示 "Permission denied"**
- 脚本需要安装到系统目录（`/usr/local/bin`）需要 sudo 权限
- 或安装到用户目录：`./install.sh --install-dir ~/.local/bin`

**Q: 安装后提示 "command not found"**
- 检查 `$PATH` 是否包含安装目录：`echo $PATH`
- 手动添加：`export PATH="$PATH:/usr/local/bin"`（添加到 `~/.bashrc` 或 `~/.zshrc`）

## 高级用法

### 企业内网环境

如果无法访问 GitHub：

1. 手动下载可执行文件
2. 将安装脚本中的 `DOWNLOAD_URL` 替换为内网地址
3. 运行修改后的安装脚本

### CI/CD 集成

```yaml
# GitHub Actions 示例
- name: Install sshm
  run: |
    curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash
    sshm --version
```

```groovy
// Jenkins Pipeline 示例
stage('Install sshm') {
    steps {
        sh 'curl -fsSL https://raw.githubusercontent.com/365tools/SSHKeyManager/main/scripts/install.sh | bash'
        sh 'sshm --version'
    }
}
```

## 脚本参数说明

### install.ps1 (Windows)

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `-Version` | String | 指定版本 | `-Version v2.1.0` |
| `-InstallDir` | String | 安装目录 | `-InstallDir "C:\Tools"` |
| `-NoAddPath` | Switch | 不添加到 PATH | `-NoAddPath` |
| `-Uninstall` | Switch | 卸载 | `-Uninstall` |

### install.sh (Linux/macOS)

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `--version` | String | 指定版本 | `--version v2.1.0` |
| `--install-dir` | String | 安装目录 | `--install-dir ~/.local/bin` |
| `--no-add-path` | Flag | 不添加到 PATH | `--no-add-path` |
| `--uninstall` | Flag | 卸载 | `--uninstall` |
