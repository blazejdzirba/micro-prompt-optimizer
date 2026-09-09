"""Konfiguracja aplikacji przechowywana w pliku JSON.

Zmiany po refaktoryzacji:
- plik z konfiguracją dostaje uprawnienia 600 (tylko właściciel) — zawiera
  klucz API; katalog konfiguracyjny 700,
- backfill brakujących kluczy kopiuje wartości z DEFAULT_CONFIG GŁĘBOKO
  (wcześniej config dzielił mutowalną listę fragmentów z DEFAULT_CONFIG —
  edycja biblioteki po aktualizacji programu modyfikowałaby globalny default),
- jedna metoda set_snippets() zamiast trzech martwych (nigdy nieużywanych):
  okno ustawień pracuje na roboczej kopii biblioteki i podmienia ją w całości.
"""

import copy
import json
import os
import uuid

CONFIG_DIR = os.path.expanduser("~/.config/micro-prompt-optimizer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_SYSTEM_PROMPT = (
    "Jesteś ekspertem w dziedzinie inżynierii promptów (prompt engineering). "
    "Twoim zadaniem jest ulepszyć prompt dostarczony przez użytkownika, aby był bardziej precyzyjny, efektywny i dawał lepsze rezultaty w modelach językowych.\n\n"
    "Zasady transformacji:\n"
    "1. Zachowaj oryginalną intencję i cel promptu użytkownika.\n"
    "2. Dodaj jasną rolę dla modelu (np. \"Jesteś ekspertem ds. marketingu\").\n"
    "3. Doprecyzuj oczekiwany format odpowiedzi (np. lista, akapit, tabela, JSON).\n"
    "4. Dodaj kryteria sukcesu lub jakościowe (np. \"odpowiedź powinna być zwięzła, nie dłuższa niż 100 słów\").\n"
    "5. Jeśli to konieczne, dodaj kontekst lub przykłady.\n"
    "6. Unikaj niejasności i wieloznaczności.\n\n"
    "Ważne: Odpowiedz WYŁĄCZNIE treścią ulepszonego promptu. Nie dodawaj żadnych komentarzy, wyjaśnień, nagłówków ani cudzysłowów. "
    "Po prostu zwróć gotowy prompt, który użytkownik mógłby wkleić gdzie indziej."
)

# Domyślna, wbudowana biblioteka fragmentów — użytkownik może dodawać własne
# w Ustawieniach. Fragmenty są doklejane do system_prompt TYLKO gdy zaznaczone
# na liście „Fragmenty" w głównym oknie (widget wbudowany — nie popover).
# Katalog świadomie ograniczony do 6 kategorii: budowa promptów dla agenta LLM,
# asystent programisty, koder (pair programming), webowy agent LLM,
# struktury JSON/YAML i dokumentacja techniczna.
LEGACY_DEFAULT_SNIPPETS = [
    {
        "id": "default-styl-zwiezly",
        "name": "Styl: zwięzły i konkretny",
        "text": (
            "1. Lead with the next action.\n"
            "2. Number multi-step tasks.\n"
            "3. End with one concrete next step.\n"
            "4. Suppress tangents.\n"
            "5. Restate state every turn.\n"
            "6. Specific time estimates (minutes, not \"a bit\").\n"
            "7. Make wins visible.\n"
            "8. Matter-of-fact errors.\n"
            "9. Cap lists at 5 items.\n"
            "10. No preamble. No recap. No closers."
        ),
    },
]

DEFAULT_SNIPPETS = [
    {
        "id": "rola-prompty-agent-llm",
        "name": "Rola: budowa promptów dla agenta LLM",
        "text": (
            "Jesteś ekspertem od projektowania system promptów dla agentów LLM "
            "(autonomiczne użycie narzędzi, pętla decyzyjna). Każdy prompt zawiera: "
            "cel i zakres agenta, listę dostępnych narzędzi z kontraktem (wejście/wyjście), "
            "jawne reguły MUST/NEVER, strategię radzenia sobie z błędami narzędzi "
            "(retry/limit/eskala-do-użytkownika) oraz format końcowej odpowiedzi. "
            "Reguły numerujesz i unikasz rozmytych sformułowań typu „postaraj się”."
        ),
    },
    {
        "id": "rola-asystent-programisty",
        "name": "Rola: asystent programisty",
        "text": (
            "Jesteś moim asystentem programisty. Odpowiadasz po polsku; kod, nazwy "
            "symboli i komunikaty błędów zostawiasz po angielsku. Zanim odpiszesz, "
            "sprawdź kompletność rozwiązania (importy, typy, przypadki brzegowe). "
            "Przy niejasnych wymaganiach zadaj maksymalnie 2 kluczowe pytania i jednocześnie "
            "pokaż rozwiązanie na jawnych założeniach. Podaj minimalny, działający przykład."
        ),
    },
    {
        "id": "rola-koder-pair",
        "name": "Rola: koder (pair programming)",
        "text": (
            "Jesteś moim pair-programmerem. Piszesz w tym języku i frameworku, "
            "w którym pracuję, i dopasowujesz się do stylu istniejącego kodu "
            "(nazewnictwo, wcięcia, konwencje importów). Zmiany przedstawiasz diff-first: "
            "najpierw 1-2 zdania „co i dlaczego zmieniam”, potem fragment kodu. "
            "Nie przepisujesz całych plików, gdy wystarczy łatka. "
            "Ostrzegasz, gdy zmiana ma efekty uboczne poza edytowanym miejscem."
        ),
    },
    {
        "id": "rola-webowy-agent-llm",
        "name": "Rola: webowy agent LLM",
        "text": (
            "Projektujesz zachowanie agenta LLM działającego w interfejsie webowym "
            "(chat w przeglądarce). Definiujesz: spójną z marką personę i ton, "
            "granice tematyczne (czego agent NIE obsługuje), politykę anty-halucynacyjną "
            "(cytowanie źródeł albo jawne „nie wiem”), reguły przekierowania do człowieka "
            "oraz obsługę danych osobowych zgodnie z minimalizacją. "
            "Odpowiedzi agenta są zwięzłe i renderowalne w chmurkach czatu."
        ),
    },
    {
        "id": "format-json-yaml",
        "name": "Format: struktury JSON/YAML",
        "text": (
            "Wynik ZAWSZE zwracasz jako poprawną strukturę JSON lub YAML: "
            "czytelne klucze na top-level, wartości zgodne typami z podanym przykładem/schematem. "
            "JSON: bez komentarzy i bez końcowych przecinków; stringi w podwójnych cudzysłowach. "
            "YAML: wcięcia 2 spacje, komentarz nad każdą sekcją, wartości z dwukropkiem/tyldą "
            "w cudzysłowie. Przed zwróceniem mentalnie parsujesz wynik i poprawiasz błędy."
        ),
    },
    {
        "id": "rola-dokumentacja-techniczna",
        "name": "Rola: dokumentacja techniczna",
        "text": (
            "Piszesz dokumentację techniczną dla programistów: na wejściu krótki opis "
            "„po co i kiedy”, potem sygnatury API z params/returns/wyjątkami, "
            "minimalny działający przykład użycia i sekcja „Edge cases & gotchas”. "
            "Zdania krótkie, terminologia konsekwentna, wersjonowanie (since/deprecated) "
            "tam, gdzie ma to znaczenie. Linkujesz do źródeł zamiast streszczać je z błędami."
        ),
    },
]

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "openai/gpt-4o",
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "mode": "standard",            # "standard" | "mega" | "kreator" | "systemowy"
    "snippets": DEFAULT_SNIPPETS,  # biblioteka fragmentów (edytowalna)
    "selected_snippets": [],       # id-y aktualnie aktywnych fragmentów
    "models": [],                  # raz pobrana lista modeli (id), trwała w configu
    "builder": {},                 # ostatnie wartości pól trybu Kreator
    "geometry": "",                # zapamiętany rozmiar/pozycja okna (np. "560x720+100+80")
    "whisper_model": "small",      # aktywny model Whispera do notatek głosowych
}


class Config:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        """Wczytuje konfigurację z pliku JSON. Jeśli plik nie istnieje,
        tworzy go z domyślnymi wartościami."""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, mode=0o700)   # config zawiera klucz API
        else:
            try:
                os.chmod(CONFIG_DIR, 0o700)       # katalog mógł powstać dawniej
            except OSError:
                pass
        if not os.path.isfile(CONFIG_FILE):
            self.data = copy.deepcopy(DEFAULT_CONFIG)
            self.save()   # save() już ustawia uprawnienia pliku
        else:
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                # uszkodzony plik (np. przerwany zapis) nie może bliźnić
                # aplikacji — zostawiamy ślad obok defaultów
                try:
                    os.replace(CONFIG_FILE, CONFIG_FILE + ".bak")
                except OSError:
                    pass
                self.data = copy.deepcopy(DEFAULT_CONFIG)
                self.save()
        # Upewnij się, że wszystkie klucze istnieją (np. po aktualizacji
        # programu). Głęboka kopia — inaczej config dzieliłby mutowalne
        # listy/słowniki z globalnym DEFAULT_CONFIG.
        for key, value in DEFAULT_CONFIG.items():
            if key not in self.data:
                self.data[key] = copy.deepcopy(value)
        # Migracja per-wpis: jeśli w bibliotece jest stary domyślny fragment,
        # dopisz do niej nowe domyślne wpisy (których jeszcze nie ma), zamiast
        # podmieniać całą listę — własne fragmenty użytkownika pozostają.
        legacy_ids = {s["id"] for s in LEGACY_DEFAULT_SNIPPETS}
        current = self.data.get("snippets", [])
        if any(s.get("id") in legacy_ids for s in current):
            existing_ids = {s["id"] for s in current}
            for s in DEFAULT_SNIPPETS:
                if s["id"] not in existing_ids:
                    current.append(copy.deepcopy(s))
            self.data["snippets"] = current
            ids = {s["id"] for s in self.data["snippets"]}
            self.data["selected_snippets"] = [
                sid for sid in self.data.get("selected_snippets", []) if sid in ids]
            self.save()

    def save(self):
        """Zapisuje bieżącą konfigurację ATOMOWO (tmp + os.replace):
        przerwanie w połowie zapisu nie zostawi pół-pliku, który zabiłby
        następny start aplikacji (i zmusił do przywracania klucza API)."""
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())              # zapis fizycznie na dysku
        os.replace(tmp, CONFIG_FILE)          # atomowa podmiana
        try:
            os.chmod(CONFIG_FILE, 0o600)   # klucz API tylko dla właściciela
        except OSError:
            pass                           # Windows: bity uprawnień ignorowane

    @property
    def api_key(self):
        return self.data.get("api_key", "")

    @api_key.setter
    def api_key(self, value):
        self.data["api_key"] = value

    @property
    def model(self):
        return self.data.get("model", "openai/gpt-4o")

    @model.setter
    def model(self, value):
        self.data["model"] = value

    @property
    def system_prompt(self):
        return self.data.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

    @system_prompt.setter
    def system_prompt(self, value):
        self.data["system_prompt"] = value

    @property
    def mode(self):
        return self.data.get("mode", "standard")

    @mode.setter
    def mode(self, value):
        self.data["mode"] = value

    @property
    def snippets(self):
        return self.data.get("snippets", [])

    @property
    def selected_snippets(self):
        return self.data.get("selected_snippets", [])

    @selected_snippets.setter
    def selected_snippets(self, value):
        self.data["selected_snippets"] = value

    @property
    def models(self):
        """Raz pobrana lista ID modeli z OpenRouter (trwała — w configu)."""
        return self.data.get("models", [])

    @models.setter
    def models(self, value):
        self.data["models"] = value

    @property
    def builder(self):
        """Ostatnio wypełnione pola trybu Kreator (słownik pól składowych)."""
        return self.data.get("builder", {})

    @builder.setter
    def builder(self, value):
        self.data["builder"] = value

    @property
    def geometry(self):
        """Zapamiętana geometria okna (string tk, np. "560x720+100+80" lub "")."""
        return self.data.get("geometry", "")

    @geometry.setter
    def geometry(self, value):
        self.data["geometry"] = value

    @property
    def whisper_model(self):
        """Aktywny model Whispera do notatek głosowych (tiny/base/small/…)."""
        return self.data.get("whisper_model", "small")

    @whisper_model.setter
    def whisper_model(self, value):
        self.data["whisper_model"] = value

    # -- biblioteka fragmentów --
    def set_snippets(self, snippets):
        """Podmienia całą bibliotekę fragmentów (np. zapisaną z okna ustawień).

        Wpisom bez id nadaje nowe identyfikatory i czyści zaznaczenie
        fragmentów, które zostały usunięte. Okno ustawień pracuje na roboczej
        kopii listy — "Anuluj" po prostu ich nie zapisuje.
        """
        normalized = []
        for s in snippets:
            if not s.get("id"):
                s = {**s, "id": uuid.uuid4().hex[:8]}
            normalized.append(s)
        self.data["snippets"] = normalized
        valid = {s["id"] for s in normalized}
        self.data["selected_snippets"] = [
            i for i in self.data.get("selected_snippets", []) if i in valid
        ]
