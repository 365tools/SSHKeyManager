#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国际化 (i18n) 模块 - 支持中英双语输出

设计:
- 默认语言为英文 (en)，可切换为中文 (zh)
- 语言优先级: SSHM_LANG 环境变量 > 状态文件 lang 字段 > 默认 en
- 源字符串使用英文作为 key（也即英文显示文本），中文通过翻译表映射
- 支持 {placeholder} 占位符格式化
"""

import os
from typing import Dict

# --------------------------------------------------------------------------
# 当前语言（运行时可变）
# --------------------------------------------------------------------------
_current_lang: str = 'en'


def set_lang(lang: str):
    """设置当前语言（en/zh），非法值回退 en"""
    global _current_lang
    _current_lang = lang if lang == 'zh' else 'en'


def get_lang() -> str:
    """获取当前语言"""
    return _current_lang


# --------------------------------------------------------------------------
# 语言解析
# --------------------------------------------------------------------------

def resolve_lang(env: str = None, state_lang: str = None) -> str:
    """解析最终语言: env > state > 'en'

    Args:
        env: SSHM_LANG 环境变量值
        state_lang: 状态文件中保存的 lang 字段
    """
    if env:
        e = env.strip().lower()
        if e in ('zh', 'zh-cn', 'zh_cn', 'cn', 'zh-hans', 'zh_hans'):
            return 'zh'
        if e in ('en', 'en-us', 'en_us', 'us'):
            return 'en'
    if state_lang:
        s = state_lang.strip().lower()
        if s in ('zh', 'zh-cn', 'zh_cn', 'cn', 'zh-hans', 'zh_hans'):
            return 'zh'
        if s in ('en', 'en-us', 'en_us', 'us'):
            return 'en'
    return 'en'


def load_from_state(state_lang: str):
    """从状态文件加载语言并应用（环境变量优先）"""
    env = os.environ.get('SSHM_LANG')
    set_lang(resolve_lang(env, state_lang))


# --------------------------------------------------------------------------
# 翻译表: 英文 -> 中文
# --------------------------------------------------------------------------
ZH: Dict[str, str] = {
    # ---- 通用 ----
    "error": "错误",
    "not a git repo": "不是 Git 仓库",
    "operation cancelled": "操作已取消",
    "not set": "未设置",
    "global": "全局",
    "repo-level": "仓库级",
    "system-level": "系统级",
    "Scope": "作用域",

    # ---- use (connection test) ----
    "SSH connection test failed": "SSH 连接测试失败",
    "The public key may not have been added to the platform yet.": "公钥可能尚未添加到该平台",
    "SSH test failed, still update the remote URL?": "SSH 测试失败，仍要更新 remote URL？",

    # ---- alias (config helpers) ----
    "SSH config alias: {alias} -> {hostname}": "SSH 配置别名: {alias} -> {hostname}",
    "   usage: git@{alias}:user/repo.git": "使用方式: git@{alias}:user/repo.git",
    "SSH config alias removed: {alias}": "已删除 SSH 配置别名: {alias}",
    "SSH config alias updated: {old} -> {new}": "SSH 配置别名已更新: {old} -> {new}",
    "Create failed: {err}": "创建失败: {err}",

    # ---- system (PATH) ----
    "Add to PATH": "添加到环境变量（PATH）",
    "Current executable: {path}": "当前可执行文件位置: {path}",
    "Directory: {dir}": "目录路径: {dir}",
    "Path already in environment variable: {path}": "路径已在环境变量中: {path}",
    "Current path: {path}": "当前路径: {path}",
    "Existing path: {path}": "已有路径: {path}",
    "Update to the current path?": "是否更新为当前路径？",
    "Environment variable updated!": "环境变量已更新！",
    "Tip: restart your terminal for the change to take effect": "提示: 请重启命令行窗口使环境变量生效",
    "Then you can use the 'sshm' command directly": "然后可以直接使用 'sshm' 命令",
    "Added to environment variable!": "已添加到环境变量！",
    "Permission denied, please run as administrator": "权限不足，请以管理员身份运行",
    "Failed to add: {err}": "添加失败: {err}",
    "Path already in {name}": "路径已在 {name} 中",
    "Will add to: {path}": "将添加到: {path}",
    "Command: {cmd}": "命令: {cmd}",
    "Continue?": "是否继续？",
    "Added to config file!": "已添加到配置文件！",
    "Run the following to apply:": "执行以下命令使环境变量生效：",
    "or restart your terminal": "或重启终端",

    # ---- list ----
    "sshm - Key List": "sshm - 密钥列表",
    "SSH directory:": "SSH 目录:",
    "No key files found": "未找到任何密钥文件",
    "Tip: use 'sshm add <label> <email>' to create a new key": "提示: 使用 'sshm add <标签> <邮箱>' 创建新密钥",
    "Label": "标签",
    "File": "文件",
    "Public": "公钥",
    "Size": "大小",
    "Modified": "修改时间",
    "Alias": "别名",
    "Status": "状态",
    "in use": "当前使用",
    "default": "默认",
    "Public Key Contents": "公钥内容",
    "Tip: use 'use <label> --global' to configure the global default key": "提示: 使用 'use <label> --global' 配置全局默认密钥",

    # ---- backups ----
    "Backup List": "备份列表",
    "No backups yet": "暂无备份",
    "Time:": "时间:",
    "Files:": "文件数:",
    "Path:": "路径:",

    # ---- backup ----
    "Backup complete:": "备份完成:",
    "files backed up": "已备份 {count} 个文件",

    # ---- restore ----
    "Restore Keys from Backup": "从备份恢复密钥",
    "Backup not found:": "未找到备份:",
    "Use 'sshm backups' to view available backups": "使用 'sshm backups' 查看可用备份",
    "No backups to restore": "暂无备份可恢复",
    "Use 'sshm backup' to create a backup": "使用 'sshm backup' 创建备份",
    "Will use latest backup:": "将使用最新备份:",
    "No recoverable key files in backup": "备份中没有可恢复的密钥文件",
    "Will restore the following {count} file(s):": "将恢复以下 {count} 个文件:",
    "Restore? (existing files will be overwritten)": "是否恢复？（同名文件将被覆盖）",
    "Restore failed:": "恢复失败:",
    "Restored {count} file(s):": "已恢复 {count} 个文件:",
    "Tip: use 'sshm list' to view restored keys": "提示: 使用 'sshm list' 查看恢复后的密钥",
    "Backup contains SSH config; for safety it will NOT overwrite current config": "备份包含 SSH config 文件，为安全起见不会自动覆盖当前配置",
    "Run 'sshm use <label>' to regenerate alias config": "请运行 'sshm use <标签>' 重新生成别名配置",

    # ---- add ----
    "Unsupported key type: {type}, supported: {supported}": "不支持的密钥类型: {type}，支持的类型: {supported}",
    "Invalid email: {email}, please provide a valid email e.g. user@example.com": "邮箱地址无效: {email}，请提供有效邮箱，例如: user@example.com",
    "Key already exists: {name}": "密钥已存在: {name}",
    "Creating new key: {label} ({key_type})": "创建新密钥: {label} ({key_type})",
    "Email:": "邮箱:",
    "Key created successfully: {name}": "密钥创建成功: {name}",
    "SSH config updated: Host {alias} -> {hostname}": "SSH config 已更新: Host {alias} -> {hostname}",
    "Public key content:": "公钥内容:",
    "Add this public key to your Git platform (GitHub/GitLab etc.)": "请将公钥添加到 Git 平台（GitHub/GitLab 等）",
    "Author info recorded: {name} <{email}>": "已记录作者信息: {name} <{email}>",
    "Create failed:": "创建失败:",

    # ---- validate label ----
    "Label cannot be empty": "标签不能为空",
    "Invalid label '{label}': only letters, digits, underscore(_) and hyphen(-) are allowed, and it cannot start with a symbol": "标签 '{label}' 不合法：只能包含字母、数字、下划线(_)、连字符(-)，且不能以符号开头",
    "Label '{label}' is a reserved name and cannot be used": "标签 '{label}' 是保留名称，不可使用",
    "Label '{label}' is a reserved name and cannot be switched to": "标签 '{label}' 是保留名称，不可用于切换",
    "Label \"{label}\" is a reserved name and cannot be switched to": "标签 '{label}' 是保留名称，不可用于切换",
    "Restore from backup": "从备份恢复",
    "Usage: sshm author add <label> -n \"name\" -e \"email\"": "用法: sshm author add <标签> -n \"姓名\" -e \"邮箱\"",
    "re-run 'sshm use {new_label}' in that repo to update remote URL": "请在该仓库重新运行 'sshm use {new_label}' 更新 remote URL",
    "No key found for label '{label}'": "未找到标签 '{label}' 的密钥",
    "No key found for label '{label}' (key files)": "未找到标签 '{label}' 对应的密钥",

    # ---- remove ----
    "About to delete default key ({type}), continue?": "即将删除默认密钥 ({type})，是否继续？",
    "About to delete all default keys, continue?": "即将删除所有默认密钥，是否继续？",
    "Auto-backed up to: {path}": "已自动备份到: {path}",
    "Deleted {count} file(s):": "已删除 {count} 个文件:",
    "Tip: if any repo uses alias {alias} in its remote URL,": "提示: 若已有仓库使用别名 {alias} 配置了 remote URL，",
    "re-run 'sshm use <other-label>' in that repo to update config": "请在该仓库重新运行 'sshm use <其他标签>' 更新配置",
    "Key not found: {label}": "未找到密钥: {label}",

    # ---- switch ----
    "Auto-detected key type: {key_type}": "自动检测到密钥类型: {key_type}",
    "Key does not exist: {name}": "密钥不存在: {name}",
    "Original key backed up as: {name}": "原始密钥已备份为: {name}",
    "Switched to key: {label} ({key_type})": "已切换到密钥: {label} ({key_type})",
    "File:": "文件:",

    # ---- tag ----
    "No default key found": "未找到默认密钥",
    "Default key does not exist: {name}": "默认密钥不存在: {name}",
    "Label already exists: {new_label}": "标签已存在: {new_label}",
    "Overwrite?": "是否覆盖？",
    "Tag added: {new_label} ({key_type})": "已添加标签: {new_label} ({key_type})",

    # ---- rename ----
    "Cannot rename the 'default' label": "不能重命名 default 标签",
    "Old and new labels are the same, no need to rename": "新旧标签相同，无需重命名",
    "Target label already exists: {new_label} ({type})": "目标标签已存在: {new_label} ({type})",
    "File: {name}": "文件: {name}",
    "Renamed: {old} -> {new} ({count} type(s): {types})": "已重命名: {old} -> {new}（{count} 个类型: {types}）",
    "Tip: if any repo uses alias {alias},": "提示: 若已有仓库使用别名 {alias}，",
    "re-run 'sshm use {new_label}' in that repo to update remote URL": "请在该仓库重新运行 'sshm use {new_label}' 更新 remote URL",

    # ---- use ----
    "Not a git repository: {path}": "不是 Git 仓库: {path}",
    "Please run this command inside a Git repository": "请在 Git 仓库目录下执行此命令",
    "Configure Key for Git Repo: {label}": "为 Git 仓库配置密钥: {label}",
    "Repo path:": "仓库路径:",
    "Current Remote URL:": "当前 Remote URL:",
    "Failed to parse Git URL": "无法解析 Git URL",
    "Parsed info:": "解析信息:",
    "Platform:": "平台:",
    "User/Org:": "用户/组织:",
    "Repo:": "仓库:",
    "New Remote URL:": "新的 Remote URL:",
    "Update Remote URL?": "是否更新 Remote URL？",
    "Remote URL updated": "Remote URL 已更新",
    "Testing SSH connection...": "测试 SSH 连接...",
    "SSH connection test passed!": "SSH 连接测试成功！",
    "SSH connection test:": "SSH 连接测试:",
    "Configuration complete! Now you can use:": "配置完成！现在可以使用以下命令:",
    "No 'origin' remote found": "未找到 origin remote",
    "Please add a remote first: git remote add origin <url>": "请先添加 remote: git remote add origin <url>",
    "Git command failed: {err}": "Git 命令执行失败: {err}",
    "SSH connection test timed out": "SSH 连接测试超时",

    # ---- author ----
    "Git Repo Author Info": "Git 仓库作者信息",
    "Author name:": "作者姓名:",
    "Author email:": "作者邮箱:",
    "Global author:": "全局作者:",
    "Current effective: repo-level (local) config overrides global": "当前生效: 仓库级 (local) 配置优先于全局",
    "Tip: use 'sshm author list' to view saved authors": "提示: 使用 'sshm author list' 查看已保存的作者",
    "Use 'sshm author use <label>' to quickly set the current repo author": "使用 'sshm author use <标签>' 快速设置当前仓库作者",
    "Use 'sshm author unset' to clear repo-level config": "使用 'sshm author unset' 清除仓库级配置",
    "Set Author for Git Repo: {label}": "为 Git 仓库设置作者: {label}",
    "(no new value, keeping current)": "（未提供新值，保持现状）",
    "Current {scope} author configured:": "当前{scope}已配置作者:",
    "Overwrite?": "覆盖？",
    "No author info available to set": "没有可设置的作者信息",
    "Set ({scope}):": "已设置（{scope}）:",
    "Unchanged (keeping current):": "未修改项（保持现状）:",
    "Verify: git config user.name && git config user.email": "验证: git config user.name && git config user.email",
    "Confirm clearing current {scope} author config? It will fall back to {fallback} config": "确定清除当前{scope}的作者配置吗？将回落到{fallback}配置",
    "Cleared ({scope}): {keys}": "已清除（{scope}）: {keys}",
    "No config found to clear": "未找到需要清除的配置",
    "Need at least a name or email": "需要提供姓名或邮箱至少一项",
    "Usage: sshm author add <label> -n \"name\" -e \"email\"": "用法: sshm author add <标签> -n \"姓名\" -e \"邮箱\"",
    "Tip: if a key with this label exists, email is auto-filled from the public key comment": "提示: 若已存在该标签的密钥，邮箱会自动从公钥注释补全",
    "Author saved: {label}": "已保存作者: {label}",
    "Name:": "姓名:",
    "Email:": "邮箱:",
    "Saved to author list": "已保存到作者列表",
    "Use 'sshm author list' to view all authors": "使用 'sshm author list' 查看所有作者",
    "Use 'sshm author use <label>' to apply to the current repo": "使用 'sshm author use <标签>' 应用到当前仓库",
    "Saved Authors List": "已保存的作者列表",
    "No saved authors yet": "暂无已保存的作者",
    "Use 'sshm author add <label> -n name -e email' to add an author": "使用 'sshm author add <标签> -n 姓名 -e 邮箱' 添加作者",
    "Key": "密钥",
    "Usage:": "用法:",
    "Apply to current repo/global": "应用到当前仓库/全局",
    "Remove author": "移除作者",
    "Add/update author": "添加/更新作者",
    "Saved author not found: {label}": "未找到已保存的作者: {label}",
    "Use 'sshm author list' to view saved authors": "使用 'sshm author list' 查看已保存的作者",
    "About to remove author: {label}": "即将移除作者: {label}",
    "Confirm remove?": "确定移除？",
    "Author removed: {label}": "已移除作者: {label}",
    "Note: already-applied git config will NOT be rolled back": "注意: 已应用到仓库的 git config 不会被回滚",
    "No key found for label '{label}'": "未找到标签 '{label}' 的密钥",
    "Use 'sshm list' to view all available keys": "使用 'sshm list' 查看所有可用密钥",
    "No key is configured for the current repo": "当前仓库未配置任何密钥",
    "Use 'sshm use <label>' to configure a key for this repo": "使用 'sshm use <label>' 为本仓库配置密钥",
    "Or run 'sshm list' to view all keys": "或运行 'sshm list' 查看所有密钥",
    "The repo hostname ({host}) differs from the one mapped to label '{label}' ({cur})": "仓库主机名 ({host}) 与标签 '{label}' 映射的 ({cur}) 不一致",
    "This is likely a private/self-hosted Git server.": "这很可能是私有化部署的 Git 服务器。",
    "To connect, an SSH config matching '{host}' is needed.": "要连接，需要创建与 '{host}' 匹配的 SSH 配置。",
    "Updated host mapping: {label} -> {host}": "已更新主机映射: {label} -> {host}",
    "Create matching SSH config for '{host}' and use it?": "创建与 '{host}' 匹配的 SSH 配置并使用？",
    "Skipped. The key may not work for this repo without a matching host mapping.": "已跳过。没有匹配的主机映射，该密钥在此仓库可能无法使用。",
    "Label '{label}' has no usable author info": "标签 '{label}' 没有可用的作者信息",
    "Available remedies:": "可用的补救方式:",
    "recreate key and record author": "重建密钥并记录作者",
    "temporary override": "临时指定",

    # ---- info ----
    "Git Repo Config Info": "Git 仓库配置信息",
    "Not a valid Git repository: {path}": "不是有效的 Git 仓库: {path}",
    "Remote URL:": "Remote URL:",
    "Current alias in use: {alias}": "当前使用别名: {alias}",
    "Key info:": "密钥信息:",
    "Private key:": "私钥:",
    "Public key:": "公钥:",
    "SSH Config:": "SSH Config:",
    "No key file found for label '{label}'": "未找到标签 '{label}' 对应的密钥文件",
    "Tip: using a standard SSH URL or unconfigured alias": "提示: 当前使用标准 SSH URL 或未配置的别名",
    "Use 'sshm use <label>' to configure a key": "可以使用 'sshm use <标签>' 配置密钥",
    "Tip: using an HTTPS URL": "提示: 使用的是 HTTPS URL",
    "Use 'sshm use <label>' to convert to SSH and configure a key": "可以使用 'sshm use <标签>' 转换为 SSH 并配置密钥",
    "Failed to parse remote URL": "无法解析 remote URL",
    "No 'origin' remote configured": "未配置 origin remote",

    # ---- test ----
    "Test All SSH Key Connections": "测试所有 SSH 密钥连接",
    "No keys found": "未找到任何密钥",
    "no alias configured, run 'sshm use <label>' first": "未配置别名，请先运行 'sshm use <标签>'",
    "Test Results Summary:": "测试结果汇总:",
    "Test SSH Connection: {label}": "测试 SSH 连接: {label}",
    "Host:": "主机:",
    "Alias {alias} not configured in SSH config": "SSH config 中未配置别名 {alias}",
    "Run 'sshm use {label}' first to create the alias config": "请先运行 'sshm use {label}' 自动创建别名配置",
    "Or run 'sshm use {label} --global' to set as global default before testing": "或运行 'sshm use {label} --global' 设为全局默认后再测试",
    "Testing connection...": "正在测试连接...",
    "Test Current Repo SSH Connection": "测试当前仓库 SSH 连接",
    "Testing {host}...": "正在测试 {host}...",
    "Tip: check that your key config is correct": "提示: 请检查密钥配置是否正确",
    "Use 'sshm info' to view config details": "使用 'sshm info' 查看配置详情",
    "Current URL is not an SSH URL, cannot test connection": "当前使用的不是 SSH URL，无法测试连接",
    "Use 'sshm use <label>' to convert to SSH URL": "使用 'sshm use <label>' 转换为 SSH URL",
    "Authenticated successfully! (Hi {user}!)": "认证成功! (Hi {user}!)",
    "Connected successfully!": "连接成功!",
    "Connection failed: {detail}": "连接失败: {detail}",
    "Connection timed out": "连接超时",
    "ssh command not found": "未找到 ssh 命令",

    # ---- parser / commands ----
    "available commands": "可用命令",
    "view all current SSH keys": "查看当前所有 SSH 密钥",
    "show public key contents": "显示公钥内容",
    "backup all SSH keys to archive": "备份所有 SSH 密钥到归档",
    "list all backup archives": "列出所有备份归档",
    "restore keys from a backup": "从备份恢复密钥",
    "backup name (default: restore latest backup)": "备份名称（默认恢复最新备份）",
    "only restore keys of the specified type": "仅恢复指定类型的密钥",
    "skip confirmation prompts": "跳过确认提示",
    "create a new SSH key": "创建新的 SSH 密钥",
    "key label": "密钥标签",
    "email address": "邮箱地址",
    "key type": "密钥类型",
    "hostname (for SSH config)": "主机名（用于 SSH config）",
    "author name (auto-recorded for sshm author)": "作者姓名（自动记录，供 sshm author 使用）",
    "delete an SSH key": "删除 SSH 密钥",
    "specify key type to delete (default: all types)": "指定删除的密钥类型（默认删除所有类型）",
    "save the current default key as a label": "将当前默认密钥另存为指定标签",
    "new label": "新标签名",
    "key type (default: auto-detect)": "密钥类型（默认自动检测）",
    "switch after tagging": "打标签后立即切换",
    "rename a key label": "重命名密钥标签",
    "old label": "旧标签名",
    "new label name": "新标签名",
    "configure the specified key for a Git repo": "为当前 Git 仓库配置指定密钥",
    "Git repo path (default: current directory)": "Git 仓库路径（默认当前目录）",
    "configure as global default key": "配置为全局默认密钥",
    "skip confirmation and execute directly": "跳过确认直接执行",
    "configure the key and set author at the same time": "配置密钥后同时设置作者（仓库级或全局）",
    "manage/view/set Git repo author": "管理/查看/设置 Git 仓库作者",
    "subcommands: list/add/remove/use/unset": "子命令: list/add/remove/use/unset",
    "list all saved authors": "列出所有已保存的作者",
    "add/update an author to the list": "添加/更新作者到列表",
    "author label": "作者标签",
    "author name": "作者姓名",
    "author email (auto-filled from public key comment if omitted)": "作者邮箱（未提供时自动从公钥注释补全）",
    "remove an author from the list": "从列表移除作者",
    "use author info to set repo/global": "用列表中的作者信息设置仓库/全局",
    "temporarily override author name": "临时覆盖作者姓名",
    "temporarily override author email": "临时覆盖作者邮箱",
    "set as global author config": "设置为全局作者配置",
    "clear author config (fall back to parent)": "清除作者配置（回落上层）",
    "clear global author config": "清除全局作者配置",
    "display Git repo config info": "显示 Git 仓库配置信息",
    "test SSH connection": "测试 SSH 连接",
    "key label (omit to test current repo)": "密钥标签（不指定则测试当前仓库配置）",
    "Git repo path": "Git 仓库路径（默认当前目录）",
    "test all keys": "测试所有密钥",
    "check and update to the latest version": "检查并更新到最新版本",
    "check for updates only, without updating": "仅检查更新，不执行更新",
    "force check, ignore cache": "强制检查，忽略缓存",
    "sshm v{version} - Multi-account Git SSH key management tool": "sshm v{version} - 多账号 Git SSH 密钥管理工具",
    "Examples:": "示例:",

    # ---- update ----
    "Check for Updates": "检查更新",
    "Current version:": "当前版本:",
    "Platform:": "平台:",
    "Checking for updates...": "正在检查更新...",
    "You are up to date!": "已是最新版本！",
    "New version found: {version}": "发现新版本: {version}",
    "Release date:": "发布时间:",
    "Update notes:": "更新内容:",
    "Run 'sshm update' to update to the latest version": "运行 'sshm update' 更新到最新版本",
    "Update to {version}? [Y/n] ": "是否更新到 {version}? [Y/n] ",
    "Update cancelled": "已取消更新",
    "Currently running from source, cannot auto-update": "当前为源码运行模式，无法自动更新",
    "Use 'git pull' to get the latest source, or download from the Releases page": "请使用 'git pull' 获取最新源码，或从 Releases 页面下载",
    "Downloading...": "正在下载...",
    "Download progress: {percent:.1f}%": "下载进度: {percent:.1f}%",
    "Updating...": "正在更新...",
    "Update script started": "更新脚本已启动",
    "The program will exit automatically; run sshm again after the update": "程序将自动退出，更新完成后请重新运行 sshm",
    "Update complete!": "更新完成！",
    "Please run sshm again": "请重新运行 sshm",
    "Administrator privileges required to update": "需要管理员权限更新",
    "Please run manually: sudo mv {src} {dst}": "请手动运行: sudo mv {src} {dst}",
    "Update failed:": "更新失败:",
    "A new version is available: {version} (current: v{current})": "有新版本可用: {version} (当前: v{current})",
    "Run 'sshm update' to update to the latest version": "运行 'sshm update' 更新到最新版本",

    # ---- interactive menu ----
    "sshm - Interactive Menu": "🔑 sshm - 交互式菜单",
    "Welcome to sshm!": "欢迎使用 sshm！",
    "Current version:": "当前版本:",
    "This is a command-line tool. On Windows, using sshm_gui.bat is recommended for a better experience.": "提示: 这是一个命令行工具。在 Windows 上推荐使用 sshm_gui.bat 获得更好的体验。",
    "You can also complete all operations here.": "你也可以直接在此界面完成所有操作。",
    "Please choose an operation:": "请选择操作：",
    "View all keys (list)": "查看所有密钥 (list)",
    "Create new key (add)": "创建新密钥 (add)",
    "Delete key (remove)": "删除密钥 (remove)",
    "Backup all keys (backup)": "备份所有密钥 (backup)",
    "View backup list (backups)": "查看备份列表 (backups)",
    "Restore from backup (restore)": "从备份恢复 (restore)",
    "Save default key as label (tag)": "将默认密钥另存为标签 (tag)",
    "Rename label (rename)": "重命名标签 (rename)",
    "Configure repo key (use)": "配置仓库密钥 (use)",
    "Manage/view author (author)": "管理/查看作者 (author)",
    "View current config (info)": "查看当前配置 (info)",
    "Test connection (test)": "测试连接 (test)",
    "Check for updates (update)": "检查更新 (update)",
    "Add to PATH": "添加到环境变量 (PATH)",
    "View full help": "查看完整帮助",
    "Exit": "退出",
    "Please enter an option: ": "请输入选项: ",
    "Invalid option, please try again": "无效选项，请重新选择",
    "This field cannot be empty, please enter a value": "此处不能为空，请输入",
    "Operation failed:": "操作失败:",
    "view current all SSH keys": "查看当前所有 SSH 密钥",
    "backup all SSH keys": "备份所有 SSH 密钥",
    "list all backups": "列出所有备份",
    "restore keys from backup": "从备份恢复密钥",
    "create a new SSH key (with label)": "创建新的 SSH 密钥（带标签）",
    "delete an SSH key": "删除 SSH 密钥",
    "save the current default key as a label": "将当前默认密钥另存为指定标签",
    "rename key label": "重命名密钥标签",
    "configure a key for a Git repo": "为 Git 仓库配置指定密钥",
    "manage/view/set Git repo author": "管理/查看/设置 Git 仓库作者",
    "display Git repo config info": "显示 Git 仓库配置信息",
    "test SSH connection": "测试 SSH 连接",
    "check for updates": "检查更新",
    "Usage:": "使用方法:",
    "Commands:": "命令列表:",
    "For detailed help:": "详细帮助:",
    "Project home:": "项目主页:",
    "Create new key": "--- 创建新密钥 ---",
    "Enter key label (e.g. github, work): ": "请输入密钥标签 (如: github, work): ",
    "Enter email address: ": "请输入邮箱地址: ",
    "Enter host address (e.g. github.com, leave empty to skip): ": "请输入主机地址 (如: github.com，留空跳过): ",
    "Enter key type (ed25519/rsa, default {default}): ": "请输入密钥类型 (ed25519/rsa, 默认 {default}): ",
    "Delete key": "--- 删除密钥 ---",
    "Enter the label to delete: ": "请输入要删除的标签: ",
    "Save as label": "--- 另存为标签 ---",
    "Enter new label: ": "请输入新标签名: ",
    "Switch immediately after tagging? [y/N]: ": "添加后是否立即切换? [y/N]: ",
    "Rename label": "--- 重命名标签 ---",
    "Enter old label: ": "请输入旧标签名: ",
    "Enter new label: ": "请输入新标签名: ",
    "Configure repo key": "--- 配置仓库密钥 ---",
    "Enter key label to use: ": "请输入要使用的密钥标签: ",
    "Author management": "--- 作者管理 ---",
    "View current repo author": "查看当前仓库作者",
    "View saved author list": "查看已保存的作者列表",
    "Add/update author": "添加/更新作者",
    "Use author to set current repo": "使用作者设置当前仓库",
    "Remove author": "移除作者",
    "Back to main menu": "返回主菜单",
    "Add/update author": "--- 添加/更新作者 ---",
    "Enter author label: ": "请输入作者标签: ",
    "Enter author name (leave empty to skip): ": "请输入作者姓名 (留空跳过): ",
    "Enter author email (leave empty to auto-fill from public key): ": "请输入作者邮箱 (留空自动从公钥注释补全): ",
    "Use author to set current repo": "--- 使用作者设置当前仓库 ---",
    "Enter author label: ": "请输入作者标签: ",
    "Apply to global? [y/N]: ": "应用到全局? [y/N]: ",
    "Remove author": "--- 移除作者 ---",
    "Enter the author label to remove: ": "请输入要移除的作者标签: ",
    "Test connection": "--- 测试连接 ---",
    "Enter label to test (leave empty for current repo, 'all' for all): ": "请输入要测试的标签 (留空测试当前仓库, 'all' 测试所有): ",
    "Operation failed:": "操作失败:",
    "Goodbye!": "再见！",
    "Invalid option, please reselect": "无效选项，请重新选择",
    "Press any key to continue...": "按任意键继续...",
    "Operation cancelled": "操作已取消",
    "Help": "帮助",
    "sshm v{version} - Multi-account Git SSH key management tool": "sshm v{version} - 多账号 Git SSH 密钥管理工具",
    "Usage:": "使用方法:",
    "Commands:": "命令列表:",
    "view current all SSH keys": "查看当前所有 SSH 密钥",
    "backup all SSH keys": "备份所有 SSH 密钥",
    "list all backups": "列出所有备份",
    "restore keys from backup": "从备份恢复密钥",
    "create a new SSH key (with label)": "创建新的 SSH 密钥（带标签）",
    "delete an SSH key": "删除 SSH 密钥",
    "save the current default key as a label": "将当前默认密钥另存为指定标签",
    "rename key label": "重命名密钥标签",
    "configure a key for a Git repo": "为 Git 仓库配置指定密钥",
    "manage/view/set Git repo author": "管理/查看/设置 Git 仓库作者",
    "display Git repo config info": "显示 Git 仓库配置信息",
    "test SSH connection": "测试 SSH 连接",
    "check for updates": "检查更新",
    "For detailed help:": "详细帮助:",
    "Project home:": "项目主页:",

    # ---- lang command ----
    "set the output language": "设置输出语言",
    "en or zh (omitted: show current language)": "en 或 zh（省略则显示当前语言）",
    "Current language:": "当前语言:",
    "Language set to Chinese": "语言已切换为中文",
    "Language set to English": "语言已切换为英文",
    "Available languages: en (English), zh (Chinese)": "可用语言: en (English), zh (Chinese)",

    # ---- error hints ----
    "Tip: run 'sshm {cmd} --help' to view full usage": "提示: 运行 'sshm {cmd} --help' 查看完整用法",
    "Tip: run 'sshm --help' to view all commands": "提示: 运行 'sshm --help' 查看所有命令",
    "Tip: run 'sshm author list' to view existing author labels": "提示: 运行 'sshm author list' 查看已有作者标签",
    "Tip: run 'sshm list' to view existing key labels": "提示: 运行 'sshm list' 查看已有密钥标签",

    # ---- author path help ----
    "Git repo path (default: current directory, used for view/clear)": "Git 仓库路径（默认当前目录，仅查看/清除时使用）",
}


# --------------------------------------------------------------------------
# 翻译函数
# --------------------------------------------------------------------------

def _(text: str, **kwargs) -> str:
    """翻译文本（支持 {placeholder} 格式化）

    Args:
        text: 英文字符串（作为 key，也是 en 的显示文本）
        **kwargs: 占位符变量
    """
    if _current_lang == 'zh' and text in ZH:
        result = ZH[text]
    else:
        result = text
    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return result
