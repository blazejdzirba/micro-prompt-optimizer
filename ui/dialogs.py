"""Małe dialogi modalne aplikacji."""

import tkinter as tk

from ui.theme import BG, FIELD_BG, FG, BTN_BG, BTN_ACTIVE, ACCENT, BORDER, dark_text


def prompt_snippet_dialog(parent, title, name="", text=""):
    """Mały modal do dodania/edycji jednego fragmentu w Ustawieniach.
    Zwraca (nazwa, treść) albo None gdy anulowano / pola puste."""
    result = {"value": None}
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=BG)
    dlg.transient(parent)
    dlg.geometry("420x360")
    dlg.grab_set()

    tk.Label(dlg, text="Nazwa:", bg=BG, fg=FG, anchor="w").pack(fill=tk.X, padx=10, pady=(10, 0))
    name_entry = tk.Entry(dlg, bg=FIELD_BG, fg=FG, insertbackground=FG, relief=tk.FLAT,
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=ACCENT, font=("TkDefaultFont", 10))
    name_entry.insert(0, name)
    name_entry.pack(fill=tk.X, padx=10, pady=(2, 6), ipady=4)

    tk.Label(dlg, text="Treść fragmentu:", bg=BG, fg=FG, anchor="w").pack(fill=tk.X, padx=10)
    text_frame, text_widget = dark_text(dlg, height=8, wrap=tk.WORD)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))
    text_widget.insert("1.0", text)

    def do_ok():
        n = name_entry.get().strip()
        t = text_widget.get("1.0", tk.END).strip()
        if n and t:
            result["value"] = (n, t)
        dlg.destroy()

    bf = tk.Frame(dlg, bg=BG)
    bf.pack(fill=tk.X, padx=10, pady=(0, 10))
    tk.Button(bf, text="Anuluj", command=dlg.destroy, bg=BTN_BG, fg=FG,
              activebackground=BTN_ACTIVE, activeforeground=FG, relief=tk.RAISED, bd=2,
              padx=6, pady=2).pack(side=tk.LEFT)
    tk.Button(bf, text="Zapisz", command=do_ok, bg=ACCENT, fg="#FFFFFF",
              activebackground=BTN_ACTIVE, activeforeground=FG, relief=tk.RAISED, bd=2,
              padx=6, pady=2).pack(side=tk.RIGHT)

    parent.wait_window(dlg)
    return result["value"]
