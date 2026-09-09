"""Kreator promptu — trzeci tryb pracy obok Standard i Mega.

Zamiast jednego pola na cały prompt, użytkownik wypełnia składowe
profesjonalnego promptu (rola, zadanie, odbiorca, format, ograniczenia),
każde z podpowiedzią, co powinno się w nim znaleźć. Tam, gdzie ma to sens,
przycisk „▾" rozwija listę gotowych elementów — rozbudowana lista jest
WBUDOWANA W OKNO (Listbox pod polem, dziecko tego panelu — nie osobne
okno Toplevel): rozwija/zwija się razem z panelem, klik w pozycję od razu
uzupełnia pole i zwija listę. Zawsze można też wpisać wartość od ręki.

Złożony szkic (compose()) trafia do tego samego potoku co tryb Standard —
model przepisuje go na dopracowany prompt.
"""

import tkinter as tk
from tkinter import ttk

from ui.theme import (BG, FG, FG_MUTED, BTN_BG, BTN_ACTIVE, ACCENT, BORDER,
                      FIELD_BG, dark_text)

# ── Gotowe elementy do wyboru (doklejane/zastępujące wartość pola) ────
ROLE_PRESETS = [
    "Doświadczony redaktor tekstów",
    "Senior programista Python",
    "Specjalista ds. marketingu i copywritingu",
    "Cierpliwy nauczyciel — tłumaczy prosto i po ludzku",
    "Analityk danych",
    "Doradca biznesowy / coach",
    "Profesjonalny tłumacz",
    "Asystent osobisty — zwięzły i konkretny",
    "Kreatywny pisarz",
]

AUDIENCE_PRESETS = [
    "Ekspert w dziedzinie",
    "Osoba nietechniczna",
    "Początkujący",
    "Zaawansowany praktyk",
    "Dziecko w wieku ok. 10 lat",
    "Zarząd / klient biznesowy",
    "Zespół programistów",
]

FORMAT_PRESETS = [
    "Zwięzłe akapity (max kilka zdań każdy)",
    "Lista wypunktowana",
    "Tabela porównawcza",
    "Instrukcja krok po kroku (numerowana)",
    "JSON",
    "Fragment kodu z komentarzami",
    "FAQ — pytania i odpowiedzi",
    "Pełny artykuł z nagłówkami",
]

CONSTRAINT_PRESETS = [
    "Maksymalnie 150 słów",
    "Maksymalnie 500 słów",
    "Ton formalny",
    "Ton luźny i przyjazny",
    "Odpowiedź po polsku",
    "Bez żargonu",
    "Tylko konkrety — bez lania wody",
    "Podaj 2–3 przykłady",
    "Na końcu zaproponuj następny krok",
]


class BuilderPanel(tk.Frame):
    """Panel pól składowych promptu (Kreator). UI bez logiki sieciowej —
    App odczytuje wartości przez get_values()/compose()."""

    def __init__(self, parent, initial=None, on_submit=None):
        """
        initial:   słownik z poprzednimi wartościami pól (z configu).
        on_submit: wywoływane po Enter w jednej z jednolinijkowych rubryk
                   (App podpina tu on_send); pole Zadanie pozostaje wielolinijkowe.
        """
        super().__init__(parent, bg=BG)
        self._on_submit = on_submit
        self._preset_band = None     # rozwinięta lista (tworzona leniwie)
        self._preset_entry = None    # pole obsługiwane przez rozwiniętą listę
        self._preset_append = False
        self._preset_btn = None      # aktywny przycisk ▾ (podświetlony)
        self._preset_list = None
        self._preset_title = None

        # 1. Rola
        self.role_entry = self._entry_field(
            self, 1, "Rola modelu",
            "kim ma być AI? (gotowe role pod ▾, możesz też wpisać własną)",
            presets=ROLE_PRESETS)

        # 2. Zadanie — wielolinijkowe, rośnie wraz z wolna przestrzenią
        self._field_label(self, 2, "Zadanie i cel",
                          "co dokładnie ma zrobić? opisz treść i materiał wejściowy")
        task_frame, self.task_text = dark_text(self, height=3, wrap=tk.WORD)
        task_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        # 3. Odbiorca + 4. Format — obok siebie (krótkie wartości)
        two = tk.Frame(self, bg=BG)
        two.pack(fill=tk.X, pady=(0, 6))
        two.grid_columnconfigure(0, weight=1)
        two.grid_columnconfigure(1, weight=1)
        left = tk.Frame(two, bg=BG)
        left.grid(row=0, column=0, sticky="new", padx=(0, 3))
        self.audience_entry = self._entry_field(
            left, 3, "Odbiorca",
            "dla kogo jest wynik?", presets=AUDIENCE_PRESETS)
        right = tk.Frame(two, bg=BG)
        right.grid(row=0, column=1, sticky="new", padx=(3, 0))
        self.format_entry = self._entry_field(
            right, 4, "Format odpowiedzi",
            "np. tabela, lista, JSON", presets=FORMAT_PRESETS)

        # 5. Ograniczenia — z listy wybiera się KILKA (doklejane po średniku)
        self.constraints_entry = self._entry_field(
            self, 5, "Ograniczenia i wymagania",
            "długość, ton, język — z ▾ dobierzesz kilka",
            presets=CONSTRAINT_PRESETS, append_presets=True)

        if initial:
            self.set_values(initial)

    # ── budowa pojedynczego pola ─────────────────────────────────────
    def _field_label(self, parent, num, title, hint):
        """Numer + nazwa pola oraz mniejsza podpowiedź pod spodem."""
        head = tk.Frame(parent, bg=BG)
        head.pack(fill=tk.X, pady=(4, 1))
        tk.Label(head, text=f"{num}. {title}", bg=BG, fg=FG,
                 font=("TkDefaultFont", 9, "bold"), anchor="w"
                 ).pack(side=tk.LEFT)
        tk.Label(head, text=f"  — {hint}", bg=BG, fg=FG_MUTED,
                 font=("TkDefaultFont", 8), anchor="w"
                 ).pack(side=tk.LEFT)

    def _entry_field(self, parent, num, title, hint, presets=None,
                     append_presets=False):
        """Etykieta + wiersz: Entry (edytowalny) i opcjonalny przycisk ▾."""
        self._field_label(parent, num, title, hint)
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, pady=(0, 2))
        entry = tk.Entry(row, bg=FIELD_BG, fg=FG, insertbackground=FG,
                         relief=tk.FLAT, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT,
                         font=("TkDefaultFont", 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        if self._on_submit:
            entry.bind("<Return>", lambda e: self._on_submit())
        if presets:
            # ▾ dopasowany wysokością do pola obok: pack(fill=Y) w rozciąga
            # dokładnie do wysokości wiersza (którą narzuca Entry); bd=0 i
            # pady=0 likwidują wewnętrzny margines, który robił go wyższym.
            btn = tk.Button(row, text="▾", width=2, bg=BTN_BG, fg=FG,
                            activebackground=BTN_ACTIVE, activeforeground=FG,
                            relief=tk.RAISED, bd=0, padx=3, pady=0,
                            font=("TkDefaultFont", 9))
            btn.pack(side=tk.LEFT, fill=tk.Y, padx=(3, 0))
            btn.config(command=lambda b=btn, e=entry, p=presets,
                                 a=append_presets, r=row, t=title:
                       self._toggle_presets(b, e, p, a, r, t))
        return entry

    # ── rozwijana lista gotowych elementów (WBUDOWANA w panel) ───────
    def _top_child(self, widget):
        """Wchodzi po masterach aż do bezpośredniego dziecka tego panelu —
        jedynie takim widgetem można użyć pack(after=…) dla listy."""
        while widget.master is not self:
            widget = widget.master
        return widget

    def _build_preset_band(self):
        """Ramka z 'combo'-listą: nagłówek (dla którego pola) + Listbox.
        Dziecko tego panelu → skaluje się z oknem i chowa razem z nim."""
        band = tk.Frame(self, bg=FIELD_BG, highlightthickness=1,
                        highlightbackground=BORDER)
        head = tk.Frame(band, bg=FIELD_BG)
        head.pack(fill=tk.X, padx=6, pady=(4, 0))
        self._preset_title = tk.Label(head, text="", bg=FIELD_BG, fg=FG_MUTED,
                                      font=("TkDefaultFont", 8), anchor="w")
        self._preset_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(head, text="zwiń ✕", command=self._hide_presets,
                  bg=BTN_BG, fg=FG_MUTED, activebackground=BTN_ACTIVE,
                  activeforeground=FG, relief=tk.RAISED, bd=0, padx=5, pady=0,
                  font=("TkDefaultFont", 8)).pack(side=tk.RIGHT)
        body = tk.Frame(band, bg=FIELD_BG)
        body.pack(fill=tk.X, padx=6, pady=(2, 4))
        scrollbar = ttk.Scrollbar(body, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._preset_list = tk.Listbox(
            body, selectmode=tk.SINGLE, activestyle="none",
            exportselection=False, bg=FIELD_BG, fg=FG,
            selectbackground=ACCENT, selectforeground="#FFFFFF",
            highlightthickness=0, relief=tk.SUNKEN, bd=2, font=("TkDefaultFont", 9),
            yscrollcommand=scrollbar.set)
        self._preset_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.config(command=self._preset_list.yview)
        # klik w pozycję = natychmiastowy wybór (bez Enter)
        self._preset_list.bind("<<ListboxSelect>>", self._pick_preset)
        return band

    def _toggle_presets(self, btn, entry, presets, append, row, title):
        """▾ = przełącznik: ten sam przycisk rozwija i zwija listę."""
        if (self._preset_band and self._preset_band.winfo_manager()
                and self._preset_entry is entry):
            self._hide_presets()
            return
        self._show_presets(btn, entry, presets, append, row, title)

    def _show_presets(self, btn, entry, presets, append, row, title):
        self._hide_presets()                      # odpinamy poprzednią listę
        if self._preset_band is None:
            self._preset_band = self._build_preset_band()
        self._preset_entry = entry
        self._preset_append = append
        self._preset_btn = btn
        btn.config(bg=ACCENT)                      # wyróżnienie aktywnego ▾
        self._preset_title.config(
            text=f"Podpowiedzi do: {title} — klik wstawia do pola")
        self._preset_list.delete(0, tk.END)
        for p in presets:
            self._preset_list.insert(tk.END, p)
        self._preset_list.config(height=min(len(presets), 7))
        current = entry.get().strip()
        for i, p in enumerate(presets):           # podświetl aktualną wartość
            if p == current:
                self._preset_list.selection_set(i)
                self._preset_list.see(i)
        # lista otwiera się pod polem (po wierszu pola na poziomie panelu)
        self._preset_band.pack(fill=tk.X, after=self._top_child(row),
                               pady=(2, 6))

    def _pick_preset(self, _event=None):
        """Klik w pozycję listy: od razu wpisz do pola i zwiń (bez Enter)."""
        if not (self._preset_list and self._preset_entry):
            return
        sel = self._preset_list.curselection()
        if not sel:
            return
        value = self._preset_list.get(sel[0])
        entry = self._preset_entry
        if self._preset_append:
            current = entry.get().strip()
            if not current:
                entry.insert(0, value)
            elif value not in [c.strip() for c in current.split(";")]:
                entry.insert(tk.END, "; " + value)
        else:
            entry.delete(0, tk.END)
            entry.insert(0, value)
        self._hide_presets()
        entry.focus_set()
        entry.icursor(tk.END)

    def _hide_presets(self):
        if self._preset_band and self._preset_band.winfo_manager():
            self._preset_band.pack_forget()
        if self._preset_btn:
            self._preset_btn.config(bg=BTN_BG)    # gaś podświetlenie ▾
        self._preset_entry = None
        self._preset_btn = None

    # ── odczyt / zapis wartości ──────────────────────────────────────
    def get_values(self):
        return {
            "role": self.role_entry.get().strip(),
            "task": self.task_text.get("1.0", tk.END).strip(),
            "audience": self.audience_entry.get().strip(),
            "format": self.format_entry.get().strip(),
            "constraints": self.constraints_entry.get().strip(),
        }

    def set_values(self, values):
        def fill(entry, value):
            entry.delete(0, tk.END)
            entry.insert(0, value or "")

        fill(self.role_entry, values.get("role"))
        fill(self.audience_entry, values.get("audience"))
        fill(self.format_entry, values.get("format"))
        fill(self.constraints_entry, values.get("constraints"))
        self.task_text.delete("1.0", tk.END)
        self.task_text.insert("1.0", values.get("task", ""))

    def compose(self):
        """Składa wypełnione pola w szkic promptu (puste pola pomijane).
        Wymagane jest tylko Zadanie — waliduje to App przed wysyłką."""
        v = self.get_values()
        parts = []
        if v["role"]:
            parts.append(f"Rola: {v['role']}.")
        if v["task"]:
            parts.append(f"Zadanie: {v['task']}")
        if v["audience"]:
            parts.append(f"Odbiorca: {v['audience']}.")
        if v["format"]:
            parts.append(f"Format odpowiedzi: {v['format']}.")
        if v["constraints"]:
            parts.append(f"Ograniczenia i wymagania: {v['constraints']}.")
        return "\n".join(parts)
