@echo off
chcp 65001 >nul
title SSH Key Manager
color 0A

:: 直接启动 Python 统一交互界面
:: 如果不带参数运行 run_sshm.py，它会自动进入 interactive.py 的 show_interactive_menu()

python "%~dp0src\run_sshm.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 程序异常退出或未找到 Python 环境
    pause
)