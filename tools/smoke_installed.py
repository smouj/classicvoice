from __future__ import annotations

import argparse
from pathlib import Path
import queue
import sys
import tempfile
import threading


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from classicvoice import app, core  # noqa: E402
from classicvoice.natural_engine import model_is_installed, synthesize_kokoro_to_wav  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise the installed ClassicVoice engine and WAV export.")
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=Path.home() / "AppData" / "Local" / "Programs" / "ClassicVoice",
    )
    args = parser.parse_args()
    resource_root = args.install_dir / "_internal"
    app.APP_DIR = resource_root

    worker = object.__new__(app.ClassicVoiceApp)
    worker.engine = core.resolve_espeak(resource_root)
    worker.tts_engine = "espeak"
    worker.natural_voice = "ef_dora"
    worker._natural_model_dir = app.DATA_DIR / "models" / f"kokoro-{app.KOKORO_MODEL_VERSION}"
    if not worker.engine:
        raise SystemExit(f"eSpeak NG was not found in the installed resources: {resource_root}")
    worker._events = queue.Queue()
    worker._process_lock = threading.Lock()
    worker._process = None
    cancel = threading.Event()
    output = Path(tempfile.gettempdir()) / "classicvoice-installed-smoke.wav"

    try:
        worker._run_generation(
            "export",
            output,
            "Hola. Esta es una prueba de la versión instalada de ClassicVoice.",
            core.PRESETS[0],
            {"speed": 145, "pitch": 45, "volume": 100, "normalize": True},
            cancel,
        )
        event = worker._events.get_nowait()
        if event[0] != "done" or event[2] != str(output) or event[3]:
            raise SystemExit(f"Synthesis worker failed: {event}")
        frames, duration = core.validate_wav(output)
        if output.read_bytes()[:4] != b"RIFF":
            raise SystemExit("The generated output does not have a RIFF/WAV header.")
        print(f"Engine: {worker.engine}")
        print(f"End-to-end WAV export: PASS ({frames} frames, {duration:.2f} seconds, {output.stat().st_size} bytes)")
        if model_is_installed(worker._natural_model_dir):
            natural_output = output.with_name("classicvoice-installed-natural-smoke.wav")
            try:
                language = next(item for item in core.discover_voice_languages(worker.engine, resource_root) if item.code == "es")
                app.APP_DIR = resource_root
                worker._run_generation(
                    "export",
                    natural_output,
                    "Hola. Esta es una prueba de la voz natural en español.",
                    core.PRESETS[0],
                    {
                        "tts_engine": "kokoro",
                        "natural_voice": "ef_dora",
                        "language": language,
                        "speed": 145,
                        "normalize": True,
                    },
                    cancel,
                )
                natural_event = worker._events.get_nowait()
                if natural_event[0] != "done" or natural_event[2] != str(natural_output) or natural_event[3]:
                    raise SystemExit(f"Natural synthesis worker failed: {natural_event}")
                natural_frames, natural_duration = core.validate_wav(natural_output)
                print(f"Kokoro WAV export: PASS ({natural_frames} frames, {natural_duration:.2f} seconds)")
            finally:
                natural_output.unlink(missing_ok=True)
        else:
            print("Kokoro installed smoke: SKIP (optional model is not installed)")
        return 0
    finally:
        output.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
