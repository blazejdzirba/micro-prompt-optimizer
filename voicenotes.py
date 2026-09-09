"""Logika notatek głosowych: nagrywanie (sounddevice) + transkrypcja Whisper.

WAŻNE projektowo: pakiety openai-whisper, sounddevice i numpy są OPCJONALNE
i importowane LENIWIE (sam import whisper = import torch = kilka sekund i
~1 GB pamięci). Reszta aplikacji musi działać bez nich — stąd wszystkie
sprawdzenia przez whisper_ok()/sounddevice_ok() przed użyciem.

Modele trzymane są w domyślnym cache Whispera (~/.cache/whisper), więc
zarządzanie (pobierz/usuń) to operacje na plikach {nazwa}.pt.
"""

import os

WHISPER_CACHE = os.path.expanduser("~/.cache/whisper")
DEFAULT_MODEL = "small"
LANGUAGE = "pl"          # język na sztywno — użytkownik notuje po polsku

# Medium i large pomięte świadomie: na GTX 1650 4GB fp32 (patrz fp16=False
# niżej) medium przestaje mieścić się sensownie, a large to ~6 GB VRAM.
WHISPER_MODELS = [
    {"name": "tiny",   "size": "~75 MB",
     "desc": "najszybszy, ale sporo błędów — raczej do testów"},
    {"name": "base",   "size": "~140 MB",
     "desc": "lekki; sensowna jakość do krótkich notatek"},
    {"name": "small",  "size": "~460 MB",
     "desc": "POLECANy — najlepsza jakość mieszcząca się w GTX 1650 4GB"},
    {"name": "medium", "size": "~1.4 GB",
     "desc": "za ciężki dla GTX 1650 4GB (wolny / niestabilny)"},
]


# ── dostępność pakietów (bez błędów przy braku) ─────────────────────
def whisper_ok():
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


def sounddevice_ok():
    try:
        import sounddevice  # noqa: F401
        return True
    except (ImportError, OSError):
        # OSError: moduł jest, ale brak libportaudio w systemie
        return False


def install_hint():
    return "pip install openai-whisper sounddevice"


# ── zarządzanie plikami modeli ───────────────────────────────────────
def model_path(name):
    return os.path.join(WHISPER_CACHE, f"{name}.pt")


def is_downloaded(name):
    return os.path.isfile(model_path(name))


def delete_model(name):
    """Usuwa plik modelu z cache. Zwraca True, gdy coś usunięto."""
    path = model_path(name)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# ── ładowanie i transkrypcja (wołać wyłącznie z wątku roboczego!) ────
def load_model(name):
    """Wczytuje model do pamięci; przy braku pliku POBIERA go z sieci
    (dlatego nigdy na wątku UI). Whisper sam wykrywa GPU (CUDA)."""
    import whisper
    return whisper.load_model(name)


def transcribe(model, audio_np, language=LANGUAGE):
    """audio_np: float32 16 kHz mono (sounddevice domyślnie tak oddaje).
    fp16=False przejęte z poprzedniej wersji narzędzia — na kartach NVIDIA
    potrafiło bez tego wyrzucać NaN w wynikach; fp32 na small/base i tak
    jest szybkie na GTX 1650."""
    result = model.transcribe(audio_np, language=language, fp16=False)
    return (result.get("text") or "").strip()


def free_gpu():
    """Zwalnia cache VRAM po zmianie modelu (bez twardego importu torcha)."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
