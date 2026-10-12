from pathlib import Path
import tkinter as tk
from tkinter import ttk
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
    children = [child for child in parent.winfo_children() if child.winfo_ismapped()]
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


@pytest.mark.parametrize("size", ["860x620", "1100x720", "1400x900"])
def test_controls_fit_without_global_scrolling(app, size):
    app.geometry(size)
    app.update()
    editor_width = app.text.winfo_width()
    for tab in app.settings_tabs.tabs():
        app.settings_tabs.select(tab)
        app.update()
        assert_contained(app._page)
        assert app.text.winfo_width() == editor_width
    assert not hasattr(app, "_viewport")
    assert app.stop_button.winfo_rooty() + app.stop_button.winfo_height() <= app.winfo_rooty() + app.winfo_height()


def test_save_shortcut_while_busy_does_not_open_dialog(app, monkeypatch):
    def unexpected_dialog(**kwargs):
        pytest.fail("Save dialog opened during synthesis")
    monkeypatch.setattr(ui.messagebox, "showinfo", unexpected_dialog)
    monkeypatch.setattr(ui.filedialog, "asksaveasfilename", unexpected_dialog)
    app._busy = True
    app._hotkey_save()
    app._busy = False


def test_voice_slider_rounds_to_integer(app):
    def sliders(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Scale):
                yield child
            yield from sliders(child)

    speed_slider = next(sliders(app))
    speed_slider.set(128.8)
    assert app.speed.get() == 129
    speed_slider.set(449.8)
    assert app.speed.get() == 450


def test_numeric_input_recovers_empty_invalid_and_out_of_range_values(app):
    value, variable, low, high = app._numeric_inputs[0]
    original = variable.get()
    for invalid in ("", "abc"):
        value.set(invalid)
        app._commit_number(value, variable, low, high)
        assert variable.get() == original
    value.set("9999")
    app._commit_number(value, variable, low, high)
    assert variable.get() == 450
    assert value.get() == "450"


def test_pronunciation_and_language_are_saved_independently(app):
    if not any(language.code == "en-us" for language in app.languages):
        pytest.skip("English engine voice not installed")
    app.pronunciation_rules["WAV"] = "uve doble a uve"
    english = next(language for language in app.languages if language.code == "en-us")
    app.language_label.set(english.label)
    app._apply_language()
    assert app.pronunciation_rules == {}
    app.pronunciation_rules["WAV"] = "wave"
    config = app._config_values()
    assert config["language_code"] == "en-us"
    assert config["pronunciation_by_language"]["es"]["WAV"] == "uve doble a uve"
    assert config["pronunciation_by_language"]["en-us"]["WAV"] == "wave"


def test_legacy_spanish_rules_survive_config_migration(app, monkeypatch):
    monkeypatch.setattr(ui, "_load_config", lambda: {"preset_key": "classic", "pronunciation_rules": {"WAV": "uve doble a uve"}})
    migrated = ui.ClassicVoiceApp()
    try:
        assert migrated.pronunciation_rules == {"WAV": "uve doble a uve"}
        config = migrated._config_values()
        assert config["version"] == 5
        assert config["pronunciation_by_language"]["es"]["WAV"] == "uve doble a uve"
    finally:
        migrated._close()


def test_utf16_text_import_can_be_undone(app, monkeypatch, tmp_path):
    document = tmp_path / "document.txt"
    document.write_text("Texto nuevo: áéíóú", encoding="utf-16")
    monkeypatch.setattr(ui.filedialog, "askopenfilename", lambda **kwargs: str(document))
    app._clear_placeholder()
    app.text.insert("1.0", "Texto anterior")
    app.text.edit_reset()
    app._import_text()
    assert app._text_value() == "Texto nuevo: áéíóú"
    app.text.edit_undo()
    assert app._text_value() == "Texto anterior"
    assert document.read_text(encoding="utf-16") == "Texto nuevo: áéíóú"


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


def test_workflow_dialogs_fit_compact_sizes(app):
    errors = []

    app._open_batch_dialog()
    batch = app._batch_dialog
    batch.geometry("600x430")
    batch.update()
    try:
        assert_contained(batch)
    except AssertionError as exc:
        errors.append(exc)
    batch.destroy()

    app._open_voice_profiles()
    profiles = app._voice_profile_dialog
    profiles.geometry("480x360")
    profiles.update()
    try:
        assert_contained(profiles)
    except AssertionError as exc:
        errors.append(exc)
    profiles.destroy()
    assert not errors, errors


def test_natural_engine_switch_preserves_classic_preset_and_disables_unsupported_controls(app, monkeypatch):
    monkeypatch.setattr(ui, "kokoro_runtime_available", lambda: True)
    app._apply_preset()
    original_preset = app._classic_preset_key
    app._set_tts_engine("kokoro")

    assert app.tts_engine == "kokoro"
    assert app._language_code == "es"
    assert app.natural_voice == "ef_dora"
    assert app.preset_combo.cget("values") == ("Dora · femenina", "Alex · masculina", "Santa · masculina")
    assert all(control.instate(["disabled"]) for control in app._pitch_controls + app._volume_controls)
    assert app._config_values()["tts_engine"] == "kokoro"

    app._set_tts_engine("espeak")
    assert app._classic_preset_key == original_preset
    assert all(control.instate(["!disabled"]) for control in app._pitch_controls + app._volume_controls)


def test_natural_voice_reset_returns_to_the_default_voice_and_normal_speed(app, monkeypatch):
    monkeypatch.setattr(ui, "kokoro_runtime_available", lambda: True)
    app._set_tts_engine("kokoro")
    app.preset_label.set("Alex · masculina")
    app._apply_preset()
    app.speed.set(210)

    app._reset_voice()

    assert app.natural_voice == "ef_dora"
    assert app.speed.get() == 145
    assert app.preset_label.get() == "Dora · femenina"


def test_natural_engine_dialog_fits_compact_size(app, monkeypatch):
    monkeypatch.setattr(ui, "kokoro_runtime_available", lambda: True)
    errors = []
    app._open_tts_settings()
    dialog = app._natural_settings_dialog
    dialog.geometry("500x365")
    dialog.update()
    try:
        assert_contained(dialog)
    except AssertionError as exc:
        errors.append(exc)
    dialog.destroy()
    assert not errors, errors


def test_batch_render_is_atomic_and_combines_book_chapters(app, monkeypatch, tmp_path):
    source = tmp_path / "Libro.txt"
    source.write_text("Capítulo 1\nHola mundo\n\nCapítulo 2\nOtro capítulo", encoding="utf-8")
    output_dir = tmp_path / "Audio"
    existing = output_dir / "Libro - Capítulo 1.wav"
    output_dir.mkdir()
    existing.write_bytes(b"contenido original")

    def fake_synthesis(_engine, _app_dir, _text, output, _preset, _settings, _cancel, _on_process):
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8_000)
            audio.writeframes(b"\x01\x00" * 8)
        return 0.001

    monkeypatch.setattr(ui, "synthesize_text_to_wav", fake_synthesis)
    monkeypatch.setattr(ui, "APP_DIR", tmp_path)
    app.engine = "unused-by-fake"
    settings = {"speed": 145, "pitch": 45, "volume": 100, "normalize": False, "language": None}
    app._run_batch_generation((source,), output_dir, True, app._preset(), settings, {}, app._cancel_event)
    events = []
    while not app._events.empty():
        events.append(app._events.get_nowait())

    result = next(event for event in events if event[0] == "batch_done")
    paths = [Path(value) for value in result[1]]
    assert len(paths) == 3, events
    assert result[2] and Path(result[2]).is_file()
    assert existing.read_bytes() == b"contenido original"
    assert all(path.is_file() for path in paths)
    assert not list(output_dir.glob(".classicvoice-batch-*"))


def test_cancelled_batch_removes_staged_outputs(app, monkeypatch, tmp_path):
    source = tmp_path / "Libro.txt"
    source.write_text("Capítulo 1\nTexto", encoding="utf-8")
    output_dir = tmp_path / "Audio"

    def cancel_synthesis(_engine, _app_dir, _text, _output, _preset, _settings, cancel, _on_process):
        cancel.set()
        raise ui.SynthesisCancelled("cancelled")

    monkeypatch.setattr(ui, "synthesize_text_to_wav", cancel_synthesis)
    monkeypatch.setattr(ui, "APP_DIR", tmp_path)
    app.engine = "unused-by-fake"
    settings = {"speed": 145, "pitch": 45, "volume": 100, "normalize": False, "language": None}
    app._run_batch_generation((source,), output_dir, True, app._preset(), settings, {}, app._cancel_event)

    assert app._events.get_nowait() == ("batch_total", 1)
    assert app._events.get_nowait() == ("batch_cancelled",)
    assert list(output_dir.iterdir()) == []
