#Requires -Version 5.1
<#
.SYNOPSIS
    本地开发 / 在线安装统一的 sshm 部署脚本（Windows）

.DESCRIPTION
    采用「单一安装目录 + 单一 PATH」策略：本地编译版与在线安装版都写入
    %LOCALAPPDATA%\Programs\sshm\sshm.exe，PATH 只指向这一个目录。
    这样任意位置敲 `sshm xxx` 始终命中同一路径，只是文件被谁覆盖而已，
    无需在多个 PATH 目录间切换，最简单也最不易出错。

    子命令：
      install-local   本地打包 dist\sshm.exe -> 复制覆盖安装目录的 sshm.exe
      install-release 从 GitHub 下载 sshm-windows-amd64.exe -> 重命名并覆盖为 sshm.exe
      status          查看安装目录当前是本地编译版还是在线版
      uninstall       从 PATH 移除本脚本的安装目录（不删文件）

.EXAMPLE
    .\scripts\dev_local.ps1 install-local      # 打包并部署本地编译版
    .\scripts\dev_local.ps1 install-release    # 下载并部署在线版
    .\scripts\dev_local.ps1 status             # 查看当前是哪个版本
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install-local', 'install-release', 'status', 'uninstall')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

# ---------- 路径定位 ----------
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DistExe = Join-Path $ProjectRoot 'dist\sshm.exe'
# 唯一安装目录（与 install.ps1 保持一致）
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\sshm'
$InstallExe = Join-Path $InstallDir 'sshm.exe'
# 来源标记文件：记录当前安装的是 local 还是 release
$MarkerLocal = Join-Path $InstallDir '.source_local'
$MarkerRelease = Join-Path $InstallDir '.source_release'
# 远端资产名
$ReleaseAssetName = 'sshm-windows-amd64.exe'

function Write-Info { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Ok { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "❌ $msg" -ForegroundColor Red }

# ---------- PATH 工具（用户级） ----------
# 确保安装目录在 User PATH 中（幂等），放最前以保证优先级
function Ensure-InstallDirInPath {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $norm = $InstallDir.TrimEnd('\')
    $exists = @($userPath -split ';' | Where-Object {
        $_ -ne '' -and $_.TrimEnd('\') -ieq $norm
    })
    if ($exists) {
        Write-Info "安装目录已在 PATH 中（无需重复配置）"
    } else {
        $new = "$norm" + $(if ($userPath) { ";$userPath" } else { '' })
        [Environment]::SetEnvironmentVariable('Path', $new, 'User')
        # 同步到当前会话（幂等去重）
        $env:Path = (($norm) + ';' + @($env:Path -split ';' | Where-Object {
            $_ -ne '' -and $_.TrimEnd('\') -ine $norm
        } | Select-Object -Unique)) -join ';'
        Write-Ok "已把安装目录加入 PATH: $InstallDir"
        Write-Info "PATH 只需配置这一次，之后本地/在线安装都复用此目录"
    }
}

# 从 User PATH 移除安装目录
function Remove-InstallDirFromPath {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $norm = $InstallDir.TrimEnd('\')
    $kept = @($userPath -split ';' | Where-Object {
        $_ -ne '' -and $_.TrimEnd('\') -ine $norm
    })
    [Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'User')
    Write-Ok "已从 PATH 移除安装目录: $InstallDir"
}

# ---------- 本地打包 ----------
function Invoke-LocalBuild {
    $buildScript = Join-Path $PSScriptRoot 'build_local.py'
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = 'python' }
    $env:PYTHONIOENCODING = 'utf-8'
    & $py $buildScript
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Test-Path $DistExe)) {
        Write-Err "打包失败：未找到 $DistExe"
        exit 1
    }
}

# ---------- install-local ----------
function Invoke-InstallLocal {
    Write-Info "本地打包..."
    Invoke-LocalBuild
    if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }
    Copy-Item -Path $DistExe -Destination $InstallExe -Force
    Write-Ok "已把本地编译版部署到 $InstallExe"
    # 写入来源标记
    Remove-Item (Join-Path $InstallDir '.source_release') -Force -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $MarkerLocal -Force | Out-Null
    Ensure-InstallDirInPath
    Write-Host ""
    Show-Status
}

# ---------- install-release ----------
function Invoke-InstallRelease {
    $repo = 'Eavelabs/sshm'
    Write-Info "获取最新 release 信息..."
    try {
        $release = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest"
    } catch {
        Write-Err "获取版本信息失败: $_"
        exit 1
    }
    $asset = $release.assets | Where-Object { $_.name -eq $ReleaseAssetName }
    if (-not $asset) {
        Write-Err "未找到资产: $ReleaseAssetName"
        exit 1
    }
    Write-Info "版本 $($release.tag_name) / 大小 $([math]::Round($asset.size / 1MB, 2)) MB"

    if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }

    $tempFile = Join-Path $env:TEMP $ReleaseAssetName
    Write-Info "下载中..."
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($asset.browser_download_url, $tempFile)
        $wc.Dispose()
    } catch {
        Write-Err "下载失败: $_"
        exit 1
    }

    # 关键：PATH 只认 sshm.exe，必须重命名（覆盖）为 sshm.exe
    Write-Info "部署（重命名为 sshm.exe）..."
    Move-Item -Path $tempFile -Destination $InstallExe -Force
    Write-Ok "已部署在线版: $InstallExe"
    # 写入来源标记
    Remove-Item (Join-Path $InstallDir '.source_local') -Force -ErrorAction SilentlyContinue
    New-Item -ItemType File -Path $MarkerRelease -Force | Out-Null
    Ensure-InstallDirInPath
    Write-Host ""
    Show-Status
}

# ---------- status ----------
function Show-Status {
    Write-Host ""
    Write-Host "================ sshm 部署状态 ================" -ForegroundColor Magenta
    if (-not (Test-Path $InstallExe)) {
        Write-Warn "安装目录尚无 sshm.exe: $InstallExe"
        Write-Info "请先运行: .\scripts\dev_local.ps1 install-local 或 install-release"
    } else {
        $size = [math]::Round((Get-Item $InstallExe).Length / 1MB, 2)
        Write-Info "安装位置: $InstallExe ($size MB)"
        if (Test-Path $MarkerLocal) {
            Write-Ok "当前为：本地编译版"
        } elseif (Test-Path $MarkerRelease) {
            Write-Ok "当前为：在线版"
        } else {
            Write-Warn "当前为：未知来源（可能是 install.ps1 早期安装）"
        }
        $inPath = @([Environment]::GetEnvironmentVariable('Path','User') -split ';' |
            Where-Object { $_ -ne '' -and $_.TrimEnd('\') -ieq $InstallDir.TrimEnd('\') })
        if ($inPath) { Write-Ok "PATH 已指向: $InstallDir" }
        else { Write-Warn "PATH 未包含安装目录（重启终端后可能找不到 sshm）" }
    }
    Write-Host "================================================" -ForegroundColor Magenta
}

# ---------- uninstall ----------
function Invoke-Uninstall {
    Remove-InstallDirFromPath
    Write-Info "（未删除 $InstallDir 下的文件；如需完全卸载请运行 scripts\install.ps1 -Uninstall）"
    Show-Status
}

# ---------- 主流程 ----------
switch ($Action) {
    'install-local'   { Invoke-InstallLocal }
    'install-release' { Invoke-InstallRelease }
    'status'          { Show-Status }
    'uninstall'       { Invoke-Uninstall }
}
