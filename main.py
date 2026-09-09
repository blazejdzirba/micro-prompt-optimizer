"""Micro Prompt Optimizer — punkt wejścia aplikacji.

Cała logika po refaktoryzacji mieszka w app.py (główne okno) oraz pakiecie
ui/ (motyw, popovery, dialogi, ustawienia). Uruchomienie:  python main.py

Ustawiamy klasę okna (WM_CLASS) i ikonę — dzięki temu skrót na pulpicie /
wpis w menu (plik .desktop / .lnk z packaging/) dopina się do właściwej
ikony i nazwy w Interfejsie systemu.
"""

import os
import tkinter as tk

from app import App

APP_CLASS = "Micropromptoptimizer"
# Tk normalizuje className (pierwsza litera wielka, reszta mała) — dlatego
# pisownia wygląda dziwnie, ale MUSI pokrywać się z StartupWMClass
# w pliku .desktop (packaging/linux/install.sh), inaczej ikona w panelu
# systemu nie dopina się do okna aplikacji.


def main():
    root = tk.Tk(className=APP_CLASS)
    try:                             # ikona okna/panelu; brak pliku ≠ awaria
        icon = tk.PhotoImage(file=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png"))
        root.iconphoto(True, icon)
        root._mpo_icon = icon        # Tk zwalnia PhotoImage bez referencji
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
