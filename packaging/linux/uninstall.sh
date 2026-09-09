#!/usr/bin/env bash
# Odinstalowuje Micro Prompt Optimizer z Pop!_OS/Ubuntu.
# Usuwa: katalog aplikacji + venv, wpisy menu/pulpitu.
# Na życzenie także dane użytkownika (config, pobrane modele Whispera).
set -euo pipefail

APP_NAME="micro-prompt-optimizer"
TARGET="$HOME/.local/share/$APP_NAME"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

rm -f "$HOME/.local/share/applications/$APP_NAME.desktop"
rm -f "$HOME/Desktop/$APP_NAME.desktop" "$HOME/Pulpit/$APP_NAME.desktop" 2>/dev/null || true
command -v update-desktop-database >/dev/null \
    && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

if [ -d "$TARGET" ]; then
    rm -rf "$TARGET"
    say "Usunięto aplikację z $TARGET"
fi

read -r -p "Usunąć też konfigurację aplikacji (w tym klucz API)? [t/N] " ans1
if [[ "${ans1,,}" == "t" || "${ans1,,}" == "tak" ]]; then
    rm -rf "$HOME/.config/micro-prompt-optimizer"
    say "Usunięto konfigurację."
fi

# ~/.cache/whisper jest WSPÓŁDZIELONY z innymi narzędziami Whispera —
# pytamy osobno i kasujemy tylko pliki modeli tej aplikacji (.pt nazwane
# wg WHISPER_MODELS), zostawiając cudze pobrania w spokoju.
read -r -p "Usunąć pobrane przez aplikację modele Whispera? [t/N] " ans2
if [[ "${ans2,,}" == "t" || "${ans2,,}" == "tak" ]]; then
    # usuń puste/podwieszone katalogi dopiero, gdy nic innego tam nie ma
    for m in tiny.pt base.pt small.pt medium.pt; do
        rm -f "$HOME/.cache/whisper/$m"
    done
    find "$HOME/.cache/whisper" -maxdepth 0 -empty -delete 2>/dev/null || true
    say "Usunięto modele aplikacji z ~/.cache/whisper (innych narzędzi nie ruszono)."
fi
say "✅ Deinstalacja zakończona."
