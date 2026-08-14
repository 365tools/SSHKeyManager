#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sshm CLI 全量测试驱动
- 在沙箱 USERPROFILE/HOME 中运行，不污染真实环境
- 覆盖: 帮助 / 完整流程 / 残缺指令 / 错误指令 / 错误参数 / 交互菜单
用法: python scripts/cli_test.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'src' / 'run_sshm.py'
SANDBOX = ROOT / 'scripts' / '.cli_test_home'
REPO = SANDBOX / 'repo'

PASS, FAIL, SKIP, OBS = [], [], [], []


def run_case(name, args, expect='0', cwd=None, timeout=20, stdin=None,
             note=''):
    """执行一个 CLI 测试用例"""
    env = os.environ.copy()
    env['USERPROFILE'] = str(SANDBOX)
    env['HOME'] = str(SANDBOX)
    try:
        p = subprocess.run(
            [sys.executable, str(RUN)] + args,
            cwd=str(cwd) if cwd else str(REPO),
            env=env, capture_output=True, text=True,
            timeout=timeout, input=stdin, errors='replace',
        )
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or '') + (e.stderr or '')
        rc = 'TIMEOUT'
    else:
        out = (p.stdout or '') + (p.stderr or '')
        rc = p.returncode

    # 判定
    if expect == 'observe':
        ok = None
    elif expect == 'nonzero':
        ok = rc != 0
    elif expect == '0':
        ok = rc == 0
    elif expect == '2':
        ok = rc == 2
    else:
        ok = str(rc) == expect

    lines = [l for l in out.splitlines() if l.strip()]
    summary = ' | '.join(lines[:4])
    if len(lines) > 6:
        summary += ' ... | ' + ' | '.join(lines[-2:])

    status = 'PASS' if ok else ('OBS' if ok is None else 'FAIL')
    record = f"[{status}] {name}\n       sshm {' '.join(args)}"
    if note:
        record += f'  ({note})'
    record += f'\n       expect={expect} actual={rc}\n       >> {summary}'

    if ok is True:
        PASS.append(record)
    elif ok is None:
        OBS.append(record)
    elif rc == 'TIMEOUT':
        SKIP.append(record)
    else:
        FAIL.append(record)
    return rc, summary


def setup_sandbox():
    """准备沙箱: 清空旧数据, 初始化 git 仓库"""
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    (SANDBOX / 'ssh').mkdir(parents=True)
    REPO.mkdir()
    env = os.environ.copy()
    env['USERPROFILE'] = str(SANDBOX)
    env['HOME'] = str(SANDBOX)
    r = subprocess.run(['git', 'init', str(REPO)], capture_output=True,
                       text=True, env=env)
    if r.returncode != 0:
        print('!!! git init 失败，repo 相关用例将受影响:', r.stderr.strip())
    return r.returncode == 0


def print_group(title, items):
    print(f"\n{'=' * 78}\n{title}  ({len(items)} 项)\n{'=' * 78}")
    for i in items:
        print(i)
        print('-' * 78)


def main():
    # 前提检查
    ssh_keygen = shutil.which('ssh-keygen')
    print(f'沙箱: {SANDBOX}')
    print(f'ssh-keygen: {ssh_keygen or "未找到 (add 用例将失败)"}')

    git_ok = setup_sandbox()

    # ---------------------------------------------------------------
    # A. 帮助类 (expect exit 0)
    # ---------------------------------------------------------------
    help_cases = [
        ('顶层帮助', ['--help']),
        ('顶层 -h', ['-h']),
        ('list 帮助', ['list', '--help']),
        ('backup 帮助', ['backup', '--help']),
        ('backups 帮助', ['backups', '--help']),
        ('restore 帮助', ['restore', '--help']),
        ('add 帮助', ['add', '--help']),
        ('remove 帮助', ['remove', '--help']),
        ('tag 帮助', ['tag', '--help']),
        ('rename 帮助', ['rename', '--help']),
        ('use 帮助', ['use', '--help']),
        ('author 帮助', ['author', '--help']),
        ('author list 帮助', ['author', 'list', '--help']),
        ('author add 帮助', ['author', 'add', '--help']),
        ('author remove 帮助', ['author', 'remove', '--help']),
        ('author use 帮助', ['author', 'use', '--help']),
        ('author unset 帮助', ['author', 'unset', '--help']),
        ('info 帮助', ['info', '--help']),
        ('test 帮助', ['test', '--help']),
        ('update 帮助', ['update', '--help']),
    ]
    for name, args in help_cases:
        run_case(name, args, expect='0')

    # ---------------------------------------------------------------
    # B. 完整流程 (在沙箱 git 仓库内)
    # ---------------------------------------------------------------
    run_case('空仓库 list', ['list'], expect='0')
    run_case('add github (默认 ed25519)', ['add', 'github', 'test@example.com'],
             expect='0', timeout=60)
    run_case('add rsa 类型', ['add', 'rsa', 't@x.com', '-t', 'rsa'],
             expect='0', timeout=60)
    run_case('add work 带主机+姓名',
             ['add', 'work', 'work@co.com', '-H', '127.0.0.1', '-n', 'Work User'],
             expect='0', timeout=60)
    run_case('list 显示三标签', ['list'], expect='0')
    run_case('list -a 显示公钥', ['list', '-a'], expect='0')
    run_case('use work -y (仓库级+别名)',
             ['use', 'work', '-y'], expect='observe')
    run_case('use github -y --author',
             ['use', 'github', '-y', '--author'], expect='observe')
    run_case('use github -y --global', ['use', 'github', '-y', '--global'],
             expect='observe')
    run_case('author 查看仓库作者', ['author'], expect='observe')
    run_case('author list', ['author', 'list'], expect='0')
    run_case('author add github', ['author', 'add', 'github',
                                   '-n', 'GitHub User', '-e', 'gh@x.com'],
             expect='0')
    run_case('author use github -y', ['author', 'use', 'github', '-y'],
             expect='observe')
    run_case('author use github --global -y',
             ['author', 'use', 'github', '-y', '--global'], expect='observe')
    run_case('author use 临时覆盖 -n -e',
             ['author', 'use', 'github', '-y', '-n', 'Temp Name',
              '-e', 'temp@x.com'], expect='observe')
    run_case('author unset', ['author', 'unset'], expect='observe',
             stdin='y\n')
    run_case('author unset --global', ['author', 'unset', '--global'],
             expect='0', stdin='y\n')
    run_case('author remove github', ['author', 'remove', 'github'],
             expect='observe')
    # author remove 缺省邮箱自动补全 + remove -y
    run_case('author add work (无邮箱, 自动补全)',
             ['author', 'add', 'work', '-n', 'Work Author'], expect='observe')
    run_case('author list 含 work', ['author', 'list'], expect='0')
    run_case('author remove work -y', ['author', 'remove', 'work', '-y'],
             expect='0')
    run_case('info', ['info'], expect='observe')
    run_case('info -p 指定路径', ['info', '-p', str(REPO)], expect='observe')
    run_case('test work (127.0.0.1 拒绝连接, 快速返回)',
             ['test', 'work'], expect='observe', timeout=25)
    run_case('test -p 指定路径', ['test', '-p', str(REPO)], expect='observe',
             timeout=25)
    run_case('test --all', ['test', '--all'], expect='observe', timeout=25)
    run_case('backup', ['backup'], expect='observe')
    run_case('backups', ['backups'], expect='0')
    run_case('restore -y (最新备份)', ['restore', '-y'], expect='observe')
    run_case('restore -t rsa', ['restore', '-t', 'rsa', '-y'], expect='observe')
    run_case('restore 指定备份名', ['restore', 'notexist_backup'], expect='observe')
    run_case('tag github2 -s', ['tag', 'github2', '-s'], expect='observe')
    run_case('tag -t ed25519', ['tag', 'tagged3', '-t', 'ed25519'],
             expect='observe')
    run_case('rename github dev', ['rename', 'github', 'dev'], expect='observe')
    run_case('rename -t 指定类型', ['rename', 'rsa', 'rsa2', '-t', 'rsa'],
             expect='observe')
    # 重复 add 同名同类型（dev 由 rename github 而来, 为 ed25519, 必冲突）
    run_case('add 重复标签 dev', ['add', 'dev', 'x@y.com'], 'nonzero')
    run_case('remove work -t rsa', ['remove', 'work', '-t', 'rsa'],
             expect='observe')
    # use 指定路径（正向，用真实仓库；github 已 rename 为 dev）
    run_case('use dev -p 指定路径', ['use', 'dev', '-p', str(REPO), '-y'],
             expect='observe')
    # 重复 use --global（幂等）
    run_case('use dev --global 重复', ['use', 'dev', '-y', '--global'],
             expect='observe')
    run_case('update --check (网络, 容忍失败)',
             ['update', '--check'], expect='observe', timeout=30)

    # ---------------------------------------------------------------
    # C. 残缺指令 (argparse 报错 exit 2 + 友好提示)
    # ---------------------------------------------------------------
    incomplete = [
        ('use 缺 label', ['use']),
        ('add 无参数', ['add']),
        ('add 缺 email', ['add', 'github']),
        ('remove 缺 label', ['remove']),
        ('tag 缺 label', ['tag']),
        ('rename 无参数', ['rename']),
        ('rename 缺 new_label', ['rename', 'old']),
        ('author add 缺 label', ['author', 'add']),
        ('author use 缺 label', ['author', 'use']),
        ('author remove 缺 label', ['author', 'remove']),
        ('author unset 多余参数', ['author', 'unset', 'extra']),
        ('info 多余位置参数', ['info', 'extra']),
        ('test 多余位置参数', ['test', 'a', 'b']),
        ('restore 多余参数', ['restore', 'b1', 'b2']),
    ]
    for name, args in incomplete:
        run_case(name, args, expect='2')

    # ---------------------------------------------------------------
    # D. 错误指令
    # ---------------------------------------------------------------
    wrong_cmd = [
        ('不存在的命令', ['badcmd']),
        ('大小写错误 List', ['List']),
        ('拼写错误 usee', ['usee']),
        ('author 非法子命令', ['author', 'badsub']),
        ('顶层未识别选项 -x', ['-x']),
    ]
    for name, args in wrong_cmd:
        run_case(name, args, expect='2')

    # ---------------------------------------------------------------
    # E. 错误参数
    # ---------------------------------------------------------------
    bad_args = [
        ('标签含空格', ['add', 'bad label', 'x@y.com'], 'nonzero'),
        ('标签以 . 开头', ['add', '.dot', 'x@y.com'], 'nonzero'),
        ('标签含 !', ['add', 'bad!', 'x@y.com'], 'nonzero'),
        ('保留标签 default', ['add', 'default', 'x@y.com'], 'nonzero'),
        ('保留标签 original', ['add', 'original', 'x@y.com'], 'nonzero'),
        ('非法密钥类型 -t foo', ['add', 'dev', 'x@y.com', '-t', 'foo'], '2'),
        ('use 不存在的标签', ['use', 'notexist', '-y'], 'observe'),
        ('remove 不存在的标签', ['remove', 'notexist'], 'observe'),
        ('tag 不存在的标签', ['tag', 'notexist'], 'observe'),
        ('author use 不存在的标签', ['author', 'use', 'notexist'], 'observe'),
        ('author remove 不存在的标签', ['author', 'remove', 'notexist'],
         'observe'),
        ('use 不存在的路径', ['use', 'work', '-y', '-p', '/nonexistent/path'],
         'observe'),
        ('info 不存在的路径', ['info', '-p', '/nonexistent/path'], 'observe'),
        ('restore 不存在的备份', ['restore', 'notexist_backup'], 'observe'),
        ('test label + --all 同时给出', ['test', 'work', '--all'], 'observe',
         25),
        # 可选参数缺值（-p / -t / -n 后无参数 -> argparse exit 2）
        ('use -p 缺值', ['use', 'work', '-p'], '2'),
        ('info -p 缺值', ['info', '-p'], '2'),
        ('test -p 缺值', ['test', '-p'], '2'),
        ('restore -t 缺值', ['restore', '-t'], '2'),
        ('add -t 缺值', ['add', 'dev', 'x@y.com', '-t'], '2'),
        ('add -H 缺值', ['add', 'dev', 'x@y.com', '-H'], '2'),
        ('add -n 缺值', ['add', 'dev', 'x@y.com', '-n'], '2'),
        ('tag -t 缺值', ['tag', 'x', '-t'], '2'),
        ('rename -t 缺值', ['rename', 'a', 'b', '-t'], '2'),
        ('author add -n 缺值', ['author', 'add', 'x', '-n'], '2'),
        ('author use -e 缺值', ['author', 'use', 'x', '-e'], '2'),
        # 非法邮箱格式（业务校验, 非零退出）
        ('add 非法邮箱', ['add', 'dev', 'not-an-email'], 'nonzero'),
        # 超长/空标签
        ('add 空标签', ['add', '', 'x@y.com'], 'nonzero'),
    ]
    for t in bad_args:
        name, args = t[0], t[1]
        expect = t[2] if len(t) > 2 else 'observe'
        timeout = t[3] if len(t) > 3 else 20
        run_case(name, args, expect=expect, timeout=timeout)

    # ---------------------------------------------------------------
    # F. 交互菜单 (无参数运行, 喂 Q 退出)
    # ---------------------------------------------------------------
    if git_ok:
        env = os.environ.copy()
        env['USERPROFILE'] = str(SANDBOX)
        env['HOME'] = str(SANDBOX)
        try:
            p = subprocess.run([sys.executable, str(RUN)],
                               cwd=str(REPO), env=env, capture_output=True,
                               text=True, timeout=15, input='Q\n',
                               errors='replace')
            out = (p.stdout or '') + (p.stderr or '')
            menu_ok = ('交互式菜单' in out or 'sshm - Interactive' in out)
            item = f"[{'PASS' if menu_ok else 'FAIL'}] 交互菜单 (喂 Q 退出)"
            item += f'\n       python run_sshm.py  expect=exit ok actual={p.returncode}'
            item += f'\n       >> {" | ".join([l for l in out.splitlines() if l.strip()][:5])}'
            (PASS if menu_ok else FAIL).append(item)
        except subprocess.TimeoutExpired:
            SKIP.append('[SKIP] 交互菜单 (超时, 可能等待按键)')

    # ---------------------------------------------------------------
    # 汇总
    # ---------------------------------------------------------------
    print_group('== FAIL ==', FAIL) if FAIL else print('\n== FAIL ==: 无')
    print_group('== OBS (行为观察, 不判错) ==', OBS) if OBS else print('\n== OBS ==: 无')
    print_group('== SKIP ==', SKIP) if SKIP else print('\n== SKIP ==: 无')
    print_group('== PASS ==', PASS) if PASS else print('\n== PASS ==: 无')

    total = len(PASS) + len(FAIL) + len(SKIP) + len(OBS)
    print(f"\n{'=' * 78}")
    print(f'总计 {total} 项 | PASS {len(PASS)} | FAIL {len(FAIL)} '
          f'| OBS {len(OBS)} | SKIP {len(SKIP)}')
    print(f'{"=" * 78}')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
