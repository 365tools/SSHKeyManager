#Requires -Version 5.1
<#
.SYNOPSIS
    SSH Manager Windows install/uninstall script
.DESCRIPTION
    Automatically downloads, renames, adds to PATH, and can uninstall
.PARAMETER Version
    Version to install (default: latest)
.PARAMETER InstallDir
    Install directory (default: $env:LOCALAPPDATA\Programs\sshm)
.PARAMETER NoAddPath
    Do not add to PATH
.PARAMETER Uninstall
    Uninstall mode
.EXAMPLE
    # Install (latest by default)
    .\install.ps1
    
    # Install a specific version
    .\install.ps1 -Version v2.1.0
    
    # Uninstall
    .\install.ps1 -Uninstall
    
    # Online install
    irm https://raw.githubusercontent.com/365tools/sshm/main/scripts/install.ps1 | iex
    
    # Online uninstall
    irm https://raw.githubusercontent.com/365tools/sshm/main/scripts/install.ps1 | iex -Args '-Uninstall'
#>

[CmdletBinding()]
param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\sshm",
    [switch]$NoAddPath,
    [switch]$CleanPath,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'

function Write-ColorText {
    param($Message, $Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

# Remove stale sshm entries from User PATH (keep current install dir)
function Remove-StaleSshmFromPath {
    Write-ColorText "Cleaning stale sshm entries from PATH..." "Cyan"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $userPath) {
        Write-ColorText "[OK] User PATH is empty, nothing to clean" "Green"
        return
    }
    $keep = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
    $keepList = @()
    $removed = @()
    foreach ($e in ($userPath -split ';')) {
        if (-not $e) { continue }
        $full = $e.TrimEnd('\')
        # keep the current install dir
        if ($full -ieq $keep) { $keepList += $e; continue }
        # dir contains sshm.exe/sshm.bat and is not the install dir -> stale
        $hasSshm = (Test-Path (Join-Path $e 'sshm.exe') -ErrorAction SilentlyContinue) -or
                   (Test-Path (Join-Path $e 'sshm.bat') -ErrorAction SilentlyContinue)
        if ($hasSshm) {
            $removed += $e
            continue
        }
        $keepList += $e
    }
    if ($removed.Count -gt 0) {
        $newPath = ($keepList -join ';')
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-ColorText "[OK] Removed old sshm dirs from PATH:" "Green"
        foreach ($r in $removed) { Write-ColorText "   - $r" "Yellow" }
        Write-ColorText "   Restart terminal to take effect" "Cyan"
    } else {
        Write-ColorText "[OK] No stale sshm found in PATH" "Green"
    }
}

function Uninstall-SSHM {
    Write-ColorText "=================================" "Cyan"
    Write-ColorText "SSH Manager Uninstall" "Cyan"
    Write-ColorText "=================================" "Cyan"
    Write-Host ""
    
    $exePath = Join-Path $InstallDir "sshm.exe"
    
    if (Test-Path $exePath) {
        Remove-Item $exePath -Force
        Write-ColorText "[OK] Deleted: $exePath" "Green"
    } else {
        Write-ColorText "[WARN] Not found: $exePath" "Yellow"
    }
    
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -like "*$InstallDir*") {
        $newPath = ($userPath -split ';' | Where-Object { $_ -ne $InstallDir }) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-ColorText "[OK] Removed from PATH" "Green"
    }
    
    if (Test-Path $InstallDir) {
        try {
            Remove-Item $InstallDir -Force -Recurse -ErrorAction Stop
            Write-ColorText "[OK] Deleted directory" "Green"
        } catch {
            Write-ColorText "[WARN] Cannot delete directory: $InstallDir" "Yellow"
        }
    }
    
    Write-Host ""
    Write-ColorText "Uninstall complete!" "Green"
    exit 0
}

if ($Uninstall) {
    Uninstall-SSHM
}

Write-ColorText "=================================" "Cyan"
Write-ColorText "SSH Manager Installer" "Cyan"
Write-ColorText "=================================" "Cyan"
Write-Host ""

$repo = "365tools/sshm"
try {
    if ($Version -eq "latest") {
        Write-ColorText "[INFO] Getting latest version..." "Cyan"
        $releaseInfo = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/latest" -ErrorAction Stop
        $Version = $releaseInfo.tag_name
    } else {
        Write-ColorText "[INFO] Getting version $Version..." "Cyan"
        $releaseInfo = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/tags/$Version" -ErrorAction Stop
    }
} catch {
    Write-ColorText "[ERROR] Cannot get version info: $_" "Red"
    exit 1
}

$asset = $releaseInfo.assets | Where-Object { $_.name -eq "sshm-windows-amd64.exe" }
if (-not $asset) {
    Write-ColorText "[ERROR] Windows executable not found" "Red"
    exit 1
}

$downloadUrl = $asset.browser_download_url
$fileSize = [math]::Round($asset.size / 1MB, 2)

Write-ColorText "[OK] Found version: $Version" "Green"
Write-ColorText "[INFO] File size: $fileSize MB" "Cyan"
Write-Host ""
Write-ColorText "[INFO] Install location: $InstallDir" "Cyan"
Write-Host ""

if (-not $PSBoundParameters.ContainsKey('InstallDir')) {
    $response = Read-Host "Continue installation? [Y/n]"
    if ($response -eq 'n' -or $response -eq 'N') {
        Write-ColorText "[CANCELLED]" "Yellow"
        exit 0
    }
}

if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$tempFile = Join-Path $env:TEMP "sshm-windows-amd64.exe"
$finalPath = Join-Path $InstallDir "sshm.exe"

Write-Host ""
Write-ColorText "[INFO] Downloading..." "Cyan"
try {
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($downloadUrl, $tempFile)
    $webClient.Dispose()
    Write-ColorText "[OK] Download complete" "Green"
} catch {
    Write-ColorText "[ERROR] Download failed: $_" "Red"
    exit 1
}

Write-ColorText "[INFO] Installing..." "Cyan"
try {
    Move-Item -Path $tempFile -Destination $finalPath -Force
    Write-ColorText "[OK] Installed: $finalPath" "Green"
} catch {
    Write-ColorText "[ERROR] Install failed: $_" "Red"
    exit 1
}

$addToPath = $false
if (!$NoAddPath) {
    Write-Host ""
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    
    if ($userPath -like "*$InstallDir*") {
        Write-ColorText "[OK] PATH already configured" "Green"
    } else {
        Write-ColorText "[QUESTION] Add to PATH? (Run 'sshm' from anywhere)" "Yellow"
        $response = Read-Host "  [Y/n]"
        
        if ($response -ne 'n' -and $response -ne 'N') {
            $addToPath = $true
        }
    }
}

if ($addToPath) {
    try {
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $separator = if ($userPath) { ";" } else { "" }
        $newPath = "$userPath$separator$InstallDir"
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        
        Write-ColorText "[OK] Added to PATH" "Green"
        Write-ColorText "  Restart terminal to take effect" "Cyan"
        $env:Path = "$env:Path;$InstallDir"
    } catch {
        Write-ColorText "[ERROR] Failed to add PATH: $_" "Red"
    }
}

# Clean stale sshm PATH entries (-CleanPath)
if ($CleanPath) {
    Write-Host ""
    Remove-StaleSshmFromPath
}

Write-Host ""
Write-ColorText "[INFO] Verifying..." "Cyan"
try {
    $null = & $finalPath --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-ColorText "[OK] Verification passed!" "Green"
    }
} catch {
    Write-ColorText "[WARN] Verification failed but file installed" "Yellow"
}

Write-Host ""
Write-ColorText "=================================" "Cyan"
Write-ColorText "[SUCCESS] Installation complete!" "Green"
Write-ColorText "=================================" "Cyan"
Write-Host ""
Write-ColorText "Location: $finalPath" "Cyan"
Write-ColorText "Version: $Version" "Cyan"
Write-Host ""

if ($addToPath) {
    Write-ColorText "Usage (after restart terminal):" "Yellow"
    Write-Host "  sshm list" -ForegroundColor White
} else {
    Write-ColorText "Usage:" "Yellow"
    Write-Host "  $finalPath list" -ForegroundColor White
}

Write-Host ""
Write-Host "More help: https://github.com/365tools/sshm" -ForegroundColor DarkGray
Write-Host "Uninstall: powershell -File install.ps1 -Uninstall" -ForegroundColor DarkGray
Write-Host "Clean stale PATH: powershell -File install.ps1 -CleanPath" -ForegroundColor DarkGray
Write-Host ""
