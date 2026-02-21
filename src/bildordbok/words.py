"""Word database for Bildordbok with categories and translations."""

from __future__ import annotations
import gettext
_ = gettext.gettext
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import random
import time

CATEGORIES = {
    "djur": {"name": _("Animals"), "icon": "🐾"},
    "mat": {"name": _("Food"), "icon": "🍎"},
    "klader": {"name": _("Clothes"), "icon": "👕"},
    "kroppen": {"name": _("Body"), "icon": "🫀"},
    "hem": {"name": _("Home"), "icon": "🏠"},
    "skola": {"name": _("School"), "icon": "📚"},
}

# Each word: (category, sv, en, emoji)
WORDS = [
    # Djur
    ("djur", "hund", "dog", "🐕"),
    ("djur", "katt", "cat", "🐈"),
    ("djur", "häst", "horse", "🐴"),
    ("djur", "ko", "cow", "🐄"),
    ("djur", "fågel", "bird", "🐦"),
    ("djur", "fisk", "fish", "🐟"),
    ("djur", "kanin", "rabbit", "🐇"),
    ("djur", "gris", "pig", "🐷"),
    ("djur", "anka", "duck", "🦆"),
    ("djur", "fjäril", "butterfly", "🦋"),
    ("djur", "björn", "bear", "🐻"),
    ("djur", "lejon", "lion", "🦁"),
    ("djur", "elefant", "elephant", "🐘"),
    ("djur", "orm", "snake", "🐍"),
    ("djur", "groda", "frog", "🐸"),
    # Mat
    ("mat", "äpple", "apple", "🍎"),
    ("mat", "banan", "banana", "🍌"),
    ("mat", "bröd", "bread", "🍞"),
    ("mat", "mjölk", "milk", "🥛"),
    ("mat", "ost", "cheese", "🧀"),
    ("mat", "ägg", "egg", "🥚"),
    ("mat", "fisk", "fish", "🐟"),
    ("mat", "kött", "meat", "🥩"),
    ("mat", "ris", "rice", "🍚"),
    ("mat", "soppa", "soup", "🍲"),
    ("mat", "glass", "ice cream", "🍦"),
    ("mat", "morot", "carrot", "🥕"),
    ("mat", "tomat", "tomato", "🍅"),
    ("mat", "vatten", "water", "💧"),
    ("mat", "juice", "juice", "🧃"),
    # Kläder
    ("klader", "tröja", "sweater", "🧥"),
    ("klader", "byxor", "pants", "👖"),
    ("klader", "skor", "shoes", "👟"),
    ("klader", "mössa", "hat", "🧢"),
    ("klader", "vantar", "mittens", "🧤"),
    ("klader", "jacka", "jacket", "🧥"),
    ("klader", "strumpor", "socks", "🧦"),
    ("klader", "klänning", "dress", "👗"),
    ("klader", "t-shirt", "t-shirt", "👕"),
    ("klader", "stövlar", "boots", "👢"),
    # Kroppen
    ("kroppen", "huvud", "head", "🗣️"),
    ("kroppen", "öga", "eye", "👁️"),
    ("kroppen", "öra", "ear", "👂"),
    ("kroppen", "näsa", "nose", "👃"),
    ("kroppen", "mun", "mouth", "👄"),
    ("kroppen", "hand", "hand", "✋"),
    ("kroppen", "fot", "foot", "🦶"),
    ("kroppen", "arm", "arm", "💪"),
    ("kroppen", "ben", "leg", "🦵"),
    ("kroppen", "mage", "stomach", "🫃"),
    ("kroppen", "hjärta", "heart", "❤️"),
    ("kroppen", "tand", "tooth", "🦷"),
    # Hem
    ("hem", "hus", "house", "🏠"),
    ("hem", "dörr", "door", "🚪"),
    ("hem", "fönster", "window", "🪟"),
    ("hem", "stol", "chair", "🪑"),
    ("hem", "bord", "table", "🪑"),
    ("hem", "säng", "bed", "🛏️"),
    ("hem", "lampa", "lamp", "💡"),
    ("hem", "tv", "tv", "📺"),
    ("hem", "kök", "kitchen", "🍳"),
    ("hem", "badrum", "bathroom", "🛁"),
    ("hem", "soffa", "sofa", "🛋️"),
    ("hem", "nyckel", "key", "🔑"),
    # Skola
    ("skola", "bok", "book", "📕"),
    ("skola", "penna", "pen", "✏️"),
    ("skola", "lärare", "teacher", "👩‍🏫"),
    ("skola", "skola", "school", "🏫"),
    ("skola", "väska", "bag", "🎒"),
    ("skola", "papper", "paper", "📄"),
    ("skola", "sax", "scissors", "✂️"),
    ("skola", "linjal", "ruler", "📏"),
    ("skola", "dator", "computer", "💻"),
    ("skola", "klocka", "clock", "🕐"),
    ("skola", "bänk", "desk", "🪑"),
    ("skola", "tavla", "board", "📋"),
]


@dataclass
class WordEntry:
    category: str
    sv: str
    en: str
    emoji: str
    # Spaced repetition fields
    ease: float = 2.5
    interval: int = 1  # days
    next_review: float = 0.0  # timestamp
    reps: int = 0

    @property
    def id(self) -> str:
        return f"{self.category}:{self.sv}"

    def get_text(self, lang: str) -> str:
        return getattr(self, lang, self.sv)

    def update_sr(self, quality: int):
        """Update spaced repetition. quality: 0-5 (0=forgot, 5=perfect)."""
        if quality < 3:
            self.reps = 0
            self.interval = 1
        else:
            if self.reps == 0:
                self.interval = 1
            elif self.reps == 1:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.ease)
            self.ease = max(1.3, self.ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            self.reps += 1
        self.next_review = time.time() + self.interval * 86400


class WordDatabase:
    def __init__(self):
        self.words: list[WordEntry] = []
        self._sr_path = Path(os.path.expanduser("~/.local/share/bildordbok/sr_data.json"))
        self._load_words()
        self._load_sr()

    def _load_words(self):
        for cat, sv, en, emoji in WORDS:
            self.words.append(WordEntry(category=cat, sv=sv, en=en, emoji=emoji))

    def _load_sr(self):
        if self._sr_path.exists():
            try:
                data = json.loads(self._sr_path.read_text())
                sr_map = {d["id"]: d for d in data}
                for w in self.words:
                    if w.id in sr_map:
                        d = sr_map[w.id]
                        w.ease = d.get("ease", 2.5)
                        w.interval = d.get("interval", 1)
                        w.next_review = d.get("next_review", 0.0)
                        w.reps = d.get("reps", 0)
            except Exception:
                pass

    def save_sr(self):
        self._sr_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {"id": w.id, "ease": w.ease, "interval": w.interval,
             "next_review": w.next_review, "reps": w.reps}
            for w in self.words if w.reps > 0
        ]
        self._sr_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def by_category(self, cat: str) -> list[WordEntry]:
        return [w for w in self.words if w.category == cat]

    def search(self, query: str) -> list[WordEntry]:
        q = query.lower().strip()
        if not q:
            return []
        return [w for w in self.words if q in w.sv.lower() or q in w.en.lower()]

    def due_for_review(self) -> list[WordEntry]:
        now = time.time()
        due = [w for w in self.words if w.next_review <= now]
        random.shuffle(due)
        return due[:20]

    def new_words(self, count: int = 10) -> list[WordEntry]:
        unseen = [w for w in self.words if w.reps == 0]
        random.shuffle(unseen)
        return unseen[:count]
