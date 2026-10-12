"""Optional, local Kokoro ONNX voices for more natural speech."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import urllib.request
import uuid
import wave

from .core import app_data_dir, app_resource_dir, normalize_wav, resolve_espeak, resolve_espeak_data, validate_wav
from .workflows import SynthesisCancelled


KOKORO_MODEL_VERSION = "v1.0-int8"
KOKORO_MODEL_BYTES = 114_119_327
KOKORO_VOICES_BYTES = 28_214_398
KOKORO_MODEL_SHA256 = "ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c"
KOKORO_VOICES_SHA256 = "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"
KOKORO_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    "kokoro-v1.0.int8.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
    "voices-v1.0.bin"
)
KOKORO_LICENSE_NAME = "Kokoro-82M-Apache-2.0.txt"
KOKORO_LICENSE_PATH = app_resource_dir() / "licenses" / KOKORO_LICENSE_NAME
NATURAL_MODEL_DIR = app_data_dir() / "models" / f"kokoro-{KOKORO_MODEL_VERSION}"
MAX_KOKORO_CHARS = 50_000
_DOWNLOAD_TIMEOUT = 30
_DOWNLOAD_BLOCK = 1024 * 1024
_CHUNK_PAUSE_SECONDS = 0.35


# Kokoro ships preset voices; these are voice IDs from its published voice pack.
# Language identifiers follow the bundled eSpeak NG catalogue.
KOKORO_VOICES: dict[str, tuple[tuple[str, str], ...]] = {
    "en-us": (
        ("af_heart", "Heart · femenina"),
        ("af_bella", "Bella · femenina"),
        ("af_sarah", "Sarah · femenina"),
        ("af_nicole", "Nicole · femenina"),
        ("af_nova", "Nova · femenina"),
        ("am_michael", "Michael · masculina"),
        ("am_fenrir", "Fenrir · masculina"),
        ("am_puck", "Puck · masculina"),
    ),
    "en-gb": (
        ("bf_emma", "Emma · femenina"),
        ("bf_isabella", "Isabella · femenina"),
        ("bm_george", "George · masculina"),
        ("bm_fable", "Fable · masculina"),
    ),
    "es": (("ef_dora", "Dora · femenina"), ("em_alex", "Alex · masculina"), ("em_santa", "Santa · masculina")),
    "fr-fr": (("ff_siwis", "Siwis · femenina"),),
    "it": (("if_sara", "Sara · femenina"), ("im_nicola", "Nicola · masculina")),
    "pt-br": (("pf_dora", "Dora · femenina"), ("pm_alex", "Alex · masculina"), ("pm_santa", "Santa · masculina")),
    "ja": (("jf_alpha", "Alpha · femenina"), ("jf_gongitsune", "Gongitsune · femenina"), ("jm_kumo", "Kumo · masculina")),
    "cmn": (("zf_xiaobei", "Xiaobei · femenina"), ("zf_xiaoni", "Xiaoni · femenina"), ("zm_yunxi", "Yunxi · masculina")),
    "hi": (("hf_alpha", "Alpha · femenina"), ("hf_beta", "Beta · femenina"), ("hm_omega", "Omega · masculina")),
}

_LANGUAGE_ALIASES = {
    "pt": "pt-br",
    "zh": "cmn",
    "zh-cn": "cmn",
    "zh-tw": "cmn",
    "fr": "fr-fr",
}
_KOKORO_LANG = {
    "en-us": "en-us",
    "en-gb": "en-gb",
    "es": "es",
    "fr-fr": "fr-fr",
    "it": "it",
    "pt-br": "pt-br",
    "ja": "ja",
    "cmn": "zh",
    "hi": "hi",
}


def canonical_language(code: str) -> str | None:
    normalized = str(code).strip().casefold().replace("_", "-")
    normalized = _LANGUAGE_ALIASES.get(normalized, normalized)
    return normalized if normalized in KOKORO_VOICES else None


def voices_for_language(code: str) -> tuple[tuple[str, str], ...]:
    language = canonical_language(code)
    return KOKORO_VOICES.get(language, ()) if language else ()


def kokoro_runtime_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("kokoro_onnx", "onnxruntime"))


def model_paths(model_dir: Path | None = None) -> tuple[Path, Path]:
    root = model_dir or NATURAL_MODEL_DIR
    return root / "kokoro-v1.0.int8.onnx", root / "voices-v1.0.bin"


def _clear_known_model_files(folder: Path) -> None:
    model_path, voices_path = model_paths(folder)
    for path in (model_path, voices_path, folder / KOKORO_LICENSE_NAME):
        path.unlink(missing_ok=True)
    try:
        folder.rmdir()
    except OSError:
        # Leave unexpected files in place rather than deleting user data.
        pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(_DOWNLOAD_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def _weights_are_verified(model_path: Path, voices_path: Path) -> bool:
    try:
        return (
            model_path.stat().st_size == KOKORO_MODEL_BYTES
            and voices_path.stat().st_size == KOKORO_VOICES_BYTES
            and _sha256_file(model_path) == KOKORO_MODEL_SHA256
            and _sha256_file(voices_path) == KOKORO_VOICES_SHA256
        )
    except OSError:
        return False


def model_is_installed(model_dir: Path | None = None) -> bool:
    model_path, voices_path = model_paths(model_dir)
    try:
        root = model_dir or NATURAL_MODEL_DIR
        license_path = root / KOKORO_LICENSE_NAME
        return (
            model_path.stat().st_size == KOKORO_MODEL_BYTES
            and voices_path.stat().st_size == KOKORO_VOICES_BYTES
            and license_path.is_file()
            and license_path.stat().st_size > 1_000
        )
    except OSError:
        return False


def _download_verified(url: str, destination: Path, size: int, digest: str, cancel: threading.Event, on_progress) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "ClassicVoice/0.4"})
    hasher = hashlib.sha256()
    received = 0
    try:
        with urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT) as response, destination.open("wb") as output:
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) != size:
                raise ValueError("El archivo remoto tiene un tamaño distinto al esperado.")
            while True:
                if cancel.is_set():
                    raise SynthesisCancelled("cancelled")
                block = response.read(_DOWNLOAD_BLOCK)
                if not block:
                    break
                received += len(block)
                if received > size:
                    raise ValueError("El archivo remoto supera el tamaño esperado.")
                output.write(block)
                hasher.update(block)
                if on_progress:
                    on_progress(received, size)
        if received != size or hasher.hexdigest() != digest:
            raise ValueError("La descarga no ha superado la comprobación de integridad SHA-256.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def install_kokoro_model(
    model_dir: Path | None = None,
    cancel: threading.Event | None = None,
    on_progress=None,
) -> Path:
    """Download the CPU-sized model and voice pack, verify hashes, then publish together."""
    destination = model_dir or NATURAL_MODEL_DIR
    cancellation = cancel or threading.Event()
    if not KOKORO_LICENSE_PATH.is_file():
        raise RuntimeError(f"Falta el aviso de licencia del modelo: {KOKORO_LICENSE_PATH}")
    model_path, voices_path = model_paths(destination)
    if _weights_are_verified(model_path, voices_path):
        if not model_is_installed(destination):
            # Add the license to an already verified install without downloading again.
            destination.mkdir(parents=True, exist_ok=True)
            staged_license = destination / f".{KOKORO_LICENSE_NAME}.tmp"
            try:
                shutil.copyfile(KOKORO_LICENSE_PATH, staged_license)
                os.replace(staged_license, destination / KOKORO_LICENSE_NAME)
            finally:
                staged_license.unlink(missing_ok=True)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.install-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.previous-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        _download_verified(
            KOKORO_MODEL_URL,
            staging / "kokoro-v1.0.int8.onnx",
            KOKORO_MODEL_BYTES,
            KOKORO_MODEL_SHA256,
            cancellation,
            (lambda current, total: on_progress("modelo", current, total)) if on_progress else None,
        )
        _download_verified(
            KOKORO_VOICES_URL,
            staging / "voices-v1.0.bin",
            KOKORO_VOICES_BYTES,
            KOKORO_VOICES_SHA256,
            cancellation,
            (lambda current, total: on_progress("voces", current, total)) if on_progress else None,
        )
        shutil.copyfile(KOKORO_LICENSE_PATH, staging / KOKORO_LICENSE_NAME)
        if cancellation.is_set():
            raise SynthesisCancelled("cancelled")
        if destination.exists():
            destination.replace(backup)
        try:
            staging.replace(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        if backup.exists():
            _clear_known_model_files(backup)
        return destination
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and destination.exists():
            _clear_known_model_files(backup)


def remove_kokoro_model(model_dir: Path | None = None) -> None:
    """Remove only ClassicVoice's downloaded Kokoro files."""
    destination = model_dir or NATURAL_MODEL_DIR
    _clear_known_model_files(destination)


def _text_chunks(text: str, limit: int = 1800) -> tuple[str, ...]:
    """Make paragraph-aware input chunks without splitting words or dropping punctuation."""
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text.strip()) if paragraph.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs or ([text.strip()] if text.strip() else []):
        remaining = paragraph
        while len(remaining) > limit:
            separators = (". ", "! ", "? ", "; ", ", ")
            sentence_breaks = [(remaining.rfind(mark, 0, limit), mark) for mark in separators]
            break_at, marker = max(sentence_breaks, key=lambda item: item[0])
            if break_at >= limit // 3:
                cut = break_at + len(marker) - 1
            else:
                cut = remaining.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            piece = remaining[:cut].strip()
            chunks.append(piece)
            remaining = remaining[cut:].strip()
        if remaining:
            chunks.append(remaining)
    return tuple(chunks)


def synthesize_kokoro_to_wav(
    text: str,
    output: Path,
    voice: str,
    language_code: str,
    speed: int,
    normalize: bool,
    cancel: threading.Event,
    model_dir: Path | None = None,
    app_dir: Path | None = None,
    on_progress=None,
) -> float:
    """Generate local PCM WAV audio using Kokoro with a conservative CPU session."""
    if not kokoro_runtime_available():
        raise RuntimeError("La versión instalada no contiene el motor Kokoro. Actualiza ClassicVoice desde GitHub.")
    if not model_is_installed(model_dir):
        raise RuntimeError("Descarga primero el modelo de voz natural desde «Configurar motor».")
    if not text.strip() or len(text) > MAX_KOKORO_CHARS:
        raise ValueError(f"El texto debe tener entre 1 y {MAX_KOKORO_CHARS:,} caracteres.")
    canonical = canonical_language(language_code)
    valid_voices = {voice_id for voice_id, _label in voices_for_language(language_code)}
    if not canonical or voice not in valid_voices:
        raise ValueError("La voz seleccionada no corresponde al idioma del texto.")
    if not 80 <= int(speed) <= 450:
        raise ValueError("La velocidad debe estar entre 80 y 450.")

    from kokoro_onnx import Kokoro
    from kokoro_onnx.config import EspeakConfig
    import onnxruntime as ort
    import numpy as np

    root = model_dir or NATURAL_MODEL_DIR
    model_path, voices_path = model_paths(root)
    if not _weights_are_verified(model_path, voices_path):
        raise RuntimeError("Los archivos del modelo natural no superaron la verificación SHA-256. Vuelve a instalarlos desde «Configurar motor».")
    app_root = app_dir or app_resource_dir()
    espeak_executable = resolve_espeak(app_root)
    espeak_dir = Path(espeak_executable).resolve().parent if espeak_executable else app_root / "bin" / "espeak-ng"
    espeak_lib = espeak_dir / "libespeak-ng.dll"
    espeak_data = resolve_espeak_data(app_root, espeak_executable) if espeak_executable else None
    espeak_config = EspeakConfig(
        lib_path=str(espeak_lib) if espeak_lib.is_file() else None,
        data_path=str(espeak_data) if espeak_data and espeak_data.is_dir() else None,
    )

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = max(1, min(2, (os.cpu_count() or 2) // 2))
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if hasattr(ort, "disable_telemetry_events"):
        ort.disable_telemetry_events()
    session = ort.InferenceSession(str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"])
    if os.name == "nt" and espeak_dir.is_dir():
        with os.add_dll_directory(str(espeak_dir)):
            engine = Kokoro.from_session(session, str(voices_path), espeak_config=espeak_config)
    else:
        engine = Kokoro.from_session(session, str(voices_path), espeak_config=espeak_config)

    language = _KOKORO_LANG[canonical]
    speed_value = int(speed)
    speed_ratio = (
        0.6 + 0.4 * (speed_value - 80) / 65
        if speed_value <= 145
        else 1.0 + 0.5 * (speed_value - 145) / 305
    )
    chunks = _text_chunks(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.partial.wav")
    async def write_stream(audio_file: wave.Wave_write) -> None:
        for index, chunk in enumerate(chunks, start=1):
            if cancel.is_set():
                raise SynthesisCancelled("cancelled")
            async for samples, sample_rate in engine.create_stream(
                chunk,
                voice=voice,
                speed=speed_ratio,
                lang=language,
                sentence_pause=0.28,
                clause_pause=0.12,
            ):
                if cancel.is_set():
                    raise SynthesisCancelled("cancelled")
                if sample_rate != 24_000:
                    raise ValueError(f"El motor ha devuelto una frecuencia inesperada: {sample_rate} Hz.")
                pcm = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
                pcm = np.rint(pcm * 32767.0).astype("<i2", copy=False)
                audio_file.writeframes(pcm.tobytes())
            if index < len(chunks):
                # Kokoro trims each call; leave a natural breath between paragraphs/chunks.
                pause = np.zeros(round(24_000 * _CHUNK_PAUSE_SECONDS), dtype="<i2")
                audio_file.writeframes(pause.tobytes())
            if on_progress:
                on_progress(index, len(chunks))

    try:
        with wave.open(str(temporary), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(24_000)
            asyncio.run(write_stream(audio_file))
        if cancel.is_set():
            raise SynthesisCancelled("cancelled")
        frames, duration = validate_wav(temporary)
        if frames <= 0:
            raise ValueError("El motor neuronal no ha generado audio.")
        if normalize:
            normalize_wav(temporary)
        os.replace(temporary, output)
        return duration
    finally:
        temporary.unlink(missing_ok=True)
