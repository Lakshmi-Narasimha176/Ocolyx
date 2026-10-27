<#
.SYNOPSIS
    Ocolyx Release Helper Script
.DESCRIPTION
    Automates test execution, Windows binary packaging, checksum generation,
    and release verification for Ocolyx releases.
.PARAMETER Version
    The release version tag (e.g., "0.1.0" or "0.1.1"). Default is "0.1.0".
.PARAMETER SkipTests
    Skip running tests before building.
.EXAMPLE
    .\tools\release.ps1 -Version "0.1.1"
#>
[CmdletBinding()]
Param(
    [string]$Version = "0.1.0",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   Ocolyx Release Preparation: v$Version        " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Locate Python
$pythonCandidates = @(
    (Join-Path $Root ".venv\Scripts\python.exe"),
    (Join-Path $Root "venv\Scripts\python.exe"),
    "python"
)

$Python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -ne "python" -and -not (Test-Path $candidate)) {
        continue
    }
    try {
        & $candidate -c "import PyInstaller" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $Python = $candidate
            break
        }
    } catch {}
}

if ($null -eq $Python) {
    throw "No Python environment with PyInstaller found. Run: python -m pip install -r requirements-prod.txt"
}

# 2. Run Test Suite
if (-not $SkipTests) {
    Write-Host "[1/3] Running complete test suite..." -ForegroundColor Yellow
    $testTmp = Join-Path $Root "test-tmp"
    & $Python -m pytest --basetemp $testTmp
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed. Release aborted. Use -SkipTests to bypass if intentional."
    }
    Write-Host "Tests passed successfully." -ForegroundColor Green
} else {
    Write-Host "[1/3] Skipping tests (-SkipTests specified)." -ForegroundColor DarkGray
}

# 3. Build Windows Executable & Package
Write-Host "[2/3] Building Windows executable package..." -ForegroundColor Yellow
$buildScript = Join-Path $PSScriptRoot "build_windows.ps1"
& $buildScript -SkipTests
if ($LASTEXITCODE -ne 0) {
    throw "Build failed. Check PyInstaller logs."
}

# 4. Verify Release Artifacts
Write-Host "[3/3] Verifying generated release artifacts..." -ForegroundColor Yellow
$distDir = Join-Path $Root "dist"
$exePath = Join-Path $distDir "Ocolyx.exe"
$zipPath = Join-Path $distDir "Ocolyx-Windows.zip"
$pkgDir  = Join-Path $distDir "Ocolyx-Windows"
$sumPath = Join-Path $pkgDir "SHA256SUMS.txt"

if (-not (Test-Path $exePath)) { throw "Missing $exePath" }
if (-not (Test-Path $zipPath)) { throw "Missing $zipPath" }
if (-not (Test-Path $sumPath)) { throw "Missing $sumPath" }

$hash = (Get-Content $sumPath).Trim()
$exeSizeMb = [Math]::Round((Get-Item $exePath).Length / 1MB, 2)
$zipSizeMb = [Math]::Round((Get-Item $zipPath).Length / 1MB, 2)

Write-Host ""
Write-Host "Release Artifacts Ready for v$Version!" -ForegroundColor Green
Write-Host "  - Executable:       $exePath ($exeSizeMb MB)"
Write-Host "  - Deployment Zip:   $zipPath ($zipSizeMb MB)"
Write-Host "  - SHA256 Checksum:  $hash"
Write-Host ""
Write-Host "Next steps for publishing to GitHub:" -ForegroundColor Cyan
Write-Host "  1. git add README.md tools/release.ps1"
Write-Host "  2. git commit -m 'Prepare release v$Version'"
Write-Host "  3. git tag -a v$Version -m 'Release v$Version'"
Write-Host "  4. git push origin main --tags"
Write-Host "  5. Upload dist/Ocolyx-Windows.zip to https://github.com/Lakshmi-Narasimha176/Ocolyx/releases"
Write-Host ""
