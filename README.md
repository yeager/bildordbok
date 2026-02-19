# 📖 Bildordbok

Tvåspråkig bildordbok med TTS – för barn med språkstörning och nyanlända.

> **Målgrupp / Target audience:** Barn och vuxna med språkstörning (DLD), autism,
> intellektuell funktionsnedsättning, samt nyanlända som lär sig svenska. Bildordboken
> ger visuellt stöd med bilder, text och uppläsning på två språk.
>
> **For:** Children and adults with developmental language disorder (DLD), autism
> spectrum disorder (ASD), intellectual disabilities, and newcomers learning Swedish.
> The picture dictionary provides visual support with images, text, and text-to-speech
> in two languages.

## Funktioner

- **6 kategorier**: Djur, Mat, Kläder, Kroppen, Hem, Skola
- **80+ ord** med bilder och text på svenska + engelska
- **ARASAAC-piktogram** — automatisk nedladdning av fria piktogram från
  [ARASAAC](https://arasaac.org) (CC BY-NC-SA, Gobierno de Aragón / Sergio Palao)
- Emoji som reserv vid offline
- **TTS-uppläsning** på båda språken (via espeak-ng)
- **Spaced Repetition** flashcards för effektiv inlärning
- **Sökfunktion** för att snabbt hitta ord
- **Mörkt/ljust tema** toggle
- Modern GTK4/Adwaita-design

## Fria bildresurser

| Resurs | Licens | URL |
|--------|--------|-----|
| **ARASAAC** | CC BY-NC-SA 4.0 | https://arasaac.org |
| **OpenMoji** | CC BY-SA 4.0 | https://openmoji.org |
| **Mulberry Symbols** | CC BY-SA 2.0 UK | https://mulberrysymbols.org |
| **Sclera** | CC BY-NC 2.0 BE | https://sclera.be |

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

## ARASAAC-attribution

Piktografiska symboler © Gobierno de Aragón, skapade av Sergio Palao för
[ARASAAC](https://arasaac.org), distribuerade under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

## Licens

GPL-3.0-or-later © Daniel Nylander
