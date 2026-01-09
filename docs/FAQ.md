# ❓ 常见问题 (FAQ)

## 使用问题

### Q: 为什么推荐使用别名而不是切换默认密钥？

**A:** 别名方式的优势：

- ✅ 多账号可以同时使用，无需频繁切换
- ✅ 项目配置一次，永久生效
- ✅ 不会因为忘记切换而推送到错误账号
- ✅ 团队成员可以使用不同的密钥

**示例**：
```bash
# 个人项目
cd ~/personal-project
git remote set-url origin git@personal:user/repo.git
git push  # 自动使用 personal 密钥

# 公司项目
cd ~/work-project
git remote set-url origin git@company:org/repo.git
git push  # 自动使用 company 密钥
```

---

### Q: 如何将现有项目改用别名方式？

**A:** 只需修改 remote URL：

```bash
# 1. 查看当前 URL
git remote -v
# origin  git@github.com:user/repo.git (fetch)

# 2. 修改为别名（将 github.com 改为 <别名>）
git remote set-url origin git@github-personal:user/repo.git

# 3. 验证
git remote -v
# origin  git@github-personal:user/repo.git (fetch)

# 4. 测试连接
ssh -T git@github-personal
```

---

### Q: 密钥类型如何选择？

**A:** 推荐优先级：

| 密钥类型 | 安全性 | 性能 | 兼容性 | 推荐 |
|----------|--------|------|--------|------|
| **ed25519** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 默认推荐 |
| **rsa 4096** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 兼容旧系统 |
| ecdsa | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⚠️ 不推荐 |
| dsa | ⭐⭐ | ⭐⭐ | ⭐⭐ | ❌ 已弃用 |

**建议**：
- 新项目：优先使用 `ed25519`（默认）
- 旧系统：使用 `rsa -b 4096`
- 避免使用：`ecdsa`、`dsa`

---

### Q: 误删除密钥怎么办？

**A:** 所有操作都有自动备份，可以轻松恢复：

```bash
# 1️⃣ 查看备份列表
sshm backups

# 输出示例：
# 📦 备份列表
# ├─ keys_20260109_120000 (3 files)
# ├─ keys_20260108_150000 (2 files)
# └─ keys_20260107_100000 (2 files)

# 2️⃣ 找到备份位置
# Windows: C:\Users\<用户>\.ssh\key_backups\
# Linux/Mac: ~/.ssh/key_backups/

# 3️⃣ 手动恢复
cd ~/.ssh/key_backups/keys_20260109_120000/
cp id_rsa.github-personal* ~/.ssh/
```

**预防措施**：
- 定期手动备份：`sshm back`
- 重要操作前备份：`sshm back` → 执行操作
- 将备份目录加入云同步（OneDrive、Dropbox 等）

---

### Q: 为什么切换后看不到效果？

**A:** 可能的原因和解决方法：

**原因 1：使用了别名方式**
```bash
# 检查 remote URL
git remote -v

# 如果是：git@github-personal:user/repo.git
# 说明使用的是别名，不受切换影响（这是正常的！）
```

**原因 2：项目使用的别名与切换的密钥不一致**
```bash
# 查看当前状态
sshm list

# 如果项目 URL 是 git@company:...
# 但你切换的是 personal 密钥
# 那么项目仍然使用 company 密钥
```

**原因 3：SSH 配置缓存**
```bash
# 清理 SSH 连接缓存
ssh-add -D  # 清除所有密钥
ssh-add ~/.ssh/id_rsa  # 重新加载当前密钥

# 测试连接
ssh -T git@github.com
```

---

### Q: 如何同时使用多个平台（GitHub、GitLab、Gitee）？

**A:** 为每个平台创建独立密钥：

```bash
# 1️⃣ 创建密钥
sshm add github me@example.com -H github.com
sshm add gitlab me@example.com -H gitlab.com
sshm add gitee me@example.com -H gitee.com

# 2️⃣ 查看生成的别名
sshm list

# 3️⃣ 复制公钥到各平台
sshm list -a  # 显示所有公钥

# 4️⃣ 克隆时使用别名
git clone git@github:user/repo.git
git clone git@gitlab:user/repo.git
git clone git@gitee:user/repo.git
```

**自动配置的 SSH config**：
```ssh-config
Host github
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa.github

Host gitlab
    HostName gitlab.com
    User git
    IdentityFile ~/.ssh/id_rsa.gitlab

Host gitee
    HostName gitee.com
    User git
    IdentityFile ~/.ssh/id_rsa.gitee
```

---

## 安装问题

### Q: Windows 提示"禁止运行脚本"

**A:** PowerShell 执行策略限制，三种解决方法：

**方法 1：使用 -ExecutionPolicy 参数（推荐）**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

**方法 2：临时修改策略（仅当前会话）**
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\scripts\install.ps1
```

**方法 3：用户级别永久允许（谨慎使用）**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### Q: 如何添加到 PATH 环境变量？

**A:** 安装脚本会自动配置，如果需要手动配置：

**Windows**：
```powershell
# PowerShell（管理员）
$installDir = "$env:LOCALAPPDATA\Programs\sshm"
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";$installDir",
    "User"
)

# 重启终端验证
sshm --version
```

**Linux/macOS**：
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
echo 'export PATH="$PATH:/usr/local/bin"' >> ~/.bashrc
source ~/.bashrc

# 验证
sshm --version
```

---

### Q: Linux/macOS 提示 "Permission denied"

**A:** 没有写入权限，两种解决方法：

**方法 1：使用 sudo 安装到系统目录**
```bash
sudo bash scripts/install.sh
```

**方法 2：安装到用户目录（无需 sudo）**
```bash
bash scripts/install.sh --install-dir ~/.local/bin

# 添加到 PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

### Q: 安装后找不到 sshm 命令

**A:** PATH 未刷新或未添加，按以下步骤排查：

**1. 检查安装位置**
```bash
# Windows
where sshm
Get-Command sshm

# Linux/macOS
which sshm
```

**2. 如果找不到，手动刷新 PATH**
```powershell
# Windows PowerShell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

```bash
# Linux/macOS
source ~/.bashrc  # 或 ~/.zshrc
```

**3. 如果还是找不到，重启终端**

**4. 最后手段：完整路径运行**
```bash
# Windows
C:\Users\<用户>\AppData\Local\Programs\sshm\sshm.exe list

# Linux/macOS
/usr/local/bin/sshm list
```

---

## 高级问题

### Q: 如何备份到云存储？

**A:** 将备份目录链接到云同步文件夹：

**Windows (OneDrive)**：
```powershell
# 1. 创建云同步目录
$cloudDir = "$env:OneDrive\SSH_Backups"
New-Item -ItemType Directory -Force -Path $cloudDir

# 2. 移动现有备份
Move-Item "$env:USERPROFILE\.ssh\key_backups" $cloudDir

# 3. 创建符号链接
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.ssh\key_backups" -Target $cloudDir
```

**Linux/macOS (Dropbox)**：
```bash
# 1. 创建云同步目录
mkdir -p ~/Dropbox/SSH_Backups

# 2. 移动现有备份
mv ~/.ssh/key_backups/* ~/Dropbox/SSH_Backups/

# 3. 创建符号链接
ln -s ~/Dropbox/SSH_Backups ~/.ssh/key_backups
```

---

### Q: 如何迁移到新电脑？

**A:** 三步快速迁移：

```bash
# 旧电脑：打包备份
cd ~/.ssh
tar -czf ssh_backup.tar.gz key_backups/ config id_rsa.* *.pub

# 传输到新电脑（U盘、网盘等）

# 新电脑：解压恢复
cd ~/.ssh
tar -xzf ssh_backup.tar.gz

# 设置权限（重要！）
chmod 600 id_rsa*
chmod 644 *.pub
chmod 644 config

# 验证
sshm list
ssh -T git@github.com
```

---

### Q: 如何在多台电脑间同步密钥？

**⚠️ 安全警告**：不推荐同步私钥到多台设备！

**推荐方案：每台设备独立密钥**
```bash
# 设备 A
sshm add github-laptop me@example.com

# 设备 B  
sshm add github-desktop me@example.com

# 将两个公钥都添加到 GitHub
# Settings → SSH Keys → Add SSH Key
```

**为什么不推荐同步私钥？**
- 🔐 私钥泄露风险增加
- 🚨 一台设备被盗，所有设备都不安全
- ✅ 使用独立密钥，被盗只需删除对应公钥

---

### Q: 企业环境使用注意事项

**A:** 企业使用建议：

**1. 权限管理**
```bash
# 确保密钥目录权限正确
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_rsa*
chmod 644 ~/.ssh/*.pub
chmod 644 ~/.ssh/config
```

**2. 密钥命名规范**
```bash
# 建议格式：<平台>-<公司>-<项目>
sshm add github-company-projectA user@company.com
sshm add gitlab-company-backend user@company.com
```

**3. 定期轮换密钥**
```bash
# 每季度更新一次
sshm back  # 备份旧密钥
sshm add github-company-new user@company.com  # 生成新密钥
# 在平台上替换公钥
sshm remove github-company-old  # 删除旧密钥
```

**4. 离职清理**
```bash
# 离职前从所有平台删除公钥
# 然后删除本地密钥
sshm remove github-company
sshm remove gitlab-company
```

---

### Q: 如何处理密钥冲突？

**A:** 如果出现"Host key verification failed"：

```bash
# 1. 清除旧的 known_hosts
ssh-keygen -R github.com

# 2. 重新连接
ssh -T git@github.com

# 3. 输入 yes 接受新指纹
```

如果出现"Permission denied (publickey)"：

```bash
# 1. 检查密钥是否存在
sshm list

# 2. 检查 SSH config
cat ~/.ssh/config

# 3. 测试连接（显示详细信息）
ssh -vT git@github.com

# 4. 确认公钥已添加到平台
sshm list -a  # 查看公钥内容
```

---

## 故障排查

### Q: 如何启用调试模式？

**A:** 使用 SSH 的 verbose 模式：

```bash
# 单个 v：基本调试信息
ssh -vT git@github.com

# 三个 v：详细调试信息
ssh -vvvT git@github.com
```

**常见错误信息**：
- `No such identity`: 密钥文件不存在
- `Permission denied`: 公钥未添加到平台或权限错误
- `Host key verification failed`: known_hosts 冲突

---

### Q: 如何验证配置是否正确？

**A:** 完整验证流程：

```bash
# 1️⃣ 检查密钥列表
sshm list
# 确认密钥存在且状态正确

# 2️⃣ 检查 SSH config
cat ~/.ssh/config
# 确认 Host 配置正确

# 3️⃣ 检查文件权限
ls -la ~/.ssh/
# 私钥应该是 600，公钥 644

# 4️⃣ 测试 SSH 连接
ssh -T git@github.com
# 应该显示：Hi <username>! You've successfully authenticated

# 5️⃣ 测试别名连接
ssh -T git@github-personal
# 应该显示相同的欢迎信息

# 6️⃣ 测试 Git 操作
git ls-remote git@github.com:user/repo.git
# 应该显示仓库的 refs
```

---

## 更多帮助

### 📚 文档导航

- [README.md](../README.md) - 项目主文档
- [INSTALL.md](INSTALL.md) - 详细安装文档
- [USAGE.md](USAGE.md) - 详细使用指南
- [UPDATE.md](UPDATE.md) - 更新功能文档
- [DEVELOPER.md](DEVELOPER.md) - 开发者文档

### 🆘 获取支持

- **GitHub Issues**: [报告问题](https://github.com/365tools/SSHKeyManager/issues)
- **Discussions**: [讨论和提问](https://github.com/365tools/SSHKeyManager/discussions)
- **命令帮助**: `sshm --help` 或 `sshm <command> --help`

### 💡 贡献 FAQ

发现文档中没有你的问题？欢迎贡献：

1. Fork 本仓库
2. 编辑 `docs/FAQ.md`
3. 提交 Pull Request

或者直接在 [Issues](https://github.com/365tools/SSHKeyManager/issues) 提问，我们会将常见问题添加到这里。

---

<div align="center">

**找到答案了吗？别忘了给项目一个 ⭐️ Star！**

</div>
