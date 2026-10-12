"""Render real documentation screenshots without modifying user preferences.

Run on Windows from the repository virtual environment. The source application
runs its normal Tk event loop while Windows renders each selected client area.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from classicvoice.app import ClassicVoiceApp  # noqa: E402


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Screenshots require Windows.")
    failures = []
    with patch("classicvoice.app._load_config", return_value={}), patch("classicvoice.app._save_config"):
        app = ClassicVoiceApp()
        app.geometry("1100x720")

        def capture(title, filename, continuation):
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
                    app._close()
                    return
                print(output.decode(errors="replace").strip())
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
                capture("Diccionario de pronunciación", "classicvoice-pronunciation.png", app._pronunciation_dialog.destroy)

            app.after(250, ready)
            app._open_pronunciation()
            app._close()

        app.after(300, lambda: capture("ClassicVoice", "classicvoice-main.png", capture_example))
        app.mainloop()
    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
