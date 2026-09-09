"""Okno ustawień: klucz API, model, prompt systemowy, biblioteka fragmentów.
Lista modeli: pobierana raz, asynchronicznie (wątkiem roboczym — wcześniej
synchroniczne get_models() zamrażało UI na czas timeoutu), a następnie
zapisywana TRWALE w configu ("lista i tak się nie zmienia"). Przycisk ↻ przy
polu modelu wymusza ponowne pobranie — gdyby użytkownik jednak chciał
świeższą listę.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import openrouter
import voicenotes
from ui.theme import (BG, FIELD_BG, FG, FG_MUTED, BTN_BG, BTN_ACTIVE,
                      ACCENT, BORDER, ERR_FG, OK_FG, dark_text)
from ui.popovers import ListPopover
from ui.dialogs import prompt_snippet_dialog


class SettingsWindow:
    """Szeroki, przewijany panel ustawień z popoverem wyboru modelu."""

    def __init__(self, app):
        self.app = app              # dostęp do config, run_async i cache modeli
        self.win = None
        self._popover = None
        self._chosen = None         # wybrany model: {"id": ...}
        self._model_ids = []        # id modeli (lista awaryjna → pełna z API)
        self._working_snippets = [] # robocza kopia biblioteki (Cancel = bez zmian)
        self._hint_label = None
        self._model_trigger = None
        self._api_key_entry = None
        self._system_prompt_text = None
        self._snip_listbox = None

    # ── cykl życia okna ──────────────────────────────────────────────
    def is_alive(self):
        """Czy okno ustawień wciąż istnieje (guard przed duplikatami okien)."""
        return bool(self.win and self.win.winfo_exists())

    def lift(self):
        if self.is_alive():
            self.win.lift()
            self.win.focus_force()

    def open(self):
        cfg = self.app.config
        win = tk.Toplevel(self.app.root)
        self.win = win
        win.title("Ustawienia")
        win.transient(self.app.root)
        win.configure(bg=BG)

        # responsywny rozmiar: 65% ekranu; mały ekran → fullscreen
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        if sw < 1100 or sh < 750:
            w, h, x, y = sw, sh, 0, 0
        else:
            w, h = int(sw * 0.65), int(sh * 0.7)
            x, y = (sw - w) // 2, (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.minsize(520, 420)

        # przyciski najpierw, przypięte na dole — zawsze widoczne
        bf = tk.Frame(win, bg=BG)
        bf.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=12)

        # obszar przewijany
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        iw = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(iw, width=e.width))
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0), pady=(16, 0))
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # Kółko myszy — zależnie od platformy: na X11 (Linux) to przyciski
        # Button-4/5, na Windows i macOS zdarzenie <MouseWheel> z deltą
        # (mac: małe wartości ±1, win: ±120). Bez tej gałęzi panel ustawień
        # był nieprzewijalny na Windows.
        import sys as _sys
        _WHEEL_EVENTS = ("<Button-4>", "<Button-5>") \
            if _sys.platform.startswith("linux") else ("<MouseWheel>",)
        if _sys.platform.startswith("linux"):
            canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        else:
            if _sys.platform == "darwin":
                canvas.bind_all("<MouseWheel>",
                                lambda e: canvas.yview_scroll(-1 * e.delta, "units"))
            else:  # Windows: delta ±120 na klik kółka
                canvas.bind_all("<MouseWheel>",
                                lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        def unbind_wheel(e):
            # <Destroy> odpala się też dla widgetów-dzieci — reaguj tylko
            # na zamknięcie samego okna.
            if e.widget is win:
                for seq in _WHEEL_EVENTS:
                    canvas.unbind_all(seq)
        win.bind("<Destroy>", unbind_wheel)

        # sekcje panelu
        self._build_api_key_section(inner)
        self._build_model_section(inner)
        self._build_system_prompt_section(inner)
        self._build_snippets_section(inner)
        self._build_voice_section(inner)

        tk.Button(bf, text="Anuluj", command=self.win.destroy, width=12,
                  bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=6, pady=2
                  ).pack(side=tk.LEFT)
        tk.Button(bf, text="Zapisz", command=self._save, width=12,
                  bg=ACCENT, fg="#FFFFFF", activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=6, pady=2
                  ).pack(side=tk.RIGHT)

    def _section(self, parent, title_text):
        tk.Label(parent, text=title_text, bg=BG, fg=FG,
                 font=("TkDefaultFont", 11, "bold"), anchor="w"
                 ).pack(fill=tk.X, padx=8, pady=(14, 2))

    # ── sekcja: klucz API ────────────────────────────────────────────
    def _build_api_key_section(self, inner):
        self._section(inner, "Klucz API OpenRouter")
        entry = tk.Entry(inner, show="*", width=60, bg=FIELD_BG, fg=FG,
                         insertbackground=FG, relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=BORDER,
                         highlightcolor=ACCENT, font=("TkDefaultFont", 10))
        entry.insert(0, self.app.config.api_key)
        entry.pack(fill=tk.X, padx=8, ipady=5)
        self._api_key_entry = entry

    # ── sekcja: model (trigger + popover + przycisk odświeżenia) ─────
    def _build_model_section(self, inner):
        self._section(inner, "Model")
        self._chosen = {"id": self.app.config.model}
        row = tk.Frame(inner, bg=BG)
        row.pack(fill=tk.X, padx=8, pady=2)
        line = tk.Frame(row, bg=BG)          # [trigger | ↻] w jednej linii
        line.pack(fill=tk.X)
        trigger = tk.Button(line, text=self._chosen["id"], bg=BTN_BG, fg=FG,
                            activebackground=BTN_ACTIVE, activeforeground=FG,
                            relief=tk.RAISED, bd=2, anchor="w", padx=8, pady=4,
                            highlightthickness=1, highlightbackground=BORDER,
                            highlightcolor=ACCENT, command=self._open_model_popover)
        trigger.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._model_trigger = trigger
        # ↻ = wymuś ponowne pobranie listy (normalnie pobiera się tylko raz)
        tk.Button(line, text="↻", width=3, command=self._refresh_models,
                  bg=BTN_BG, fg=FG_MUTED, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=4, pady=4,
                  highlightthickness=1, highlightbackground=BORDER,
                  ).pack(side=tk.LEFT, padx=(4, 0))
        self._hint_label = tk.Label(row, text="", bg=BG, fg=FG_MUTED,
                                    font=("TkDefaultFont", 8), anchor="w")
        self._hint_label.pack(fill=tk.X)

        # klik gdziekolwiek w panelu zamyka otwarty popover
        self.win.bind("<Button-1>", lambda _e: self._close_popover_if_open())

        self._start_model_load()

    def _refresh_models(self):
        """Wymusza ponowne pobranie listy modeli z API (kliknięte ↻)."""
        self.app.config.models = []
        self._close_popover_if_open()
        self._start_model_load()

    def _set_hint(self, text):
        if self._hint_label and self._hint_label.winfo_exists():
            self._hint_label.config(text=text)

    def _close_popover_if_open(self):
        if self._popover and self._popover.winfo_exists():
            self._popover.close()

    def _open_model_popover(self):
        self._close_popover_if_open()

        def on_pick(model_id):
            self._chosen["id"] = model_id
            self._model_trigger.config(text=model_id)

        self._popover = ListPopover(self.win, self._model_trigger,
                                    self._model_ids, self._chosen["id"], on_pick)

    # ── lista modeli: pobierana RAZ w tle i trzymana trwale w configu ─
    def _start_model_load(self):
        # 1) lista już pobrana kiedykolwiek wcześniej → zero sieci, od razu
        saved = self.app.config.models
        if saved:
            self._apply_model_ids(list(saved))
            self._set_hint("Kliknij, aby wybrać z listy (↻ odświeża listę modeli).")
            return

        # 2) pierwszy raz: otwieramy na liście awaryjnej, pełną dociągamy w tle
        self._set_hint("Pobieram listę modeli z OpenRouter...")
        self._model_ids = [m["id"] for m in openrouter.FALLBACK_MODELS]

        # Pobieramy po kluczu Z OKNA (użytkownik mógł go właśnie wpisać i nie
        # zapisać). Odczyt widgetu MUSI się stać na wątku UI — tkinter nie jest
        # thread-safe, wątek roboczy dostaje tylko gotową wartość.
        api_key_from_window = self._api_key_entry.get().strip()

        def work():
            models = openrouter.get_models(api_key_from_window)
            # get_models zwraca modułową listę awaryjną przy błędzie sieci —
            # takiej NIE zapisujemy na stałe (przy następnym otwarciu ponowi
            # próbę; zapis tylko dla prawdziwej odpowiedzi z API)
            return {"ids": [m["id"] for m in models],
                    "from_network": models is not openrouter.FALLBACK_MODELS}

        def ok(result):
            if not self.win.winfo_exists():
                return
            if result["from_network"]:
                self.app.config.models = result["ids"]
                self.app.config.save()
                self._apply_model_ids(result["ids"])
                self._set_hint("Kliknij, aby wybrać z listy (↻ odświeża listę modeli).")
            else:
                self._set_hint("Brak sieci — awaryjna lista modeli. Ponów przez ↻.")

        def err(_message):
            # get_models ma własny fallback, więc tu praktycznie nie trafimy
            if self.win.winfo_exists():
                self._set_hint("Użyto awaryjnej listy modeli (sprawdź sieć).")

        self.app.run_async(work, ok, err)

    def _apply_model_ids(self, model_ids):
        self._model_ids = model_ids
        # jeśli popover jest już otwarty (na liście awaryjnej) — podmień zawartość
        if self._popover and self._popover.winfo_exists():
            self._popover.update_items(self._model_ids, self._chosen["id"])

    # ── sekcja: prompt systemowy ─────────────────────────────────────
    def _build_system_prompt_section(self, inner):
        self._section(inner, "Prompt systemowy optymalizatora")
        sp_frame, text = dark_text(inner, height=10, wrap=tk.WORD)
        sp_frame.pack(fill=tk.BOTH, expand=False, padx=8, pady=2)
        text.insert("1.0", self.app.config.system_prompt)
        self._system_prompt_text = text

    # ── sekcja: biblioteka fragmentów ────────────────────────────────
    def _build_snippets_section(self, inner):
        self._section(inner, "Biblioteka fragmentów (opcjonalnie doklejane do promptu)")
        # robocza kopia — zmiany trafiają do config dopiero po "Zapisz"
        self._working_snippets = [dict(s) for s in self.app.config.snippets]

        snip_row = tk.Frame(inner, bg=BG)
        snip_row.pack(fill=tk.X, padx=8, pady=2)
        listbox = tk.Listbox(snip_row, height=5, bg=FIELD_BG, fg=FG,
                             selectbackground=ACCENT, selectforeground="#FFFFFF",
                             activestyle="none", relief=tk.SUNKEN, bd=2,
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT, exportselection=False,
                             font=("TkDefaultFont", 9))
        for s in self._working_snippets:
            listbox.insert(tk.END, s["name"])
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._snip_listbox = listbox

        btns = tk.Frame(snip_row, bg=BG)
        btns.pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btns, text="Dodaj", width=10, command=self._snip_add,
                  bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=4, pady=2
                  ).pack(fill=tk.X, pady=(0, 3))
        tk.Button(btns, text="Edytuj", width=10, command=self._snip_edit,
                  bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=4, pady=2
                  ).pack(fill=tk.X, pady=(0, 3))
        tk.Button(btns, text="Usuń", width=10, command=self._snip_delete,
                  bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=2, padx=4, pady=2
                  ).pack(fill=tk.X)

    def _snip_refresh_listbox(self):
        self._snip_listbox.delete(0, tk.END)
        for s in self._working_snippets:
            self._snip_listbox.insert(tk.END, s["name"])

    def _snip_add(self):
        picked = prompt_snippet_dialog(self.win, "Nowy fragment")
        if picked:
            name, text = picked
            # id=None — Config nada identyfikator przy zapisie (set_snippets)
            self._working_snippets.append({"id": None, "name": name, "text": text})
            self._snip_refresh_listbox()

    def _snip_edit(self):
        sel = self._snip_listbox.curselection()
        if not sel:
            return
        s = self._working_snippets[sel[0]]
        picked = prompt_snippet_dialog(self.win, "Edytuj fragment", s["name"], s["text"])
        if picked:
            s["name"], s["text"] = picked
            self._snip_refresh_listbox()

    def _snip_delete(self):
        sel = self._snip_listbox.curselection()
        if not sel:
            return
        snippet = self._working_snippets[sel[0]]
        if not tk.messagebox.askyesno(
            "Usuń fragment",
            f'Czy na pewno usunąć fragment „{snippet.get("name", "")}"?\n'
            "Tej operacji nie można cofnąć.",
            parent=self.win,
        ):
            return
        del self._working_snippets[sel[0]]
        self._snip_refresh_listbox()

    # ── notatki głosowe: zarządzanie modelami Whispera ──────────────
    def _build_voice_section(self, inner):
        self._section(inner, "Notatki głosowe (Whisper, tylko polski)")
        self._voice_busy = False
        self._voice_container = tk.Frame(inner, bg=BG)
        self._voice_container.pack(fill=tk.X, pady=(0, 2))
        self._voice_status = tk.Label(inner, text="", bg=BG, fg=FG_MUTED,
                                      font=("TkDefaultFont", 8), anchor="w",
                                      wraplength=360, justify=tk.LEFT)
        self._voice_status.pack(fill=tk.X, pady=(0, 2))
        self._rebuild_voice_rows()

    def _rebuild_voice_rows(self):
        """Przebudowuje wiersze modeli wg stanu cache (nie działa, gdy okno zamknięte)."""
        if not (self._voice_container and self._voice_container.winfo_exists()):
            return
        for child in self._voice_container.winfo_children():
            child.destroy()

        if not (voicenotes.whisper_ok() and voicenotes.sounddevice_ok()):
            tk.Label(self._voice_container,
                     text=("Pakiety opcjonalne niezainstalowane.\n"
                           f"Zainstaluj:  {voicenotes.install_hint()}"),
                     bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 9),
                     anchor="w", justify=tk.LEFT, wraplength=360
                     ).pack(fill=tk.X, pady=2)
            self._set_voice_status("Po instalacji uruchom aplikację ponownie.")
            return

        active = self.app.config.whisper_model
        btn_kw = dict(relief=tk.FLAT, padx=6, pady=0, font=("TkDefaultFont", 8),
                      activebackground=BTN_ACTIVE, activeforeground=FG)
        for m in voicenotes.WHISPER_MODELS:
            name = m["name"]
            downloaded = voicenotes.is_downloaded(name)
            is_active = name == active
            row = tk.Frame(self._voice_container, bg=BG)
            row.pack(fill=tk.X, pady=1)

            marker = "● AKTYWNY" if is_active else "○"
            tk.Label(row, text=f"{marker}  {name} ({m['size']}) — {m['desc']}",
                     bg=BG, fg=(OK_FG if is_active else FG),
                     font=("TkDefaultFont", 8), anchor="w", wraplength=240,
                     justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

            if not downloaded:
                tk.Button(row, text="Pobierz", bg=ACCENT, fg="#FFFFFF",
                          command=lambda n=name: self._voice_download(n),
                          **btn_kw).pack(side=tk.RIGHT, padx=(4, 0))
            else:
                if not is_active:
                    tk.Button(row, text="✕ usuń", bg=BTN_BG, fg=ERR_FG,
                              command=lambda n=name: self._voice_delete(n),
                              **btn_kw).pack(side=tk.RIGHT, padx=(4, 0))
                    tk.Button(row, text="Użyj", bg=BTN_BG, fg=FG,
                              command=lambda n=name: self._voice_use(n),
                              **btn_kw).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Label(self._voice_container,
                 text=f"Pliki modeli: {voicenotes.WHISPER_CACHE}",
                 bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 8),
                 anchor="w").pack(fill=tk.X, pady=(4, 0))

    def _set_voice_status(self, text, error=False):
        if self._voice_status and self._voice_status.winfo_exists():
            self._voice_status.config(text=text,
                                      fg=ERR_FG if error else FG_MUTED)

    def _voice_toggle_buttons(self, enabled):
        if not (self._voice_container and self._voice_container.winfo_exists()):
            return
        for w in self._voice_container.winfo_children():
            for b in w.winfo_children():
                if isinstance(b, tk.Button):
                    b.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _voice_download(self, name):
        """Pobieranie w tle (run_async) — synchroniczne wisiało by na UI
        nawet kilka minut przy słabnym łączu. Flaga _voice_busy blokuje
        równoległe pobrania (whisper i tak liczy jeden plik naraz)."""
        if self._voice_busy:
            return
        self._voice_busy = True
        self._voice_toggle_buttons(False)
        self._set_voice_status(
            f"Pobieranie modelu „{name}”… może potrwać kilka minut.")

        def work():
            return voicenotes.load_model(name)

        def ok(_model):
            self._voice_busy = False
            self._rebuild_voice_rows()
            self._set_voice_status(
                f"„{name}” pobrany. Aby go używać, kliknij „Użyj” przy wierszu.")
            self.app.rec_panel.refresh_model_state()

        def err(message):
            self._voice_busy = False
            self._rebuild_voice_rows()
            self._set_voice_status(f"Nie udało się pobrać „{name}”: {message}",
                                   error=True)

        self.app.run_async(work, ok, err)

    def _voice_use(self, name):
        cfg = self.app.config
        cfg.whisper_model = name
        cfg.save()                     # zapis natychmiastowy — akcja jednoklikowa
        self._rebuild_voice_rows()
        self._set_voice_status(f"Aktywny model: „{name}”.")
        self.app.rec_panel.refresh_model_state()

    def _voice_delete(self, name):
        if name == self.app.config.whisper_model:
            self._set_voice_status("Nie można usunąć aktywnego modelu — "
                                   "najpierw przełącz na inny.", error=True)
            return
        # Jeśli ten model jest aktualnie wczytany w REC, zwolnij go z pamięci
        if getattr(self.app.rec_panel, "_model_name", None) == name:
            self.app.rec_panel._model = None
            self.app.rec_panel._model_name = None
            voicenotes.free_gpu()
        voicenotes.delete_model(name)
        self._rebuild_voice_rows()
        self._set_voice_status(f"Usunięto plik modelu „{name}”.")
        self.app.rec_panel.refresh_model_state()

    # ── zapis ────────────────────────────────────────────────────────
    def _save(self):
        cfg = self.app.config
        api_key = self._api_key_entry.get().strip()
        if api_key and not api_key.startswith("sk-or-"):
            if not tk.messagebox.askyesno(
                "Nieprawidłowy format klucza",
                "Klucz API nie zaczyna się od prefiksu 'sk-or-' (standard dla OpenRouter).\n"
                "Czy na pewno chcesz zapisać taki klucz?",
                parent=self.win,
            ):
                return
        cfg.api_key = api_key
        cfg.model = self._chosen["id"]
        cfg.system_prompt = self._system_prompt_text.get("1.0", tk.END).strip()

        # Config nada id nowym wpisom, podmieni bibliotekę i usunie
        # zaznaczenie skasowanych fragmentów (wcześniej robiono to ręcznie
        # tutaj, a odpowiednie metody w Config były martwym kodem).
        cfg.set_snippets(self._working_snippets)
        self.app.selected_snippet_ids = set(cfg.selected_snippets)
        self.app.refresh_snippet_button()

        cfg.save()
        self.win.destroy()
