"""Główne okno aplikacji Micro Prompt Optimizer.

Po refaktoryzacji klasa App odpowiada wyłącznie za główny ekran (wejście,
tryby, wysyłkę, tłumaczenie, kopiowanie) i deleguje resztę do modułów:

    ui.theme      — paleta kolorów, helpery widgetów
    ui.popovers   — ListPopover (pop-up listy modeli w ustawieniach)
    ui.dialogs    — dialogi modalne
    ui.settings   — okno ustawień (w tym asynchroniczne pobieranie modeli)

Lista fragmentów NIE jest popoverem (wymaganie v6): to panel wbudowany
w główne okno (tk.Frame + Listbox w kontenerze _view) — skaluje się razem
z oknem i chowa przy minimalizacji, a klik w pozycję działa natychmiast.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk

import pyperclip

import config
import openrouter
from ui.theme import (BG, FIELD_BG, OUT_BG, FG, FG_MUTED, BTN_BG, BTN_ACTIVE,
                      ACCENT, BORDER, ERR_FG, OK_FG, REC_RED, REC_RED_ACTIVE,
                      apply_dark_theme, dark_text)
from ui.settings import SettingsWindow
from ui.builder import BuilderPanel
from ui.recorder import RecPanel

SUCCESS_MESSAGES = ("Gotowe", "Skopiowano do schowka.")

# Krótkie podpowiedzi trybów wyświetlane na pasku statusu przy zmianie trybu
MODE_HINTS = {
    "standard": "Standard: wpisz cały prompt jednym polem.",
    "mega": "Mega: model zada 3 pytania doprecyzowujące przed optymalizacją.",
    "kreator": "Kreator: złóż prompt ze składowych z podpowiedziami i gotowych list.",
    "systemowy": "Systemowy: opisz asystenta — powstanie gotowy prompt systemowy („Jesteś …”).",
}


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Micro Prompt Optimizer")
        apply_dark_theme(root)

        # Wczytaj konfigurację
        self.config = config.Config()
        self._request_in_flight = False
        self._closing = False           # [X] = koniec planowania poll()
        self._settings_window = None      # guard: tylko jedno okno ustawień

        # Rozmiar/pozycja: przywróć zapamiętaną, inaczej domyślna
        self.root.geometry(self.config.geometry or "560x720")
        self.root.minsize(480, 580)
        # zamknięcie [X] — zapamiętaj geometrię i stan Kreatora
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.selected_snippet_ids = set(self.config.selected_snippets)

        # Stan trybu Mega (pytania doprecyzowujące)
        self._qa_questions = []
        self._qa_entries = []
        self._mega_pending_prompt = None

        # Stan tłumaczenia
        self._current_pl = None
        self._current_en = None
        self._showing_en = False

        # ── Górny pasek: tytuł + przełącznik widoku REC (mikrofon) ───
        topbar = tk.Frame(root, bg=ACCENT)
        topbar.pack(fill=tk.X, padx=0, pady=0)
        tk.Label(topbar, text="MPO — mikro optymalizator promptów",
                 bg=ACCENT, fg="#FFFFFF", font=("TkDefaultFont", 9, "bold"),
                 padx=12, pady=6
                 ).pack(side=tk.LEFT)
        self.mic_button = tk.Button(topbar, text="🎤", command=self.toggle_view,
                                    bg=REC_RED, fg="#FFFFFF",
                                    activebackground=REC_RED_ACTIVE,
                                    activeforeground="#FFFFFF", relief=tk.RAISED, bd=2,
                                    padx=8, pady=1)
        self.mic_button.pack(side=tk.RIGHT)

        # ── Dwa podmieniane widoki: prompt (poniżej) ↔ REC (notatki) ─
        self._view = tk.Frame(root, bg=BG)     # widok promptu
        self._view.pack(fill=tk.BOTH, expand=True)
        self._in_rec = False
        self.rec_panel = RecPanel(root, app=self)   # pack() dopiero przy przełączeniu
        view = self._view

        # ── Układ (grid weights na wierszach ramek) ─────────────────
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=0)    # panel fragmentów (gdy pokazany: 1)
        view.grid_rowconfigure(3, weight=2)    # ramka pola wejściowego
        view.grid_rowconfigure(7, weight=7)    # ramka pola wyniku

        # Pasek trybu: Standard / Mega + wybór aktywnych fragmentów
        mode_frame = tk.Frame(view, bg=BG)
        mode_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))
        tk.Label(mode_frame, text="Tryb:", bg=BG, fg=FG_MUTED,
                 font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.mode_var = tk.StringVar(value=self.config.mode)
        tk.Radiobutton(mode_frame, text="Standard", variable=self.mode_var,
                       value="standard", command=self.on_mode_change,
                       bg=BG, fg=FG, selectcolor=FIELD_BG, activebackground=BG,
                       activeforeground=FG, font=("TkDefaultFont", 9)
                       ).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Mega", variable=self.mode_var,
                       value="mega", command=self.on_mode_change,
                       bg=BG, fg=FG, selectcolor=FIELD_BG, activebackground=BG,
                       activeforeground=FG, font=("TkDefaultFont", 9)
                       ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(mode_frame, text="Kreator", variable=self.mode_var,
                       value="kreator", command=self.on_mode_change,
                       bg=BG, fg=FG, selectcolor=FIELD_BG, activebackground=BG,
                       activeforeground=FG, font=("TkDefaultFont", 9)
                       ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(mode_frame, text="Systemowy", variable=self.mode_var,
                       value="systemowy", command=self.on_mode_change,
                       bg=BG, fg=FG, selectcolor=FIELD_BG, activebackground=BG,
                       activeforeground=FG, font=("TkDefaultFont", 9)
                       ).pack(side=tk.LEFT, padx=(6, 0))
        self.snippet_button = tk.Button(mode_frame, command=self.toggle_snippets_panel,
                                        bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE,
                                        activeforeground=FG, relief=tk.RAISED, bd=2, padx=6, pady=1,
                                        font=("TkDefaultFont", 9))
        self.snippet_button.pack(side=tk.RIGHT)
        self.refresh_snippet_button()

        # Wiersz nad polem wejścia: etykieta po lewej, Wyczyść po prawej.
        # (Przycisk NIE wchodzi do dolnego paska — przy 4 stałych przyciskach
        #  byłby ucinany na systemach z szerszą czcionką.)
        in_row = tk.Frame(view, bg=BG)
        in_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 0))
        self.in_label = tk.Label(in_row, text="Twój prompt:", bg=BG, fg=FG, anchor="w")
        self.in_label.pack(side=tk.LEFT)
        self.clear_button = tk.Button(in_row, text="Wyczyść", command=self.on_clear,
                                      bg=BTN_BG, fg=FG_MUTED, activebackground=BTN_ACTIVE,
                                      activeforeground=FG, relief=tk.RAISED, bd=2, padx=5, pady=0,
                                      font=("TkDefaultFont", 8))
        self.clear_button.pack(side=tk.RIGHT)

        # ── Panel fragmentów — WBUDOWANY w główne okno (nie popover) ──
        # Listbox jest dzieckiem kontenera _view, więc skaluje się razem
        # z oknem (pozycja/rozmieszczenie grida) i naturalnie chowa przy
        # minimalizacji. Klik w pozycję = natychmiastowe dołączenie/odłączenie
        # fragmentu (MULTIPLE + <<ListboxSelect>>), bez Enter ani „Zastosuj".
        self.snip_panel = tk.Frame(view, bg=BG, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.snip_panel.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 2))
        snip_head = tk.Frame(self.snip_panel, bg=BG)
        snip_head.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(snip_head, text="Fragmenty — klik dołącza/odłącza do promptu systemowego:",
                 bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 8),
                 anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        for label, cmd in (("wszystkie", lambda: self._set_all_snippets(True)),
                           ("żaden", lambda: self._set_all_snippets(False))):
            tk.Button(snip_head, text=label, command=cmd, bg=BTN_BG, fg=FG_MUTED,
                      activebackground=BTN_ACTIVE, activeforeground=FG, relief=tk.RAISED, bd=2,
                      padx=5, pady=0, font=("TkDefaultFont", 8)).pack(side=tk.RIGHT, padx=(4, 0))
        lb_row = tk.Frame(self.snip_panel, bg=BG)
        lb_row.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        scrollbar = ttk.Scrollbar(lb_row, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.snip_listbox = tk.Listbox(
            lb_row, selectmode=tk.MULTIPLE, activestyle="none",
            exportselection=False, height=5, bg=FIELD_BG, fg=FG,
                                relief=tk.SUNKEN, bd=2,
            selectbackground=ACCENT, selectforeground="#FFFFFF",
            highlightthickness=0, yscrollcommand=scrollbar.set,
            font=("TkDefaultFont", 9))
        self.snip_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.snip_listbox.yview)
        self.snip_listbox.bind("<<ListboxSelect>>", self._on_snippet_pick)
        self._snip_shown = []          # fragmenty widoczne w listboxie (kolejność)
        self._snip_syncing = False     # guard: programowe zaznaczanie ≠ klik
        self.snip_panel.grid_remove()  # startuje schowany; pokazuje przycisk w pasku trybu

        # Dwa zamiennie pokazywane obszary wejścia w tej samej komórce siatki:
        # pole na cały prompt (Standard/Mega) oraz panel Kreatora.
        self.input_frame, self.input_text = dark_text(view, height=4, wrap=tk.WORD)
        self.input_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(2, 4))
        self.builder_panel = BuilderPanel(view, initial=self.config.builder,
                                          on_submit=self.on_send)
        self.builder_panel.grid(row=3, column=0, sticky="nsew", padx=10, pady=(2, 4))

        # Ramka pytań doprecyzowujących (tryb Mega) — pusta i niewidoczna
        # dopóki nie przyjdą pytania z API; budowana dynamicznie.
        self.qa_frame = tk.Frame(view, bg=BG)
        self.qa_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 2))

        # Przyciski
        button_frame = tk.Frame(view, bg=BG)
        button_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=4)
        self.send_button = tk.Button(button_frame, text="Wyślij", width=12,
                                     command=self.on_send, bg=BTN_BG, fg=FG,
                                     activebackground=BTN_ACTIVE, activeforeground=FG,
                                     relief=tk.RAISED, bd=2, padx=6, pady=2)
        self.send_button.pack(side=tk.LEFT, padx=(0, 6))
        self.copy_button = tk.Button(button_frame, text="Kopiuj", width=12,
                                     command=self.on_copy, bg=BTN_BG, fg=FG,
                                     activebackground=BTN_ACTIVE, activeforeground=FG,
                                     relief=tk.RAISED, bd=2, padx=6, pady=2, state=tk.DISABLED)
        self.copy_button.pack(side=tk.LEFT, padx=(0, 6))
        self.translate_button = tk.Button(button_frame, text="Przetłumacz → EN", width=16,
                                          command=self.on_translate, bg=BTN_BG, fg=FG,
                                          activebackground=BTN_ACTIVE, activeforeground=FG,
                                          relief=tk.RAISED, bd=2, padx=6, pady=2, state=tk.DISABLED)
        self.translate_button.pack(side=tk.LEFT, padx=(0, 6))
        self.options_button = tk.Button(button_frame, text="⚙ Ustawienia",
                                        command=self.open_options, bg=BTN_BG, fg=FG,
                                        activebackground=BTN_ACTIVE, activeforeground=FG,
                                        relief=tk.RAISED, bd=2, padx=6, pady=2)
        self.options_button.pack(side=tk.RIGHT)

        out_label = tk.Label(view, text="Zoptymalizowany prompt:", bg=BG, fg=FG, anchor="w")
        out_label.grid(row=6, column=0, sticky="w", padx=12, pady=(6, 0))
        out_frame, self.output_text = dark_text(view, height=6, wrap=tk.WORD,
                                                bg=OUT_BG, state=tk.DISABLED)
        out_frame.grid(row=7, column=0, sticky="nsew", padx=10, pady=(2, 6))

        # Pasek statusu
        self.status_var = tk.StringVar(value="Gotowy")
        self.status_label = tk.Label(view, textvariable=self.status_var, anchor=tk.W,
                                     bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 9))
        self.status_label.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 6))

        # Skróty: Ctrl+Enter (globalnie) + Enter = wyślij, Shift+Enter = nowa linia
        self.root.bind("<Control-Return>", lambda e: self.on_send())
        self.root.bind("<Control-Shift-C>", lambda e: self.on_copy())
        self.input_text.bind("<Return>", lambda e: (self.on_send(), "break")[1])
        self.input_text.bind("<Shift-Return>",
                             lambda e: (self.input_text.insert(tk.INSERT, "\n"), "break")[1])

        # Pokaż właściwy obszar wejścia wg zapamiętanego trybu
        self._apply_mode_layout()
        # Pierwszy start: doprowadź użytkownika do klucza API od razu,
        # zamiast czekać na jego pierwszą nieudaną wysyłkę
        if not self.config.api_key:
            self.set_status("Podaj klucz API OpenRouter w ⚙ Ustawieniach — bez niego nie wyślesz zapytań.",
                            error=True)

    # ── przełączanie obszaru wejścia: pole vs Kreator ───────────────
    def _apply_mode_layout(self):
        """Standard/Mega/Systemowy: zwykłe pole na prompt. Kreator: panel
        składowych. Kreator jest wyższy, więc przesuwamy proporcje siatki
        na jego korzyść."""
        mode = self.mode_var.get()
        if mode == "kreator":
            self.input_frame.grid_remove()
            self.builder_panel.grid()
            self._view.grid_rowconfigure(3, weight=5)  # kreator dostaje więcej
            self._view.grid_rowconfigure(7, weight=3)  # kosztem pola wyniku
            self.in_label.config(text="Złóż prompt ze składowych:")
        else:
            self.builder_panel.grid_remove()
            self.input_frame.grid()
            self._view.grid_rowconfigure(3, weight=2)
            self._view.grid_rowconfigure(7, weight=7)
            if mode == "systemowy":
                self.in_label.config(text="Opisz asystenta (rola, zadania, styl…):")
            else:
                self.in_label.config(text="Twój prompt:")
        hint = MODE_HINTS.get(mode)
        if hint and not self._request_in_flight:
            self.set_status(hint, error=False)

    # ── status / pomocnicze ─────────────────────────────────────────
    def set_status(self, text, error=False):
        self.status_var.set(text)
        if error:
            self.status_label.config(fg=ERR_FG)
        elif any(text.startswith(m) for m in SUCCESS_MESSAGES):
            # startswith, bo do sukcesu doklejamy zużycie tokenów ("Gotowe · …")
            self.status_label.config(fg=OK_FG)
        else:
            self.status_label.config(fg=FG_MUTED)

    @staticmethod
    def _status_with_usage(base, usage):
        """Dołącza zużycie tokenów (z odpowiedzi API) do statusu sukcesu."""
        total = (usage or {}).get("total_tokens")
        if isinstance(total, (int, float)) and total > 0:
            sep = f"{int(total):,}".replace(",", "\u00a0")   # twarda spacja tysięcy
            return f"{base} · zużyte tokeny: {sep}"
        return base

    def _refresh_copy_button(self):
        """Stan 'Kopiuj' wg specyfikacji: aktywny tylko gdy wynik niepusty."""
        has_result = bool(self.output_text.get("1.0", tk.END).strip())
        self.copy_button.config(state=tk.NORMAL if has_result else tk.DISABLED)

    def refresh_snippet_button(self):
        """Licznik aktywnych fragmentów na przycisku + odbudowa listboxa
        (publiczne — woła go również okno ustawień po zapisie biblioteki)."""
        n = len(self.selected_snippet_ids)
        self.snippet_button.config(text=f"Fragmenty ({n})")
        if hasattr(self, "snip_listbox") and self.snip_panel.winfo_manager():
            self._refresh_snippet_listbox()

    def _set_output(self, text):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", text)
        self.output_text.config(state=tk.DISABLED)
        self._refresh_copy_button()

    def _build_system_prompt(self):
        """Prompt systemowy = bazowy prompt użytkownika + zaznaczone fragmenty
        z biblioteki (jeśli jakieś są aktywne)."""
        base = self.config.system_prompt
        texts = [s["text"] for s in self.config.snippets if s["id"] in self.selected_snippet_ids]
        if texts:
            base += "\n\nDodatkowe wytyczne stylu:\n" + "\n\n".join(texts)
        return base

    # ── generyczny wrapper na wątek + kolejkę (bez zamrażania GUI) ──
    # Publiczne: używa go także okno ustawień (pobieranie listy modeli).
    def run_async(self, work_fn, on_ok, on_err):
        q = queue.Queue()

        def worker():
            try:
                q.put(("ok", work_fn()))
            except Exception as e:
                q.put(("err", str(e)))

        threading.Thread(target=worker, daemon=True).start()

        def poll():
            # po rozpoczęciu zamykania okna nie planuj kolejnych cykli —
            # callbacki dotykałyby niszczonych widgetów (TclError)
            if self._closing:
                return
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                self.root.after(100, poll)
                return
            if self._closing:          # odpowiedź mogła minąć się z [X]
                return
            if kind == "ok":
                on_ok(payload)
            else:
                on_err(payload)

        self.root.after(100, poll)

    # ── tryb: Standard / Mega / Kreator ─────────────────────────────
    def on_mode_change(self):
        # wychodząc z Kreatora zapamiętaj wypełnione pola
        if self.config.mode == "kreator":
            self.config.builder = self.builder_panel.get_values()
        self.config.mode = self.mode_var.get()
        self.config.save()
        self._reset_mega_state()
        self._apply_mode_layout()

    def _reset_mega_state(self):
        self._qa_questions = []
        self._qa_entries = []
        self._mega_pending_prompt = None
        for child in self.qa_frame.winfo_children():
            child.destroy()
        if not self._request_in_flight:
            self.send_button.config(text="Wyślij")

    def _build_qa_frame(self, questions):
        for child in self.qa_frame.winfo_children():
            child.destroy()
        self._qa_entries = []
        tk.Label(self.qa_frame, text="Doprecyzuj (opcjonalnie) i kliknij dalej:",
                 bg=BG, fg=FG_MUTED, font=("TkDefaultFont", 9), anchor="w"
                 ).pack(fill=tk.X, pady=(2, 2))
        for q in questions:
            tk.Label(self.qa_frame, text=q, bg=BG, fg=FG, anchor="w",
                     wraplength=520, justify=tk.LEFT, font=("TkDefaultFont", 9)
                     ).pack(fill=tk.X, pady=(4, 0))
            entry = tk.Entry(self.qa_frame, bg=FIELD_BG, fg=FG, insertbackground=FG,
                             relief=tk.FLAT, highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=ACCENT,
                             font=("TkDefaultFont", 10))
            entry.pack(fill=tk.X, ipady=3, pady=(1, 0))
            self._qa_entries.append(entry)

    # ── wysyłka ──────────────────────────────────────────────────────
    def on_send(self):
        if self._request_in_flight:
            return  # nie dubluj żądań
        mode = self.mode_var.get()

        if mode == "mega" and self._qa_questions:
            self._submit_mega_answers()
            return

        if mode == "kreator":
            values = self.builder_panel.get_values()
            if not values["task"]:
                self.set_status("Kreator: wypełnij przynajmniej pole „Zadanie”.",
                                error=True)
                return
            if not self.config.api_key:
                self.set_status("Brak klucza API. Ustaw go w Opcjach.", error=True)
                return
            # zapamiętaj pola na następny raz i wyślij złożony szkic
            # do tego samego potoku optymalizacji co tryb Standard
            self.config.builder = values
            self.config.save()
            self._run_optimize(self.builder_panel.compose())
            return

        user_prompt = self.input_text.get("1.0", tk.END).strip()
        if not user_prompt:
            if mode == "systemowy":
                self.set_status("Opisz asystenta — czym ma się zajmować i jak ma odpowiadać.",
                                error=True)
            else:
                self.set_status("Prompt nie może być pusty.", error=True)
            return
        if not self.config.api_key:
            self.set_status("Brak klucza API. Ustaw go w Opcjach.", error=True)
            return

        if mode == "mega":
            self._mega_pending_prompt = user_prompt
            self._start_mega_questions(user_prompt)
        elif mode == "systemowy":
            self._run_create_system_prompt(user_prompt)
        else:
            self._run_optimize(user_prompt)

    def _run_optimize(self, user_prompt):
        self._request_in_flight = True
        self.send_button.config(state=tk.DISABLED, text="Wysyłanie...")
        self.copy_button.config(state=tk.DISABLED)
        self.translate_button.config(state=tk.DISABLED)
        self.set_status("Wysyłanie...", error=False)

        system_prompt = self._build_system_prompt()
        model = self.config.model
        api_key = self.config.api_key

        def work():
            return openrouter.optimize_prompt(api_key, model, system_prompt, user_prompt,
                                              with_usage=True)

        self.run_async(work, self._on_optimize_ok, self._on_async_err)

    # ── tryb Systemowy: opis asystenta -> gotowy prompt systemowy ────
    def _run_create_system_prompt(self, description):
        self._request_in_flight = True
        self.send_button.config(state=tk.DISABLED, text="Tworzę...")
        self.copy_button.config(state=tk.DISABLED)
        self.translate_button.config(state=tk.DISABLED)
        self.set_status("Tworzę prompt systemowy...", error=False)

        model = self.config.model
        api_key = self.config.api_key

        def work():
            return openrouter.create_system_prompt(api_key, model, description,
                                                   with_usage=True)

        self.run_async(work, self._on_optimize_ok, self._on_async_err)

    def _start_mega_questions(self, user_prompt):
        self._request_in_flight = True
        self.send_button.config(state=tk.DISABLED, text="Generuję pytania...")
        self.set_status("Generuję pytania doprecyzowujące...", error=False)

        api_key = self.config.api_key
        model = self.config.model

        def work():
            return openrouter.generate_questions(api_key, model, user_prompt)

        self.run_async(work, self._on_questions_ok, self._on_async_err)

    def _on_questions_ok(self, questions):
        self._request_in_flight = False
        self.send_button.config(state=tk.NORMAL)
        if not questions:
            # model nie zwrócił pytań — nie blokuj, po prostu zoptymalizuj wprost
            self.set_status("Model nie zwrócił pytań — optymalizuję wprost.", error=False)
            self._run_optimize(self._mega_pending_prompt)
            return
        self._qa_questions = questions
        self._build_qa_frame(questions)
        self.send_button.config(text="Generuj finalny prompt")
        self.set_status("Odpowiedz na pytania (opcjonalnie) i kliknij dalej.", error=False)

    def _submit_mega_answers(self):
        answers = [e.get().strip() for e in self._qa_entries]
        qa_pairs = list(zip(self._qa_questions, answers))
        user_prompt = self._mega_pending_prompt

        self._request_in_flight = True
        self.send_button.config(state=tk.DISABLED, text="Wysyłanie...")
        self.copy_button.config(state=tk.DISABLED)
        self.translate_button.config(state=tk.DISABLED)
        self.set_status("Generuję finalny prompt...", error=False)

        system_prompt = self._build_system_prompt()
        model = self.config.model
        api_key = self.config.api_key

        def work():
            return openrouter.optimize_prompt_mega(
                api_key, model, system_prompt, user_prompt, qa_pairs, with_usage=True)

        self.run_async(work, self._on_optimize_ok, self._on_async_err)

    def _on_optimize_ok(self, result):
        self._request_in_flight = False
        self._reset_mega_state()
        # warstwa API może zwrócić (treść, usage) albo samą treść
        text, usage = result if isinstance(result, tuple) else (result, {})
        self._current_pl = text
        self._current_en = None
        self._showing_en = False
        self._set_output(text)
        self.send_button.config(state=tk.NORMAL, text="Wyślij")
        self.translate_button.config(state=tk.NORMAL, text="Przetłumacz → EN")
        self.set_status(self._status_with_usage("Gotowe", usage), error=False)

    def _on_async_err(self, message):
        self._request_in_flight = False
        # Przywróć etykietę przycisku adekwatną do stanu (pytania mogły już przyjść)
        label = "Generuj finalny prompt" if self._qa_questions else "Wyślij"
        self.send_button.config(state=tk.NORMAL, text=label)
        self.set_status(message, error=True)
        self._refresh_copy_button()

    # ── tłumaczenie wyniku na angielski (bez zbędnych wywołań API) ──
    def on_translate(self):
        if self._current_pl is None:
            return
        if self._showing_en:
            self._set_output(self._current_pl)
            self._showing_en = False
            self.translate_button.config(text="Przetłumacz → EN")
            return
        if self._current_en is not None:
            self._set_output(self._current_en)
            self._showing_en = True
            self.translate_button.config(text="Pokaż PL")
            return

        self.translate_button.config(state=tk.DISABLED, text="Tłumaczę...")
        self.set_status("Tłumaczę na angielski...", error=False)

        api_key = self.config.api_key
        model = self.config.model
        text = self._current_pl

        def work():
            return openrouter.translate_to_english(api_key, model, text, with_usage=True)

        def ok(result):
            translated, usage = result if isinstance(result, tuple) else (result, {})
            self._current_en = translated
            self._showing_en = True
            self._set_output(translated)
            self.translate_button.config(state=tk.NORMAL, text="Pokaż PL")
            self.set_status(self._status_with_usage("Gotowe", usage), error=False)

        def err(message):
            self.translate_button.config(state=tk.NORMAL, text="Przetłumacz → EN")
            self.set_status(message, error=True)

        self.run_async(work, ok, err)

    # ── czyszczenie pól + zamknięcie aplikacji ──────────────────────
    def on_clear(self):
        """Czyści pole wejścia (lub pola Kreatora), wynik i stan tłumaczenia."""
        if self.mode_var.get() == "kreator":
            self.builder_panel.set_values({})
            # persystencja spójna z on_close: bez tego stare wartości pól
            # wracały po restarcie aplikacji
            self.config.builder = {}
            self.config.save()
        else:
            self.input_text.delete("1.0", tk.END)
        self._set_output("")
        self._current_pl = None
        self._current_en = None
        self._showing_en = False
        self.translate_button.config(state=tk.DISABLED, text="Przetłumacz → EN")
        self._reset_mega_state()
        self.set_status("Wyczyszczono.")

    def on_close(self):
        """[X] okna: zapamiętaj geometrię i wypełnione pola Kreatora."""
        self._closing = True   # pętla poll() przestaje planować cykle
        if self.mode_var.get() == "kreator":
            self.config.builder = self.builder_panel.get_values()
        self.config.geometry = self.root.geometry()
        self.config.save()
        self.root.destroy()

    # ── kopiowanie ──────────────────────────────────────────────────
    def on_copy(self):
        result = self.output_text.get("1.0", tk.END).strip()
        if not result:
            return
        try:
            pyperclip.copy(result)
            self.set_status("Skopiowano do schowka.", error=False)
        except Exception:
            self.set_status("Nie udało się skopiować do schowka.", error=True)

    # ── panel fragmentów (widget wbudowany w główne okno) ──────────
    def toggle_snippets_panel(self):
        """Przycisk paska trybu pokazuje/chowa wbudowany panel fragmentów.
        Chowa = grid_remove + waga wiersza na 0 (inaczej pusty wiersz
        z wagą>0 zjadałby miejsce)."""
        if self.snip_panel.winfo_manager():
            self.snip_panel.grid_remove()
            self._view.grid_rowconfigure(2, weight=0)
        else:
            self._refresh_snippet_listbox()
            self.snip_panel.grid()
            self._view.grid_rowconfigure(2, weight=1)

    def _refresh_snippet_listbox(self):
        """Odbudowuje zawartość listboxa wg biblioteki z configu i zaznacza
        pozycje aktywne (sync przy pokazaniu panelu i po zapisie ustawień)."""
        self._snip_syncing = True
        try:
            self.snip_listbox.delete(0, tk.END)
            self._snip_shown = list(self.config.snippets)
            for s in self._snip_shown:
                preview = " ".join(s["text"].split())
                preview = preview[:60] + "…" if len(preview) > 60 else preview
                self.snip_listbox.insert(tk.END, f"{s['name']}  —  {preview}")
            for i, s in enumerate(self._snip_shown):
                if s["id"] in self.selected_snippet_ids:
                    self.snip_listbox.selection_set(i)
        finally:
            self._snip_syncing = False

    def _on_snippet_pick(self, _event=None):
        """Klik w pozycję listy = natychmiastowy wybór (toggle) i zapis —
        bez Enter ani przycisku „Zastosuj" (wymaganie: wstawienie od kliku)."""
        if self._snip_syncing:
            return
        self._apply_snippet_selection(
            self.snip_listbox.curselection())

    def _apply_snippet_selection(self, indices):
        """Jedyny punkt zapisu zaznaczenia: zbiór w pamięci + config + plik
        + licznik na przycisku (za jednym zamachem, żeby nic się nie rozjechało)."""
        self.selected_snippet_ids = {self._snip_shown[i]["id"] for i in indices}
        # zapis w kolejności biblioteki (deterministyczny config, ułatwia diff)
        self.config.selected_snippets = [
            s["id"] for s in self._snip_shown
            if s["id"] in self.selected_snippet_ids]
        self.config.save()
        self.refresh_snippet_button()

    def _set_all_snippets(self, value):
        """Przyciski „wszystkie"/„żaden" w nagłówku panelu."""
        self._apply_snippet_selection(
            range(len(self._snip_shown)) if value else ())
        self._refresh_snippet_listbox()

    # ── ustawienia (szeroki panel — osobny moduł ui.settings) ───────
    def open_options(self):
        # guard: bez tego każdy klik w ⚙ otwierał KOLEJNE okno na stosie
        if self._settings_window and self._settings_window.is_alive():
            self._settings_window.lift()
            return
        self._settings_window = SettingsWindow(self)
        self._settings_window.open()

    # ── przełączanie widoków: prompt ↔ REC (notatki głosowe) ────────
    def toggle_view(self):
        if not self._in_rec:
            self._in_rec = True
            self._view.pack_forget()
            self.rec_panel.pack(fill=tk.BOTH, expand=True)
            self.mic_button.config(text="← Prompt",
                                   font=("TkDefaultFont", 9, "bold"))
            self.rec_panel.on_show()
        else:
            self._in_rec = False
            self.rec_panel.pack_forget()
            self._view.pack(fill=tk.BOTH, expand=True)
            self.mic_button.config(text="🎤", font=("TkDefaultFont", 10))

    def use_transcript_as_prompt(self, text):
        """Wstawia transkrypcję do pola wejścia i wraca do widoku promptu."""
        if self.mode_var.get() == "kreator":
            # w Kreatorze notatka trafia do pola zadania
            self.builder_panel.task_text.delete("1.0", tk.END)
            self.builder_panel.task_text.insert("1.0", text)
        else:
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", text)
        if self._in_rec:
            self.toggle_view()
        self.root.focus_force()
