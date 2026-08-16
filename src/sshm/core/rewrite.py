"""Git 历史作者重写模块（纯 Python 实现，不依赖外部 filter-repo/filter-branch）

使用 git fast-export / fast-import 流协议：
1. `git fast-export --all` 导出完整历史（含 author/committer 信息）
2. Python 逐行解析流，对匹配旧作者名/邮箱的 author/committer 行进行替换
3. `git fast-import` 导入重写后的流
4. 原 refs 先备份到 refs/original/，避免历史丢失

适用于 sshm 打包分发（无 Python 环境），无需额外安装任何工具。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# author/committer 行示例：
#   author Alice <alice@x.com> 1786862590 +0800
#   committer Bob <bob@y.com> 1786862590 +0800
# 解析：前缀(author|committer) + 姓名(可能含空格，到 < 为止) + <邮箱> + 时间戳 + 时区
_PERSON_LINE = re.compile(
    r'^(?P<kind>author|committer) '
    r'(?P<name>(?:[^<]|\\.)+) '
    r'<(?P<email>[^>]*)>'
    r'(?P<rest>[ \t].*)$'
)


class RewriteConfig:
    """一次历史重写的匹配/替换规则。所有字段均可选。"""

    def __init__(self, old_name: Optional[str] = None,
                 new_name: Optional[str] = None,
                 old_email: Optional[str] = None,
                 new_email: Optional[str] = None):
        self.old_name = old_name
        self.new_name = new_name
        self.old_email = old_email
        self.new_email = new_email


def _run_git(repo: Path, args: list, input_text: Optional[str] = None,
             capture: bool = True, binary_input: bool = False
             ) -> subprocess.CompletedProcess:
    """在指定仓库执行 git 命令。

    - input_text：可选的 stdin 文本输入
    - binary_input：为 True 时以 UTF-8 编码的 bytes 写入 stdin，
      避免 Windows 下 text mode 把 \\n 转成 \\r\\n 污染 fast-import 流
    """
    cmd = ['git', '-C', str(repo)] + args
    if binary_input and input_text is not None:
        return subprocess.run(
            cmd,
            input=input_text.encode('utf-8'),
            capture_output=capture,
        )
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=capture,
        text=True,
        encoding='utf-8',
        errors='replace',
    )


def _count_matches(stream: str, cfg: RewriteConfig) -> int:
    """统计流中匹配旧作者/邮箱的提交行数（用于预览与结果确认）。"""
    count = 0
    for line in stream.splitlines():
        m = _PERSON_LINE.match(line)
        if not m:
            continue
        name = m.group('name')
        email = m.group('email')
        if cfg.old_name and name == cfg.old_name:
            count += 1
        elif cfg.old_email and email == cfg.old_email:
            count += 1
    return count


def _rewrite_stream(stream: str, cfg: RewriteConfig) -> Tuple[str, int]:
    """重写 fast-export 流，返回 (新流, 替换次数)。"""
    lines = stream.splitlines(keepends=True)
    out: list[str] = []
    replaced = 0
    for line in lines:
        stripped = line.rstrip('\r\n')
        m = _PERSON_LINE.match(stripped)
        if not m:
            out.append(line)
            continue
        name = m.group('name')
        email = m.group('email')
        new_name = name
        new_email = email
        hit = False
        if cfg.old_name and name == cfg.old_name:
            new_name = cfg.new_name if cfg.new_name is not None else name
            hit = True
        if cfg.old_email and email == cfg.old_email:
            new_email = cfg.new_email if cfg.new_email is not None else email
            hit = True
        if hit:
            replaced += 1
            rest = m.group('rest')
            # 统一输出 LF（\n），避免 Windows CRLF 混入 fast-import 流
            out.append(f"{m.group('kind')} {new_name} <{new_email}>{rest}\n")
        else:
            # 保留原始行，但确保以 LF 结尾
            line = line.rstrip('\r\n') + '\n'
            out.append(line)
    return ''.join(out), replaced


def _backup_refs(repo: Path) -> None:
    """把当前所有 refs 备份到 refs/original/，避免重写后历史丢失。"""
    refs = _run_git(repo, ['for-each-ref', '--format=%(refname)'])
    if refs.returncode != 0:
        return
    for ref in refs.stdout.splitlines():
        if not ref or ref.startswith('refs/original/'):
            continue
        new_ref = 'refs/original/' + ref.removeprefix('refs/heads/')
        _run_git(repo, ['update-ref', new_ref, ref])


def _update_current_branch(repo: Path) -> None:
    """fast-import 会更新 refs/heads/*，但需要把当前分支 checkout 到新提交。"""
    head = _run_git(repo, ['symbolic-ref', '--quiet', 'HEAD'])
    if head.returncode == 0:
        branch = head.stdout.strip()
        _run_git(repo, ['checkout', '-f', branch])


def rewrite_history(repo_path: Path, cfg: RewriteConfig) -> dict:
    """重写指定仓库的历史作者/邮箱。

    返回统计信息 dict：
        matched_commits: 匹配到旧作者/邮箱的提交数（预览阶段）
        rewritten: 实际重写的行数
    """
    if not cfg.old_name and not cfg.old_email:
        raise ValueError('old_name 和 old_email 至少需要一个')

    repo = Path(repo_path)

    # 1. 导出原始流，统计受影响提交数
    export = _run_git(repo, ['fast-export', '--all'])
    if export.returncode != 0:
        raise RuntimeError(f"git fast-export failed: {export.stderr.strip()}")
    # 归一化换行：Windows 下 git 可能输出 CRLF，统一为 LF 避免污染 fast-import 流
    original = (export.stdout or '').replace('\r\n', '\n').replace('\r', '\n')

    matched = _count_matches(original, cfg)
    if matched == 0:
        return {'matched_commits': 0, 'rewritten': 0}

    # 2. 备份原 refs
    _backup_refs(repo)

    # 3. 重写流
    new_stream, replaced = _rewrite_stream(original, cfg)

    # 4. 导入重写后的流（二进制 stdin，避免 Windows 换行污染）
    imp = _run_git(repo, ['fast-import', '--quiet', '--force'],
                   input_text=new_stream, binary_input=True)
    if imp.returncode != 0:
        raise RuntimeError(f"git fast-import failed: {imp.stderr.strip()}")

    # 5. 更新当前分支指向
    _update_current_branch(repo)

    return {'matched_commits': matched, 'rewritten': replaced}


def get_authors_in_repo(repo_path: Path) -> list:
    """列出仓库历史中出现过的所有作者（用于预览，展示将影响谁）。"""
    repo = Path(repo_path)
    log = _run_git(repo, ['log', '--all', '--format=%an <%ae>'])
    if log.returncode != 0:
        return []
    seen = {}
    for line in log.stdout.splitlines():
        if line and line not in seen:
            seen[line] = True
    return list(seen.keys())
