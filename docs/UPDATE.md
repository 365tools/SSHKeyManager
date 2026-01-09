# 自动更新功能说明

## 功能概述

SSH Manager 现已支持自动检查更新和一键更新功能。

## 功能特性

### ✅ 已实现

1. **静默版本检查**
   - 每次运行命令时自动检查更新
   - 24小时缓存，避免频繁请求
   - 发现新版本时在命令执行前提示
   - 不干扰正常使用

2. **手动更新命令**
   - `sshm update` - 检查并更新到最新版本
   - `sshm update --check` - 仅检查更新，不执行更新
   - `sshm update --force` - 强制检查，忽略缓存

3. **版本比较**
   - 自动解析语义化版本号
   - 准确判断版本新旧

4. **自动下载**
   - 显示下载进度
   - 支持断点续传

5. **跨平台支持**
   - Windows: 自动批处理脚本替换
   - Linux/macOS: 直接替换或提示 sudo

## 使用方法

### 1. 查看当前版本

```bash
sshm --version
# 或
sshm list  # 标题行显示版本
```

### 2. 检查更新

```bash
# 仅检查是否有新版本
sshm update --check

# 强制检查（忽略缓存）
sshm update --check --force
```

### 3. 更新到最新版本

```bash
sshm update
```

执行流程：
1. 检查是否有新版本
2. 显示更新内容
3. 询问确认
4. 下载新版本
5. 自动替换可执行文件

### 4. 静默检查（自动）

每次运行任何命令时，程序会自动检查更新：

```bash
sshm list

# 如果有新版本，会在输出前显示提示：
# 💡 有新版本可用: v2.2.0 (当前: v2.1.0)
#    运行 'sshm update' 更新到最新版本
```

## 示例输出

### 检查更新（无更新）

```
$ sshm update --check
================================================================================
检查更新
================================================================================

当前版本: v2.1.0
平台: windows

正在检查更新...
✅ 已是最新版本！
```

### 检查更新（有更新）

```
$ sshm update --check
================================================================================
检查更新
================================================================================

当前版本: v2.1.0
平台: windows

正在检查更新...

🎉 发现新版本: v2.2.0
发布时间: 2026-01-10T12:00:00Z

更新内容:
  ## SSH Key Manager v2.2.0
  
  ### 新功能
  - 添加自动更新功能
  - 优化版本检查机制
  
  ### Bug 修复
  - 修复 Windows 路径问题

💡 运行 'sshm update' 更新到最新版本
```

### 执行更新

```
$ sshm update
================================================================================
检查更新
================================================================================

当前版本: v2.1.0
平台: windows

正在检查更新...

🎉 发现新版本: v2.2.0
发布时间: 2026-01-10T12:00:00Z

更新内容:
  [...]

是否更新到 v2.2.0? [Y/n] y

⬇️  正在下载...
  下载进度: 100.0%
📝 正在更新...

✅ 更新脚本已启动
程序将自动退出，更新完成后请重新运行 sshm
```

## 技术实现

### 版本检查

- 使用 GitHub API 获取最新 release 信息
- 缓存结果 24 小时，减少 API 请求
- 缓存文件: `~/.sshm_update_cache`

### 版本比较

```python
# 语义化版本比较
v2.2.0 > v2.1.0  # True
v2.1.1 > v2.1.0  # True
v3.0.0 > v2.9.9  # True
```

### 更新机制

**Windows**:
1. 下载新版本到临时文件
2. 创建批处理脚本延迟替换
3. 启动批处理脚本
4. 程序退出
5. 批处理脚本等待 2 秒后替换文件

**Linux/macOS**:
1. 下载新版本到临时文件
2. 尝试直接替换当前可执行文件
3. 如果需要权限，提示用户手动执行 `sudo mv` 命令

## 配置选项

### 禁用自动检查

如果不想要启动时的版本检查提示，可以：

```bash
# 方式 1: 设置环境变量
export SSHM_NO_UPDATE_CHECK=1

# 方式 2: 删除缓存文件
rm ~/.sshm_update_cache
```

### 修改缓存时间

默认缓存 24 小时，可以通过修改源码调整：

```python
# src/sshm/utils/updater.py
CACHE_VALID_HOURS = 24  # 改为其他值
```

## 安全考虑

1. **HTTPS 下载**
   - 所有下载均通过 HTTPS
   - 验证 GitHub 官方域名

2. **文件完整性**
   - 从官方 GitHub Release 下载
   - 建议未来添加 SHA256 校验

3. **权限管理**
   - Linux/macOS 需要写入权限
   - Windows 使用批处理脚本安全替换

## 故障排查

### 问题：提示网络错误

**原因**: 无法连接 GitHub API

**解决**:
```bash
# 1. 检查网络连接
ping api.github.com

# 2. 使用代理
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

# 3. 手动下载
# 访问 https://github.com/365tools/SSHKeyManager/releases
# 手动下载对应平台的文件
```

### 问题：更新后无法运行

**Windows**:
```cmd
# 检查文件是否被替换
where sshm

# 检查文件大小
dir C:\path\to\sshm.exe
```

**Linux/macOS**:
```bash
# 检查文件权限
ls -l /usr/local/bin/sshm

# 重新赋予执行权限
chmod +x /usr/local/bin/sshm
```

### 问题：Linux/macOS 提示权限不足

**解决**:
```bash
# 使用 sudo 手动移动文件
sudo mv /tmp/sshm-xxx /usr/local/bin/sshm
sudo chmod +x /usr/local/bin/sshm
```

## 最佳实践

1. **定期更新**
   - 每周运行一次 `sshm update --check`
   - 关注新版本的功能和修复

2. **更新前备份**
   - 虽然程序会自动备份 SSH 密钥
   - 但建议在重大版本更新前手动备份配置

3. **测试新版本**
   - 更新后运行 `sshm list` 验证功能
   - 测试关键命令如 `sshm switch`

4. **关注 Release Notes**
   - 查看每个版本的更新内容
   - 了解新功能和潜在的破坏性变更

## 未来计划

- [ ] 添加 SHA256 文件完整性校验
- [ ] 支持回滚到旧版本
- [ ] 支持 beta/stable 通道选择
- [ ] 添加更新日志查看命令
- [ ] 支持离线更新包

## 相关命令

```bash
# 查看版本
sshm --version

# 查看帮助
sshm update --help

# 检查更新
sshm update --check

# 强制检查
sshm update --force

# 执行更新
sshm update
```

## 技术细节

### API 端点

```
GET https://api.github.com/repos/365tools/SSHKeyManager/releases/latest
```

### 响应格式

```json
{
  "tag_name": "v2.2.0",
  "published_at": "2026-01-10T12:00:00Z",
  "body": "Release notes...",
  "assets": [
    {
      "name": "sshm-windows-amd64.exe",
      "browser_download_url": "https://github.com/.../sshm-windows-amd64.exe",
      "size": 7428855
    }
  ]
}
```

### 文件路径

- 缓存文件: `~/.sshm_update_cache`
- Windows 更新脚本: `%TEMP%\sshm_update.bat`
- 下载临时文件: `tempfile.mkstemp()`
