from __future__ import annotations

from array import array
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave


MAX_TEXT_CHARS = 50_000


@dataclass(frozen=True)
class VoicePreset:
    key: str
    label: str
    voice: str
    speed: int
    pitch: int
    amplitude: int = 100
    description: str = ""


PRESETS: tuple[VoicePreset, ...] = (
    VoicePreset("classic", "Clásica", "es+m3", 145, 45, 100, "Voz clásica equilibrada"),
    VoicePreset("deep", "Clásica grave", "es+m3", 132, 30, 110, "Tono más profundo y pausado"),
    VoicePreset("bright", "Clásica brillante", "es+f3", 158, 62, 100, "Tono más agudo y ligero"),
    VoicePreset("narrator", "Narrador", "es+m2", 128, 38, 105, "Lectura más pausada"),
)

LEGACY_PRESET_LABELS = {
    "Clásica española": "classic",
    "Classic ES": "classic",
    "Classic ES Grave": "deep",
    "Classic ES Agudo": "bright",
    "Narrador": "narrator",
}


@dataclass(frozen=True)
class VoiceLanguage:
    code: str
    name: str
    identifier: str

    @property
    def label(self) -> str:
        return f"{self.name} · {self.code}"


LANGUAGE_NAMES = {
    "es": "Español", "es-419": "Español (Latinoamérica)",
    "en-gb": "Inglés (Reino Unido)", "en-us": "Inglés (Estados Unidos)",
    "fr-fr": "Francés", "de": "Alemán", "it": "Italiano",
    "pt": "Portugués (Brasil)", "pt-pt": "Portugués (Portugal)",
    "ca": "Catalán", "eu": "Euskera", "gl": "Gallego",
    "ar": "Árabe", "ru": "Ruso", "ja": "Japonés", "ko": "Coreano",
    "cmn": "Chino mandarín", "yue": "Chino cantonés", "hi": "Hindi",
}


def parse_voice_languages(output: str) -> tuple[VoiceLanguage, ...]:
    """List built-in language voices, excluding external MBROLA backends."""
    languages: dict[str, VoiceLanguage] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or not fields[0].isdigit():
            continue
        code, name, identifier = fields[1], fields[3], fields[4].replace("\\", "/")
        if identifier.startswith("mb/") or not re.fullmatch(r"[a-zA-Z0-9/_-]+", identifier):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9-]*", code):
            continue
        languages.setdefault(code, VoiceLanguage(code, LANGUAGE_NAMES.get(code, name.replace("_", " ")), identifier))
    return tuple(sorted(languages.values(), key=lambda language: (language.code != "es", language.name.casefold())))


def discover_voice_languages(executable: str | None, app_dir: Path) -> tuple[VoiceLanguage, ...]:
    if not executable:
        return ()
    try:
        result = subprocess.run(
            [executable, "--voices"], capture_output=True, timeout=5,
            encoding="utf-8", errors="replace", env=espeak_environment(app_dir, executable),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    return parse_voice_languages(result.stdout) if result.returncode == 0 else ()


def app_resource_dir() -> Path:
    """Return the read-only resource root in source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def app_data_dir() -> Path:
    """Return a per-user writable settings directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ClassicVoice"
    return Path.home() / ".classicvoice"


def resolve_espeak(app_dir: Path) -> str | None:
    """Find a bundled, user-installed, or PATH eSpeak NG executable."""
    candidates = [
        app_dir / "bin" / "espeak-ng" / "espeak-ng.exe",
        app_dir / "bin" / "espeak-ng.exe",
        app_dir / "bin" / "espeak.exe",
    ]
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        install_root = os.environ.get(variable)
        if install_root:
            candidates.extend(
                (
                    Path(install_root) / "eSpeak NG" / "espeak-ng.exe",
                    Path(install_root) / "eSpeak NG" / "espeak.exe",
                )
            )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which("espeak-ng") or shutil.which("espeak")


def resolve_espeak_data(app_dir: Path, executable: str) -> Path | None:
    """Find the language data directory required by the Windows distribution."""
    executable_dir = Path(executable).resolve().parent
    candidates = (
        app_dir / "bin" / "espeak-ng" / "espeak-ng-data",
        app_dir / "bin" / "espeak-ng-data",
        executable_dir / "espeak-ng-data",
        executable_dir.parent / "espeak-ng-data",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def espeak_environment(app_dir: Path, executable: str) -> dict[str, str]:
    """Build a child-only environment for eSpeak without changing Windows settings."""
    env = os.environ.copy()
    executable_dir = str(Path(executable).resolve().parent)
    env["PATH"] = executable_dir + os.pathsep + env.get("PATH", "")
    data_dir = resolve_espeak_data(app_dir, executable)
    if data_dir is not None:
        env["ESPEAK_DATA_PATH"] = str(data_dir)
    return env


def _validated_values(
    preset: VoicePreset,
    speed: int | None,
    pitch: int | None,
    amplitude: int | None,
) -> tuple[int, int, int]:
    s = preset.speed if speed is None else speed
    p = preset.pitch if pitch is None else pitch
    a = preset.amplitude if amplitude is None else amplitude
    if not 80 <= s <= 450:
        raise ValueError("speed out of range")
    if not 0 <= p <= 99:
        raise ValueError("pitch out of range")
    if not 0 <= a <= 200:
        raise ValueError("amplitude out of range")
    return s, p, a


def build_espeak_file_command(
    executable: str,
    input_file: Path,
    output: Path,
    preset: VoicePreset,
    speed: int | None = None,
    pitch: int | None = None,
    amplitude: int | None = None,
    language: VoiceLanguage | None = None,
) -> list[str]:
    """Build a safe command that reads UTF-8 text from a file, avoiding OS arg limits."""
    s, p, a = _validated_values(preset, speed, pitch, amplitude)
    return [
        executable,
        "-v", voice_for_language(preset, language),
        "-s", str(s),
        "-p", str(p),
        "-a", str(a),
        "-b", "1",
        "-f", str(input_file),
        "-w", str(output),
    ]


def voice_for_language(preset: VoicePreset, language: VoiceLanguage | None) -> str:
    if language is None:
        return preset.voice
    if not re.fullmatch(r"[a-zA-Z0-9/_-]+", language.identifier) or language.identifier.startswith("mb/"):
        raise ValueError("Invalid built-in voice identifier")
    variant = preset.voice.partition("+")[2]
    return language.identifier + (f"+{variant}" if variant else "")


def build_espeak_command(
    executable: str,
    text: str,
    output: Path,
    preset: VoicePreset,
    speed: int | None = None,
    pitch: int | None = None,
    amplitude: int | None = None,
) -> list[str]:
    """Compatibility helper for short command-line examples and tests."""
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("text is empty")
    s, p, a = _validated_values(preset, speed, pitch, amplitude)
    return [
        executable,
        "-v", preset.voice,
        "-s", str(s),
        "-p", str(p),
        "-a", str(a),
        "-w", str(output),
        clean,
    ]


def apply_pronunciation_rules(text: str, rules: dict[str, str]) -> str:
    """Replace configured words/phrases case-insensitively without partial-word hits."""
    for original, spoken in rules.items():
        source = original.strip()
        if not source:
            continue
        text = re.sub(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            lambda _match, replacement=spoken: replacement,
            text,
            flags=re.IGNORECASE,
        )
    return text


def validate_wav(path: Path) -> tuple[int, float]:
    """Validate that eSpeak produced a non-empty, readable PCM WAV."""
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            rate = source.getframerate()
            frame_count = source.getnframes()
            sample_width = source.getsampwidth()
            compression = source.getcomptype()
            if channels < 1 or rate < 1 or frame_count < 1:
                raise ValueError("El motor no ha generado audio.")
            if sample_width not in (1, 2, 3, 4) or compression != "NONE":
                raise ValueError("El motor ha generado un WAV PCM no compatible.")
            return frame_count, frame_count / rate
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("El archivo WAV generado está vacío o dañado.") from exc


def normalize_wav(path: Path, target_peak: float = 0.89) -> bool:
    """Normalize PCM WAV peak to a safe target. Returns False for silence/already-normalized."""
    if not 0.0 < target_peak <= 1.0:
        raise ValueError("target_peak must be within (0, 1]")

    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        if params.comptype != "NONE":
            raise ValueError("Solo se pueden normalizar WAV PCM sin compresión.")
        raw = source.readframes(params.nframes)

    width = params.sampwidth
    if width == 1:
        values = [sample - 128 for sample in raw]
        max_value = 127
        peak = max((abs(sample) for sample in values), default=0)
        if peak == 0:
            return False
        gain = (max_value * target_peak) / peak
        normalized = bytes(max(0, min(255, round(128 + sample * gain))) for sample in values)
    elif width in (2, 4):
        samples = array("h" if width == 2 else "i")
        samples.frombytes(raw)
        if sys.byteorder != "little":
            samples.byteswap()
        max_value = (1 << (width * 8 - 1)) - 1
        min_value = -(1 << (width * 8 - 1))
        peak = max((abs(sample) for sample in samples), default=0)
        if peak == 0:
            return False
        gain = (max_value * target_peak) / peak
        for index, sample in enumerate(samples):
            samples[index] = max(min_value, min(max_value, round(sample * gain)))
        if sys.byteorder != "little":
            samples.byteswap()
        normalized = samples.tobytes()
    elif width == 3:
        values = [
            int.from_bytes(raw[offset:offset + 3], "little", signed=True)
            for offset in range(0, len(raw), 3)
        ]
        max_value = (1 << 23) - 1
        min_value = -(1 << 23)
        peak = max((abs(sample) for sample in values), default=0)
        if peak == 0:
            return False
        gain = (max_value * target_peak) / peak
        output = bytearray()
        for sample in values:
            scaled = max(min_value, min(max_value, round(sample * gain)))
            output.extend(int(scaled).to_bytes(3, "little", signed=True))
        normalized = bytes(output)
    else:  # guarded by validate_wav, retained for direct callers
        raise ValueError("Profundidad de audio no compatible.")

    temporary = path.with_name(path.name + ".normalizing")
    try:
        with wave.open(str(temporary), "wb") as target:
            target.setparams(params)
            target.writeframes(normalized)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
