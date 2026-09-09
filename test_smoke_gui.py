"""Test dymny GUI — uruchamiany pod Xvfb (wymaga xauth: apt install xauth).

Sprawdza: start aplikacji, stany przycisków, tryb Mega, popover fragmentów,
okno ustawień (w tym ASYNCHRONICZNE pobieranie modeli — deterministycznie,
ze sztucznym spowolnieniem sieci), edycję biblioteki fragmentów na kopii
roboczej oraz kontrakt wątkowy run_async.

Uruchomienie:  xvfb-run -a python3 test_smoke_gui.py
"""

import os
import sys
import tempfile
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Izolowany katalog konfiguracyjny — zanim App utworzy Config()
import config
_tmp = tempfile.mkdtemp()
config.CONFIG_DIR = os.path.join(_tmp, "cfg")
config.CONFIG_FILE = os.path.join(config.CONFIG_DIR, "config.json")

import openrouter
import voicenotes
from app import App
import ui.settings
from ui.settings import SettingsWindow

root = tk.Tk()
app = App(root)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


# ── 1. stan początkowy przycisków ───────────────────────────────────
assert str(app.copy_button["state"]) == "disabled"
assert str(app.translate_button["state"]) == "disabled"
print("1. stan początkowy OK")

# ── 2. wynik -> kopiowanie aktywne ──────────────────────────────────
app._set_output("wynik testowy")
assert str(app.copy_button["state"]) == "normal"
assert app.output_text.get("1.0", tk.END).strip() == "wynik testowy"
print("2. kopiowanie blokuje/odblokowuje OK")

# ── 3. statusy i kolory ─────────────────────────────────────────────
app.set_status("błąd testowy", error=True)
assert str(app.status_label.cget("fg")) == "#FF5555"
app.set_status("Gotowe")
assert str(app.status_label.cget("fg")) == "#50FA7B"
print("3. statusy OK")

# ── 4. walidacja wysyłki (bez klucza API) ───────────────────────────
app.on_send()
assert "pusty" in app.status_var.get().lower()
app.input_text.insert("1.0", "napisz dziennik treningowy")
app.on_send()
assert "klucz" in app.status_var.get().lower()
assert not app._request_in_flight
print("4. walidacja wysyłki OK")

# ── 5. tryb Mega — ramka pytań ──────────────────────────────────────
app.mode_var.set("mega")
app.on_mode_change()
app._build_qa_frame(["Pytanie pierwsze?", "Pytanie drugie?", "Pytanie trzecie?"])
app._qa_questions = ["q1", "q2", "q3"]
assert len(app._qa_entries) == 3
app.send_button.config(text="Generuj finalny prompt")
app._reset_mega_state()
assert not app.qa_frame.winfo_children()
assert app.send_button.cget("text") == "Wyślij"
print("5. tryb Mega OK")

# ── 6. run_async: kontrakt wątkowy + ścieżka błędu ──────────────────
results = {}
app.run_async(lambda: 42,
              lambda v: results.update(ok=(v, threading.current_thread() is threading.main_thread())),
              lambda m: results.update(err=m))
app.run_async(lambda: 1 / 0,
              lambda v: None,
              lambda m: results.update(blad=(m, threading.current_thread() is threading.main_thread())))
pump(0.5)
assert results["ok"] == (42, True), results.get("ok")           # callback na wątku UI
assert "blad" in results and results["blad"][1] is True         # błąd też na wątku UI
print("6. run_async OK (wynik i błąd na wątku UI)")

# ── 7. panel fragmentów WBUDOWANY w główne okno (nie popover) ──────
assert app.snip_panel.winfo_manager() == ""                    # start: schowany
assert app._view.grid_rowconfigure(2)["weight"] == 0
app.toggle_snippets_panel()
pump(0.1)
assert app.snip_panel.winfo_manager() == "grid"                # pokazany
assert app._view.grid_rowconfigure(2)["weight"] == 1
# widget jest DZIECKIEM widoku głównego → skaluje się z oknem i chowa
# przy minimalizacji (za darmo, bez ręcznej obsługi WM_ICONIFY)
assert app.snip_panel.winfo_parent().endswith(app._view.winfo_name()) or \
    str(app.snip_panel).startswith(str(app._view))
n_items = app.snip_listbox.size()
assert n_items == len(app.config.snippets) and n_items >= 1
# klik w pozycję = NATYCHMIASTOWY wybór, bez Enter ani „Zastosuj"
app.snip_listbox.selection_clear(0, tk.END)
app.snip_listbox.selection_set(0)
app.snip_listbox.event_generate("<<ListboxSelect>>")
pump(0.1)
snippet_id = app._snip_shown[0]["id"]
assert app.selected_snippet_ids == {snippet_id}
assert app.config.selected_snippets == [snippet_id]            # zapis do configu
# prompt systemowy zawiera tekst klikniętego fragmentu
sys_prompt = app._build_system_prompt()
assert app._snip_shown[0]["text"].splitlines()[0][:20] in sys_prompt
# „wszystkie"/„żaden"
app._set_all_snippets(True)
pump(0.05)
assert len(app.selected_snippet_ids) == n_items
app._set_all_snippets(False)
pump(0.05)
assert app.selected_snippet_ids == set()
assert app.snippet_button.cget("text") == "Fragmenty (0)"
# ponowny klik: ponowne włączenie tej samej pozycji
app.snip_listbox.selection_set(0)
app.snip_listbox.event_generate("<<ListboxSelect>>")
pump(0.1)
assert app.selected_snippet_ids == {snippet_id}
app.toggle_snippets_panel()                                    # ukryj z powrotem
pump(0.1)
assert app.snip_panel.winfo_manager() == ""
assert app._view.grid_rowconfigure(2)["weight"] == 0
print("7. panel fragmentów (wbudowany, klik=wybór, skalowanie) OK")

# ── 8. DETERMINISTYCZNIE: wolna sieć — fallback od razu, lista w tle ──
app.config.models = []        # jak u nowego użytkownika — nic jeszcze nie pobrano
fake_models = [{"id": f"fake/model-{i:02d}"} for i in range(12)]
fake_ids = [m["id"] for m in fake_models]

def slow_get_models(api_key=None):
    time.sleep(2.0)                       # symulacja wolnej sieci
    return fake_models

orig_get_models = openrouter.get_models
openrouter.get_models = slow_get_models

t0 = time.time()
sw = SettingsWindow(app)
sw.open()
pump(0.3)
opened_in = time.time() - t0
assert opened_in < 1.0, f"okno ustawień otwierało się {opened_in:.1f}s — UI zamrożone!"
assert sw._hint_label.cget("text").startswith("Pobieram"), sw._hint_label.cget("text")
assert len(sw._model_ids) == len(openrouter.FALLBACK_MODELS)   # fallback od razu
print(f"8. ustawienia otwarte w {opened_in:.2f}s na liście awaryjnej OK")

# popover otwarty PRZED dociągnięciem pełnej listy
sw._open_model_popover()
pump(0.2)
assert sw._popover.winfo_exists()
assert sw._popover.listbox.size() == len(openrouter.FALLBACK_MODELS)

pump(2.5)                                                  # fake już skończył
assert len(sw._model_ids) == 12, sw._model_ids
assert sw._popover.listbox.size() == 12                    # podmiana w OTWARTYM popoverze
assert app.config.models == fake_ids                       # zapis TRWAŁY w configu
assert sw._hint_label.cget("text").startswith("Kliknij")
sw._close_popover_if_open()

# drugie otwarcie okna: lista z configu — ŻADNEGO pobierania (zero sieci)
openrouter.get_models = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("nie wolno pobierać modeli drugi raz!"))
sw2 = SettingsWindow(app)
sw2.open()
pump(0.3)
assert len(sw2._model_ids) == 12
assert "↻" in sw2._hint_label.cget("text")
sw2.win.destroy()
pump(0.2)
openrouter.get_models = orig_get_models
print("8b. async: raz pobrane → trwałe w configu → kolejne otwarcia bez sieci OK")

# ── 9. biblioteka fragmentów: dodaj/edytuj/usuń na kopii roboczej ───
n_before = len(sw._working_snippets)

orig_dialog = ui.settings.prompt_snippet_dialog
ui.settings.prompt_snippet_dialog = lambda parent, title, name="", text="": ("Testowy", "treść X")
sw._snip_add()
assert len(sw._working_snippets) == n_before + 1
assert sw._working_snippets[-1]["id"] is None          # id nada Config przy zapisie

ui.settings.prompt_snippet_dialog = lambda parent, title, name="", text="": ("Zmieniony", "treść Y")
sw._snip_listbox.selection_clear(0, tk.END)
sw._snip_listbox.selection_set(n_before)               # ostatni element
sw._snip_edit()
assert sw._working_snippets[-1]["name"] == "Zmieniony"
ui.settings.prompt_snippet_dialog = orig_dialog

# uwaga: przebudowa listboxu po edycji czyści zaznaczenie — użytkownik
# klika pozycję ponownie przed "Usuń"
sw._snip_listbox.selection_set(n_before)
sw._snip_delete()
assert len(sw._working_snippets) == n_before
print("9. edycja biblioteki na kopii roboczej OK")

# ── 10. zapis ustawień -> Config, przycisk fragmentów, plik ─────────
sw._api_key_entry.delete(0, tk.END)
sw._api_key_entry.insert(0, "sk-test-123")
ui.settings.prompt_snippet_dialog = lambda *a, **k: ("Zapisany", "nowa treść")
sw._snip_add()
ui.settings.prompt_snippet_dialog = orig_dialog
app.selected_snippet_ids = {"nieistniejący-id"}
app.config.selected_snippets = ["nieistniejący-id"]

sw._save()
pump(0.2)
assert not sw.win.winfo_exists()
assert app.config.api_key == "sk-test-123"
assert all(s["id"] for s in app.config.snippets)
assert app.selected_snippet_ids == set()                       # ghost wyczyszczony
assert app.snippet_button.cget("text") == "Fragmenty (0)"

# konfiguracja faktycznie zapisana na dysku (reload z pliku)
c2 = config.Config()
assert c2.api_key == "sk-test-123"
assert c2.snippets[-1]["name"] == "Zapisany"
print("10. zapis ustawień OK (config + plik + czyszczenie zaznaczeń)")

# ── 10b. migracja: legacy domyślna biblioteka → nowy katalog (v6) ──
import copy, json
legacy_dir = tempfile.mkdtemp()
legacy_file = os.path.join(legacy_dir, "c.json")
legacy_data = copy.deepcopy(config.DEFAULT_CONFIG)
legacy_data["snippets"] = copy.deepcopy(config.LEGACY_DEFAULT_SNIPPETS)
legacy_data["selected_snippets"] = ["default-styl-zwiezly"]     # stary id (duch)
with open(legacy_file, "w", encoding="utf-8") as f:
    json.dump(legacy_data, f)
saved_dir, saved_file = config.CONFIG_DIR, config.CONFIG_FILE
try:
    config.CONFIG_DIR, config.CONFIG_FILE = legacy_dir, legacy_file
    cm = config.Config()
    # biblioteka podmieniona na nowy katalog kategorii…
    assert [x["id"] for x in cm.snippets] == [x["id"] for x in config.DEFAULT_SNIPPETS]
    assert len(cm.snippets) == 6                                # 6 kategorii
    # …a zaznaczenie starego id oczyszczone (nie ma go w nowej bibliotece)
    assert cm.selected_snippets == []
    # katalog kategorii ograniczony do wymaganych dziedzin
    joined_names = " ".join(x["name"].lower() for x in cm.snippets)
    for kw in ("agent", "programist", "koder", "webow", "json/yaml", "dokumentac"):
        assert kw in joined_names, kw
finally:
    config.CONFIG_DIR, config.CONFIG_FILE = saved_dir, saved_file
print("10b. migracja legacy biblioteki fragmentów OK")


# ── 11. Kreator: przełączanie pól, składanie, wysyłka, persystencja ─
app.mode_var.set("kreator")
app.on_mode_change()
pump(0.2)
assert app.input_frame.winfo_manager() == ""                      # pole ukryte
assert app.builder_panel.winfo_manager() == "grid"                # kreator widoczny
app.on_send()                                                     # puste Zadanie
assert "Zadanie" in app.status_var.get(), app.status_var.get()

app.builder_panel.set_values({
    "role": "Doświadczony redaktor tekstów",
    "task": "Przygotuj plan postów na 2 tygodnie",
    "audience": "Osoba nietechniczna",
    "format": "Lista wypunktowana",
    "constraints": "Maksymalnie 500 słów; Ton luźny",
})
draft = app.builder_panel.compose()
for fragment in ("Rola:", "Zadanie:", "Odbiorca:", "Format odpowiedzi:",
                 "Ograniczenia i wymagania:"):
    assert fragment in draft, fragment

orig_optimize = openrouter.optimize_prompt
openrouter.optimize_prompt = lambda *a, **k: "WYNIK Z KREATORA:\n" + a[3]
app.on_send()
pump(0.5)
openrouter.optimize_prompt = orig_optimize
out = app.output_text.get("1.0", tk.END)
assert "WYNIK Z KREATORA" in out and "Rola: Doświadczony" in out, out[:300]

# pola Kreatora zapamiętane w configu (i przeładowanie z pliku)
assert app.config.builder["task"] == "Przygotuj plan postów na 2 tygodnie"
c3 = config.Config()
assert c3.builder["role"] == "Doświadczony redaktor tekstów"
assert c3.mode == "kreator" and c3.models == fake_ids

# powrót do Standard layoutu
# ── 11b. Kreator: lista presetów WBUDOWANA (nie Toplevel), klik=wpisz ──
app.mode_var.set("kreator")
app.on_mode_change()
pump(0.2)
bp = app.builder_panel
role_row = bp.role_entry.master
widgets = role_row.winfo_children()
entry_w = next(w for w in widgets if isinstance(w, tk.Entry))
btn_w = next(w for w in widgets if isinstance(w, tk.Button))
pump(0.2)
# wysokość ▾ dopasowana do pola obok (fill=Y w tym samym wierszu)
assert abs(btn_w.winfo_height() - entry_w.winfo_height()) <= 8, \
    (btn_w.winfo_height(), btn_w.winfo_height() - entry_w.winfo_height())
top_before = {str(w) for w in root.winfo_children()}
btn_w.invoke()                                                 # rozwiń ▾
pump(0.1)
assert bp._preset_band and bp._preset_band.winfo_manager() == "pack"
from ui.builder import ROLE_PRESETS, CONSTRAINT_PRESETS
# lista jest dzieckiem PANELU kreatora, a nie nowym oknem Toplevel
assert bp._preset_band.winfo_parent() == str(bp)
assert {str(w) for w in root.winfo_children()} == top_before   # zero nowych Toplevel
assert bp._preset_list.size() == len(ROLE_PRESETS)
# klik w pozycję = natychmiastowe wpisanie i zwinięcie (bez Enter)
bp.role_entry.delete(0, tk.END)
bp._preset_list.selection_clear(0, tk.END)
bp._preset_list.selection_set(1)
bp._preset_list.event_generate("<<ListboxSelect>>")
pump(0.1)
from ui.builder import ROLE_PRESETS
assert bp.role_entry.get() == ROLE_PRESETS[1]
assert bp._preset_band.winfo_manager() == ""                   # zwinięta po kliku
# ten sam ▾ rozwija i zwija (toggle)
btn_w.invoke(); pump(0.05)
assert bp._preset_band.winfo_manager() == "pack"
btn_w.invoke(); pump(0.05)
assert bp._preset_band.winfo_manager() == ""
# Ograniczenia: wybór dokleja po średniku, bez duplikatów
cons_row = bp.constraints_entry.master
cbtn = next(w for w in cons_row.winfo_children() if isinstance(w, tk.Button))
bp.constraints_entry.delete(0, tk.END)
cbtn.invoke(); pump(0.1)
bp._preset_list.selection_set(0)
bp._preset_list.event_generate("<<ListboxSelect>>"); pump(0.05)
cbtn.invoke(); pump(0.1)
bp._preset_list.selection_clear(0, tk.END)   # selection_set NIE czyści
bp._preset_list.selection_set(1)              # wcześniejszego zaznaczenia — klik myszy czyści
bp._preset_list.event_generate("<<ListboxSelect>>"); pump(0.05)
assert bp.constraints_entry.get() == \
    CONSTRAINT_PRESETS[0] + "; " + CONSTRAINT_PRESETS[1], bp.constraints_entry.get()
# lista presetów chowa się razem z trybem (dziecko okna)
app.mode_var.set("standard")
app.on_mode_change()
pump(0.2)
assert app.builder_panel.winfo_manager() == ""
assert app.input_frame.winfo_manager() == "grid"
print("11. Kreator: składanie ze składowych + wysyłka + persystencja OK")
print("11b. Kreator: lista presetów wbudowana, klik=wpisz, ▾=wysokość pola OK")

# ── 12. Tryb Systemowy: walidacja + tworzenie promptu systemowego ───
app.mode_var.set("systemowy")
app.on_mode_change()
pump(0.2)
assert app.input_frame.winfo_manager() == "grid"     # zwykłe pole (nie kreator)
assert "asystenta" in app.in_label.cget("text")
app.input_text.delete("1.0", tk.END)
app.on_send()
assert "Opisz asystenta" in app.status_var.get(), app.status_var.get()

app.input_text.insert("1.0", "Asystent księgowy: uprzejmy, konkretny, "
                             "odpowiada tabelami, nie zna się na sporcie")
orig_create = openrouter.create_system_prompt
openrouter.create_system_prompt = lambda *a, **k: ("Jesteś asystentem "
    "księgowym. Odpowiadasz uprzejmie i konkretnie, dane tabelaryzujesz. "
    "Nie wypowiadasz się na tematy spoza finansów.")
app.on_send()
pump(0.5)
openrouter.create_system_prompt = orig_create
assert "asystentem księgowym" in app.output_text.get("1.0", tk.END), \
    app.output_text.get("1.0", tk.END)[:200]
print("12. tryb Systemowy OK (walidacja + opis -> prompt systemowy)")

# ── 13. Wyczyść + zużycie tokenów w statusie ────────────────────────
app.mode_var.set("standard")
app.on_mode_change()
app.input_text.delete("1.0", tk.END)
app.input_text.insert("1.0", "dowolny prompt")
orig_optimize = openrouter.optimize_prompt
openrouter.optimize_prompt = lambda *a, **k: ("WYNIK TOK", {"total_tokens": 1234})
app.on_send()
pump(0.5)
openrouter.optimize_prompt = orig_optimize
status = app.status_var.get()
assert "Gotowe" in status and "234" in status, status   # "Gotowe · zużyania: 1 234"
assert str(app.status_label.cget("fg")) == "#50FA7B"     # sukces nadal zielony

app.on_clear()
assert app.input_text.get("1.0", tk.END).strip() == ""
assert app.output_text.get("1.0", tk.END).strip() == ""
assert str(app.translate_button["state"]) == "disabled"

# formatowanie separatora tysięcy (twarda spacja) w helperze
s = app._status_with_usage("Gotowe", {"total_tokens": 1234567})
assert s.startswith("Gotowe") and "1" in s and "234" in s and "567" in s, s
assert app._status_with_usage("Gotowe", {}) == "Gotowe"
print("13. Wyczyść + tokeny OK")

# ── 14. guard: tylko jedno okno Ustawień ────────────────────────
app.open_options()
pump(0.3)
first = app._settings_window
assert first and first.is_alive()
app.open_options()                                     # drugi klik — bez duplikatu
pump(0.2)
assert app._settings_window is first                   # to samo okno
first.win.destroy()
pump(0.2)
assert not first.is_alive()
print("14. guard okien ustawień OK")


# ── 15. REC: przełączanie widoków mikrofonem w topbarze ───────────
assert app.mic_button.cget("text") == "🎤"
assert app._view.winfo_manager() == "pack"                    # widok promptu widoczny
assert app.rec_panel.winfo_manager() == ""                    # REC schowany

app.toggle_view()
pump(0.1)
assert app.mic_button.cget("text") == "← Prompt"
assert app._view.winfo_manager() == ""
assert app.rec_panel.winfo_manager() == "pack"

app.toggle_view()
pump(0.1)
assert app.mic_button.cget("text") == "🎤"
assert app._view.winfo_manager() == "pack"
assert app.rec_panel.winfo_manager() == ""
print("15. REC: przełączanie widoków OK")

# ── 16. REC: fallback bez pakietów opcjonalnych (sandbox = brak whisper) ──
app.toggle_view()                                             # wejdź w REC
pump(0.2)
status_rec = app.rec_panel.status_var.get()
assert "pip install -r requirements.txt" in status_rec, status_rec
assert str(app.rec_panel.rec_button["state"]) == "disabled"   # REC nieklikalne
# ➜ Użyj jako prompt: transkrypcja wpada w pole wejścia + powrót do widoku
app.rec_panel.output_text.delete("1.0", tk.END)
app.rec_panel.output_text.insert("1.0", "testowa notatka głosowa")
app.use_transcript_as_prompt("testowa notatka głosowa")
assert app.input_text.get("1.0", tk.END).strip() == "testowa notatka głosowa"
assert app._view.winfo_manager() == "pack"                    # i wróciliśmy do promptu
app.input_text.delete("1.0", tk.END)
print("16. REC: fallback bez whisper + Użyj jako prompt OK")

# ── 17. voicenotes: katalog modeli, domyślny model, stan cache ────
names = [m["name"] for m in voicenotes.WHISPER_MODELS]
assert voicenotes.DEFAULT_MODEL in names, names
assert voicenotes.DEFAULT_MODEL == "small"                    # rekomendacja pod GTX 1650 4GB
assert "large" not in names                                   # celowo pominięty (nie mieści się w VRAM)
assert not voicenotes.is_downloaded("nie-istnieje")           # bogus → False
assert voicenotes.model_path("small").endswith("small.pt")    # nazwa pliku w cache
# whisper_ok/sounddevice_ok nie rzucają wyjątków nawet bez pakietów
assert voicenotes.whisper_ok() in (True, False)
assert voicenotes.sounddevice_ok() in (True, False)
print("17. voicenotes: metadane modeli + cache OK")


# ── 18. REC z mockiem voicenotes (sandbox nie ma pakietów audio) ───
cp = app.rec_panel
KEYS = ("whisper_ok", "sounddevice_ok", "is_downloaded", "load_model",
        "free_gpu", "transcribe")
_orig = {k: getattr(voicenotes, k) for k in KEYS}
calls = {"load": 0, "tr": 0}
try:
    voicenotes.whisper_ok = lambda: True
    voicenotes.sounddevice_ok = lambda: True
    voicenotes.transcribe = lambda m, a: calls.__setitem__("tr", calls["tr"]+1) or "xd"
    voicenotes.free_gpu = lambda: None

    # (a) model niepobrany → guzik 📥 widoczny, REC zablokowany
    voicenotes.is_downloaded = lambda name: False
    voicenotes.load_model = lambda name: calls.__setitem__("load", calls["load"]+1) or object()
    app.toggle_view()                                  # wejście w REC
    pump(0.1)
    assert cp.dl_button.winfo_manager() == "pack"
    assert str(cp.rec_button["state"]) == "disabled"
    assert "NIEPOBRANY" in cp.model_var.get()
    cp.dl_button.invoke()                              # pobieranie (mock)
    voicenotes.is_downloaded = lambda name: True       # „plik już jest"
    pump(0.6)
    assert cp._model is not None and cp._model_name == "small"
    assert str(cp.rec_button["state"]) == "normal"
    assert cp.dl_button.winfo_manager() == ""
    assert "gotowy" in cp.model_var.get()

    # (b) model na dysku, brak w RAM: refresh sam wczyta w tle
    saved_model = cp._model
    cp._model = None
    cp._model_name = None
    cp.refresh_model_state()
    pump(0.5)
    assert calls["load"] == 2                          # lazy-load zadziałał
    assert cp._model is not None and "gotowy" in cp.model_var.get()

    # (c) guard: nagranie bez wczytanego modelu NIE woła transcribe(None)
    cp._model = None
    cp._recording = True
    cp._stream = type("S", (), {"stop": lambda _s: None, "close": lambda _s: None})()
    _fake_arr = type("A", (), {"flatten": lambda _s: b"\x00" * 9600})()  # 0,3 s
    cp._np = type("N", (), {"concatenate": staticmethod(lambda a, axis: _fake_arr)})()
    cp._audio = [b"\x00" * 4800]
    cp._stop_recording()
    pump(0.1)
    assert calls["tr"] == 0                            # zero AttributeError
    assert "wczyt" in cp.status_var.get().lower(), cp.status_var.get()
    pump(0.4)                                          # ensure-model w tle OK
    assert cp._model is not None

    # (d) ścieżka błędu pobierania: guzik wraca w stan „spróbuj ponownie"
    cp._model = None
    cp._model_name = None
    voicenotes.is_downloaded = lambda name: False
    def boom(name):
        raise RuntimeError("sieć padła")
    voicenotes.load_model = boom
    cp.refresh_model_state()
    pump(0.1)
    cp.dl_button.invoke()
    pump(0.5)
    assert "Spróbuj jeszcze raz" in cp.dl_button.cget("text")
    assert str(cp.dl_button["state"]) == "normal"      # odblokowany do retry
    assert cp._loading is False and cp._model is None
finally:
    for k, v in _orig.items():
        setattr(voicenotes, k, v)
    app._in_rec and app.toggle_view()                  # wyjście z REC
    pump(0.1)
print("18. REC (mock): download/lazy-load/guard/błąd OK")

# ── 19. config: atomowy zapis + odbudowa po uszkodzonym pliku ──────
import json as _json
assert not os.path.exists(config.CONFIG_FILE + ".tmp")   # żadnych zalegających tmp
with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
    f.write("{ciąć ! nie-json")                          # symulowany crash zapisu
cfg2 = config.Config()                                   # ma wstać z defaultów
assert cfg2.api_key == "" and cfg2.model == config.DEFAULT_CONFIG["model"]
assert os.path.isfile(config.CONFIG_FILE + ".bak")       # ślad zachowany
with open(config.CONFIG_FILE, encoding="utf-8") as f:
    _json.load(f)                                        # config znowu poprawny
os.remove(config.CONFIG_FILE + ".bak")
print("19. config: atomowy zapis + .bak po uszkodzeniu OK")

# ── 20. Wyczyść w Kreatorze persystuje puste pola natychmiast ──────
app.mode_var.set("kreator")
app.on_mode_change()
pump(0.2)
app.builder_panel.set_values({"role": "X", "task": "Y"})
app.config.builder = app.builder_panel.get_values()
app.config.save()
app.on_clear()
pump(0.1)
c4 = config.Config()
assert c4.builder == {}, c4.builder                      # po restarcie nic nie wraca
app.mode_var.set("standard")
app.on_mode_change()
pump(0.2)
print("20. Wyczyść persystuje builder OK")

print("\n=== WSZYSTKIE TESTY DYMNE GUI PRZESZŁY ===")
root.destroy()
