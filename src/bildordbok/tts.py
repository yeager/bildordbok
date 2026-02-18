"""TTS support using espeak-ng or piper."""

from __future__ import annotations
import subprocess
import shutil


def speak(text: str, lang: str = "sv"):
    """Speak text using espeak-ng. lang: 'sv' or 'en'."""
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak:
        return
    lang_map = {"sv": "sv", "en": "en"}
    voice = lang_map.get(lang, lang)
    try:
        subprocess.Popen(
            [espeak, "-v", voice, "-s", "130", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
