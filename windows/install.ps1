# Insidir Video Studio - one-time setup for Windows 10/11.
# Installs into this folder: a Python virtual environment, FFmpeg (if not already
# installed) and the Kokoro voice model. Nothing here costs money or needs an account.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor White }

# Run "py -3.12 ..." or "python ..." with extra arguments.
function Invoke-Py([string]$cand, [string[]]$rest) {
    $p = $cand -split " "
    $a = @()
    if ($p.Count -gt 1) { $a += $p[1..($p.Count - 1)] }
    & $p[0] @($a + $rest)
}

# 1. Python 3.10-3.13
Step "Python"
$py = $null
foreach ($cand in @("py -3.12", "py -3.13", "py -3.11", "py -3.10", "python")) {
    try {
        $v = Invoke-Py $cand @("-c", "import sys; print('%d.%d' % sys.version_info[:2])") 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^3\.(1[0-3])$') { $py = $cand; break }
    } catch { }
}
if (-not $py) {
    Write-Host "Python 3.10-3.13 was not found."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.12 with winget (free)..."
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $py = "py -3.12"
    } else {
        throw "Install Python 3.12 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), then run install.bat again."
    }
}
Write-Host "Using $py"

# 2. Virtual environment and packages
Step "Python packages"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Py $py @("-m", "venv", ".venv")
}
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# 3. FFmpeg (GPL build from gyan.dev, includes libass for captions)
Step "FFmpeg"
$haveFfmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path "tools\ffmpeg\bin\ffmpeg.exe")
if (-not $haveFfmpeg) {
    $zip = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
    Write-Host "Downloading FFmpeg (about 100 MB)..."
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip
    $tmp = Join-Path $env:TEMP ("ffmpeg-" + [guid]::NewGuid())
    Expand-Archive $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path "tools" | Out-Null
    if (Test-Path "tools\ffmpeg") { Remove-Item "tools\ffmpeg" -Recurse -Force }
    Move-Item $inner.FullName "tools\ffmpeg"
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "FFmpeg installed in tools\ffmpeg"
} else {
    Write-Host "FFmpeg found"
}

# 4. Kokoro voice model (Apache-2.0)
Step "Kokoro voice model"
& .venv\Scripts\python.exe -m insidir_studio download-models
if ($LASTEXITCODE -ne 0) { throw "Model download failed. Check your connection and run install.bat again." }

# 5. Check everything
Step "Checking"
& .venv\Scripts\python.exe -m insidir_studio doctor

# 6. Desktop shortcut
try {
    $lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Insidir Video Studio.lnk"
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $s.TargetPath = Join-Path $Root "start.bat"
    $s.WorkingDirectory = $Root
    $s.Save()
    Write-Host "Desktop shortcut created."
} catch { }

Write-Host ""
Write-Host "Setup complete. Double-click start.bat (or the desktop shortcut) to open the studio." -ForegroundColor Green
