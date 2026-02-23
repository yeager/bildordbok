"""Bildordbok – main application."""

from __future__ import annotations

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, Pango, GdkPixbuf  # noqa: E402

from bildordbok.words import WordDatabase, WordEntry, CATEGORIES  # noqa: E402
from bildordbok.tts import speak  # noqa: E402
from bildordbok import __version__, _  # noqa: E402
from bildordbok import arasaac  # noqa: E402

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
        sv_btn.set_tooltip_text(_("Lyssna (svenska)"))
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
        sv_btn = Gtk.Button(label=_("🔊 Svenska"))
        sv_btn.connect("clicked", self._speak_sv)
        self.tts_box.append(sv_btn)
        en_btn = Gtk.Button(label=_("🔊 English"))
        en_btn.connect("clicked", self._speak_en)
        self.tts_box.append(en_btn)
        self.card_box.append(self.tts_box)

        self.append(self.card_box)

        # Reveal button
        self.reveal_btn = Gtk.Button(label=_("Visa svar"))
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
            (1, _("Fel ✗"), "destructive-action"),
            (3, _("Svårt"), ""),
            (4, _("Bra"), ""),
            (5, _("Lätt ✓"), "suggested-action"),
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
        done_label = Gtk.Label(label=_("🎉 Alla kort klara!"))
        done_label.add_css_class("title-1")
        self.done_box.append(done_label)
        back_btn = Gtk.Button(label=_("Tillbaka"))
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
            self.status_label.set_text(_("Inga kort att öva!"))

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
        self.status_label.set_text(_("Kort {current} / {total}").format(current=self.current_idx + 1, total=len(self.cards)))
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
        super().__init__(application=app, title=_("Bildordbok"), default_width=900, default_height=700)
        self.db = WordDatabase()
        self._dark = False

        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar
        self.header = Adw.HeaderBar()
        self.main_box.append(self.header)

        # Title
        title_widget = Adw.WindowTitle(title=_("Picture Dictionary"), subtitle=_("Tvåspråkig bildordbok"))
        self.header.set_title_widget(title_widget)
        self.title_widget = title_widget

        # Search button
        search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic")
        search_btn.set_tooltip_text(_("Sök (Ctrl+F)"))
        search_btn.connect("toggled", self._on_search_toggled)
        self.header.pack_start(search_btn)
        self.search_btn = search_btn

        # Back button (hidden initially)
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.back_btn.set_tooltip_text(_("Tillbaka"))
        self.back_btn.set_visible(False)
        self.back_btn.connect("clicked", self._go_home)
        self.header.pack_start(self.back_btn)

        # Theme toggle
        theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic")
        theme_btn.set_tooltip_text(_("Växla tema"))
        theme_btn.connect("clicked", self._toggle_theme)
        self.header.pack_end(theme_btn)
        self.theme_btn = theme_btn

        # Menu
        menu = Gio.Menu()
        menu.append(_("Om Bildordbok"), "app.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        self.header.pack_end(menu_btn)

        # Flashcard button
        fc_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        fc_btn.set_tooltip_text(_("Flashcards / Övning"))
        fc_btn.connect("clicked", self._start_flashcards)
        self.header.pack_end(fc_btn)

        # Search bar
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(_("Sök ord..."))
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
        self.statusbar = Gtk.Label(label=_("{count} ord i ordboken").format(count=len(self.db.words)))
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

        sub = Gtk.Label(label=_("Välj en kategori för att börja lära dig ord"))
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

            name = Gtk.Label(label=cat_info["sv"])
            name.add_css_class("title-3")
            btn_box.append(name)

            count = len(self.db.by_category(cat_id))
            count_label = Gtk.Label(label=_("{count} ord").format(count=count))
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
        self.title_widget.set_subtitle(f"{cat_info['icon']} {cat_info['sv']}")
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
        self.statusbar.set_text(_("{count} ord i {category}").format(count=len(self.db.by_category(cat_id)), category=cat_info["sv"]))

    def _go_home(self, *_args):
        self.stack.set_visible_child_name("categories")
        self.back_btn.set_visible(False)
        self.title_widget.set_subtitle(_("Tvåspråkig bildordbok"))
        self.statusbar.set_text(_("{count} ord i ordboken").format(count=len(self.db.words)))
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
        self.title_widget.set_subtitle(_("Sökresultat: \"{query}\"").format(query=query))
        self.statusbar.set_text(_("{count} träffar").format(count=len(results)))

    def _start_flashcards(self, _btn):
        self.back_btn.set_visible(True)
        self.title_widget.set_subtitle(_("📝 Flashcards"))
        self.stack.set_visible_child_name("flashcards")
        self.flashcard_view.start()
        self.statusbar.set_text(_("Övningsläge – Spaced Repetition"))

    def _toggle_theme(self, btn):
        mgr = Adw.StyleManager.get_default()
        self._dark = not self._dark
        if self._dark:
            mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            btn.set_icon_name("weather-clear-symbolic")
        else:
            mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)
            btn.set_icon_name("weather-clear-night-symbolic")


class BildordbokApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = BildordbokWindow(self)
        win.present()

    def do_startup(self):
        Adw.Application.do_startup(self)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Quit action with Ctrl+Q
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        # Search with Ctrl+F
        self.set_accels_for_action("win.search", ["<Control>f"])

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name=_("Picture Dictionary"),
            application_icon="se.danielnylander.Bildordbok",
            developer_name="Daniel Nylander",
            version=__version__,
            developers=["Daniel Nylander"],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/bildordbok",
            issue_url="https://github.com/yeager/bildordbok/issues",
            comments=_("Tvåspråkig bildordbok med TTS.\nFör barn med språkstörning och nyanlända."),
            translator_credits="Daniel Nylander\nhttps://www.transifex.com/danielnylander/bildordbok",
        )
        about.present(self.props.active_window)


def main():
    app = BildordbokApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
