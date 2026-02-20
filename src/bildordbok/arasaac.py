"""ARASAAC pictogram provider with Swedish keyword search.

Fetches pictograms from the ARASAAC API (https://arasaac.org) and caches
them locally. Includes a bundled Swedish keyword lookup (13,000+ terms)
translated by Daniel Nylander, enabling native Swedish pictogram search
without API calls.

ARASAAC pictograms are licensed under Creative Commons BY-NC-SA 4.0
by the Government of Aragon, created by Sergio Palao.

Usage:
    provider = get_provider()
    # Swedish search (uses local lookup — no API call needed):
    path = provider.get_pictogram("katt", lang="sv", resolution=300)
    # English search (uses ARASAAC API):
    path = provider.get_pictogram("cat", lang="en", resolution=300)
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError


ARASAAC_API = "https://api.arasaac.org/v1"
ARASAAC_SEARCH = ARASAAC_API + "/pictograms/{lang}/search/{term}"
ARASAAC_IMAGE = "https://static.arasaac.org/pictograms/{picto_id}/{picto_id}_{resolution}.png"

VALID_RESOLUTIONS = [300, 500, 2500]


def _load_json_data(filename: str) -> dict:
    """Load a JSON data file bundled with the package."""
    # Try importlib.resources first (works with installed packages)
    try:
        pkg = __name__.rsplit(".", 1)[0]  # e.g. "bildschema"
        ref = resources.files(pkg).joinpath("data").joinpath(filename)
        return json.loads(ref.read_text(encoding="utf-8"))
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass
    # Fallback: look in ../data/ relative to this file
    data_dir = Path(__file__).parent / "data"
    data_file = data_dir / filename
    if data_file.exists():
        return json.loads(data_file.read_text(encoding="utf-8"))
    # Last resort: package-level data/
    data_dir2 = Path(__file__).parent.parent / "data"
    data_file2 = data_dir2 / filename
    if data_file2.exists():
        return json.loads(data_file2.read_text(encoding="utf-8"))
    return {}


class ArasaacProvider:
    """Fetches and caches ARASAAC pictograms with Swedish support."""

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(
                os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                "arasaac",
            )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._search_cache: dict[str, int] = {}
        self._load_search_cache()
        # Swedish lookup: {sv_term: [picto_id, ...]}
        self._sv_lookup: Optional[dict] = None
        # English→Swedish for display labels
        self._en2sv: Optional[dict] = None

    def _get_sv_lookup(self) -> dict:
        """Lazy-load Swedish keyword → pictogram ID lookup."""
        if self._sv_lookup is None:
            self._sv_lookup = _load_json_data("arasaac_sv.json")
        return self._sv_lookup

    def _get_en2sv(self) -> dict:
        """Lazy-load English → Swedish keyword lookup."""
        if self._en2sv is None:
            self._en2sv = _load_json_data("arasaac_en2sv.json")
        return self._en2sv

    def translate_sv(self, en_term: str) -> str:
        """Get Swedish label for an English keyword, or return original."""
        return self._get_en2sv().get(en_term.lower(), en_term)

    def _load_search_cache(self):
        cache_file = self.cache_dir / "search_cache.json"
        if cache_file.exists():
            try:
                self._search_cache = json.loads(cache_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._search_cache = {}

    def _save_search_cache(self):
        cache_file = self.cache_dir / "search_cache.json"
        try:
            cache_file.write_text(json.dumps(self._search_cache))
        except OSError:
            pass

    def search_sv(self, term: str) -> list[int]:
        """Search Swedish term locally. Returns list of pictogram IDs."""
        lookup = self._get_sv_lookup()
        term_lower = term.lower().strip()
        # Exact match
        if term_lower in lookup:
            return lookup[term_lower]
        # Prefix match (for partial typing)
        matches = []
        for sv_term, ids in lookup.items():
            if sv_term.startswith(term_lower):
                matches.extend(ids)
            if len(matches) >= 60:
                break
        return matches

    def search(self, term: str, lang: str = "en") -> Optional[int]:
        """Search for a pictogram by term, return pictogram ID or None.

        For lang="sv", uses bundled Swedish lookup (no API call).
        For other languages, uses ARASAAC API.
        """
        if lang == "sv":
            ids = self.search_sv(term)
            if ids:
                return ids[0]
            return None

        cache_key = f"{lang}:{term}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        url = ARASAAC_SEARCH.format(lang=lang, term=term)
        try:
            req = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "DanneL10nSuite/1.0"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                if data and isinstance(data, list):
                    picto_id = data[0]["_id"]
                    self._search_cache[cache_key] = picto_id
                    self._save_search_cache()
                    return picto_id
        except (URLError, json.JSONDecodeError, KeyError, OSError):
            pass
        return None

    def search_multiple(self, term: str, lang: str = "sv",
                        limit: int = 60) -> list[int]:
        """Search and return multiple pictogram IDs."""
        if lang == "sv":
            return self.search_sv(term)[:limit]
        # For English, use API
        url = ARASAAC_SEARCH.format(lang=lang, term=term)
        try:
            req = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "DanneL10nSuite/1.0"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                if data and isinstance(data, list):
                    return [p["_id"] for p in data[:limit]]
        except (URLError, json.JSONDecodeError, KeyError, OSError):
            pass
        return []

    def get_image_path(self, picto_id: int, resolution: int = 300) -> Optional[str]:
        """Download pictogram image and return local file path."""
        resolution = min(VALID_RESOLUTIONS, key=lambda r: abs(r - resolution))
        filename = f"{picto_id}_{resolution}.png"
        local_path = self.cache_dir / filename
        if local_path.exists():
            return str(local_path)

        url = ARASAAC_IMAGE.format(picto_id=picto_id, resolution=resolution)
        try:
            req = Request(url, headers={"User-Agent": "DanneL10nSuite/1.0"})
            with urlopen(req, timeout=10) as resp:
                data = resp.read()
                local_path.write_bytes(data)
                return str(local_path)
        except (URLError, OSError):
            pass
        return None

    def get_pictogram(self, term: str, lang: str = "sv",
                      resolution: int = 300) -> Optional[str]:
        """Search for term and return local image path, or None.

        Default language is now Swedish.
        """
        picto_id = self.search(term, lang=lang)
        if picto_id is not None:
            return self.get_image_path(picto_id, resolution=resolution)
        return None


_default_provider: Optional[ArasaacProvider] = None


def get_provider() -> ArasaacProvider:
    """Get or create the default ARASAAC provider."""
    global _default_provider
    if _default_provider is None:
        _default_provider = ArasaacProvider()
    return _default_provider
