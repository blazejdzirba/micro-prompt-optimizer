"""Wyskakujący popover: uniwersalny wybór z listy (np. lista modeli w Ustawieniach).

Pozycjonowanie absolutne + rollover nad triggerem przy braku miejsca pod spodem
(zobacz ui.theme.position_popover). Uwaga: lista fragmentów NIE jest popoverem —
od v6 lives wbudowana jako widget podrzędny w głównym oknie (app.py).
"""

import tkinter as tk
from tkinter import ttk

from ui.theme import (FIELD_BG, FG, FG_MUTED, BTN_ACTIVE, ACCENT, BORDER,
                      position_popover)


class ListPopover(tk.Toplevel):
    """Uniwersalny dropdown kotwiczony DOKŁADNIE pod przyciskiem triggera.

    Zastępuje Combobox, którego lista na Linuksie potrafiła wyskoczyć w róg
    ekranu. Pozycjonowanie absolutne + obsługa przepełnienia viewportu
    (gdy brakuje miejsca pod triggerem — otwiera się nad nim).

    Używany przez: wybór modelu (Ustawienia, duża lista + filtr) oraz
    Kreator (krótkie listy gotowych elementów, bez filtra).

    Parametry opcjonalne: width/height (domyślne dla listy modeli),
    show_filter=False ukrywa pole filtra (krótkie listy).
    """
    POPUP_W = 430
    POPUP_H = 360

    def __init__(self, master, trigger, items, current=None, on_pick=None,
                 width=None, height=None, show_filter=True):
        super().__init__(master)
        self._on_pick = on_pick or (lambda _v: None)
        self._all = list(items)
        self._popup_w = width or self.POPUP_W
        self._popup_h = height or self.POPUP_H
        self.overrideredirect(True)          # bez ramek WM — czysty popover
        self.attributes("-topmost", True)
        self.configure(bg=FIELD_BG, highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT)

        # filtr po nazwie (wewnątrz popoveru, nie w panelu); opcjonalny —
        # dla krótkich list gotowych elementów nie jest potrzebny
        self.filter_var = tk.StringVar()
        pad_y = 2
        if show_filter:
            top = tk.Frame(self, bg=FIELD_BG)
            top.pack(fill=tk.X, padx=6, pady=(6, 2))
            fe = tk.Entry(top, textvariable=self.filter_var, bg=FIELD_BG, fg=FG,
                          insertbackground=FG, relief=tk.FLAT, font=("TkDefaultFont", 10))
            fe.pack(fill=tk.X, ipady=4)
            fe.bind("<KeyRelease>", lambda e: self._apply_filter())
            fe.bind("<Return>", lambda e: self._pick_current())
            fe.bind("<Down>", lambda e: (self.listbox.focus_set(), "break")[1])
            fe.bind("<Escape>", lambda e: self.close())
        else:
            pad_y = 6

        row = tk.Frame(self, bg=FIELD_BG)
        row.pack(fill=tk.BOTH, expand=True, padx=6, pady=(pad_y, 6))
        self.listbox = tk.Listbox(
            row, bg=FIELD_BG, fg=FG, selectbackground=ACCENT,
            selectforeground="#FFFFFF", activestyle="none", relief=tk.SUNKEN, bd=2,
            highlightthickness=0, exportselection=False, font=("TkDefaultFont", 10))
        lsb = ttk.Scrollbar(row, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=lsb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind("<Return>", lambda e: self._pick_current())
        self.listbox.bind("<Button-1>", lambda e: self._pick_on_click())
        self.listbox.bind("<Escape>", lambda e: self.close())

        self._render(self._all, current)
        position_popover(self, trigger, self._popup_w, self._popup_h)

        def _armed(_e):
            # grab po mapowaniu: bez niego WM (XWayland) nie dostarcza kliknięć
            self.grab_set()
            self._grab_focus()
        self.bind("<Map>", _armed)
        # klik poza popoverem = zamknij (grab przekazany, więc event trafia tutaj)
        self.bind("<Button-1>", lambda e: self.close() if e.widget is self else None)

    def _grab_focus(self):
        self.focus_force()
        self.listbox.focus_set()
        if self.listbox.size() and not self.listbox.curselection():
            self.listbox.selection_set(0)

    # -- zawartość / filtrowanie --
    def _render(self, items, select=None):
        self.listbox.delete(0, tk.END)
        for m in items:
            self.listbox.insert(tk.END, m)
        if select in items:
            i = items.index(select)
            self.listbox.selection_set(i)
            self.listbox.see(i)
        elif items:
            self.listbox.see(0)

    def _apply_filter(self):
        needle = self.filter_var.get().strip().lower()
        shown = [m for m in self._all if needle in m.lower()] if needle else self._all
        self._render(shown)

    def update_items(self, items, select=None):
        """Podmienia listę — np. gdy pełna lista modeli z API dociąga się PO
        otwarciu popoveru (modele pobierane są asynchronicznie).
        Zachowuje bieżący filtr."""
        self._all = list(items)
        needle = self.filter_var.get().strip().lower()
        shown = [m for m in self._all if needle in m.lower()] if needle else self._all
        self._render(shown, select)

    # -- wybór / zamknięcie --
    def _pick_on_click(self, _e):
        # pojedyncze kliknięcie = wybór (konwencja dropdownu)
        def _do():
            if self.winfo_exists():      # popover mógł już zniknąć (Return/Esc)
                self._pick_current()
        self.after(50, _do)

    def _pick_current(self):
        sel = self.listbox.curselection() or (
            (self.listbox.nearest(self.listbox.winfo_height() // 2),)
            if self.listbox.size() else ())
        if sel:
            value = self.listbox.get(sel[0])
            self.close()
            self._on_pick(value)

    def close(self):
        self.destroy()

