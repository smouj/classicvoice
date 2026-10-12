from pathlib import Path
import tkinter as tk
import wave

import pytest

import classicvoice.app as ui


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "_load_config", lambda: {})
    monkeypatch.setattr(ui, "CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(ui, "DATA_DIR", tmp_path)
    try:
        window = ui.ClassicVoiceApp()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    yield window
    window._close()


def assert_contained(parent):
    children = [child for child in parent.winfo_children() if child.winfo_manager()]
    for child in children:
        assert child.winfo_x() >= 0, str(child)
        assert child.winfo_y() >= 0, str(child)
        assert child.winfo_x() + child.winfo_width() <= parent.winfo_width() + 2, str(child)
        assert child.winfo_y() + child.winfo_height() <= parent.winfo_height() + 2, str(child)
        assert_contained(child)
    for index, first in enumerate(children):
        for second in children[index + 1:]:
            overlap_x = min(first.winfo_x() + first.winfo_width(), second.winfo_x() + second.winfo_width()) - max(first.winfo_x(), second.winfo_x())
            overlap_y = min(first.winfo_y() + first.winfo_height(), second.winfo_y() + second.winfo_height()) - max(first.winfo_y(), second.winfo_y())
            assert overlap_x <= 0 or overlap_y <= 0, f"Overlapping controls: {first}, {second}"


@pytest.mark.parametrize("size", ["780x650", "900x820", "1200x900"])
def test_controls_fit_and_short_windows_scroll(app, size):
    app.status.set("WAV guardado correctamente · " + "Nombre largo del archivo " * 6)
    app.geometry(size)
    app.update()
    assert_contained(app._page)
    assert bool(app._page_scrollbar.winfo_manager()) == (app._page.winfo_reqheight() > app._viewport.winfo_height())
    app._viewport.yview_moveto(1)
    app.update()
    assert app.stop_button.winfo_rooty() + app.stop_button.winfo_height() <= app._viewport.winfo_rooty() + app._viewport.winfo_height()


def test_save_shortcut_while_busy_does_not_open_dialog(app, monkeypatch):
    def unexpected_dialog(**kwargs):
        pytest.fail("Save dialog opened during synthesis")
    monkeypatch.setattr(ui.messagebox, "showinfo", unexpected_dialog)
    monkeypatch.setattr(ui.filedialog, "asksaveasfilename", unexpected_dialog)
    app._busy = True
    app._hotkey_save()
    app._busy = False


def test_preview_survives_worker_until_playback_cleanup(app, monkeypatch, tmp_path):
    monkeypatch.setattr(ui.tempfile, "gettempdir", lambda: str(tmp_path))

    class FakeProcess:
        returncode = 0

        def __init__(self, command, **kwargs):
            output = Path(command[command.index("-w") + 1])
            with wave.open(str(output), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22050)
                audio.writeframes(b"\x00\x01" * 2205)

        def communicate(self, timeout):
            return b"", b""

    monkeypatch.setattr(ui.subprocess, "Popen", FakeProcess)
    app.engine = "espeak-ng.exe"
    app._run_generation("preview", None, "Hola", app._preset(), {"speed": 145, "pitch": 45, "volume": 100, "normalize": False}, app._cancel_event)
    event = app._events.get_nowait()
    assert event[0] == "done" and event[3] is None
    preview = Path(event[2])
    assert preview.is_file(), "The preview must exist when the UI receives the completed job"
    app._preview_path = preview
    app._remove_preview()
    assert not preview.exists()


def test_pronunciation_dialog_fits_minimum_size(app):
    errors = []

    def inspect_and_close():
        dialog = app._pronunciation_dialog
        try:
            dialog.geometry("540x430")
            dialog.update()
            assert_contained(dialog)
        except AssertionError as exc:
            errors.append(exc)
        finally:
            dialog.destroy()

    app.after(30, inspect_and_close)
    app._open_pronunciation()
    assert not errors, errors
