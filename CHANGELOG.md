# Micro Prompt Optimizer

Desktopowa aplikacja (tkinter) do optymalizacji promptów przez OpenRouter API.

## Uruchomienie

```bash
pip install -r requirements.txt
python main.py
```

## Struktura projektu

```
micro-prompt-optimizer/
├── main.py            (37 ln)   punkt wejścia — tylko startuje App
├── app.py             (702 ln)  klasa App: główne okno + logika przepływu
├── config.py          (305 ln)  JSON config: domyślne wartości, biblioteka fragmentów
├── openrouter.py      (249 ln)  klient API OpenRouter (bez zmian w logice)
├── voicenotes.py      (96 ln)     logika REC: modele Whispera, cache, transkrypcja (pl)
├── ui/
│   ├── theme.py       (80 ln)   paleta kolorów, apply_dark_theme, dark_text, position_popover
│   ├── popovers.py    (136 ln)  ListPopover (uniwersalny wybór z listy), SnippetPopover
│   ├── dialogs.py     (48 ln)   dialog dodawania/edycji fragmentu
│   ├── builder.py     (299 ln)  BuilderPanel: tryb Kreator (składowe promptu)
│   ├── recorder.py    (354 ln)     RecPanel: widok REC (● REC / ■ STOP, timer, transkrypcja)
│   └── settings.py    (439 ln)  SettingsWindow: + sekcja Notatki głosowe
├── requirements.txt
├── assets/                     ikona aplikacji (png/ico) do skrótów i okna
├── packaging/                  instalatory systemowe (v8)
│   ├── linux/                  install.sh / uninstall.sh (+ generowany .desktop)
│   └── windows/                install.ps1 / Install-MPO.cmd / uninstall.ps1
├── test_smoke_gui.py           test dymny GUI (xvfb-run -a python3 test_smoke_gui.py)
├── shot_driver.py              sterownik zrzutów ekranu pod Xvfb (utility)
├── docs/                       zrzuty ekranu UI
└── CHANGELOG.md                ten plik
```

## Hotfix z code review (v9) 🆕

Fixy pakietu A po zewnętrznym code review (zgłaszający miał rację):

- **REC: przywrócona `_ensure_model_loaded`** — przy dopisówce free_gpu
  w v7 linia `def` zniknęła w splajcie i ciało metody wtopiło się w
  `_download_model` → **AttributeError dla każdego, kto miał pobrany model**,
  a przy nagrywaniu bez wczytanego modelu: `NoneType … transcribe` (widoczne
  jako czerwony status na screenshotach). Odtworzone jako osobna metoda,
  `_download_model` ma własną parę ok/err, guard `_loading` na początku,
  `_stop_recording` broni się przed `transcribe(None)` (wczytuje ponownie).
  **Nowy test 18 mockuje voicenotes** — sandbox nie ma whispera, więc ścieżka
  ta była wcześniej niepokryta (lesson: gałęzie za lazy-importami wymagają
  mocków, nie fallbacków).
- **Atomowy zapis configu** (tmp + fsync + os.replace) + guard przy parsowaniu
  (uszkodzony plik → `.bak` + defaults) — połowa zapisu przestaje zabijać
  start aplikacji (test 19).
- **Przewijanie Ustawień na Windows/macOS** — gałąź `<MouseWheel>` (win: Δ/120,
  darwin: Δ), `<Button-4/5>` zostaje na X11; sprzątanie bindingów trzyma
  się tej samej listy (regresja na wersji Windows v8).
- **Flaga `_closing`** — poll() nie planuje kolejnych cykli po [X]; callbacki
  thread-safe nie dotykają niszczonych widgetów (koniec okazjonalnych
  TclError przy zamykaniu w locie żądania).
- **Limit nagrania 15 min** (`MAX_RECORD_SECONDS`) — bufor w RAM nie rośnie
  w nieskończoność (~230 MB/100 min), watchdog auto-stopuje z komunikatem.
- **Deinstalery pytają osobno** o config aplikacji i modele Whispera —
  `~/.cache/whisper` jest współdzielony z innymi narzędziami, więc kasujemy
  tylko pliki tej aplikacji (tiny/base/small/medium.pt) + pusty katalog.
- **`content=None` z API** (refusal) → czytelny błąd zamiast TclError
  w callbacku (openrouter._chat).
- **Wyczyść w Kreatorze zapisuje `builder = {}`** natychmiast — stare pola
  nie wracają po restarcie (test 20).
- **`shot_driver.py`** scena „kreator-popover": `_open_presets` nie istnieje
  od v7 — scena wywołuje `btns[0].invoke()`, jak użytkownik.
- Odłożone (pakiet B): logging+excepthook, sesja HTTP + retry 429, jawny
  marker from_network, pinning `~=`, filtry kopiowanych plików instalatorów.

## Instalatory systemowe (v8) 🆕

Aplikacja instaluje się jak każdy inny program — z ikoną i skrótem,
bez terminala po stronie użytkownika końcowego:

- **Strategia: „managed venv" zamiast PyInstallera.** Bundling Whipera
  ciągnąłby torch za 2,5 GB do każdego binariarza; instalator kopiuje projekt,
  stawia venv per-użytkownik i montuje .desktop/.lnk. Sam model transkrypcji
  i tak pobierany jest leniwie na pierwsze REC — patrz v7.
- **Pop!_OS: `packaging/linux/install.sh`** — weryfikacja Pythona ≥ 3.10,
  auto-doinstalowanie `python3-tk`/`python3-venv`/`libportaudio2` przez apt,
  kopia do `~/.local/share/micro-prompt-optimizer` (rsync z fallbackiem tar),
  venv + zależności (najpierw **torch CPU z własnego indeksu** — ~10× lżejszy,
  żeby openai-whisper nie wymusił wariantu CUDA; flaga `--gpu` przełącza na
  cu121), generowany plik `.desktop` (StartupWMClass, ikona, kategorie),
  `update-desktop-database`, opcjonalna ikona na Pulpicie z
  `gio set metadata::trusted true`. Zgodne z `uninstall.sh` (pyta, czy usunąć
  także config/modele).
- **Windows 11: `packaging/windows/install.ps1` + `Install-MPO.cmd`** —
  nakładka .cmd dla dwukliku (ExecutionPolicy Bypass); skrypt znajduje
  Pythona ≥ 3.10 (`py -3`/`python`) albo **instaluje go przez winget w trybie
  per-user** (bez admina), kopiuje projekt robocopy do
  `%LOCALAPPDATA%\MicroPromptOptimizer`, stawia venv (CPU default, `-Gpu` = cu121),
  a skróty tworzy przez COM `WScript.Shell` z wskazaniem na **pythonw.exe**
  (bez okna konsoli) i ikoną `assets/icon.ico`. `uninstall.ps1` analogicznie.
- **Ikona aplikacji (nowa)** — `assets/` (master 1024 → 512/256/48 + .ico
  wielorozmiarowe przez PIL); `main.py` ustawia ją przez `root.iconphoto`
  oraz klasę okna `Micropromptoptimizer` (uwaga: Tk normalizuje className —
  pisownia zgodna tylko z tą formą, patrz komentarz w main.py).
- Uwagi: sounddevice na Linuksie wymaga libportaudio2 (instalator apt-uje);
  aplikacja i tak działa headless-free — venv pythonw/python bez konsoli.

## Presety Kreatora wbudowane + pakiety głosowe wymagane (v7) 🆕

- **Lista ▾ w Kreatorze — przestała być osobnym oknem.** `ListPopover`
  (Toplevel) zniknął ze `ui/builder.py`; w jego miejsce `self._preset_band`
  — tk.Frame z Listboxiem, **dziecko panelu Kreatora**, otwierany
  `pack(after=wiersz pola)` prosto pod polem: nie pojawia się żadne nowe
  Toplevel, lista skaluje się z oknem i chowa razem z nim (i przy zmianie
  trybu). Pojedynczy **klik w pozycję = natychmiastowy wpis do pola i
  zwinięcie** (binding `<<ListboxSelect>>`, selectmode SINGLE); ten sam ▾
  przełącza rozwinięcie/zwinięcie, „zwiń ✕” w nagłówku listy zamyka ręcznie.
  Logika dołączania bez zmian (Ograniczenia: doklejanie po „; " z blokadą
  duplikatów), podświetlenie aktualnej wartości pola przy otwarciu, aktywny
  ▾ dostaje kolor ACCENT. Uwaga testowa: `selection_set()` nie czyści
  wcześniejszego zaznaczenia (robi to dopiero klik myszy) — stąd w teście
  jawne `selection_clear`.
- **Przycisk ▾ dopasowany wysokością do pola obok** — `bd=0`, `pady=0`,
  mniejsza czcionka i `pack(side=LEFT, fill=Y)` (rozciąganie do wysokości
  wiersza, którą narzuca Entry); wcześniej ipady+większa czcionka robiły
  go wyraźnie wyższym.
- **Pakiety głosowe WYMAGANE** — `openai-whisper`, `sounddevice`, `numpy`
  odkomentowane w `requirements.txt`. Fallback (komunikat i zablokowany REC
  bez pakietów) zostaje jako siatka bezpieczeństwa dla instalacji sprzed
  zmiany. Jedyną rzeczą pobieraną „dopiero przy użyciu" jest model
  transkrypcji (zgodnie z życzeniem) — nowy przycisk **„📥 Pobierz model —
  tylko raz" prosto w widoku REC** (pokazuje się tylko gdy model wybrany,
  ale niepobrany; download w tle przez run_async, po sukcesie free GPU
  starego modelu i od razu gotowy REC).
- README: komenda z `--timeout 120 --retries 10` przeciw ReadTimeoutError
  przy wielkich kołach torch/triton + akapit, że model pobiera się na żądanie.

## Fragmenty WBUDOWANE w okno + katalog kategorii (v6) 🆕

Wymagania z realizacją:

1. **Bez osobnego TopLevel/Popup** — stary `SnippetPopover` (Toplevel,
   overrideredirect, grab) usunięty z `ui/popovers.py`; w jego miejsce panel
   `self.snip_panel` (tk.Frame z Listbox) będący **dzieckiem kontenera**
   `_view` głównego okna, w wierszu 2 siatki, z nagłówkiem „klik dołącza/
   odłącza…" i przewijaniem.
2. **Klik = natychmiastowy wybór** — `selectmode=MULTIPLE` + binding
   `<<ListboxSelect>>`: pojedynczy klik w pozycję włącza/wyłącza fragment
   i od razu zapisuje zaznaczenie (zbiór w pamięci → config → plik JSON
   → licznik na przycisku), bez Enter ani przycisku „Zastosuj".
   Bonus: guziki „wszystkie"/„żaden" w nagłówku panelu.
3. **Skalowanie z oknem + chowanie przy minimalizacji** — widget wewnątrz
   okna dziedziczy obie właściwości za darmo: wiersz 2 ma `weight=1` gdy
   panel pokazany (lista rośnie razem z oknem) i `weight=0` + `grid_remove`
   gdy schowany (ukryty wiersz z wagą>0 zjadałby miejsce — stąd zerowanie).
4. **Katalog kategorii** — `DEFAULT_SNIPPETS` ograniczone do 6 ról/formatów:
   budowa promptów dla agenta LLM, asystent programisty, koder (pair
   programming), webowy agent LLM, struktury JSON/YAML, dokumentacja
   techniczna. Stary domyślny wpis zachowany jako `LEGACY_DEFAULT_SNIPPETS`
   wyłącznie do **migracji**: config równy starą domyślnemu zestaw →
   automatyczna podmiana na nowy katalog + oczyszczenie zaznaczenia
   (własne fragmenty użytkownika nie są ruszane).

Pokrewne: sprawdzenia w `test_smoke_gui.py` (scenariusz 7 — relacja rodzic-
dziecko, wagi wiersza, klik-applies, guziki bulk; 10b — migracja legacy +
asercje słów kluczowych kategorii), settings nie ruszane (zapis biblioteki
woła `refresh_snippet_button()`, które odbudowuje też listbox — patrz guard
`hasattr`, bo w `__init__` przycisk powstaje przed panelem).

## Notatki głosowe REC (v5) 🆕

Integracja Whispera wprost w aplikację (rezygnacja z osobnego skryptu notatek):

- **Przełączany widok, nie osobne okno** — czerwony przycisk 🎤 w prawym
  górnym rogu paska podmienia zawartość okna (pasek zostaje na miejscu,
  guzik zmienia się na „← Prompt”). Wszystkie dotychczasowe widgety przeniesione
  do kontenera `self._view`, numeracja wierszy siatki przesunięta o −1 po
  wyciągnięciu nagłówka do pakowanego (pack) topbara.
- **RecPanel** (`ui/recorder.py`): przycisk ● REC / ■ STOP z minutnikiem
  (0:SS, odświeżany co 0,5 s), nagrywanie przez `sounddevice.InputStream`
  (16 kHz mono float32, buforowanie w callbacku i `np.concatenate` — bez pliku
  tymczasowego, bez zależności od scipy), transkrypcja w wątku tła przez
  `app.run_async`. Nagranie <0,3 s odrzucane jako przypadkowe kliknięcie.
- **Tylko polski** — `language="pl"` na sztywno, brak wyboru języka w UI;
  `fp16=False` (fix NaN na NVIDIA z oryginalnego skryptu).
- **Pakiety opcjonalne i leniwe importy** — bez `openai-whisper`/`sounddevice`
  aplikacja działa normalnie, REC pokazuje komendę `pip install ...`.
  Ciężkiego torcha nie importuje się przy starcie (kilka sekund i ~1 GB RAM
  każdorazowo), dopiero przy pierwszym wejściu w REC i tylko gdy model
  jest już pobrany.
- **Zarządzanie modelami w Ustawieniach** — wiersze tiny/base/small/medium
  (medium oznaczone "za ciężki dla GTX 1650 4GB", large celowo pominięty),
  akcje Pobierz/Użyj/usuń, markery AKTYWNY/●, blokada usunięcia aktywnego,
  flaga busy podczas pobierania (w tle, przez run_async). Pliki w
  `~/.cache/whisper/` — wspólny cache z innymi narzędziami Whispera.
- **Domyślny model `small`** (config: `whisper_model`) — rekomendacja pod
  GTX 1650 4GB; konfiguracja od razu zapisywana (akcje jednoklikowe,
  nie przez przycisk Zapisz).
- **➡ Użyj jako prompt** — transkrypcja wpada do pola promptu
  (w Kreatorze do pola Zadanie) z powrotem do widoku głównego;
  📋 Kopiuj do schowka.
- `requirements.txt`: pakiety głosowe jako zakomentowany blok opcjonalny
  (+ wskazówka torch+CUDA dla GTX 1650).

## Porządki przed „produkcją" (v4)

- **README.md** — instalacja, pakiety systemowe (Linux: `python3-tk`,
  `xclip`/`xsel` dla schowka), skróty, lokalizacja konfiguracji, FAQ.
- **Zużycie tokenów** — `openrouter._chat` (i wywołania publiczne) przyjął
  `with_usage=True`; po każdym zapytaniu status pokazuje
  „Gotowe · zużyte tokeny: 1 234" (twarda spacja jako separator tysięcy).
  Detekcja „zielonego" statusu po prefixie — doklejony licznik nie psuje koloru.
- **Start bez klucza API** — status od razu prowadzi do Ustawień,
  zamiast pierwszej nieudanej wysyłki.
- **Zapamiętywanie geometrii okna** (`config.geometry`) + zapis pól Kreatora
  przy zamykaniu [X] (`WM_DELETE_WINDOW`).
- **Guard na Ustawieniach** — jeden egzemplarz okna (`is_alive()`/`lift()`),
  bez stosu duplikatów.
- **Przycisk „Wyczyść"** nad polem wejścia (czyści wejście/pola Kreatora,
  wynik i stan tłumaczenia). Uwaga implementacyjna: stanął NAD etykietą pola,
  bo w dolnym pasku przy czterech stałych przyciskach był ucinany do zera
  szerokości na części systemów (pack clipuje przy przepełnieniu ramki).
- Katalog konfiguracyjny dostaje 700 także gdy istniał wcześniej.

## Tryb Systemowy (v3) 🆕

- Czwarty radio: **Systemowy**. Użytkownik wpisuje luźny opis asystenta
  (rola, zadania, styl, ograniczenia), a aplikacja generuje **gotowy prompt
  systemowy** w drugiej osobie („Jesteś …") z rolami, zasadami i zachowaniami
  granicznymi — do wklejenia w dowolne narzędzie LLM.
- Osobna, dedkowana meta-instrukcja `SYSTEM_PROMPT_CREATE_INSTRUCTION`
  w `openrouter.py` — celowo NIE jest to `config.system_prompt` (tamta
  optymalizuje prompty użytkownika; tu cel jest inny) i celowo bez doklejania
  fragmentów stylu.
- `openrouter.create_system_prompt()` z własnym framowaniem
  `_frame_for_system_prompt()` — ten sam wzorzec anty-pomyłkowy co w pozostałych
  (opis asystenta sam potrafi wyglądać jak polecenie, więc słabsze modele
  zachowywałyby się jak asystent zamiast wyprodukować prompt).
- Przydatny duet: **„Przetłumacz → EN"** działa i tu bez zmian — system prompt
  po angielsku często działa lepiej, więc generujemy PL → tłumaczymy → kopiujemy.
- Wspólny przepływ: wynik trafia w to samo pole, Kopiuj/EN działają tak samo;
  tryb zapamiętuje się w configu jak pozostałe.

## Tryb Kreator + trwała lista modeli (v2)

### Nowy tryb: Kreator 🆕
- Trzeci radio obok Standard/Mega. Zamiast jednego pola, użytkownik wypełnia
  **składowe profesjonalnego promptu** — każda z podpowiedzią co powinna zawierać:
  1. **Rola modelu** — kim ma być AI (▾: 9 gotowych ról),
  2. **Zadanie i cel** — pole wielolinijkowe (rozciąga się z oknem),
  3. **Odbiorca** i 4. **Format odpowiedzi** — obok siebie (▾ gotowce),
  5. **Ograniczenia i wymagania** — ▾ DOKLEJA kolejne pozycje po średniku
     (można zebrać kilka: długość, ton, język...).
- Każde pole to Entry — gotowiec z listy można zawsze swobodnie edytować
  albo wpisać własną wartość od ręki.
- Wymagane jest tylko **Zadanie**; puste pola są pomijane przy składaniu.
- Złożony szkic (`Rola: ... / Zadanie: ... / Odbiorca: ... ...`) trafia do
  **tego samego potoku optymalizacji** co tryb Standard — model przepisuje
  go na dopracowany prompt; tłumaczenie → EN działa bez zmian.
- Wypełnione pola **zapamiętują się w configu** (klucz `builder`) i wracają
  po restarcie / przełączeniu trybu.
- Układ: przy przełączeniu na Kreatora obszar wejścia rośnie kosztem pola
  wyniku (wagi siatki 5:3 zamiast 2:7).
- Enter w jednolinijkowych rubrykach = Wyślij; w Zadaniu = nowa linia.
  Globalny Ctrl+Enter działa wszędzie, jak dotychczas.

### Lista modeli pobierana RAZ (trwale)
- Pobrana lista zapamiętywana w configu (`models`) — kolejne otwarcia
  Ustawień: zero sieci, natychmiastowa lista.
- Przycisk **↻** przy polu modelu wymusza ponowne pobranie (na wypadek
  chęci odświeżenia).
- Awaryjnej listy NIE zapisujemy na stałe — przy błędzie sieci aplikacja
  ponowi próbę przy kolejnym otwarciu ustawień.

### Drobiazgi techniczne
- `ModelPopover` przemianowany na **`ListPopover`** (uogólniony: opcjonalne
  width/height, włączany filtr) — ten sam widget obsługuje teraz i listę
  modeli w Ustawieniach, i listy gotowców w Kreatorze; metoda
  `update_models` → `update_items`.
- Usunięty sesyjny `App.models_cache` (zastąpiony trwałym `config.models`).
- `config.py`: nowe klucze `models` i `builder` (+ properties), uwaga o
  trzecim trybie w komentarzu `mode`.

## Co zostało zmienione (refaktoryzacja, bez zmian funkcji)

### Podział monolitycznego `main.py` (~850 ln) na moduły
- Stała paleta kolorów i helpery (`theme.py`) są importowane z jednego miejsca
  — wcześniej w `app.py` zdarzyły się zahardkodowane duplikaty kolorów
  (`#3C3C3C`, `#0E639C` w ramce pytań), teraz wszystko idzie z palety.
- `ModelPopover` dostał metodę `update_models()` (patrz niżej).
- Okno ustawień to klasa `SettingsWindow` zbudowana z sekcji-metod
  (wcześniej ~230-liniowa metoda `open_options`).

### Naprawa zamrażania UI w Ustawieniach ⚡
- **Było:** `openrouter.get_models()` wywoływany synchronicznie na wątku UI
  przy każdym otwarciu Ustawień → zamrożenie okna do 10 s (timeout).
- **Jest:** okno otwiera się natychmiast na awaryjnej liście modeli,
  pełna lista dociąga się w tle wątkiem roboczym i jest podmieniana nawet
  w już otwartym popoverze; wynik trafia do sesyjnego cache (`App.models_cache`),
  więc kolejne otwarcia są błyskawiczne.
- Klucz API do zapytania o modele brany jest z pola w oknie (niezapisane zmiany
  działają), ale odczyt widgetu dzieje się na wątku UI — tkinter nie jest
  thread-safe.

### Config — bezpieczeństwo i porządek
- Plik konfiguracji dostaje uprawnienia **600**, katalog **700**
  (zawiera klucz API).
- Backfill brakujących kluczy kopiuje wartości z `DEFAULT_CONFIG` **głęboko**
  — usunięty ukryty bug: config dzielił mutowalną listę fragmentów
  z globalnym `DEFAULT_CONFIG`.
- Martwe metody `add_snippet`/`update_snippet`/`delete_snippet`/
  `selected_snippet_texts` (nigdy nieużywane) zastąpione jedną metodą
  **`set_snippets()`**, z której faktycznie korzysta okno ustawień
  (nadaje id nowym wpisom, czyści zaznaczenie usuniętych fragmentów).
  Ręczne `import uuid as _uuid` we wnętrzu zapisu nie jest już potrzebne.

### Drobne porządki
- `_run_async` → **`run_async`** (publiczne, używa też okno ustawień),
  `_models_cache` → `models_cache`, `_refresh_snippet_button` →
  `refresh_snippet_button`.
- `SettingsWindow` sprząta bindingi kółka myszy tylko przy zamknięciu okna
  (`<Destroy>` w tkinter odpala się też dla widgetów-dzieci).
- Usunięta nieużywana ramka `content_w` w oknie ustawień (martwy kod).
- Kluczowe komentarze "dlaczego" (grab po <Map>, framowanie promptów itp.)
  zachowane razem z kodem, do którego się odnoszą.

## Testy
- `test_smoke_gui.py` — 20 scenariuszy (+ 8b/10b/11b) na wirtualnym ekranie (Xvfb): m.in.
  stany przycisków, walidacja wysyłki, tryby Mega/Kreator/Systemowy, popovery,
  kontrakt wątkowy `run_async`, sekwencja wolnej sieci (fallback → podmiana
  w otwartym popoverze → zapis TRWAŁY → zero sieci), edycja biblioteki,
  zapis ustawień, Wyczyść, **tokeny w statusie**, guard okien Ustawień, **REC: przełączanie widoków**, **fallback bez
  pakietów whisper** (komunikat z komendą instalacji), metadane modeli
  i stan cache w `voicenotes.py`, **panel fragmentów** (parentalizacja,
  wagi wiersza, klik=wybór, bulk-guziki) i **migracja legacy biblioteki**.
- Testy Config: uprawnienia plików, deepcopy backfillu, `set_snippets`,
  round-trip zapis/odczyt.
- `shot_driver.py` + `docs/` — zrzuty ekranu UI robione pod Xvfb (utility,
  nie część aplikacji).

## Propozycje na dalszą rozbudowę (niezrealizowane)
1. **Historia promptów** — zapis wyników w JSON, panel przeglądania, ulubione.
2. Licznik znaków/tokenów i szacunek kosztu (OpenRouter zwraca `usage`).
3. Retry/backoff przy HTTP 429.
4. Presety promptów systemowych (np. kod / marketing / tekst).
5. Pakowanie do jednego pliku wykonywalnego (PyInstaller).
