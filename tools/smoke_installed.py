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
        return 0
    finally:
        output.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
