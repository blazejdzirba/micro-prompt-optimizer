#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  Micro Prompt Optimizer — instalator systemowy dla Pop!_OS / Ubuntu
#
#  Co robi (jednokrotnie, za użytkownika):
#   1. dba o pakiety systemowe (python3-tk, python3-venv, libportaudio2),
#   2. kopiuje aplikację do ~/.local/share/micro-prompt-optimizer/app,
#   3. tworzy venv i instaluje zależności (torch w wersji CPU lub CUDA),
#   4. tworzy wpis w menu Aplikacje (+ opcjonalnie ikonę na Pulpicie).
#
#  Użycie:   ./install.sh            (CPU — lżejszy download, zalecane)
#           ./install.sh --gpu       (NVIDIA CUDA 12.1 — szybszy Whisper)
#
#  Po instalacji aplikację uruchamiasz z menu Aplikacje — bez terminala.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

MODE="cpu"
[ "${1:-}" = "--gpu" ] && MODE="gpu"

APP_NAME="micro-prompt-optimizer"
APP_TITLE="Micro Prompt Optimizer"
TARGET="$HOME/.local/share/$APP_NAME"
APP_DIR="$TARGET/app"
VENV="$TARGET/venv"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # katalog projektu

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[uwaga]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[błąd]\033[0m %s\n' "$*" >&2; exit 1; }

# ── 1. Python + pakiety systemowe ────────────────────────────────────
command -v python3 >/dev/null || die "Brak python3 w systemie."
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
python3 -c 'import sys; assert sys.version_info >= (3, 10)' \
    || die "Python $PYVER jest za stary — wymagany ≥ 3.10."

need_pkgs=()
python3 -c 'import tkinter'  2>/dev/null || need_pkgs+=(python3-tk)
python3 -m ensurepip --version >/dev/null 2>&1 || need_pkgs+=(python3-venv)
[ -x /usr/bin/dpkg ] && dpkg -s libportaudio2 >/dev/null 2>&1 || need_pkgs+=(libportaudio2)
if [ "${#need_pkgs[@]}" -gt 0 ]; then
    say "Instaluję pakiety systemowe: ${need_pkgs[*]} (poproszę o hasło sudo)"
    sudo apt-get update -qq
    sudo apt-get install -y "${need_pkgs[@]}"
fi

# ── 2. Kopiowanie aplikacji ──────────────────────────────────────────
say "Kopiuję aplikację do $APP_DIR"
mkdir -p "$TARGET"
rsync -a --delete \
    --exclude __pycache__ --exclude .git --exclude .venv --exclude venv \
    --exclude '*.pyc' \
    "$SRC_DIR/" "$APP_DIR/" 2>/dev/null || {
    # gdy brak rsync — prosty fallback
    mkdir -p "$APP_DIR"
    (cd "$SRC_DIR" && tar --exclude='*/__pycache__' --exclude='./.git' \
        --exclude='./.venv' --exclude='./venv' -cf - .) | (cd "$APP_DIR" && tar xf -)
}

# ── 3. Środowisko venv + zależności ──────────────────────────────────
if [ ! -x "$VENV/bin/python" ]; then
    say "Tworzę środowisko venv ($VENV)"
    python3 -m venv "$VENV"
fi
PIP="$VENV/bin/pip"
"$PIP" install --upgrade pip --quiet

# torch najpierw: wersja CPU jest ~10× mniejsza niż CUDA; whisper potem
# widzi zainstalowany torch i nie wymusza własnej (ciężkiej) wersji.
if [ "$MODE" = "gpu" ]; then
    say "Instaluję torch z CUDA 12.1 (GPU) — to może być ~2,5 GB, zachowaj cierpliwość"
    "$PIP" install --timeout 120 --retries 10 torch \
        --index-url https://download.pytorch.org/whl/cu121
else
    say "Instaluję torch (wersja CPU — lżejszy download; GPU: powtórz z --gpu)"
    "$PIP" install --timeout 120 --retries 10 torch \
        --index-url https://download.pytorch.org/whl/cpu
fi
say "Instaluję pozostałe zależności (whisper itd.)"
"$PIP" install --timeout 120 --retries 10 -r "$APP_DIR/requirements.txt"

# ── 4. Skrót w menu Aplikacje (+ opcjonalnie Pulpit) ─────────────────
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_TITLE
Comment=Optymalizacja promptów (OpenRouter) + notatki głosowe Whisper
Exec=$VENV/bin/python $APP_DIR/main.py
Path=$APP_DIR
Icon=$APP_DIR/assets/icon-512.png
Terminal=false
Categories=Utility;Development;
Keywords=prompt;whisper;AI;LLM;transkrypcja;
StartupWMClass=Micropromptoptimizer
EOF
command -v update-desktop-database >/dev/null \
    && update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ikona na Pulpicie (GNOME wymaga oznaczenia jako zaufana)
if [ -d "$HOME/Pulpit" ] || [ -d "$HOME/Desktop" ]; then
    DESK="$HOME/Desktop"; [ -d "$HOME/Pulpit" ] && DESK="$HOME/Pulpit"
    cp "$DESKTOP_DIR/$APP_NAME.desktop" "$DESK/$APP_NAME.desktop"
    chmod +x "$DESK/$APP_NAME.desktop"
    command -v gio >/dev/null \
        && gio set "$DESK/$APP_NAME.desktop" metadata::trusted true 2>/dev/null || true
fi

say "✅ Gotowe! "
echo
echo "  • Aplikacja: menu Aplikacje → „$APP_TITLE”"
echo "  • Tryb REC 🎤: przy pierwszym użyciu kliknij „📥 Pobierz model” (jednorazowo)"
echo "  • Deinstalacja:  $SRC_DIR/packaging/linux/uninstall.sh"
echo
warn "Wersja trybu transkrypcji: $MODE  (GPU zmienisz: odinstaluj i powtórz z --gpu)"
