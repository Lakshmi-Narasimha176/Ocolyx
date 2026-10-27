[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$NoClean,
    [switch]$NoPackage
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistDir = Join-Path $Root "dist"
$ExePath = Join-Path $DistDir "Ocolyx.exe"
$SpecPath = Join-Path $Root "Ocolyx.spec"
$IconPath = Join-Path $Root "assets\icons\ocolyx.ico"
$PackageDir = Join-Path $DistDir "Ocolyx-Windows"
$PackageZip = Join-Path $DistDir "Ocolyx-Windows.zip"

Set-Location $Root

$requiredPaths = @(
    "main.py",
    "Ocolyx.spec",
    "assets",
    "assets\icons\ocolyx.ico",
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
    (Join-Path $Root ".venv\Scripts\python.exe"),
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

if (-not $NoPackage) {
    $resolvedDist = (Resolve-Path $DistDir).Path
    $packageParent = Split-Path $PackageDir -Parent
    if ((Resolve-Path $packageParent).Path -ne $resolvedDist) {
        throw "Refusing to package outside the dist directory: $PackageDir"
    }

    if (Test-Path $PackageDir) {
        $resolvedPackage = (Resolve-Path $PackageDir).Path
        if (-not $resolvedPackage.StartsWith($resolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean package directory outside dist: $resolvedPackage"
        }
        Remove-Item -LiteralPath $resolvedPackage -Recurse -Force
    }

    New-Item -ItemType Directory -Path $PackageDir | Out-Null
    $packagedExe = Join-Path $PackageDir "Ocolyx.exe"
    Copy-Item -LiteralPath $ExePath -Destination $packagedExe -Force
    Copy-Item -LiteralPath $IconPath -Destination (Join-Path $PackageDir "ocolyx.ico") -Force

    $shortcutPath = Join-Path $PackageDir "Ocolyx.lnk"
    $wshShell = New-Object -ComObject WScript.Shell
    $shortcut = $wshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $packagedExe
    $shortcut.WorkingDirectory = $PackageDir
    $shortcut.Description = "Ocolyx Eye-Strain Prevention"
    $shortcut.IconLocation = "$packagedExe,0"
    $shortcut.Save()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wshShell) | Out-Null

    $checksum = Get-FileHash -Algorithm SHA256 -Path $packagedExe
    $checksum.Hash | Set-Content -Path (Join-Path $PackageDir "SHA256SUMS.txt") -Encoding ASCII

    $readme = @"
Ocolyx Windows Deployment
=========================

Executable:
  Ocolyx.exe

Shortcut:
  Ocolyx.lnk (uses the embedded Ocolyx.exe icon)

Icon asset:
  ocolyx.ico (same icon embedded in Ocolyx.exe for installer tools)

Build type:
  Single-file PyInstaller Windows executable

Runtime behavior:
  - No console window is shown.
  - assets\icons\ocolyx.ico is embedded in Ocolyx.exe and bundled for runtime window/tray icons.
  - Assets, JSON defaults, CustomTkinter data, and dlib model files are bundled into the executable.
  - User-editable settings and logs are written under %APPDATA%\Ocolyx.

Installer notes:
  - Install Ocolyx.exe as the application binary.
  - Use Ocolyx.lnk or point Start Menu/desktop shortcuts at Ocolyx.exe so Windows uses the embedded icon.
  - Use ocolyx.ico from this folder only when your installer tool requires a separate icon file.
  - Target Windows 10 or newer.

Verification:
  - Confirm the SHA256 hash in SHA256SUMS.txt after copying.
  - Confirm Ocolyx.exe shows the Ocolyx icon in File Explorer.
  - Launch Ocolyx.exe and confirm the taskbar and window title bar use the Ocolyx icon.
  - Confirm the UI opens, tray icon appears, webcam starts, and blink detection can load the bundled dlib model.
"@
    $readme | Set-Content -Path (Join-Path $PackageDir "README_DEPLOYMENT.txt") -Encoding ASCII

    if (Test-Path $PackageZip) {
        Remove-Item -LiteralPath $PackageZip -Force
    }
    Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $PackageZip -Force

    # Clean intermediate build cache to save disk space
    $buildDir = Join-Path $Root "build"
    if (Test-Path $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Ocolyx Windows executable created successfully."
Write-Host "Executable: $($exeInfo.FullName)"
Write-Host "Size: $([Math]::Round($exeInfo.Length / 1MB, 2)) MB"
if (-not $NoPackage) {
    Write-Host "Deployment folder: $PackageDir"
    Write-Host "Deployment zip: $PackageZip"
}
Write-Host ""
Write-Host "The dist folder is ready for demonstration, installer input, and deployment."
