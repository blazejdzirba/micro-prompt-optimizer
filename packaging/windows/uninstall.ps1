# Odinstalowuje Micro Prompt Optimizer z Windows 11.
# Usuwa skróty i katalog aplikacji. Opcjonalnie: dane użytkownika i modele.
$AppTitle = "Micro Prompt Optimizer"
$Target   = Join-Path $env:LOCALAPPDATA "MicroPromptOptimizer"

foreach ($lnkIn in @(
    [Environment]::GetFolderPath("Desktop"),
    [Environment]::GetFolderPath("Programs")
)) {
    $lnk = Join-Path $lnkIn "$AppTitle.lnk"
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
}
if (Test-Path $Target) { Remove-Item $Target -Recurse -Force }

$ans1 = Read-Host "Usunąć też konfigurację aplikacji (w tym klucz API)? [t/N]"
if ($ans1 -match "^[tT]") {
    $cfg = Join-Path $env:USERPROFILE ".config\micro-prompt-optimizer"
    if (Test-Path $cfg) { Remove-Item $cfg -Recurse -Force }
}

# .cache\whisper jest WSPÓŁDZIELONY z innymi narzędziami Whispera — kasujemy
# wyłącznie pliki modeli tej aplikacji, a pusty katalog usuwamy tylko,
# gdy nic innego tam nie ma.
$ans2 = Read-Host "Usunąć pobrane przez aplikację modele Whispera? [t/N]"
if ($ans2 -match "^[tT]") {
    $whsp = Join-Path $env:USERPROFILE ".cache\whisper"
    foreach ($m in @("tiny.pt","base.pt","small.pt","medium.pt")) {
        $f = Join-Path $whsp $m
        if (Test-Path $f) { Remove-Item $f -Force }
    }
    if ((Test-Path $whsp) -and -not (Get-ChildItem $whsp -Force |
           Select-Object -First 1)) {
        Remove-Item $whsp -Force
    }
}
Write-Host "==> Deinstalacja zakończona." -ForegroundColor Cyan
