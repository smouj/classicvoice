"""Small, offline book and batch helpers used by ClassicVoice."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import os
import subprocess
import tempfile
import threading
import time
import uuid
import wave

from .core import (
    MAX_TEXT_CHARS,
    PRESETS,
    VoicePreset,
    VoiceLanguage,
    build_espeak_file_command,
    espeak_environment,
    normalize_wav,
    validate_wav,
)


MAX_BOOK_CHARS = 2_000_000
MAX_BOOK_BYTES = 16 * 1024 * 1024
MAX_VOICE_PROFILES = 24
SYNTHESIS_TIMEOUT_SECONDS = 180
_CHAPTER_HEADING = re.compile(
    r"^\s{0,3}(?:#{1,3}\s*)?(?:chapter|cap[ií]tulo|part|parte|section|secci[oó]n|"
    r"prologue|pr[oó]logo|epilogue|ep[ií]logo)\b[^\r\n]*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class TextChapter:
    title: str
    text: str


class SynthesisCancelled(InterruptedError):
    """Raised when a user cancels a chapter or batch render."""


def normalize_voice_profiles(value: object) -> dict[str, dict]:
    """Load bounded reusable synthesis settings, ignoring malformed user config."""
    if not isinstance(value, dict):
        return {}
    presets = {preset.key: preset for preset in PRESETS}
    result: dict[str, dict] = {}
    for raw_name, raw_profile in value.items():
        if len(result) >= MAX_VOICE_PROFILES:
            break
        if not isinstance(raw_name, str) or not isinstance(raw_profile, dict):
            continue
        name = raw_name.strip()[:36]
        if not name or any(ord(char) < 32 for char in name):
            continue
        preset_key = str(raw_profile.get("preset_key", "classic"))
        preset = presets.get(preset_key, PRESETS[0])
        raw_rules = raw_profile.get("pronunciation_rules", {})
        rules = {}
        if isinstance(raw_rules, dict):
            for source, spoken in raw_rules.items():
                source = str(source).strip()[:80]
                spoken = str(spoken).strip()[:120]
                if source and spoken and len(rules) < 500:
                    rules[source] = spoken
        result[name] = {
            "tts_engine": raw_profile.get("tts_engine") if raw_profile.get("tts_engine") in {"espeak", "kokoro"} else "espeak",
            "natural_voice": str(raw_profile.get("natural_voice", "ef_dora"))[:32],
            "language_code": str(raw_profile.get("language_code", "es"))[:32],
            "preset_key": preset.key,
            "speed": _profile_int(raw_profile.get("speed"), preset.speed, 80, 450),
            "pitch": _profile_int(raw_profile.get("pitch"), preset.pitch, 0, 99),
            "volume": _profile_int(raw_profile.get("volume"), preset.amplitude, 0, 200),
            "normalize": raw_profile.get("normalize") if isinstance(raw_profile.get("normalize"), bool) else True,
            "pronunciation_rules": rules,
        }
    return result


def _profile_int(value: object, fallback: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def synthesize_text_to_wav(
    executable: str,
    app_dir: Path,
    text: str,
    output: Path,
    preset: VoicePreset,
    settings: dict,
    cancel_event: threading.Event,
    on_process=None,
) -> float:
    """Render one WAV with eSpeak NG while remaining cancellable and disk-bounded."""
    output.parent.mkdir(parents=True, exist_ok=True)
    input_path = output.with_name(f".{output.name}.{uuid.uuid4().hex}.txt")
    process: subprocess.Popen | None = None
    try:
        input_path.write_text(text, encoding="utf-8", newline="\n")
        command = build_espeak_file_command(
            executable,
            input_path,
            output,
            preset,
            settings["speed"],
            settings["pitch"],
            settings["volume"],
            language=settings.get("language"),
        )
        if cancel_event.is_set():
            raise SynthesisCancelled("cancelled")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            env=espeak_environment(app_dir, executable),
        )
        if on_process is not None:
            on_process(process)
        deadline = time.monotonic() + SYNTHESIS_TIMEOUT_SECONDS
        while True:
            try:
                _stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if cancel_event.is_set():
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    raise SynthesisCancelled("cancelled")
                if time.monotonic() >= deadline:
                    process.kill()
                    _stdout, stderr = process.communicate()
                    detail = stderr.decode("utf-8", errors="replace").strip()
                    raise TimeoutError(
                        detail or "La síntesis ha tardado demasiado. Prueba a dividir el texto en fragmentos más pequeños."
                    )
        if cancel_event.is_set():
            raise SynthesisCancelled("cancelled")
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "eSpeak NG ha terminado con un error.")
        frame_count, duration = validate_wav(output)
        if frame_count <= 0:
            raise ValueError("No se ha generado audio.")
        if settings.get("normalize", True):
            normalize_wav(output)
        return duration
    finally:
        if on_process is not None:
            on_process(None)
        input_path.unlink(missing_ok=True)


def read_text_document(path: Path) -> str:
    """Read a bounded UTF-8/UTF-16 text or Markdown document without changing it."""
    with path.open("rb") as source:
        raw = source.read(MAX_BOOK_BYTES + 1)
    if len(raw) > MAX_BOOK_BYTES:
        raise ValueError(f"{path.name} supera el límite de {MAX_BOOK_BYTES // (1024 * 1024)} MB.")
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    text = raw.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > MAX_BOOK_CHARS:
        raise ValueError(f"{path.name} supera el límite de {MAX_BOOK_CHARS:,} caracteres.")
    if path.suffix.casefold() == ".md":
        text = markdown_to_speech(text)
    return text.strip()


def markdown_to_speech(text: str) -> str:
    """Remove common Markdown decoration while keeping its readable text."""
    text = re.sub(r"```[^\n]*\n.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}(?:[-+*]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?<!\w)[*_~]{1,3}([^*_~]+)[*_~]{1,3}(?!\w)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", " ", text, flags=re.MULTILINE)
    text = text.replace("|", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _split_oversized(text: str, limit: int) -> list[str]:
    """Split long paragraphs at whitespace, hard-splitting only a single long token."""
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        cut = remaining.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _pack_paragraphs(text: str, limit: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        for piece in _split_oversized(paragraph, limit):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


def split_book_text(text: str, title: str, limit: int = MAX_TEXT_CHARS) -> tuple[TextChapter, ...]:
    """Split marked chapters, or safely pack a long document into bounded parts."""
    if limit < 1 or limit > MAX_TEXT_CHARS:
        raise ValueError(f"El límite por fragmento debe estar entre 1 y {MAX_TEXT_CHARS} caracteres.")
    source = text.strip()
    if not source:
        return ()

    matches = list(_CHAPTER_HEADING.finditer(source))
    sections: list[tuple[str, str]] = []
    if matches:
        preamble = source[:matches[0].start()].strip()
        if preamble:
            sections.append((title.strip() or "Introducción", preamble))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
            heading = re.sub(r"^\s{0,3}#{1,3}\s*", "", match.group(0)).strip()
            body = source[match.end():end].strip()
            if body:
                sections.append((heading or f"Capítulo {len(sections) + 1}", body))
    else:
        sections.append((title.strip() or "Texto", source))

    result: list[TextChapter] = []
    for section_title, body in sections:
        pieces = _pack_paragraphs(body, limit)
        for index, piece in enumerate(pieces, start=1):
            part_title = section_title if len(pieces) == 1 else f"{section_title} · {index:02d}"
            result.append(TextChapter(part_title, piece))
    return tuple(result)


def safe_audio_stem(value: str, limit: int = 64) -> str:
    """Return a readable Windows-safe file stem."""
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-")
    cleaned = cleaned[:limit].strip(" .-")
    return cleaned or "audio"


def merge_wav_files(paths: tuple[Path, ...] | list[Path], destination: Path, silence_ms: int = 350) -> tuple[int, float]:
    """Join compatible PCM WAV chapters without loading the whole audiobook in RAM."""
    if not paths:
        raise ValueError("No hay capítulos de audio para unir.")
    if not 0 <= silence_ms <= 5000:
        raise ValueError("La pausa entre capítulos debe estar entre 0 y 5000 ms.")

    with wave.open(str(paths[0]), "rb") as first:
        params = first.getparams()
        if params.comptype != "NONE":
            raise ValueError("Solo se pueden unir archivos WAV PCM sin compresión.")
        rate = params.framerate
        silence_frames = round(rate * silence_ms / 1000)
        silence_sample = b"\x80" if params.sampwidth == 1 else b"\x00" * params.sampwidth
        silence_block = silence_sample * params.nchannels * min(silence_frames, 65536)

    frame_count = 0
    with wave.open(str(destination), "wb") as output:
        output.setparams(params)
        for index, path in enumerate(paths):
            try:
                source = wave.open(str(path), "rb")
            except (wave.Error, EOFError, OSError) as exc:
                raise ValueError(f"No se pudo leer el capítulo {path.name}.") from exc
            with source:
                actual = source.getparams()
                if (actual.nchannels, actual.sampwidth, actual.framerate, actual.comptype) != (
                    params.nchannels, params.sampwidth, params.framerate, params.comptype
                ):
                    raise ValueError(f"El formato de {path.name} no coincide con el primer capítulo.")
                while block := source.readframes(65536):
                    output.writeframesraw(block)
                    frame_count += len(block) // (params.nchannels * params.sampwidth)
            if index + 1 < len(paths) and silence_frames:
                left = silence_frames
                while left:
                    count = min(left, 65536)
                    if len(silence_block) != count * params.nchannels * params.sampwidth:
                        silence_block = silence_sample * params.nchannels * count
                    output.writeframesraw(silence_block)
                    frame_count += count
                    left -= count
    return frame_count, frame_count / rate
