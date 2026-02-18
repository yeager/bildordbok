# 📖 Bildordbok

Tvåspråkig bildordbok med TTS – för barn med språkstörning och nyanlända.

## Funktioner

- **6 kategorier**: Djur, Mat, Kläder, Kroppen, Hem, Skola
- **80+ ord** med emoji-bilder och text på svenska + engelska
- **TTS-uppläsning** på båda språken (via espeak-ng)
- **Spaced Repetition** flashcards för effektiv inlärning
- **Sökfunktion** för att snabbt hitta ord
- **Mörkt/ljust tema** toggle
- Modern GTK4/Adwaita-design

## Installation

```bash
# Beroenden (Fedora/RHEL)
sudo dnf install python3-gobject gtk4 libadwaita espeak-ng

# Beroenden (Debian/Ubuntu)
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 espeak-ng

# Installera
pip install -e .

# Kör
bildordbok
```

## Utveckling

```bash
git clone https://github.com/yeager/bildordbok.git
cd bildordbok
pip install -e .
python -m bildordbok.main
```

## Tangentbord

- `Ctrl+Q` — Avsluta
- `Ctrl+F` — Sök

## Licens

GPL-3.0-or-later © Daniel Nylander
