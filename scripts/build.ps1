[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildDir = Join-Path $RepoRoot "build"
$DistDir = Join-Path $RepoRoot "dist"
$DistAppDir = Join-Path $DistDir "Tools"
$InstallerDir = Join-Path $DistDir "installer"
$SpecPath = Join-Path $RepoRoot "packaging\pyinstaller\Tools.spec"
$InnoScriptPath = Join-Path $RepoRoot "packaging\inno\Tools.iss"
$RequirementsPath = Join-Path $RepoRoot "requirements.txt"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

function Assert-InRepoPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedRepo = [System.IO.Path]::GetFullPath("$RepoRoot\")
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the repository: $resolvedPath"
    }
}

function Get-AppVersion {
    & $Python -c "from app.metadata import APP_VERSION; print(APP_VERSION)"
}

function Test-RequiredPythonModules {
    $dependencyProbe = @'
import importlib

required_modules = {
    "certifi": "certifi",
    "PIL": "Pillow",
    "PySide6": "PySide6",
    "pypdf": "pypdf",
    "fitz": "PyMuPDF",
    "PyInstaller": "pyinstaller",
}

missing = []
for module_name, package_name in required_modules.items():
    try:
        importlib.import_module(module_name)
    except Exception:
        missing.append(f"{package_name} (import {module_name})")

if missing:
    missing_text = ", ".join(missing)
    raise SystemExit(
        "Missing required build dependencies for the selected Python interpreter: "
        f"{missing_text}. Run 'python -m pip install -r requirements.txt' and try again."
    )
'@

    $null = $dependencyProbe | & $Python - 2>$null
    return $LASTEXITCODE -eq 0
}

function Ensure-RequiredPythonModules {
    if (Test-RequiredPythonModules) {
        return
    }

    if (-not (Test-Path $RequirementsPath)) {
        throw "requirements.txt was not found: $RequirementsPath"
    }

    Write-Warning "Required Python build dependencies are missing for $Python. Installing from requirements.txt..."
    & $Python -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install build dependencies with $Python -m pip install -r requirements.txt"
    }

    if (-not (Test-RequiredPythonModules)) {
        throw "Python dependency verification failed for build interpreter even after installing requirements: $Python"
    }
}

function Assert-BundledFFmpeg {
    $ffmpegRoot = Join-Path $RepoRoot "assets\ffmpeg"
    $requiredFiles = @(
        "bin\ffmpeg.exe",
        "bin\ffprobe.exe",
        "README.txt",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md"
    )

    foreach ($relativePath in $requiredFiles) {
        $path = Join-Path $ffmpegRoot $relativePath
        if (-not (Test-Path $path)) {
            throw "Missing bundled FFmpeg file: $path"
        }
    }
}

function Find-InnoSetupCompiler {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidateRoots = @(
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles
    ) | Where-Object { $_ }

    foreach ($root in $candidateRoots) {
        foreach ($folder in @("Inno Setup 6", "Inno Setup 7")) {
            $candidate = Join-Path $root "$folder\ISCC.exe"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

function New-VersionInfoFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    $versionParts = $Version.Split(".")
    $major = [int]$versionParts[0]
    $minor = if ($versionParts.Length -gt 1) { [int]$versionParts[1] } else { 0 }
    $patch = if ($versionParts.Length -gt 2) { [int]$versionParts[2] } else { 0 }
    $versionTuple = "$major, $minor, $patch, 0"
    $versionInfoPath = Join-Path $BuildDir "version_info.txt"

    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

    @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($versionTuple),
    prodvers=($versionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'YaBraG'),
          StringStruct('FileDescription', 'Tools desktop utility launcher'),
          StringStruct('FileVersion', '$Version'),
          StringStruct('InternalName', 'Tools'),
          StringStruct('OriginalFilename', 'Tools.exe'),
          StringStruct('ProductName', 'Tools'),
          StringStruct('ProductVersion', '$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Encoding UTF8 -Path $versionInfoPath

    return $versionInfoPath
}

Set-Location $RepoRoot

$Version = Get-AppVersion
Write-Host "Building Tools v$Version"
Ensure-RequiredPythonModules
Write-Host "Required Python build dependencies verified"
Assert-BundledFFmpeg
Write-Host "Bundled FFmpeg files found in assets\ffmpeg"

if (-not $NoClean) {
    foreach ($path in @($BuildDir, $DistDir)) {
        if (Test-Path $path) {
            Assert-InRepoPath -Path $path
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }
}

$VersionInfoPath = New-VersionInfoFile -Version $Version
Write-Host "Generated version metadata: $VersionInfoPath"

& $Python -m PyInstaller $SpecPath --noconfirm --clean

if (-not (Test-Path (Join-Path $DistAppDir "Tools.exe"))) {
    throw "PyInstaller did not produce dist\Tools\Tools.exe."
}

if ($SkipInstaller) {
    Write-Host "Installer build skipped. App bundle created at $DistAppDir"
    exit 0
}

$InnoCompiler = Find-InnoSetupCompiler
if (-not $InnoCompiler) {
    Write-Warning "Inno Setup compiler was not found. Install Inno Setup 6 to build the installer."
    Write-Warning "The PyInstaller app bundle is available at $DistAppDir"
    exit 0
}

New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null

$InnoArgs = @(
    $InnoScriptPath,
    "/DMyAppVersion=$Version",
    "/DSourceDir=$DistAppDir",
    "/DOutputDir=$InstallerDir"
)

& $InnoCompiler @InnoArgs

$InstallerPath = Join-Path $InstallerDir "Tools-Setup-v$Version.exe"
if (-not (Test-Path $InstallerPath)) {
    throw "Inno Setup did not produce $InstallerPath."
}

Write-Host "Build complete: $InstallerPath"
