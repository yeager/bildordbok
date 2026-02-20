"""Export/print functionality for Bildordbok."""

import csv
import io
import json
from datetime import datetime

import gettext
_ = gettext.gettext

from bildordbok import __version__

APP_LABEL = "Bildordbok"
AUTHOR = "Daniel Nylander"

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib


def words_to_csv(words):
    """Export word list as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([_("Swedish"), _("English"), _("Category"), _("Emoji")])
    for w in words:
        writer.writerow([w.sv, w.en, w.category, w.emoji])
    writer.writerow([])
    writer.writerow([f"{APP_LABEL} v{__version__} — {AUTHOR}"])
    return output.getvalue()


def words_to_json(words):
    """Export word list as JSON."""
    data = {
        "app": APP_LABEL,
        "version": __version__,
        "author": AUTHOR,
        "exported": datetime.now().isoformat(),
        "words": [
            {"sv": w.sv, "en": w.en, "category": w.category, "emoji": w.emoji}
            for w in words
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def words_to_pdf(words, output_path):
    """Export word list as A4 PDF."""
    try:
        import cairo
    except ImportError:
        try:
            import cairocffi as cairo
        except ImportError:
            return False

    width, height = 595, 842
    surface = cairo.PDFSurface(output_path, width, height)
    ctx = cairo.Context(surface)

    ctx.set_font_size(24)
    ctx.move_to(40, 50)
    ctx.show_text(_("Picture Dictionary"))

    ctx.set_font_size(12)
    ctx.set_source_rgb(0.5, 0.5, 0.5)
    ctx.move_to(40, 70)
    ctx.show_text(f"{len(words)} " + _("words") + f" — {datetime.now().strftime('%Y-%m-%d')}")
    ctx.set_source_rgb(0, 0, 0)

    # Table header
    y = 100
    ctx.set_font_size(12)
    ctx.set_source_rgb(0.3, 0.3, 0.3)
    ctx.move_to(40, y)
    ctx.show_text("")
    ctx.move_to(70, y)
    ctx.show_text(_("Swedish"))
    ctx.move_to(250, y)
    ctx.show_text(_("English"))
    ctx.move_to(430, y)
    ctx.show_text(_("Category"))
    ctx.set_source_rgb(0, 0, 0)
    y += 20

    row_h = 28
    ctx.set_font_size(14)
    for w in words:
        if y + row_h > height - 40:
            surface.show_page()
            y = 40

        ctx.move_to(40, y + 18)
        ctx.show_text(w.emoji)
        ctx.move_to(70, y + 18)
        ctx.show_text(w.sv.capitalize())
        ctx.set_source_rgb(0.4, 0.4, 0.4)
        ctx.move_to(250, y + 18)
        ctx.show_text(w.en.capitalize())
        ctx.set_font_size(11)
        ctx.move_to(430, y + 18)
        ctx.show_text(w.category)
        ctx.set_font_size(14)
        ctx.set_source_rgb(0, 0, 0)

        # Line
        ctx.set_source_rgb(0.9, 0.9, 0.9)
        ctx.set_line_width(0.3)
        ctx.move_to(40, y + row_h - 2)
        ctx.line_to(width - 40, y + row_h - 2)
        ctx.stroke()
        ctx.set_source_rgb(0, 0, 0)

        y += row_h

    # Footer
    ctx.set_font_size(9)
    ctx.set_source_rgb(0.5, 0.5, 0.5)
    ctx.move_to(40, height - 20)
    ctx.show_text(f"{APP_LABEL} v{__version__} — {AUTHOR} — {datetime.now().strftime('%Y-%m-%d')}")

    surface.finish()
    return True


def show_export_dialog(window, words, status_callback=None):
    """Show export dialog."""
    dialog = Adw.AlertDialog.new(
        _("Export Word List"),
        _("Choose export format:")
    )
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("csv", _("CSV"))
    dialog.add_response("json", _("JSON"))
    dialog.add_response("pdf", _("PDF"))
    dialog.set_default_response("pdf")
    dialog.set_close_response("cancel")
    dialog.connect("response", _on_export_response, window, words, status_callback)
    dialog.present(window)


def _on_export_response(dialog, response, window, words, status_callback):
    if response == "cancel":
        return
    converters = {"csv": words_to_csv, "json": words_to_json}
    if response in converters:
        content = converters[response](words)
        _save_text(window, content, response, status_callback)
    elif response == "pdf":
        _save_pdf(window, words, status_callback)


def _save_text(window, content, ext, status_callback):
    fd = Gtk.FileDialog.new()
    fd.set_title(_("Save Export"))
    fd.set_initial_name(f"bildordbok_{datetime.now().strftime('%Y%m%d')}.{ext}")
    fd.save(window, None, _on_text_done, content, ext, status_callback)


def _on_text_done(fd, result, content, ext, status_callback):
    try:
        gfile = fd.save_finish(result)
    except GLib.Error:
        return
    try:
        with open(gfile.get_path(), "w") as f:
            f.write(content)
        if status_callback:
            status_callback(_("Exported %s") % ext.upper())
    except Exception as e:
        if status_callback:
            status_callback(_("Export error: %s") % str(e))


def _save_pdf(window, words, status_callback):
    fd = Gtk.FileDialog.new()
    fd.set_title(_("Save PDF"))
    fd.set_initial_name(f"bildordbok_{datetime.now().strftime('%Y%m%d')}.pdf")
    fd.save(window, None, _on_pdf_done, words, status_callback)


def _on_pdf_done(fd, result, words, status_callback):
    try:
        gfile = fd.save_finish(result)
    except GLib.Error:
        return
    try:
        ok = words_to_pdf(words, gfile.get_path())
        if ok and status_callback:
            status_callback(_("PDF exported"))
        elif not ok and status_callback:
            status_callback(_("PDF export requires pycairo"))
    except Exception as e:
        if status_callback:
            status_callback(_("Export error: %s") % str(e))
