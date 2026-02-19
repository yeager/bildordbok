"""ARASAAC pictogram provider for AAC applications.

Fetches pictograms from the ARASAAC API (https://arasaac.org) and caches
them locally. ARASAAC pictograms are licensed under Creative Commons
BY-NC-SA 4.0 by the Government of Aragon, created by Sergio Palao.

Usage:
    provider = ArasaacProvider(cache_dir="~/.cache/arasaac")
    pixbuf_path = await provider.get_pictogram("eat", lang="en")
"""

from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError


ARASAAC_API = "https://api.arasaac.org/v1"
ARASAAC_SEARCH = f"{ARASAAC_API}/pictograms/{{lang}}/search/{{term}}"
ARASAAC_IMAGE = f"{ARASAAC_API}/pictograms/{{picto_id}}"

# Default image parameters
DEFAULT_PARAMS = "?download=false&plural=false&color=true"


class ArasaacProvider:
    """Fetches and caches ARASAAC pictograms."""

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

    def search(self, term: str, lang: str = "en") -> Optional[int]:
        """Search for a pictogram by term, return pictogram ID or None."""
        cache_key = f"{lang}:{term}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        url = ARASAAC_SEARCH.format(lang=lang, term=term)
        try:
            req = Request(url, headers={"Accept": "application/json"})
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

    def get_image_path(self, picto_id: int, resolution: int = 300) -> Optional[str]:
        """Download pictogram image and return local file path."""
        filename = f"{picto_id}_{resolution}.png"
        local_path = self.cache_dir / filename
        if local_path.exists():
            return str(local_path)

        url = f"{ARASAAC_IMAGE}/{picto_id}{DEFAULT_PARAMS}&resolution={resolution}"
        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                data = resp.read()
                local_path.write_bytes(data)
                return str(local_path)
        except (URLError, OSError):
            pass
        return None

    def get_pictogram(self, term: str, lang: str = "en",
                      resolution: int = 300) -> Optional[str]:
        """Search for term and return local image path, or None."""
        picto_id = self.search(term, lang=lang)
        if picto_id is not None:
            return self.get_image_path(picto_id, resolution=resolution)
        return None


# Singleton for convenience
_default_provider: Optional[ArasaacProvider] = None


def get_provider() -> ArasaacProvider:
    """Get or create the default ARASAAC provider."""
    global _default_provider
    if _default_provider is None:
        _default_provider = ArasaacProvider()
    return _default_provider
