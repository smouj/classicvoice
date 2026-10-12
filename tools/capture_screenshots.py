"""Render real documentation screenshots without modifying user preferences.

Run on Windows from the repository virtual environment. The source application
runs its normal Tk event loop while Windows renders each selected client area.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classicvoice.app import ClassicVoiceApp  # noqa: E402


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Screenshots require Windows.")
    failures = []
    with patch("classicvoice.app._load_config", return_value={"tts_engine": "espeak"}), patch("classicvoice.app._save_config"):
        app = ClassicVoiceApp()
        app.geometry("1100x720")
        app.report_callback_exception = lambda exc_type, exc, tb: print(
            "Tk callback failed:\n" + "".join(traceback.format_exception(exc_type, exc, tb)),
            file=sys.stderr,
            flush=True,
        )

        def capture(title, filename, continuation):
            print(f"Capturing {filename}…", flush=True)
            command = [
                "powershell.exe", "-NoProfile", "-File", str(ROOT / "tools" / "capture_window.ps1"),
                "-TargetProcessId", str(os.getpid()), "-WindowTitle", title,
                "-OutputPath", str(ROOT / "assets" / "screenshots" / filename),
            ]
            job = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)

            def finish():
                if job.poll() is None:
                    app.after(100, finish)
                    return
                output, error = job.communicate()
                if job.returncode:
                    failures.append(error.decode(errors="replace"))
                    print(f"Capture failed for {filename}: {failures[-1]}", file=sys.stderr, flush=True)
                    app._close()
                    return
                print(output.decode(errors="replace").strip())
                print(f"Captured {filename}", flush=True)
                continuation()

            app.after(100, finish)

        def capture_example():
            app._clear_placeholder()
            app.text.insert("1.0", "Welcome to ClassicVoice.\n\nChoose the language of your text, select a voice style and adjust the settings.\n\nListen to a preview and save your audio as WAV. Everything runs locally on your computer.")
            app._update_count()
            english = next(language for language in app.languages if language.code == "en-us")
            app.language_label.set(english.label)
            app._apply_language()
            app.preset_label.set("Narrador")
            app._apply_preset()
            app.after(250, lambda: capture("ClassicVoice", "classicvoice-editor.png", capture_compact))

        def capture_compact():
            app.geometry("860x620")
            app.after(250, lambda: capture("ClassicVoice", "classicvoice-compact.png", capture_output))

        def capture_output():
            app.geometry("1100x720")
            app.settings_tabs.select(1)
            app.after(250, lambda: capture("ClassicVoice", "classicvoice-output.png", capture_dictionary))

        def capture_dictionary():
            app.pronunciation_rules = {"ClassicVoice": "Classic Voice", "WAV": "wave"}

            def ready():
                capture("Diccionario de pronunciación", "classicvoice-pronunciation.png", capture_profiles)

            app.after(250, ready)
            app._open_pronunciation()

        def capture_profiles():
            app.voice_profiles = {
                "Narración serena": {"language_code": "es", "preset_key": "narrator", "speed": 128, "pitch": 38,
                                     "volume": 105, "normalize": True, "pronunciation_rules": {"ClassicVoice": "Classic Voice"}},
                "Lectura pausada": {"language_code": "en-us", "preset_key": "deep", "speed": 132, "pitch": 30,
                                    "volume": 110, "normalize": True, "pronunciation_rules": {}},
            }
            app._open_voice_profiles()
            app.after(250, lambda: capture("Perfiles de voz · ClassicVoice", "classicvoice-profiles.png", capture_batch))

        def capture_batch():
            app._open_batch_dialog()
            app._batch_tree.insert("", "end", iid="demo-one", values=("el-principito.md · 8 capítulos",))
            app._batch_tree.insert("", "end", iid="demo-two", values=("apuntes.txt · 3 capítulos",))
            app._batch_status.set("2 archivos · 11 capítulos · WAV por capítulo y audiolibro completo")
            app.after(250, lambda: capture("ClassicVoice - Audiolibros", "classicvoice-batch.png", capture_natural_editor))

        def capture_natural_editor():
            for dialog in (app._batch_dialog, app._voice_profile_dialog, app._pronunciation_dialog):
                if dialog is not None and dialog.winfo_exists():
                    dialog.destroy()
            app.lift()
            app.focus_force()
            app._set_tts_engine("kokoro")
            spanish = next(language for language in app.languages if language.code == "es")
            app.language_label.set(spanish.label)
            app._apply_language()
            app._clear_placeholder()
            app.text.delete("1.0", "end")
            app.text.insert("1.0", "Hola. Soy ClassicVoice.\n\nConvierte tus palabras en audio con una voz neuronal más natural. La síntesis se realiza en tu equipo.")
            app._update_count()
            app.settings_tabs.select(0)
            app.after(250, lambda: capture("ClassicVoice", "classicvoice-natural.png", capture_natural_dialog))

        def capture_natural_dialog():
            app._open_tts_settings()
            app.after(250, lambda: capture("Motor de voz · ClassicVoice", "classicvoice-natural-engine.png", app._close))

        app.after(300, lambda: capture("ClassicVoice", "classicvoice-main.png", capture_example))
        app.mainloop()
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
