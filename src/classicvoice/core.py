from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass(frozen=True)
class VoicePreset:
    key: str
    label: str
    voice: str
    speed: int
    pitch: int
    amplitude: int = 100


PRESETS: tuple[VoicePreset, ...] = (
    VoicePreset("classic", "Classic ES", "es+m3", 145, 45, 100),
    VoicePreset("deep", "Classic ES Grave", "es+m3", 132, 30, 110),
    VoicePreset("bright", "Classic ES Agudo", "es+f3", 158, 62, 100),
    VoicePreset("narrator", "Narrador", "es+m2", 128, 38, 105),
)


def resolve_espeak(app_dir: Path) -> str | None:
    candidates = (
        app_dir / "bin" / "espeak-ng.exe",
        app_dir / "bin" / "espeak.exe",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return shutil.which("espeak-ng") or shutil.which("espeak")


def build_espeak_command(
    executable: str,
    text: str,
    output: Path,
    preset: VoicePreset,
    speed: int | None = None,
    pitch: int | None = None,
    amplitude: int | None = None,
) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("text is empty")

    s = preset.speed if speed is None else speed
    p = preset.pitch if pitch is None else pitch
    a = preset.amplitude if amplitude is None else amplitude

    if not 80 <= s <= 450:
        raise ValueError("speed out of range")
    if not 0 <= p <= 99:
        raise ValueError("pitch out of range")
    if not 0 <= a <= 200:
        raise ValueError("amplitude out of range")

    return [
        executable,
        "-v", preset.voice,
        "-s", str(s),
        "-p", str(p),
        "-a", str(a),
        "-w", str(output),
        clean,
    ]
