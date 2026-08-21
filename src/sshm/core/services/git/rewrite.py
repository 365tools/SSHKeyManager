"""Git 历史作者重写模块（纯 Python 实现，不依赖外部 filter-repo/filter-branch）

使用 git fast-export / fast-import 流协议：
1. `git fast-export --all` 导出完整历史（含 author/committer 信息）
2. Python 逐行解析流，对匹配旧作者名/邮箱的 author/committer 行进行替换
3. `git fast-import` 导入重写后的流
4. 原 refs 先备份到 refs/original/，避免历史丢失

适用于 sshm 打包分发（无 Python 环境），无需额外安装任何工具。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# author/committer 行示例：
#   author Alice <alice@x.com> 1786862590 +0800
#   committer Bob <bob@y.com> 1786862590 +0800
# 解析：前缀(author|committer) + 姓名(可能含空格，到 < 为止) + <邮箱> + 时间戳 + 时区
_PERSON_LINE = re.compile(
    r"^(?P<kind>author|committer) "
    r"(?P<name>(?:[^<]|\\.)+) "
    r"<(?P<email>[^>]*)>"
    r"(?P<rest>[ \t].*)$"
)


class RewriteConfig:
    """一次历史重写的匹配/替换规则。所有字段均可选。"""

    def __init__(
        self,
        old_name: Optional[str] = None,
        new_name: Optional[str] = None,
        old_email: Optional[str] = None,
        new_email: Optional[str] = None,
        match_all: bool = False,
    ):
        self.old_name = old_name
        self.new_name = new_name
        self.old_email = old_email
        self.new_email = new_email
        # match_all：无 old 条件，把历史所有作者/邮箱统一为 new_name/new_email
        self.match_all = match_all


# 会被外部 git 环境劫持、导致 `-C <repo>` 指定的仓库失效或作者被覆盖的环境变量。
# 典型场景：在 git hook（如 pre-commit）内运行本工具/测试时，git 会设置
# GIT_DIR、GIT_INDEX_FILE、GIT_AUTHOR_*/GIT_COMMITTER_* 等变量，即使显式
# `-C <repo>`，这些变量仍会让 git 指向错误位置或覆盖仓库作者，造成重写不生效
# 或操作落到当前项目仓库。这里移除所有 GIT_* 前缀变量（GIT_PAGER/GIT_EXEC_PATH
# 等不影响仓库定位，一并清除也无妨），保证操作始终作用于目标仓库。
def _clean_git_env() -> dict:
    """返回移除了全部 GIT_* 污染变量后的环境副本（保留其它变量）。"""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run_git(
    repo: Path,
    args: list,
    input_text: Optional[str] = None,
    capture: bool = True,
    binary_input: bool = False,
) -> subprocess.CompletedProcess:
    """在指定仓库执行 git 命令。

    - input_text：可选的 stdin 文本输入
    - binary_input：为 True 时以 UTF-8 编码的 bytes 写入 stdin，
      避免 Windows 下 text mode 把 \\n 转成 \\r\\n 污染 fast-import 流
    - 统一使用干净 env，屏蔽外部 GIT_DIR 等环境变量干扰
    """
    cmd = ["git", "-C", str(repo)] + args
    env = _clean_git_env()
    if binary_input and input_text is not None:
        return subprocess.run(
            cmd,
            input=input_text.encode("utf-8"),
            capture_output=capture,
            env=env,
        )
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _count_matches(stream: str, cfg: RewriteConfig) -> int:
    """统计流中匹配旧作者/邮箱的提交行数（用于预览与结果确认）。

    match_all 时统计所有作者/提交者行（全量刷新）。
    """
    count = 0
    for line in stream.splitlines():
        m = _PERSON_LINE.match(line)
        if not m:
            continue
        if cfg.match_all:
            count += 1
            continue
        name = m.group("name")
        email = m.group("email")
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
        stripped = line.rstrip("\r\n")
        m = _PERSON_LINE.match(stripped)
        if not m:
            out.append(line)
            continue
        name = m.group("name")
        email = m.group("email")
        new_name = name
        new_email = email
        hit = False
        if cfg.match_all:
            # 全量刷新：所有作者/提交者统一为 new_name/new_email
            new_name = cfg.new_name if cfg.new_name is not None else name
            new_email = cfg.new_email if cfg.new_email is not None else email
            hit = True
        elif cfg.old_name and name == cfg.old_name:
            new_name = cfg.new_name if cfg.new_name is not None else name
            hit = True
        elif cfg.old_email and email == cfg.old_email:
            new_email = cfg.new_email if cfg.new_email is not None else email
            hit = True
        if hit:
            replaced += 1
            rest = m.group("rest")
            # 统一输出 LF（\n），避免 Windows CRLF 混入 fast-import 流
            out.append(f"{m.group('kind')} {new_name} <{new_email}>{rest}\n")
        else:
            # 保留原始行，但确保以 LF 结尾
            line = line.rstrip("\r\n") + "\n"
            out.append(line)
    return "".join(out), replaced


def _active_refs(repo: Path) -> list:
    """返回所有「真实」refs，排除 refs/original/ 备份命名空间。

    refs/original/ 是历史重写产生的备份（git filter-branch 同款约定），
    不属于真实历史。若 fast-export / git log --all 误包含它，会导致：
    重写后旧作者仍能通过 --all 查到、matched 计数反复命中备份旧历史。
    """
    refs = _run_git(repo, ["for-each-ref", "--format=%(refname)"])
    if refs.returncode != 0:
        return []
    return [
        r for r in refs.stdout.splitlines() if r and not r.startswith("refs/original/")
    ]


def _backup_refs(repo: Path) -> None:
    """把当前所有活跃 refs 备份到 refs/original/，避免重写后历史丢失。

    镜像路径语义：
      refs/heads/main        -> refs/original/main
      refs/tags/v1.0         -> refs/original/tags/v1.0
      refs/remotes/origin/x  -> refs/original/refs/remotes/origin/x
    """
    for ref in _active_refs(repo):
        if ref.startswith("refs/heads/"):
            target = "refs/original/" + ref[len("refs/heads/") :]
        elif ref.startswith("refs/tags/"):
            target = "refs/original/tags/" + ref[len("refs/tags/") :]
        else:
            target = "refs/original/" + ref
        _run_git(repo, ["update-ref", target, ref])


def _update_current_branch(repo: Path) -> None:
    """fast-import 更新 refs/heads/* 后，把 HEAD 重新挂回当前分支。

    fast-import 导入新历史后，HEAD 可能变成 detached（指向旧 ref 或游离状态）。
    这里稳健地恢复到原分支：优先用 symbolic-ref，失败则从 refs/heads 推断。
    """
    branch = _current_branch_name(repo)
    if not branch:
        # 无法确定当前分支，尝试 main/master 兜底
        for cand in ("main", "master"):
            if (repo / ".git").exists():
                chk = _run_git(repo, ["rev-parse", "--verify", f"refs/heads/{cand}"])
                if chk.returncode == 0:
                    branch = cand
                    break
    if branch:
        _run_git(repo, ["checkout", "-f", branch])


def _current_branch_name(repo: Path) -> str:
    """返回 HEAD 当前所在分支名；若 detached 返回空字符串。"""
    # 先尝试 symbolic-ref（正常挂载时可用）
    sym = _run_git(repo, ["symbolic-ref", "--quiet", "HEAD"])
    if sym.returncode == 0:
        ref = sym.stdout.strip()
        if ref.startswith("refs/heads/"):
            return ref[len("refs/heads/") :]
        return ""
    # detached：尝试解析 HEAD 指向的 commit 属于哪个分支
    name = _run_git(repo, ["name-rev", "--name-only", "HEAD"])
    if name.returncode == 0:
        n = name.stdout.strip()
        # 格式如 "main"、"main~1"、"tags/v0.0.1^0"
        if "~" in n or "^" in n:
            n = n.split("~")[0].split("^")[0]
        if n and not n.startswith("tags/"):
            return n
    return ""


def rewrite_history(repo_path: Path, cfg: RewriteConfig) -> dict:
    """重写指定仓库的历史作者/邮箱。

    返回统计信息 dict：
        matched_commits: 匹配到旧作者/邮箱的提交数（预览阶段）
        rewritten: 实际重写的行数
    """
    if cfg.match_all:
        # 全量刷新：无需 old 条件，但必须指定 new_name 或 new_email
        if not cfg.new_name and not cfg.new_email:
            raise ValueError("全量刷新模式需要提供 new_name 或 new_email")
    elif not cfg.old_name and not cfg.old_email:
        raise ValueError("old_name 和 old_email 至少需要一个")

    repo = Path(repo_path)

    # 1. 导出原始流，统计受影响提交数。
    #    显式传入活跃 refs（排除 refs/original/ 备份）。不能依赖 `--all --exclude`
    #    （git 不会过滤 --all 预展开的 refs），否则旧备份历史会被反复重写，
    #    且 matched 计数会反复命中已重写过的旧提交。
    active = _active_refs(repo)
    if not active:
        return {"matched_commits": 0, "rewritten": 0}
    export = _run_git(repo, ["fast-export"] + active)
    if export.returncode != 0:
        raise RuntimeError(f"git fast-export failed: {export.stderr.strip()}")
    # 归一化换行：Windows 下 git 可能输出 CRLF，统一为 LF 避免污染 fast-import 流
    original = (export.stdout or "").replace("\r\n", "\n").replace("\r", "\n")

    matched = _count_matches(original, cfg)
    if matched == 0:
        return {"matched_commits": 0, "rewritten": 0}

    # 2. 备份原 refs
    _backup_refs(repo)

    # 3. 重写流
    new_stream, replaced = _rewrite_stream(original, cfg)

    # 4. 导入重写后的流（二进制 stdin，避免 Windows 换行污染）
    imp = _run_git(
        repo,
        ["fast-import", "--quiet", "--force"],
        input_text=new_stream,
        binary_input=True,
    )
    if imp.returncode != 0:
        raise RuntimeError(f"git fast-import failed: {imp.stderr.strip()}")

    # 5. 更新当前分支指向
    _update_current_branch(repo)

    return {"matched_commits": matched, "rewritten": replaced}


def get_authors_in_repo(repo_path: Path) -> list:
    """列出仓库历史中出现过的所有作者（用于预览，展示将影响谁）。"""
    repo = Path(repo_path)
    # 显式传活跃 refs（排除 refs/original/ 备份），避免列出重写前的旧作者
    active = _active_refs(repo)
    if not active:
        return []
    log = _run_git(repo, ["log"] + active + ["--format=%an <%ae>"])
    if log.returncode != 0:
        return []
    seen = {}
    for line in log.stdout.splitlines():
        if line and line not in seen:
            seen[line] = True
    return list(seen.keys())
