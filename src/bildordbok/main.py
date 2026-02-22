"""Bildordbok – main application."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, Pango, GdkPixbuf  # noqa: E402

from bildordbok.words import WordDatabase, WordEntry, CATEGORIES  # noqa: E402
from bildordbok.tts import speak  # noqa: E402
from bildordbok import __version__, _  # noqa: E402
from bildordbok import arasaac  # noqa: E402
from bildordbok.accessibility import apply_large_text
from bildordbok.accessibility import AccessibilityManager

APP_ID = "se.danielnylander.Bildordbok"


class WordCard(Gtk.Box):
    """A card showing a word with emoji, text in both languages and TTS buttons."""

    def __init__(self, word: WordEntry, on_speak=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.word = word
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.add_css_class("card")
        self.set_size_request(180, 200)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(8)

        # Try ARASAAC pictogram, fall back to emoji
        icon_widget = None
        try:
            provider = arasaac.get_provider()
            path = provider.get_pictogram(word.en, lang="en", resolution=128)
            if path:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, 96, 96, True)
                icon_widget = Gtk.Image.new_from_pixbuf(pixbuf)
                icon_widget.set_pixel_size(96)
        except Exception:
            pass
        if icon_widget is None:
            icon_widget = Gtk.Label(label=word.emoji)
            icon_widget.add_css_class("title-1")
            icon_widget.set_markup(f'<span size="72000">{word.emoji}</span>')
        self.append(icon_widget)

        # Swedish word
        sv_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        sv_box.set_halign(Gtk.Align.CENTER)
        sv_label = Gtk.Label(label=word.sv.capitalize())
        sv_label.add_css_class("title-3")
        sv_box.append(sv_label)
        sv_btn = Gtk.Button(icon_name="audio-speakers-symbolic")
        sv_btn.add_css_class("flat")
        sv_btn.add_css_class("circular")
        sv_btn.set_tooltip_text(_("Listen (Swedish)"))
        sv_btn.connect("clicked", lambda _: speak(word.sv, "sv"))
        sv_box.append(sv_btn)
        self.append(sv_box)

        # English word
        en_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        en_box.set_halign(Gtk.Align.CENTER)
        en_label = Gtk.Label(label=word.en.capitalize())
        en_label.add_css_class("body")
        en_label.set_opacity(0.7)
        en_box.append(en_label)
        en_btn = Gtk.Button(icon_name="audio-speakers-symbolic")
        en_btn.add_css_class("flat")
        en_btn.add_css_class("circular")
        en_btn.set_tooltip_text(_("Listen (English)"))
        en_btn.connect("clicked", lambda _: speak(word.en, "en"))
        en_box.append(en_btn)
        self.append(en_box)


class FlashcardView(Gtk.Box):
    """Spaced repetition flashcard view."""

    def __init__(self, db: WordDatabase, go_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.db = db
        self.go_back = go_back
        self.cards: list[WordEntry] = []
        self.current_idx = 0
        self.revealed = False

        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        # Status
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("title-4")
        self.append(self.status_label)

        # Card area
        self.card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.card_box.add_css_class("card")
        self.card_box.set_size_request(320, 300)
        self.card_box.set_halign(Gtk.Align.CENTER)
        self.card_box.set_valign(Gtk.Align.CENTER)

        self.emoji_label = Gtk.Label()
        self.emoji_label.set_markup('<span size="96000">❓</span>')
        self.card_box.append(self.emoji_label)

        self.word_label = Gtk.Label()
        self.word_label.add_css_class("title-1")
        self.card_box.append(self.word_label)

        self.answer_label = Gtk.Label()
        self.answer_label.add_css_class("title-2")
        self.answer_label.set_opacity(0.7)
        self.answer_label.set_visible(False)
        self.card_box.append(self.answer_label)

        # TTS buttons row
        self.tts_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.tts_box.set_halign(Gtk.Align.CENTER)
        self.tts_box.set_visible(False)
        sv_btn = Gtk.Button(label=_("🔊 Swedish"))
        sv_btn.connect("clicked", self._speak_sv)
        self.tts_box.append(sv_btn)
        en_btn = Gtk.Button(label=_("🔊 English"))
        en_btn.connect("clicked", self._speak_en)
        self.tts_box.append(en_btn)
        self.card_box.append(self.tts_box)

        self.append(self.card_box)

        # Reveal button
        self.reveal_btn = Gtk.Button(label=_("Show Answer"))
        self.reveal_btn.add_css_class("suggested-action")
        self.reveal_btn.add_css_class("pill")
        self.reveal_btn.set_halign(Gtk.Align.CENTER)
        self.reveal_btn.connect("clicked", self._on_reveal)
        self.append(self.reveal_btn)

        # Rating buttons (hidden until revealed)
        self.rating_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.rating_box.set_halign(Gtk.Align.CENTER)
        self.rating_box.set_visible(False)

        for quality, label, css in [
            (1, _("Wrong ✗"), "destructive-action"),
            (3, _("Hard"), ""),
            (4, _("Good"), ""),
            (5, _("Easy ✓"), "suggested-action"),
        ]:
            btn = Gtk.Button(label=label)
            if css:
                btn.add_css_class(css)
            btn.add_css_class("pill")
            btn.connect("clicked", self._on_rate, quality)
            self.rating_box.append(btn)
        self.append(self.rating_box)

        # Done label
        self.done_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.done_box.set_halign(Gtk.Align.CENTER)
        self.done_box.set_valign(Gtk.Align.CENTER)
        self.done_box.set_visible(False)
        done_label = Gtk.Label(label=_("🎉 All cards done!"))
        done_label.add_css_class("title-1")
        self.done_box.append(done_label)
        back_btn = Gtk.Button(label=_("Back"))
        back_btn.add_css_class("pill")
        back_btn.connect("clicked", lambda _: self.go_back())
        self.done_box.append(back_btn)
        self.append(self.done_box)

    def start(self):
        due = self.db.due_for_review()
        new = self.db.new_words(max(0, 10 - len(due)))
        self.cards = due + new
        self.current_idx = 0
        self.revealed = False
        if self.cards:
            self._show_card()
        else:
            self.card_box.set_visible(False)
            self.reveal_btn.set_visible(False)
            self.rating_box.set_visible(False)
            self.done_box.set_visible(True)
            self.status_label.set_text(_("No cards to practice!"))

    def _show_card(self):
        if self.current_idx >= len(self.cards):
            self.card_box.set_visible(False)
            self.reveal_btn.set_visible(False)
            self.rating_box.set_visible(False)
            self.done_box.set_visible(True)
            self.status_label.set_text("")
            self.db.save_sr()
            return

        self.done_box.set_visible(False)
        self.card_box.set_visible(True)
        self.revealed = False
        w = self.cards[self.current_idx]
        self.status_label.set_text(_("Card {current} / {total}").format(current=self.current_idx + 1, total=len(self.cards)))
        self.emoji_label.set_markup(f'<span size="96000">{w.emoji}</span>')
        self.word_label.set_text(w.sv.capitalize())
        self.answer_label.set_text(w.en.capitalize())
        self.answer_label.set_visible(False)
        self.tts_box.set_visible(False)
        self.reveal_btn.set_visible(True)
        self.rating_box.set_visible(False)

    def _on_reveal(self, _btn):
        self.revealed = True
        self.answer_label.set_visible(True)
        self.tts_box.set_visible(True)
        self.reveal_btn.set_visible(False)
        self.rating_box.set_visible(True)

    def _on_rate(self, _btn, quality):
        w = self.cards[self.current_idx]
        w.update_sr(quality)
        self.current_idx += 1
        self._show_card()

    def _speak_sv(self, _btn):
        if self.current_idx < len(self.cards):
            speak(self.cards[self.current_idx].sv, "sv")

    def _speak_en(self, _btn):
        if self.current_idx < len(self.cards):
            speak(self.cards[self.current_idx].en, "en")


class BildordbokWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Picture Dictionary"), default_width=900, default_height=700)
        self.db = WordDatabase()
        self._dark = False

        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # Title
        title_widget = Adw.WindowTitle(title=_("Picture Dictionary"), subtitle=_("Bilingual picture dictionary"))
        self.header.set_title_widget(title_widget)
        self.title_widget = title_widget

        # Search button
        search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic")
        search_btn.set_tooltip_text(_("Search (Ctrl+F)"))
        search_btn.connect("toggled", self._on_search_toggled)
        self.header.pack_start(search_btn)
        self.search_btn = search_btn

        # Back button (hidden initially)
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.back_btn.set_tooltip_text(_("Back"))
        self.back_btn.set_visible(False)
        self.back_btn.connect("clicked", self._go_home)
        self.header.pack_start(self.back_btn)

        # Theme toggle
        theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic")
        theme_btn.set_tooltip_text(_("Toggle theme"))
        theme_btn.connect("clicked", self._toggle_theme)
        self.header.pack_end(theme_btn)
        self.theme_btn = theme_btn

        # Menu
        menu = Gio.Menu()
        menu.append(_("Export Word List"), "app.export")
        menu.append(_("Preferences"), "app.preferences")
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append(_("About Picture Dictionary"), "app.about")
        menu.append(_("Quit"), "app.quit")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        self.header.pack_end(menu_btn)

        # Flashcard button
        fc_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        fc_btn.set_tooltip_text(_("Flashcards / Practice"))
        fc_btn.connect("clicked", self._start_flashcards)
        self.header.pack_end(fc_btn)

        # Search bar
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(_("Search words..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.main_box.append(self.search_bar)

        # Stack for views
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_vexpand(True)
        self.main_box.append(self.stack)

        # Category view
        self._build_category_view()

        # Words view (reused for different categories)
        self.words_scroll = Gtk.ScrolledWindow()
        self.words_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.words_flow = Gtk.FlowBox()
        self.words_flow.set_valign(Gtk.Align.START)
        self.words_flow.set_max_children_per_line(5)
        self.words_flow.set_min_children_per_line(2)
        self.words_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.words_flow.set_homogeneous(True)
        self.words_flow.set_row_spacing(8)
        self.words_flow.set_column_spacing(8)
        self.words_flow.set_margin_top(16)
        self.words_flow.set_margin_bottom(16)
        self.words_flow.set_margin_start(16)
        self.words_flow.set_margin_end(16)
        self.words_scroll.set_child(self.words_flow)
        self.stack.add_named(self.words_scroll, "words")

        # Flashcard view
        self.flashcard_view = FlashcardView(self.db, self._go_home)
        self.stack.add_named(self.flashcard_view, "flashcards")

        # Search results view
        self.search_scroll = Gtk.ScrolledWindow()
        self.search_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.search_flow = Gtk.FlowBox()
        self.search_flow.set_valign(Gtk.Align.START)
        self.search_flow.set_max_children_per_line(5)
        self.search_flow.set_min_children_per_line(2)
        self.search_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.search_flow.set_homogeneous(True)
        self.search_flow.set_row_spacing(8)
        self.search_flow.set_column_spacing(8)
        self.search_flow.set_margin_top(16)
        self.search_flow.set_margin_bottom(16)
        self.search_flow.set_margin_start(16)
        self.search_flow.set_margin_end(16)
        self.search_scroll.set_child(self.search_flow)
        self.stack.add_named(self.search_scroll, "search")

        # Status bar
        self.statusbar = Gtk.Label(label=_("{count} words in dictionary").format(count=len(self.db.words)))
        self.statusbar.add_css_class("dim-label")
        self.statusbar.set_margin_top(4)
        self.statusbar.set_margin_bottom(4)
        self.main_box.append(self.statusbar)

        self.stack.set_visible_child_name("categories")

    def _build_category_view(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Welcome
        welcome = Gtk.Label()
        welcome.set_markup('<span size="24000">' + _('📖 Bildordbok') + '</span>')
        welcome.set_margin_bottom(8)
        box.append(welcome)

        sub = Gtk.Label(label=_("Choose a category to start learning words"))
        sub.add_css_class("dim-label")
        sub.set_margin_bottom(24)
        box.append(sub)

        # Category grid
        flow = Gtk.FlowBox()
        flow.set_valign(Gtk.Align.START)
        flow.set_max_children_per_line(3)
        flow.set_min_children_per_line(2)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_row_spacing(12)
        flow.set_column_spacing(12)

        for cat_id, cat_info in CATEGORIES.items():
            btn = Gtk.Button()
            btn.add_css_class("card")
            btn.set_size_request(200, 140)
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            btn_box.set_halign(Gtk.Align.CENTER)
            btn_box.set_valign(Gtk.Align.CENTER)

            icon = Gtk.Label()
            icon.set_markup(f'<span size="48000">{cat_info["icon"]}</span>')
            btn_box.append(icon)

            name = Gtk.Label(label=cat_info["name"])
            name.add_css_class("title-3")
            btn_box.append(name)

            count = len(self.db.by_category(cat_id))
            count_label = Gtk.Label(label=_("{count} words").format(count=count))
            count_label.add_css_class("dim-label")
            btn_box.append(count_label)

            btn.set_child(btn_box)
            btn.connect("clicked", self._on_category_clicked, cat_id)
            flow.append(btn)

        box.append(flow)
        scroll.set_child(box)
        self.stack.add_named(scroll, "categories")

    def _on_category_clicked(self, _btn, cat_id):
        cat_info = CATEGORIES[cat_id]
        self.title_widget.set_subtitle(f"{cat_info['icon']} {cat_info['name']}")
        self.back_btn.set_visible(True)

        # Clear and populate
        while True:
            child = self.words_flow.get_first_child()
            if child is None:
                break
            self.words_flow.remove(child)

        for word in self.db.by_category(cat_id):
            card = WordCard(word)
            self.words_flow.append(card)

        self.stack.set_visible_child_name("words")
        self.statusbar.set_text(_("{count} words in {category}").format(count=len(self.db.by_category(cat_id)), category=cat_info["name"]))

    def _go_home(self, *_args):
        self.stack.set_visible_child_name("categories")
        self.back_btn.set_visible(False)
        self.title_widget.set_subtitle(_("Bilingual picture dictionary"))
        self.statusbar.set_text(_("{count} words in dictionary").format(count=len(self.db.words)))
        self.search_btn.set_active(False)

    def _on_search_toggled(self, btn):
        self.search_bar.set_search_mode(btn.get_active())
        if btn.get_active():
            self.search_entry.grab_focus()
        else:
            if self.stack.get_visible_child_name() == "search":
                self._go_home()

    def _on_search_changed(self, entry):
        query = entry.get_text()
        if not query.strip():
            if self.stack.get_visible_child_name() == "search":
                self._go_home()
            return

        results = self.db.search(query)

        while True:
            child = self.search_flow.get_first_child()
            if child is None:
                break
            self.search_flow.remove(child)

        for word in results:
            card = WordCard(word)
            self.search_flow.append(card)

        self.back_btn.set_visible(True)
        self.stack.set_visible_child_name("search")
        self.title_widget.set_subtitle(_("Search results: \"{query}\"").format(query=query))
        self.statusbar.set_text(_("{count} results").format(count=len(results)))

    def _start_flashcards(self, _btn):
        self.back_btn.set_visible(True)
        self.title_widget.set_subtitle(_("📝 Flashcards"))
        self.stack.set_visible_child_name("flashcards")
        self.flashcard_view.start()
        self.statusbar.set_text(_("Practice mode — Spaced Repetition"))

    def _toggle_theme(self, btn):
        mgr = Adw.StyleManager.get_default()
        self._dark = not self._dark
        if self._dark:
            mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            btn.set_icon_name("weather-clear-symbolic")
        else:
            mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
            btn.set_icon_name("weather-clear-night-symbolic")


CONFIG_DIR = Path(GLib.get_user_config_dir()) / "bildordbok"


def _load_settings():
    path = CONFIG_DIR / "settings.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_settings(settings):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "settings.json").write_text(
        json.dumps(settings, indent=2, ensure_ascii=False))


class BildordbokApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = _load_settings()

    def do_activate(self):
        apply_large_text()
        win = self.props.active_window
        if not win:
            win = BildordbokWindow(self)
        self._apply_theme()
        self._apply_tts_settings()
        win.present()
        if not self.settings.get("welcome_shown"):
            self._show_welcome(win)

    def do_startup(self):
        Adw.Application.do_startup(self)

        for name, cb, accel in [
            ("quit", lambda *_: self.quit(), ["<Control>q"]),
            ("about", self._on_about, ["F1"]),
            ("shortcuts", self._on_shortcuts, ["<Control>slash"]),
            ("preferences", self._on_preferences, ["<Control>comma"]),
            ("export", self._on_export, ["<Control>e"]),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
            if accel:
                self.set_accels_for_action(f"app.{name}", accel)

        self.set_accels_for_action("win.search", ["<Control>f"])

    def _apply_theme(self):
        theme = self.settings.get("theme", "system")
        mgr = Adw.StyleManager.get_default()
        schemes = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
            "system": Adw.ColorScheme.DEFAULT,
        }
        mgr.set_color_scheme(schemes.get(theme, Adw.ColorScheme.DEFAULT))

    def _show_welcome(self, win):
        dialog = Adw.Dialog()
        dialog.set_title(_("Welcome"))
        dialog.set_content_width(420)
        dialog.set_content_height(480)

        page = Adw.StatusPage()
        page.set_icon_name("se.danielnylander.Bildordbok")
        page.set_title(_("Welcome to Picture Dictionary"))
        page.set_description(_(
            "Learn words with pictures and speech.\n\n"
            "✓ Browse words by category\n"
            "✓ Listen to pronunciation in Swedish and English\n"
            "✓ Practice with flashcards\n"
            "✓ ARASAAC pictograms included"
        ))

        btn = Gtk.Button(label=_("Get Started"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.set_margin_top(12)
        btn.connect("clicked", self._on_welcome_close, dialog)
        page.set_child(btn)

        box = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        hb.set_show_title(False)
        box.add_top_bar(hb)
        box.set_content(page)
        dialog.set_child(box)
        dialog.present(win)

    def _on_welcome_close(self, btn, dialog):
        self.settings["welcome_shown"] = True
        _save_settings(self.settings)
        dialog.close()

    def _on_preferences(self, *_args):
        prefs = Adw.PreferencesDialog()
        prefs.set_title(_("Preferences"))

        basic = Adw.PreferencesPage()
        basic.set_title(_("General"))
        basic.set_icon_name("preferences-system-symbolic")

        appearance = Adw.PreferencesGroup()
        appearance.set_title(_("Appearance"))

        theme_row = Adw.ComboRow()
        theme_row.set_title(_("Theme"))
        theme_row.set_subtitle(_("Choose light, dark, or follow system"))
        theme_row.set_model(Gtk.StringList.new(
            [_("System"), _("Light"), _("Dark")]))
        cur = {"system": 0, "light": 1, "dark": 2}.get(
            self.settings.get("theme", "system"), 0)
        theme_row.set_selected(cur)
        theme_row.connect("notify::selected", self._on_theme_changed)
        appearance.add(theme_row)

        size_row = Adw.ComboRow()
        size_row.set_title(_("Icon Size"))
        size_row.set_subtitle(_("Size of pictogram icons"))
        size_row.set_model(Gtk.StringList.new(
            [_("Small"), _("Medium"), _("Large")]))
        cur_size = {"small": 0, "medium": 1, "large": 2}.get(
            self.settings.get("icon_size", "medium"), 1)
        size_row.set_selected(cur_size)
        size_row.connect("notify::selected", self._on_icon_size_changed)
        appearance.add(size_row)

        speech = Adw.PreferencesGroup()
        speech.set_title(_("Speech"))

        tts_row = Adw.SwitchRow()
        tts_row.set_title(_("Text-to-speech"))
        tts_row.set_subtitle(_("Read words aloud when tapped"))
        tts_row.set_active(self.settings.get("tts_enabled", True))
        tts_row.connect("notify::active", self._on_tts_changed)
        speech.add(tts_row)

        basic.add(appearance)
        basic.add(speech)

        # ── Speech ──
        speech_group = Adw.PreferencesGroup()
        speech_group.set_title(_("Speech"))

        engine_row = Adw.ComboRow()
        engine_row.set_title(_("Speech Engine"))
        engine_row.set_subtitle(_("Piper gives natural voices, espeak is robotic but lightweight"))
        engine_row.set_model(Gtk.StringList.new(
            [_("Automatic"), _("Piper (natural)"), _("espeak-ng (robotic)")]))
        cur_engine = {"auto": 0, "piper": 1, "espeak": 2}.get(
            self.settings.get("tts_engine", "auto"), 0)
        engine_row.set_selected(cur_engine)
        engine_row.connect("notify::selected", self._on_tts_engine_changed)
        speech_group.add(engine_row)

        speed_row = Adw.ActionRow()
        speed_row.set_title(_("Speech Speed"))
        speed_row.set_subtitle(_("Slower speech can be easier to understand"))
        speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.0, 0.1)
        speed_scale.set_value(self.settings.get("tts_speed", 1.0))
        speed_scale.set_size_request(200, -1)
        speed_scale.set_valign(Gtk.Align.CENTER)
        speed_scale.set_draw_value(True)
        speed_scale.connect("value-changed", self._on_tts_speed_changed)
        speed_row.add_suffix(speed_scale)
        speech_group.add(speed_row)

        basic.add(speech_group)

        prefs.add(basic)

        advanced = Adw.PreferencesPage()
        advanced.set_title(_("Advanced"))
        advanced.set_icon_name("applications-engineering-symbolic")

        cache_group = Adw.PreferencesGroup()
        cache_group.set_title(_("ARASAAC Cache"))
        cache_dir = Path(GLib.get_user_cache_dir()) / "arasaac"
        cache_size = sum(f.stat().st_size for f in cache_dir.glob("*")
                         if f.is_file()) if cache_dir.exists() else 0
        cache_row = Adw.ActionRow()
        cache_row.set_title(_("Cached pictograms"))
        cache_row.set_subtitle(f"{cache_size / (1024*1024):.1f} MB")
        clear_btn = Gtk.Button(label=_("Clear"))
        clear_btn.add_css_class("destructive-action")
        clear_btn.set_valign(Gtk.Align.CENTER)
        clear_btn.connect("clicked", self._on_clear_cache, cache_row)
        cache_row.add_suffix(clear_btn)
        cache_group.add(cache_row)
        advanced.add(cache_group)

        debug_group = Adw.PreferencesGroup()
        debug_group.set_title(_("Developer"))
        debug_row = Adw.SwitchRow()
        debug_row.set_title(_("Debug mode"))
        debug_row.set_subtitle(_("Show extra logging in terminal"))
        debug_row.set_active(self.settings.get("debug", False))
        debug_row.connect("notify::active", self._on_debug_changed)
        debug_group.add(debug_row)
        advanced.add(debug_group)

        prefs.add(advanced)
        prefs.present(self.props.active_window)

    def _on_theme_changed(self, row, *_):
        themes = {0: "system", 1: "light", 2: "dark"}
        self.settings["theme"] = themes.get(row.get_selected(), "system")
        _save_settings(self.settings)
        self._apply_theme()

    def _on_icon_size_changed(self, row, *_):
        sizes = {0: "small", 1: "medium", 2: "large"}
        self.settings["icon_size"] = sizes.get(row.get_selected(), "medium")
        _save_settings(self.settings)

    def _on_tts_changed(self, row, *_):
        self.settings["tts_enabled"] = row.get_active()
        _save_settings(self.settings)

    def _on_clear_cache(self, btn, row):
        cache_dir = Path(GLib.get_user_cache_dir()) / "arasaac"
        if cache_dir.exists():
            for f in cache_dir.glob("*"):
                if f.is_file():
                    f.unlink()
        row.set_subtitle("0.0 MB")
        btn.set_sensitive(False)
        btn.set_label(_("Cleared"))

    def _on_debug_changed(self, row, *_):
        self.settings["debug"] = row.get_active()
        _save_settings(self.settings)

    def _on_export(self, *_args):
        win = self.props.active_window
        if win and hasattr(win, 'db'):
            from bildordbok.export import show_export_dialog
            show_export_dialog(win, win.db.words,
                               status_callback=getattr(win, 'statusbar', None) and
                               (lambda t: win.statusbar.set_text(t)))

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name=_("Picture Dictionary"),
            application_icon="se.danielnylander.Bildordbok",
            developer_name="Daniel Nylander",
            version=__version__,
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            documenters=["Daniel Nylander"],
            artists=[_("ARASAAC pictograms (https://arasaac.org)")],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/bildordbok",
            issue_url="https://github.com/yeager/bildordbok/issues",
            support_url="https://www.autismappar.se",
            translate_url="https://app.transifex.com/danielnylander/bildordbok",
            comments=_(
                "Bilingual picture dictionary with text-to-speech "
                "for children with language disorders.\n\n"
                "Part of the Autismappar suite — free tools for "
                "communication and daily structure."
            ),
            debug_info=f"TTS: {__import__('bildordbok.tts', fromlist=['get_tts_info']).get_tts_info()}\nVersion: {__version__}\n"
                       f"GTK: {Gtk.get_major_version()}.{Gtk.get_minor_version()}\n"
                       f"Adwaita: {Adw.get_major_version()}.{Adw.get_minor_version()}\n"
                       f"Python: {sys.version}",
            debug_info_filename="bildordbok-debug-info.txt",
        )
        about.add_link(_("Autismappar"), "https://www.autismappar.se")
        about.add_link("GTK 4", "https://gtk.org")
        about.add_link("libadwaita", "https://gnome.pages.gitlab.gnome.org/libadwaita/")
        about.add_link("ARASAAC", "https://arasaac.org")
        about.add_link("Piper TTS", "https://github.com/rhasspy/piper")
        about.add_link("espeak-ng", "https://github.com/espeak-ng/espeak-ng")
        about.present(self.props.active_window)

    def _on_shortcuts(self, *_args):
        builder = Gtk.Builder()
        builder.add_from_string('''
        <interface>
          <object class="GtkShortcutsWindow" id="shortcuts">
            <property name="modal">true</property>
            <child>
              <object class="GtkShortcutsSection">
                <child>
                  <object class="GtkShortcutsGroup">
                    <property name="title" translatable="yes">General</property>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Search</property>
                        <property name="accelerator">&lt;Control&gt;f</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Export</property>
                        <property name="accelerator">&lt;Control&gt;e</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Preferences</property>
                        <property name="accelerator">&lt;Control&gt;comma</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Keyboard Shortcuts</property>
                        <property name="accelerator">&lt;Control&gt;slash</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">About</property>
                        <property name="accelerator">F1</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="title" translatable="yes">Quit</property>
                        <property name="accelerator">&lt;Control&gt;q</property>
                      </object>
                    </child>
                  </object>
                </child>
              </object>
            </child>
          </object>
        </interface>''')
        win = builder.get_object("shortcuts")
        win.set_transient_for(self.props.active_window)
        win.present()


def main():
    app = BildordbokApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()


# --- Session restore ---
import json as _json
import os as _os

def _save_session(window, app_name):
    config_dir = _os.path.join(_os.path.expanduser('~'), '.config', app_name)
    _os.makedirs(config_dir, exist_ok=True)
    state = {'width': window.get_width(), 'height': window.get_height(),
             'maximized': window.is_maximized()}
    try:
        with open(_os.path.join(config_dir, 'session.json'), 'w') as f:
            _json.dump(state, f)
    except OSError:
        pass

def _restore_session(window, app_name):
    path = _os.path.join(_os.path.expanduser('~'), '.config', app_name, 'session.json')
    try:
        with open(path) as f:
            state = _json.load(f)
        window.set_default_size(state.get('width', 800), state.get('height', 600))
        if state.get('maximized'):
            window.maximize()
    except (FileNotFoundError, _json.JSONDecodeError, OSError):
        pass


# --- Fullscreen toggle (F11) ---
def _setup_fullscreen(window, app):
    """Add F11 fullscreen toggle."""
    from gi.repository import Gio
    if not app.lookup_action('toggle-fullscreen'):
        action = Gio.SimpleAction.new('toggle-fullscreen', None)
        action.connect('activate', lambda a, p: (
            window.unfullscreen() if window.is_fullscreen() else window.fullscreen()
        ))
        app.add_action(action)
        app.set_accels_for_action('app.toggle-fullscreen', ['F11'])


# --- Plugin system ---
import importlib.util
import os as _pos

def _load_plugins(app_name):
    """Load plugins from ~/.config/<app>/plugins/."""
    plugin_dir = _pos.path.join(_pos.path.expanduser('~'), '.config', app_name, 'plugins')
    plugins = []
    if not _pos.path.isdir(plugin_dir):
        return plugins
    for fname in sorted(_pos.listdir(plugin_dir)):
        if fname.endswith('.py') and not fname.startswith('_'):
            path = _pos.path.join(plugin_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(fname[:-3], path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                plugins.append(mod)
            except Exception as e:
                print(f"Plugin {fname}: {e}")
    return plugins


# --- Sound notifications ---
def _play_sound(sound_name='complete'):
    """Play a system notification sound."""
    try:
        import subprocess
        # Try canberra-gtk-play first, then paplay
        for cmd in [
            ['canberra-gtk-play', '-i', sound_name],
            ['paplay', f'/usr/share/sounds/freedesktop/stereo/{sound_name}.oga'],
        ]:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
    except Exception:
        pass
