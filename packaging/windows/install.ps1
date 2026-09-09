# ══════════════════════════════════════════════════════════════════════
#  Micro Prompt Optimizer — instalator systemowy dla Windows 11
#
#  Co robi (jednokrotnie, za użytkownika):
#   1. sprawdza/doinstalowuje Pythona ≥ 3.10 (przez winget, bez GUI),
#   2. kopiuje aplikację do %LOCALAPPDATA%\MicroPromptOptimizer\app,
#   3. tworzy venv i instaluje zależności (torch CPU lub CUDA -Gpu),
#   4. tworzy skróty: Pulpit + Menu Start (z ikoną, bez okna konsoli).
#
#  Uruchomienie przez użytkownika: podwójny klik na Install-MPO.cmd.
#  Parametry ręczne:  pwsh -File install.ps1            (CPU — zalecane)
#                     pwsh -File install.ps1 -Gpu      (NVIDIA CUDA 12.1)
# ══════════════════════════════════════════════════════════════════════
param([switch]$Gpu)

$ErrorActionPreference = "Stop"
$AppTitle = "Micro Prompt Optimizer"
$Target   = Join-Path $env:LOCALAPPDATA "MicroPromptOptimizer"
$AppDir   = Join-Path $Target "app"
$VenvDir  = Join-Path $Target "venv"
$SrcDir   = Resolve-Path (Join-Path $PSScriptRoot "..\..")   # katalog projektu

function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[uwaga] $m" -ForegroundColor Yellow }

# ── 1. Python ────────────────────────────────────────────────────────
$python = $null
foreach ($cand in @("py -3", "python")) {
    try {
        $ver = & cmd /c "$cand -c `"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')`"" 2>$null
        if ($ver -and [version]$ver -ge [version]"3.10") { $python = $cand; break }
    } catch {}
}
if (-not $python) {
    Say "Brak Pythona ≥ 3.10 — instaluję przez winget (bez pytań, dla bieżącego użytkownika)"
    winget install --id Python.Python.3.12 -e --source winget --scope user `
        --accept-package-agreements --accept-source-agreements
    $fresh = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $fresh) { $python = "`"$fresh`"" } else {
        throw "Python zainstalowany, ale nie znajduje się w PATH — uruchom nowe okno i powtórz instalację."
    }
}
Say "Python: $python"

# ── 2. Kopiowanie aplikacji ──────────────────────────────────────────
Say "Kopiuję aplikację do $AppDir"
robocopy $SrcDir $AppDir /MIR /XD __pycache__ .git .venv venv /XF *.pyc | Out-Null

# ── 3. venv + zależności ─────────────────────────────────────────────
if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    Say "Tworzę środowisko venv"
    & cmd /c "$python -m venv `"$VenvDir`""
}
$Pip = Join-Path $VenvDir "Scripts\pip.exe"
& $Pip install --upgrade pip --quiet
if ($Gpu) {
    Say "Instaluję torch z CUDA 12.1 (GPU) — ~2,5 GB, zachowaj cierpliwość"
    & $Pip install --timeout 120 --retries 10 torch --index-url https://download.pytorch.org/whl/cu121
} else {
    Say "Instaluję torch (CPU — lżejszy; GPU: powtórz z -Gpu)"
    & $Pip install --timeout 120 --retries 10 torch --index-url https://download.pytorch.org/whl/cpu
}
Say "Instaluję pozostałe zależności (whisper itd.)"
& $Pip install --timeout 120 --retries 10 -r (Join-Path $AppDir "requirements.txt")

# ── 4. Skróty (Pulpit + Menu Start), pythonw = bez okna konsoli ──────
$PythonW   = Join-Path $VenvDir "Scripts\pythonw.exe"
$IconFile  = Join-Path $AppDir "assets\icon.ico"
$Shell     = New-Object -ComObject WScript.Shell
foreach ($lnkIn in @(
    [Environment]::GetFolderPath("Desktop"),
    [Environment]::GetFolderPath("Programs")   # Menu Start\Programy
)) {
    $lnk = $Shell.CreateShortcut((Join-Path $lnkIn "$AppTitle.lnk"))
    $lnk.TargetPath       = $PythonW
    $lnk.Arguments        = "`"$(Join-Path $AppDir 'main.py')`""
    $lnk.WorkingDirectory = $AppDir
    $lnk.IconLocation     = $IconFile
    $lnk.Description      = "Optymalizacja promptów + notatki głosowe (Whisper PL)"
    $lnk.Save()
}

Write-Host ""
Say "GOTOWE!"
Write-Host "  - Skrót na Pulpicie i w Menu Start: „$AppTitle”"
Write-Host "  - Tryb REC 🎤: przy pierwszym użyciu kliknij „📥 Pobierz model” (jednorazowo)"
Write-Host "  - Deinstalacja: uninstall.ps1 w tym samym folderze packaging"
if ($Gpu) { Warn "Tryb GPU (CUDA). Zmiana na CPU: uninstall.ps1, potem install.ps1 bez -Gpu." }
