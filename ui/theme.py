"""Motyw Windows XP Luna — klasyczna niebieska kolorystyka z płaskimi
polami i wypukłymi przyciskami 3D (raised).

Kolorystyka odwzorowuje domyślny motyw Luna systemu Windows XP:
- Tło okien: srebrny #ECE9D8
- Przyciski: wypukłe (raised) z obwódką 2px
- Pola tekstowe: białe z wklęsłym reliefem (sunken)
- Zaznaczenia: granat #004080
- Font: TkDefaultFont (na XP domyślnie Tahoma 8pt)
"""

import tkinter as tk
from tkinter import ttk

# ── Paleta kolorów Windows XP Luna ────────────────────────────────────
BG              = "#ECE9D8"   # 3D Face / tło okien i ramek
FIELD_BG        = "#FFFFFF"   # tło pól edycyjnych (białe)
OUT_BG          = "#FFFFFF"   # tło pola wyniku (też białe, jak notatnik)
FG              = "#000000"   # czarny tekst
FG_MUTED        = "#555555"   # przygaszony tekst (status / podpowiedzi)
BTN_BG          = "#ECE9D8"   # tło przycisków (kolor 3D Face)
BTN_ACTIVE      = "#F5F3E8"   # przycisk wciśnięty (jaśniejszy)
ACCENT          = "#004080"   # XP niebieski akcent (zaznaczenia, fokus)
BORDER          = "#ACA899"   # 3D Shadow — ciemna krawędź
ERR_FG          = "#CC0000"   # czerwony błąd
OK_FG           = "#006600"   # zielony sukces
REC_RED         = "#CC0000"   # przycisk mikrofonu (czerwony)
REC_RED_ACTIVE  = "#990000"   # ciemniejsza czerwień (hover/stop)

# Dodatkowe kolory 3D (do ręcznego ustawienia, jeśli potrzeba)
BTN_HIGHLIGHT   = "#FFFFFF"   # rozjaśnienie przycisku (górna-lewa krawędź)
BTN_SHADOW      = "#ACA899"   # cień przycisku (dolna-prawa krawędź)
BTN_DARK_SHADOW = "#716F64"   # ciemny cień


def apply_xp_theme(root):
    """Globalne opcje + styl ttk dla motywu Windows XP Luna."""
    root.configure(bg=BG)

    # ── ttk style ────────────────────────────────────────────────────
    root.option_add("*TCombobox*Listbox.background", FIELD_BG)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    style = ttk.Style(root)
    # Na Linuksie domyślnym stylem jest 'clam' — on pozwala na kolory
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Scrollbar w stylu XP
    style.configure("Vertical.TScrollbar",
                    background=BTN_BG,
                    troughcolor=BG,
                    arrowcolor=FG,
                    bordercolor=BORDER,
                    lightcolor=BTN_HIGHLIGHT,
                    darkcolor=BTN_DARK_SHADOW)
    style.map("Vertical.TScrollbar",
              background=[("active", BTN_ACTIVE)])

    style.configure("Horizontal.TScrollbar",
                    background=BTN_BG,
                    troughcolor=BG,
                    arrowcolor=FG,
                    bordercolor=BORDER,
                    lightcolor=BTN_HIGHLIGHT,
                    darkcolor=BTN_DARK_SHADOW)
    style.map("Horizontal.TScrollbar",
              background=[("active", BTN_ACTIVE)])

    # Combobox w stylu XP
    style.configure("TCombobox",
                    fieldbackground=FIELD_BG,
                    background=BTN_BG,
                    foreground=FG,
                    arrowcolor=FG,
                    bordercolor=BORDER,
                    lightcolor=BTN_HIGHLIGHT,
                    darkcolor=BTN_DARK_SHADOW,
                    padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD_BG)],
              selectbackground=[("readonly", FIELD_BG)],
              selectforeground=[("readonly", FG)],
              arrowcolor=[("active", FG)])


# Alias dla wstecznej kompatybilności — każdy import apply_dark_theme
# dostanie apply_xp_theme, żeby nie zmieniać nazwy we wszystkich importach.
apply_dark_theme = apply_xp_theme


def dark_text(parent, **kw):
    """Ramka z polem Text w stylu XP: białe tło, cienka obwódka.

    Choć nazwa mówi 'dark', to teraz zwraca pole w kolorze XP: białe tło,
    czarny tekst, sunken relief. Zachowano nazwę, by nie zmieniać importów.
    """
    frame = tk.Frame(parent, bg=BG, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT)
    opts = dict(relief=tk.SUNKEN, bd=2, bg=FIELD_BG, insertbackground=FG,
                selectbackground=ACCENT, selectforeground="#FFFFFF",
                fg=FG, font=("TkDefaultFont", 10))
    opts.update(kw)
    text = tk.Text(frame, **opts)
    sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=sb.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    return frame, text


def position_popover(popover, trigger, width, height):
    """Pozycjonuje popover DOKŁADNIE pod przyciskiem triggera, z obsługą
    przepełnienia viewportu (gdy brakuje miejsca pod spodem — otwiera się
    nad triggerem). Współdzielone przez ModelPopover i SnippetPopover."""
    sw, sh = popover.winfo_screenwidth(), popover.winfo_screenheight()
    x = trigger.winfo_rootx()
    y = trigger.winfo_rooty() + trigger.winfo_height() + 2
    if y + height > sh:
        y = trigger.winfo_rooty() - height - 2
    if y < 0:
        y = 4
    x = min(x, sw - width - 4)
    popover.geometry(f"{width}x{height}+{max(x, 4)}+{max(y, 4)}")