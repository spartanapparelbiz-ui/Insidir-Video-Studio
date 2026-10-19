# Insidir Video Studio - one-time setup for Windows 10/11.
# Installs into this folder: a Python virtual environment (Kokoro voices, Faster Whisper),
# FFmpeg, a portable Node.js with Motion Canvas + Rough.js, and the voice and caption
# models. Everything is free; no account, card or API key is needed.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Step($t) { Write-Host ""; Write-Host "== $t" -ForegroundColor White }

# Run "py -3.12 ..." or "python ..." with extra arguments.
function Invoke-Py([string]$cand, [string[]]$rest) {
    $p = $cand -split " "
    $a = @()
    if ($p.Count -gt 1) { $a += $p[1..($p.Count - 1)] }
    & $p[0] @($a + $rest)
}

function Get-NodeMajor([string]$exe) {
    try {
        $v = & $exe --version 2>$null
        if ($v -match '^v(\d+)') { return [int]$Matches[1] }
    } catch { }
    return 0
}

# 1. Python 3.10-3.13
Step "1/8 Python"
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
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
        $py = "py -3.12"
        try { Invoke-Py $py @("--version") | Out-Null } catch {
            throw "Python was installed. Close this window and run install.bat again."
        }
    } else {
        throw "Install Python 3.12 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), then run install.bat again."
    }
}
Write-Host "Using $py"

# 2. Python packages: Kokoro (voices) and Faster Whisper (caption timing)
Step "2/8 Python packages (Kokoro, Faster Whisper)"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Py $py @("-m", "venv", ".venv")
}
& .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# 3. FFmpeg (GPL build from gyan.dev, includes libass for captions and libvpx)
Step "3/8 FFmpeg"
$haveFfmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path "tools\ffmpeg\bin\ffmpeg.exe")
if (-not $haveFfmpeg) {
    $zip = Join-Path $env:TEMP "ffmpeg-release-essentials.zip"
    Write-Host "Downloading FFmpeg (about 100 MB)..."
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip -UseBasicParsing
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

# 4. Node.js 22 LTS, portable in tools\node (no admin rights, nothing system-wide)
Step "4/8 Node.js"
$node = $null
if (Test-Path "tools\node\node.exe") {
    $node = (Resolve-Path "tools\node\node.exe").Path
} elseif ((Get-Command node -ErrorAction SilentlyContinue) -and ((Get-NodeMajor "node") -ge 18)) {
    $node = (Get-Command node).Source
}
if (-not $node) {
    Write-Host "Downloading Node.js 22 LTS (about 30 MB)..."
    $sums = (Invoke-WebRequest "https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt" -UseBasicParsing).Content
    $m = [regex]::Match($sums, "([0-9a-f]{64})\s+(node-v22\.\d+\.\d+-win-x64\.zip)")
    if (-not $m.Success) { throw "Could not find the Node.js download. Install Node.js 22 LTS from https://nodejs.org and run install.bat again." }
    $zip = Join-Path $env:TEMP $m.Groups[2].Value
    Invoke-WebRequest ("https://nodejs.org/dist/latest-v22.x/" + $m.Groups[2].Value) -OutFile $zip -UseBasicParsing
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $m.Groups[1].Value) { throw "Node.js download is corrupt. Run install.bat again." }
    $tmp = Join-Path $env:TEMP ("node-" + [guid]::NewGuid())
    Expand-Archive $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path "tools" | Out-Null
    if (Test-Path "tools\node") { Remove-Item "tools\node" -Recurse -Force }
    Move-Item $inner.FullName "tools\node"
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    $node = (Resolve-Path "tools\node\node.exe").Path
}
$nodeDir = Split-Path $node
$env:Path = "$nodeDir;$env:Path"
Write-Host ("Using Node.js " + (& $node --version) + " at $node")

# 5. Motion Canvas + Rough.js (exact versions from motion\package-lock.json)
Step "5/8 Motion Canvas and Rough.js"
Push-Location motion
& (Join-Path $nodeDir "npm.cmd") ci --no-audit --no-fund --loglevel=error
$npmExit = $LASTEXITCODE
Pop-Location
if ($npmExit -ne 0) { throw "npm ci failed in the motion folder" }

# 6. A browser for headless rendering: Microsoft Edge (built into Windows 11), else Chromium
Step "6/8 Render browser"
& $node motion\scripts\check-browser.mjs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Edge/Chrome not usable; downloading Playwright's Chromium (about 150 MB)..."
    & $node motion\node_modules\playwright-core\cli.js install chromium
    & $node motion\scripts\check-browser.mjs
    if ($LASTEXITCODE -ne 0) { throw "No browser available for rendering." }
}

# 7. Kokoro voice model (Apache-2.0)
Step "7/8 Kokoro voice model"
& .venv\Scripts\python.exe -m insidir_studio download-models
if ($LASTEXITCODE -ne 0) { throw "Model download failed. Check your connection and run install.bat again." }

# 8. Faster Whisper caption model (MIT), then check everything
Step "8/8 Faster Whisper caption model"
& .venv\Scripts\python.exe -m insidir_studio download-models --whisper
if ($LASTEXITCODE -ne 0) { Write-Host "Whisper model download failed; captions will use estimated timing until it succeeds." -ForegroundColor Yellow }

Step "Checking"
& .venv\Scripts\python.exe -m insidir_studio doctor

# Desktop shortcut
try {
    $lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Insidir Video Studio.lnk"
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $s.TargetPath = Join-Path $Root "start.bat"
    $s.WorkingDirectory = $Root
    $s.IconLocation = (Join-Path $Root "windows\insidir-studio.ico") + ",0"
    $s.Description = "Insidir Video Studio"
    $s.Save()
    Write-Host "Desktop shortcut created."
} catch { }

Write-Host ""
Write-Host "Setup complete. Double-click start.bat (or the desktop shortcut) to open the studio." -ForegroundColor Green
