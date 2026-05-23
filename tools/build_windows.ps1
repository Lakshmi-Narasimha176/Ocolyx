[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistDir = Join-Path $Root "dist"
$ExePath = Join-Path $DistDir "Ocolyx.exe"
$SpecPath = Join-Path $Root "Ocolyx.spec"

Set-Location $Root

$requiredPaths = @(
    "main.py",
    "Ocolyx.spec",
    "assets",
    "assets\icons\Ocolyx.ico",
    "assets\icons\Ocolyx.jpeg",
    "assets\models\shape_predictor_68_face_landmarks.dat",
    "config\default_config.json"
)

foreach ($relativePath in $requiredPaths) {
    $fullPath = Join-Path $Root $relativePath
    if (-not (Test-Path $fullPath)) {
        throw "Required build resource is missing: $relativePath"
    }
}

$pythonCandidates = @(
    (Join-Path $Root "venv\Scripts\python.exe"),
    "python"
)

function Test-PythonInterpreter {
    param([string]$Candidate)

    try {
        & $Candidate -c "import sys; print(sys.executable)" 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PythonModule {
    param(
        [string]$Candidate,
        [string]$ModuleName
    )

    try {
        & $Candidate -c "import $ModuleName" 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$Python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -ne "python" -and -not (Test-Path $candidate)) {
        continue
    }

    if ((Test-PythonInterpreter $candidate) -and (Test-PythonModule $candidate "PyInstaller")) {
        $Python = $candidate
        break
    }
}

if ($null -eq $Python) {
    throw "No working Python interpreter with PyInstaller was found. Install production requirements with: pip install -r requirements-prod.txt"
}

if (-not $SkipTests) {
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed. Re-run with -SkipTests only for an intentional packaging-only build."
    }
}

$pyinstallerArgs = @()
if (-not $NoClean) {
    $pyinstallerArgs += "--clean"
}
$pyinstallerArgs += "--noconfirm"
$pyinstallerArgs += $SpecPath

& $Python -m PyInstaller @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

if (-not (Test-Path $ExePath)) {
    throw "Build completed but executable was not found at: $ExePath"
}

$exeInfo = Get-Item $ExePath
Write-Host ""
Write-Host "Ocolyx Windows executable created successfully."
Write-Host "Executable: $($exeInfo.FullName)"
Write-Host "Size: $([Math]::Round($exeInfo.Length / 1MB, 2)) MB"
Write-Host ""
Write-Host "The dist folder is ready for demonstration and deployment."
