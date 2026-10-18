# =====================================================================
#  build.ps1 — build the Decepticon GUI release (Windows, PyInstaller)
#
#  Usage:
#    powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#    powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python C:\Python312\python.exe
#
#  Output:
#    dist\DecepticonGUI\DecepticonGUI.exe      onedir build
#    dist\DecepticonGUI-<version>-win64.zip    release archive
#
#  The zip ships LICENSE and NOTICE next to the binary: Apache-2.0
#  redistribution requires them.
# =====================================================================
param(
    [string]$Python = '',
    [switch]$SkipZip
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # repo root
Push-Location $root
try {
    if (-not $Python) {
        $cands = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
            'C:\Python313\python.exe',
            'C:\Python312\python.exe'
        )
        foreach ($c in $cands) { if ($c -and (Test-Path $c)) { $Python = $c; break } }
    }
    if (-not $Python -or -not (Test-Path $Python)) {
        throw 'No suitable python.exe found. Pass -Python <path> and make sure tkinter works.'
    }

    & $Python -c "import tkinter" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "$Python cannot import tkinter (Microsoft Store build?). Pick another interpreter."
    }

    & $Python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'PyInstaller missing, installing...' -ForegroundColor Yellow
        & $Python -m pip install --disable-pip-version-check "pyinstaller>=6.0"
    }

    $version = (& $Python -c "import sys; sys.path.insert(0,'.'); import decepticon_gui; print(decepticon_gui.__version__)").Trim()
    Write-Host "Building DecepticonGUI $version with $Python" -ForegroundColor Cyan

    if (Get-Process -Name DecepticonGUI -ErrorAction SilentlyContinue) {
        throw 'DecepticonGUI.exe is running; close it before rebuilding.'
    }

    # PyInstaller deletes a previous onedir itself, which fails when an
    # instance is still running or a file is locked. Move it aside instead.
    $outDir = Join-Path $root 'dist\DecepticonGUI'
    if (Test-Path $outDir) {
        $stale = Join-Path $root ('dist\.stale-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        Move-Item -LiteralPath $outDir -Destination $stale
        Write-Host "Previous build moved to $stale" -ForegroundColor DarkGray
    }

    & $Python -m PyInstaller `
        --noconfirm --clean --windowed `
        --name DecepticonGUI `
        --icon packaging\icon.ico `
        --version-file packaging\version_info.txt `
        --exclude-module pytest `
        --exclude-module numpy `
        --exclude-module pandas `
        run.py

    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

    $outDir = Join-Path $root 'dist\DecepticonGUI'
    Copy-Item LICENSE, NOTICE, README.md -Destination $outDir -Force

    $size = (Get-ChildItem $outDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
    Write-Host ("Built {0} ({1:N1} MB)" -f $outDir, $size) -ForegroundColor Green

    if (-not $SkipZip) {
        $zip = Join-Path $root ("dist\DecepticonGUI-{0}-win64.zip" -f $version)
        if (Test-Path $zip) { Remove-Item $zip -Force }
        Compress-Archive -Path $outDir -DestinationPath $zip -CompressionLevel Optimal
        $zipSize = (Get-Item $zip).Length / 1MB
        Write-Host ("Archive {0} ({1:N1} MB)" -f $zip, $zipSize) -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
