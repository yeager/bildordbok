"""ARASAAC pictogram provider with Swedish ordlista integration.

Fetches pictograms from the ARASAAC API (https://arasaac.org) and caches
them locally. Includes Swedish ↔ English translation mapping (15,606 terms)
by Daniel Nylander, enabling Swedish pictogram search with intelligent
fallback strategies.

ARASAAC pictograms are licensed under Creative Commons BY-NC-SA 4.0
by the Government of Aragon, created by Sergio Palao.

Usage:
    provider = get_provider()
    # Swedish search (tries Swedish + English terms):
    path = provider.get_pictogram("katt", lang="sv", resolution=300)
    # English search (adds Swedish labels):
    path = provider.get_pictogram("cat", lang="en", resolution=300)
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Optional, List, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote


ARASAAC_API = "https://api.arasaac.org/v1"
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
    # Fallback: look in data/ relative to this file
    data_dir = Path(__file__).parent / "data"
    data_file = data_dir / filename
    if data_file.exists():
        return json.loads(data_file.read_text(encoding="utf-8"))
    return {}


class ArasaacProvider:
    """Enhanced ARASAAC provider with Swedish ordlista support."""

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = os.path.join(
                os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                "arasaac",
            )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load ordlista
        self._en2sv: Optional[Dict[str, str]] = None
        self._sv2en: Optional[Dict[str, List[str]]] = None
        
        # Search cache
        self._search_cache: Dict[str, List[Dict]] = {}
        self._load_search_cache()

    def _get_en2sv(self) -> Dict[str, str]:
        """Lazy-load English → Swedish ordlista."""
        if self._en2sv is None:
            self._en2sv = _load_json_data("arasaac_en2sv.json")
        return self._en2sv

    def _get_sv2en(self) -> Dict[str, List[str]]:
        """Lazy-load Swedish → English reverse lookup."""
        if self._sv2en is None:
            en2sv = self._get_en2sv()
            sv2en = {}
            for en_term, sv_term in en2sv.items():
                if sv_term not in sv2en:
                    sv2en[sv_term] = []
                sv2en[sv_term].append(en_term)
            self._sv2en = sv2en
        return self._sv2en

    def translate_sv(self, en_term: str) -> str:
        """Get Swedish label for an English keyword, or return original."""
        return self._get_en2sv().get(en_term.lower(), en_term)

    def _load_search_cache(self):
        """Load search cache from disk."""
        cache_file = self.cache_dir / "search_cache_v2.json"
        if cache_file.exists():
            try:
                self._search_cache = json.loads(cache_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._search_cache = {}

    def _save_search_cache(self):
        """Save search cache to disk."""
        cache_file = self.cache_dir / "search_cache_v2.json"
        try:
            cache_file.write_text(json.dumps(self._search_cache, ensure_ascii=False))
        except OSError:
            pass

    def _api_search(self, term: str, lang: str = "en") -> List[Dict]:
        """Search ARASAAC API for pictograms."""
        encoded_term = quote(term)
        url = f"{ARASAAC_API}/pictograms/{lang}/search/{encoded_term}"
        
        try:
            req = Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Bildordbok-Swedish-Ordlista/1.0"
            })
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data if isinstance(data, list) else []
        except (URLError, json.JSONDecodeError, KeyError):
            return []

    def search_swedish(self, sv_term: str, limit: int = 20) -> List[Dict]:
        """
        Search for Swedish term using intelligent lookup strategy:
        1. Try Swedish directly with ARASAAC API
        2. Find English equivalents and search those
        3. Combine results and add Swedish labels
        """
        sv_term_lower = sv_term.lower().strip()
        cache_key = f"sv:{sv_term_lower}"
        
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        
        results = []
        seen_ids = set()
        
        # Strategy 1: Try Swedish term directly
        swedish_results = self._api_search(sv_term, lang="sv")
        for result in swedish_results[:limit//2]:  # Limit Swedish results
            picto_id = result.get("_id")
            if picto_id and picto_id not in seen_ids:
                seen_ids.add(picto_id)
                result["swedish_keyword"] = sv_term
                results.append(result)
        
        # Strategy 2: Find English equivalents and search those
        sv2en = self._get_sv2en()
        if sv_term_lower in sv2en:
            english_terms = sv2en[sv_term_lower]
            for en_term in english_terms[:3]:  # Limit English terms
                english_results = self._api_search(en_term, lang="en")
                for result in english_results[:5]:  # Limit per English term
                    picto_id = result.get("_id")
                    if picto_id and picto_id not in seen_ids:
                        seen_ids.add(picto_id)
                        result["swedish_keyword"] = sv_term
                        results.append(result)
                    
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
        
        # Cache the results
        self._search_cache[cache_key] = results[:limit]
        self._save_search_cache()
        
        return results[:limit]

    def search_english(self, en_term: str, limit: int = 20) -> List[Dict]:
        """Search for English term and add Swedish labels where available."""
        cache_key = f"en:{en_term.lower()}"
        
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        
        results = self._api_search(en_term, lang="en")
        
        # Add Swedish keywords where available
        en2sv = self._get_en2sv()
        for result in results:
            # Find best English keyword to translate
            for kw in result.get("keywords", []):
                if kw.get("locale") == "en":
                    en_keyword = kw.get("keyword", "").lower()
                    if en_keyword in en2sv:
                        result["swedish_keyword"] = en2sv[en_keyword]
                        break
        
        self._search_cache[cache_key] = results[:limit]
        self._save_search_cache()
        
        return results[:limit]

    def search(self, term: str, lang: str = "sv") -> Optional[int]:
        """Search for a pictogram by term, return pictogram ID or None."""
        results = self.search_multiple(term, lang, limit=1)
        if results:
            return results[0].get("_id")
        return None

    def search_multiple(self, term: str, lang: str = "sv", limit: int = 60) -> List[Dict]:
        """Search and return multiple pictogram results."""
        if lang == "sv":
            return self.search_swedish(term, limit)
        else:
            return self.search_english(term, limit)

    def get_swedish_label(self, pictogram: Dict, fallback_lang: str = "en") -> str:
        """Get Swedish label for pictogram, with fallback to other languages."""
        # Check if we already have a Swedish keyword from search
        if "swedish_keyword" in pictogram:
            return pictogram["swedish_keyword"]
        
        # Try to find Swedish keyword in the pictogram data
        for kw in pictogram.get("keywords", []):
            if kw.get("locale") == "sv":
                return kw.get("keyword", "")
        
        # Try to translate English keyword to Swedish
        en2sv = self._get_en2sv()
        for kw in pictogram.get("keywords", []):
            if kw.get("locale") == "en":
                en_keyword = kw.get("keyword", "").lower()
                if en_keyword in en2sv:
                    return en2sv[en_keyword]
        
        # Fallback to original keyword
        keywords = pictogram.get("keywords", [])
        if keywords:
            return keywords[0].get("keyword", "")
        
        return str(pictogram.get("_id", ""))

    def get_image_path(self, picto_id: int, resolution: int = 300) -> Optional[str]:
        """Download and cache pictogram image."""
        if resolution not in VALID_RESOLUTIONS:
            resolution = min(VALID_RESOLUTIONS, key=lambda r: abs(r - resolution))
        
        filename = f"{picto_id}_{resolution}.png"
        local_path = self.cache_dir / filename
        
        if local_path.exists():
            return str(local_path)
        
        url = ARASAAC_IMAGE.format(picto_id=picto_id, resolution=resolution)
        
        try:
            req = Request(url, headers={"User-Agent": "Bildordbok-Swedish-Ordlista/1.0"})
            with urlopen(req, timeout=15) as resp:
                local_path.write_bytes(resp.read())
                return str(local_path)
        except (URLError, OSError):
            return None

    def get_pictogram(self, term: str, lang: str = "sv", resolution: int = 300) -> Optional[str]:
        """Search for term and return first matching pictogram image path."""
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
