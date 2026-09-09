"""Widok notatek głosowych (REC) — nagrywanie z mikrofonu i transkrypcja
Whisperem, wyłącznie po polsku.

Panel przełączany czerwonym 🎤 w prawym górnym rogu głównego okna.
Logika stoi w module voicenotes (opcjonalne pakiety, leniwe importy) —
panel sam nie importuje nic ciężkiego przy starcie aplikacji.

Stany modelu:
- pakiety niezainstalowane  → komunikat z komendą pip install, REC nieaktywne
- model niepobrany          → wskazanie do sekcji Ustawień, REC nieaktywne
- model pobrany             → leniwe wczytanie w tle przy pierwszym wejściu,
                              potem REC gotowe
"""

import time
import tkinter as tk

import pyperclip

import voicenotes
from ui.theme import (BG, FG, FG_MUTED, BTN_BG, BTN_ACTIVE, ACCENT,
                      ERR_FG, OK_FG, REC_RED, REC_RED_ACTIVE, dark_text)

# Górny limit nagrania: bufor trzymany jest w RAM (~230 MB / 100 min),
# dlatego dłuższe sesje ucinamy z komunikatem. Notatka promptowa i tak
# rzadko przekracza kilka minut.
MAX_RECORD_SECONDS = 15 * 60


class RecPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._model = None
        self._model_name = None
        self._loading = False
        self._recording = False
        self._record_start = 0.0
        self._stream = None
        self._audio = []
        self._np = None                 # numpy po leniwym imporcie
        self._last_text = ""

        # ── wiersz informacji o modelu + przystawka do Ustawień ──────
        info = tk.Frame(self, bg=BG)
        info.pack(fill=tk.X, padx=12, pady=(2, 0))
        self.model_var = tk.StringVar(value="Whisper: …")
        tk.Label(info, textvariable=self.model_var, bg=BG, fg=FG_MUTED,
                 font=("TkDefaultFont", 9), anchor="w").pack(side=tk.LEFT)
        tk.Button(info, text="⚙ modele", command=self.app.open_options,
                  bg=BTN_BG, fg=FG_MUTED, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=6, pady=0,
                  font=("TkDefaultFont", 8)).pack(side=tk.RIGHT)

        # ── wielki przycisk nagrywania ───────────────────────────────
        self.rec_button = tk.Button(
            self, text="● REC", command=self.toggle_recording,
            bg=REC_RED, fg="#FFFFFF", activebackground=REC_RED_ACTIVE,
            activeforeground="#FFFFFF", disabledforeground="#7A7A7A",
            relief=tk.RAISED, bd=2, font=("TkDefaultFont", 13, "bold"), pady=6)
        self.rec_button.pack(fill=tk.X, padx=60, pady=(12, 4))

        # ── status (także timer nagrania) ────────────────────────────
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(self, textvariable=self.status_var,
                                     bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 9),
                                     anchor="center", justify=tk.CENTER, wraplength=500)
        self.status_label.pack(fill=tk.X, padx=12, pady=(0, 4))

        # Przycisk „Pobierz model" — ukryty; pojawia się dopiero, gdy model
        # jest wybrany, ale jeszcze niepobrany (pobieranie = akcja użytkownika,
        # NIE zdarza się przy instalacji ani starcie aplikacji).
        self.dl_button = tk.Button(self, text="", command=self._download_model,
                                   bg=ACCENT, fg="#FFFFFF",
                                   activebackground=BTN_ACTIVE,
                                   activeforeground="#FFFFFF", relief=tk.RAISED, bd=2,
                                   padx=10, pady=2)

        # ── transkrypcja ─────────────────────────────────────────────
        tk.Label(self, text="Transkrypcja:", bg=BG, fg=FG, anchor="w"
                 ).pack(fill=tk.X, padx=12, pady=(6, 0))
        self.output_frame, self.output_text = dark_text(self, height=6, wrap=tk.WORD)
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 6))

        btns = tk.Frame(self, bg=BG)
        btns.pack(fill=tk.X, padx=12, pady=(0, 10))
        self.copy_button = tk.Button(btns, text="📋 Kopiuj", command=self.on_copy,
                                     bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                                     activeforeground=FG, relief=tk.RAISED, bd=2, padx=10, pady=2,
                                     state=tk.DISABLED)
        self.copy_button.pack(side=tk.LEFT, padx=(0, 6))
        self.use_button = tk.Button(btns, text="➜ Użyj jako prompt", command=self.on_use,
                                    bg=ACCENT, fg="#FFFFFF", activebackground=BTN_ACTIVE,
                                    activeforeground="#FFFFFF", relief=tk.RAISED, bd=2, padx=10, pady=2,
                                    state=tk.DISABLED)
        self.use_button.pack(side=tk.LEFT)

    # ── wywoływane po przełączeniu na ten widok ──────────────────────
    def on_show(self):
        self.refresh_model_state()

    # ── stan modelu / dostępności pakietów ───────────────────────────
    def refresh_model_state(self):
        """Odświeża etykiety i aktywność REC — wołać po wejściu w widok
        oraz po każdej zmianie modeli w Ustawieniach."""
        if not self.winfo_exists():
            return
        if not (voicenotes.whisper_ok() and voicenotes.sounddevice_ok()):
            self.dl_button.pack_forget()
            self.model_var.set("Whisper: pakiety niezainstalowane")
            self.rec_button.config(state=tk.DISABLED)
            self._set_status(
                "Pakiety głosowe niezainstalowane (od v7 są wymagane w requirements.txt).\n"
                f"Zainstaluj:  pip install -r requirements.txt\n"
                "(na GPU NVIDIA doinstaluj torch z CUDA — patrz README)",
                error=True)
            return

        want = self.app.config.whisper_model
        if not voicenotes.is_downloaded(want):
            self.model_var.set(f"Whisper: {want} — NIEPOBRANY")
            self.rec_button.config(state=tk.DISABLED)
            info = next((m for m in voicenotes.WHISPER_MODELS
                         if m["name"] == want), None)
            size = info["size"] if info else ""
            self.dl_button.config(
                state=tk.NORMAL,
                text=f"📥 Pobierz model {want} ({size}) — tylko raz")
            self.dl_button.pack(after=self.status_label, fill=tk.X,
                                padx=60, pady=(0, 4))
            self._set_status(
                f"Model „{want}” nie jest pobrany — do rozpoczęcia nagrywania\n"
                "potrzebny jest jednorazowy download (albo pobierz z ⚙ Ustawień → „Notatki głosowe”).",
                error=True)
            return
        self.dl_button.pack_forget()

        if self._model is not None and self._model_name == want:
            self.model_var.set(f"Whisper: {want} ✓ gotowy")
            self.rec_button.config(state=tk.NORMAL)
            if not self._recording:
                self._set_status("Gotowy — kliknij REC i mów po polsku.")
            return

        # model pobrany, ale nie w pamięci (albo zmieniono aktywny)
        self.model_var.set(f"Whisper: {want} ✓ pobrany")
        self._ensure_model_loaded(want)

    def _download_model(self):
        """Jednorazowe pobranie modelu prosto z widoku REC (download jest
        wymuszany dopiero, gdy użytkownik chce robić notatki — nie przy
        instalacji ani starcie aplikacji)."""
        if self._loading:            # pobieranie/wczytywanie już trwa
            return
        want = self.app.config.whisper_model
        self._loading = True
        self.dl_button.config(state=tk.DISABLED,
                              text=f"📥 Pobieranie {want}…")
        self.rec_button.config(state=tk.DISABLED)
        self._set_status(f"Pobieranie modelu „{want}”…\n(przy 400+ MB i wolnym łączu to chwilę potrwa)")

        def work():
            return voicenotes.load_model(want)

        def ok(model):
            self._loading = False
            if not self.winfo_exists():
                return
            # podmianka aktywnego modelu → zwolnij VRAM po starym
            if self._model is not None and self._model_name != want:
                self._model = None
                voicenotes.free_gpu()
            self._model, self._model_name = model, want
            self.dl_button.config(state=tk.NORMAL)
            self.refresh_model_state()       # przełączy w stan „gotowy"

        def err(message):
            self._loading = False
            if self.winfo_exists():
                self.dl_button.config(
                    state=tk.NORMAL,
                    text=f"📥 Spróbuj jeszcze raz — pobierz {want}")
                self._set_status(f"Nie udało się pobrać: {message}", error=True)

        self.app.run_async(work, ok, err)

    def _ensure_model_loaded(self, want):
        """Leniwe wczytanie POBRANEGO modelu do pamięci — w tle, żeby UI
        nie stało. Wołane z refresh_model_state, gdy model jest na dysku,
        ale nie w self._model (albo użytkownik zmienił aktywny model)."""
        if self._loading:
            return
        self._loading = True
        self.rec_button.config(state=tk.DISABLED)
        self._set_status(f"Wczytuję model {want} do pamięci…\n(za pierwszym razem kilka sekund)")

        def work():
            return voicenotes.load_model(want)

        def ok(model):
            self._loading = False
            if not self.winfo_exists():
                return
            # podmianka aktywnego modelu → zwolnij VRAM po starym
            if self._model is not None and self._model_name != want:
                self._model = None
                voicenotes.free_gpu()
            self._model, self._model_name = model, want
            self.model_var.set(f"Whisper: {want} ✓ gotowy")
            self.rec_button.config(state=tk.NORMAL)
            self._set_status("Gotowy — kliknij REC i mów po polsku.")

        def err(message):
            self._loading = False
            if self.winfo_exists():
                self.model_var.set(f"Whisper: {want} — błąd wczytywania")
                self.rec_button.config(state=tk.DISABLED)
                self._set_status(f"Nie udało się wczytać modelu: {message}",
                                 error=True)

        self.app.run_async(work, ok, err)

    def _set_status(self, text, error=False):
        self.status_var.set(text)
        self.status_label.config(fg=ERR_FG if error else FG_MUTED)

    # ── nagrywanie ───────────────────────────────────────────────────
    def toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        try:
            import sounddevice as sd
            import numpy as np
            self._np = np
        except Exception as e:
            self._set_status(f"Brak sounddevice/numpy: {e}", error=True)
            return

        self._audio = []

        def callback(indata, frames, t, status):
            if self._recording:
                self._audio.append(indata.copy())

        try:
            self._stream = sd.InputStream(samplerate=16000, channels=1,
                                          dtype="float32", callback=callback)
            self._stream.start()
        except Exception as e:
            self._set_status(f"Nie mogę otworzyć mikrofonu: {e}", error=True)
            return

        self._recording = True
        self._record_start = time.time()
        self.rec_button.config(text="■ STOP", bg=REC_RED_ACTIVE)
        self._tick()

    def _tick(self):
        """Minutnik nagrania co 0,5 s (+ watchdog limitu MAX_RECORD_SECONDS)."""
        if not self._recording or not self.winfo_exists():
            return
        s = int(time.time() - self._record_start)
        if s >= MAX_RECORD_SECONDS:
            self._stop_recording(
                extra_status=f"auto-stop po limicie {MAX_RECORD_SECONDS // 60} min")
            return
        self._set_status(f"Nagrywanie… {s // 60}:{s % 60:02d}")
        self.after(500, self._tick)

    def _stop_recording(self, extra_status=""):
        if not self._recording:
            return
        self._recording = False
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        self._stream = None
        self.rec_button.config(text="● REC", bg=REC_RED)

        if not self._audio:
            self._set_status("Puste nagranie — mikrofon nic nie zarejestrował.", error=True)
            return

        audio = self._np.concatenate(self._audio, axis=0).flatten()
        self._audio = []
        duration = len(audio) / 16000.0
        if duration < 0.3:
            self._set_status("Nagranie zbyt krótkie (<0,3 s) — spróbuj ponownie.",
                             error=True)
            return

        if self._model is None:
            # obrona in-depth: REC bez wczytanego modelu (np. błąd ścieżki
            # wczytywania) — NIE wywołuj transcribe(None) (bug 'NoneType'
            # object has no attribute transcribe), tylko wczytaj ponownie.
            self._set_status(
                "Model nie jest jeszcze wczytany — wczytuję, spróbuj nagrać ponownie.",
                error=True)
            self._ensure_model_loaded(self.app.config.whisper_model)
            return

        self._set_status(f"Transkrybuję {duration:.0f} s nagrania…{extra_status}")
        self.rec_button.config(state=tk.DISABLED)
        model = self._model

        def work():
            return voicenotes.transcribe(model, audio)

        def ok(text):
            if not self.winfo_exists():
                return
            self.rec_button.config(state=tk.NORMAL)
            if not text:
                self._set_status("Nic nie usłyszałem — spróbuj mówić głośniej i bliżej mikrofonu.",
                                 error=True)
                return
            self._last_text = text
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", text)
            self.copy_button.config(state=tk.NORMAL)
            self.use_button.config(state=tk.NORMAL)
            self.status_label.config(fg=OK_FG)
            self._set_status("Gotowe — transkrypcja poniżej.")

        def err(message):
            if self.winfo_exists():
                self.rec_button.config(state=tk.NORMAL)
                self._set_status(f"Błąd transkrypcji: {message}", error=True)

        self.app.run_async(work, ok, err)

    # ── akcje na transkrypcji ────────────────────────────────────────
    def on_copy(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            return
        try:
            pyperclip.copy(text)
            self.status_label.config(fg=OK_FG)
            self._set_status("Skopiowano do schowka.")
        except Exception:
            self._set_status("Nie udało się skopiować do schowka.", error=True)

    def on_use(self):
        """Gwóźdź integracji: transkrypcja → pole promptu i powrót do widoku."""
        text = self.output_text.get("1.0", tk.END).strip()
        if text:
            self.app.use_transcript_as_prompt(text)
