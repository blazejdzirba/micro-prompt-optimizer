"""Sterownik do zrzutów ekranu pod Xvfb (nie jest częścią aplikacji).

Użycie:  DISPLAY=:99 python3 shot_driver.py <scena>
sceny: kreator | kreator-popover | ustawienia
"""
import os
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
scene = sys.argv[1] if len(sys.argv) > 1 else "kreator"

import config
_tmp = tempfile.mkdtemp()
config.CONFIG_DIR = _tmp
config.CONFIG_FILE = os.path.join(_tmp, "c.json")

import ui.builder
from app import App

root = tk.Tk()
root.geometry("560x720+60+40")
app = App(root)


def find_buttons(widget, text):
    found = [widget] if isinstance(widget, tk.Button) and str(widget.cget("text")) == text else []
    for child in widget.winfo_children():
        found += find_buttons(child, text)
    return found


if scene.startswith("kreator"):
    app.mode_var.set("kreator")
    app.on_mode_change()
    app.builder_panel.set_values({
        "role": "Doświadczony redaktor tekstów",
        "task": "Przygotuj plan postów na LinkedIn na najbliższe 2 tygodnie — firma sprzedaje kursy gotowania online.",
        "audience": "Osoba nietechniczna",
        "format": "Lista wypunktowana",
        "constraints": "Maksymalnie 500 słów; Ton luźny i przyjazny; Tylko konkrety — bez lania wody",
    })
    if scene == "kreator-popover":
        def open_role_presets():
            # od v7 presety nie mają popovera — ▾ jest przełącznikiem
            # listy wbudowanej; invoke() wykonuje dokładnie to, co klik użytkownika
            btns = find_buttons(app.builder_panel, "▾")
            btns[0].invoke()      # rozwija listę pod polem Rola
        root.after(800, open_role_presets)
elif scene == "systemowy":
    app.mode_var.set("systemowy")
    app.on_mode_change()
    app.input_text.insert(
        "1.0", "Asystent do pisania opisów produktów w sklepie z elektroniką: "
               "konkretny, sprzedażowy, bez przesadnych superlatywów, odpowiada "
               "po polsku, nie zna się na tematach spoza elektroniki.")
    app._set_output(
        "Jesteś specjalistą ds. treści e-commerce, który pisze opisy produktów "
        "dla sklepu z elektroniką. Twoim zadaniem jest tworzyć konkretne, "
        "sprzedażowe opisy na podstawie listy cech podanej przez użytkownika.\n\n"
        "Zasady:\n"
        "1. Zacznij od jednozdaniowego leadu z główną korzyścią produktu.\n"
        "2. Opisuj cechy wraz z korzyściami dla użytkownika, nie tylko parametry.\n"
        "3. Używaj tonu profesjonalnego, ale energicznego — bez przesadnych "
        "superlatywów i sloganów.\n"
        "4. Maksymalnie 120 słów na opis; odpowiadasz wyłącznie po polsku.\n"
        "5. Na koniec dodaj sekcję „Specyfikacja” jako listę wypunktowaną.\n"
        "6. Nie wypowiadaj się na tematy spoza elektroniki — grzecznie przekieruj "
        "pytanie do asortymentu sklepu.")
elif scene == "ustawienia":
    config.Config().models = []        # pierwsze otwarcie jak u nowego usera
    root.after(300, app.open_options)

root.mainloop()
