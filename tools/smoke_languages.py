"""Verify that every advertised built-in language can export a readable WAV."""
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from classicvoice.core import (  # noqa: E402
    PRESETS, app_resource_dir, build_espeak_file_command, discover_voice_languages,
    espeak_environment, resolve_espeak, validate_wav,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-dir", type=Path)
    options = parser.parse_args()
    root = options.install_dir / "_internal" if options.install_dir else app_resource_dir()
    executable = resolve_espeak(root)
    languages = discover_voice_languages(executable, root)
    if not languages:
        raise SystemExit("No built-in languages found.")
    samples = {
        "es": "Hola. Bienvenido a ClassicVoice.",
        "en-us": "Hello. Welcome to ClassicVoice.",
        "fr-fr": "Bonjour. Bienvenue dans ClassicVoice.",
        "de": "Hallo. Willkommen bei ClassicVoice.",
        "ar": "مرحبا. أهلا وسهلا.", "ru": "Здравствуйте. Добро пожаловать.",
        "cmn": "你好，欢迎使用语音工具。", "ja": "こんにちは。音声ツールへようこそ。",
        "hi": "नमस्ते। आपका स्वागत है।",
    }
    count = 0
    with tempfile.TemporaryDirectory(prefix="ClassicVoice-languages-") as temporary:
        text = Path(temporary) / "text.txt"
        output = Path(temporary) / "voice.wav"
        for language in languages:
            presets = PRESETS if language.code in samples else PRESETS[:1]
            text.write_text(samples.get(language.code, "ClassicVoice."), encoding="utf-8")
            for preset in presets:
                output.unlink(missing_ok=True)
                command = build_espeak_file_command(executable, text, output, preset, language=language)
                result = subprocess.run(command, capture_output=True, timeout=15, env=espeak_environment(root, executable), creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                if result.returncode:
                    raise SystemExit(f"{language.code}/{preset.key}: {result.stderr.decode(errors='replace')}")
                validate_wav(output)
                count += 1
    print(f"PASS: {len(languages)} built-in languages/accents, {count} WAV exports; UTF-8 and all four styles verified for representative languages.")


if __name__ == "__main__":
    main()
