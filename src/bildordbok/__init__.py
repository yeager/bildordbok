"""Bildordbok – tvåspråkig bildordbok med TTS."""
__version__ = "0.1.0"

import gettext
import locale
import os

LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "po", "locale")

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass

gettext.bindtextdomain("bildordbok", LOCALE_DIR)
gettext.textdomain("bildordbok")
_ = gettext.gettext
