from array import array
from pathlib import Path
import wave

import pytest

from classicvoice.core import (
    PRESETS,
    VoicePreset,
    app_data_dir,
    apply_pronunciation_rules,
    build_espeak_command,
    build_espeak_file_command,
    normalize_wav,
    resolve_espeak,
    validate_wav,
    parse_voice_languages,
    VoiceLanguage,
    voice_for_language,
)


def test_language_catalog_excludes_external_mbrola():
    output = "Pty Language Age/Gender VoiceName File\n1 ar --/M arabic-mbrola mb/mb-ar1\n5 ar --/M Arabic sem/ar\n5 es --/M Spanish roa/es\n5 en-us --/M English_(America) gmw/en-US\n5 ar --/M Arabic sem/ar\n"
    languages = parse_voice_languages(output)
    assert languages[0].code == "es"
    assert len(languages) == 3
    arabic = next(language for language in languages if language.code == "ar")
    assert voice_for_language(PRESETS[0], arabic) == "sem/ar+m3"


def test_language_voice_is_passed_as_a_single_argument(tmp_path):
    language = VoiceLanguage("en-us", "English", "gmw/en-US")
    command = build_espeak_file_command("espeak-ng", tmp_path / "text.txt", tmp_path / "voice.wav", PRESETS[2], language=language)
    assert command[command.index("-v") + 1] == "gmw/en-US+f3"
    with pytest.raises(ValueError):
        voice_for_language(PRESETS[0], VoiceLanguage("en", "Invalid", "../outside"))


def _write_pcm(path: Path, values: list[int], width: int = 2, rate: int = 24_000) -> None:
    if width == 1:
        raw = bytes(value + 128 for value in values)
    elif width in (2, 4):
        samples = array("h" if width == 2 else "i", values)
        raw = samples.tobytes()
    else:
        raw = b"".join(value.to_bytes(3, "little", signed=True) for value in values)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(width)
        target.setframerate(rate)
        target.writeframes(raw)


def _peak(path: Path) -> int:
    with wave.open(str(path), "rb") as source:
        raw = source.readframes(source.getnframes())
        width = source.getsampwidth()
    if width == 1:
        return max((abs(value - 128) for value in raw), default=0)
    if width == 2:
        samples = array("h")
        samples.frombytes(raw)
        return max((abs(value) for value in samples), default=0)
    if width == 4:
        samples = array("i")
        samples.frombytes(raw)
        return max((abs(value) for value in samples), default=0)
    return max(
        (abs(int.from_bytes(raw[i:i + 3], "little", signed=True)) for i in range(0, len(raw), 3)),
        default=0,
    )


def test_presets_have_unique_keys_and_labels():
    assert len({preset.key for preset in PRESETS}) == len(PRESETS)
    assert len({preset.label for preset in PRESETS}) == len(PRESETS)


def test_short_espeak_command_contains_selected_settings():
    command = build_espeak_command(
        "espeak-ng", "Hola   mundo", Path("out.wav"), PRESETS[0], 150, 40, 90
    )
    assert command[command.index("-s") + 1] == "150"
    assert command[command.index("-p") + 1] == "40"
    assert command[command.index("-a") + 1] == "90"
    assert command[-1] == "Hola mundo"


def test_empty_text_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        build_espeak_command("espeak-ng", "  ", Path("out.wav"), PRESETS[0])


def test_file_command_keeps_long_text_out_of_windows_command_line(tmp_path):
    input_file = tmp_path / "texto largo con espacios.txt"
    output_file = tmp_path / "salida.wav"
    command = build_espeak_file_command("espeak-ng", input_file, output_file, PRESETS[0])
    assert command[command.index("-f") + 1] == str(input_file)
    assert command[command.index("-w") + 1] == str(output_file)
    assert "Hola" not in command


@pytest.mark.parametrize(
    ("speed", "pitch", "volume"),
    [(79, 45, 100), (451, 45, 100), (145, -1, 100), (145, 100, 100), (145, 45, 201)],
)
def test_invalid_synthesis_settings_are_rejected(speed, pitch, volume):
    with pytest.raises(ValueError):
        build_espeak_file_command(
            "espeak-ng", Path("input.txt"), Path("out.wav"), PRESETS[0], speed, pitch, volume
        )


def test_pronunciation_rules_match_whole_words_and_phrases():
    result = apply_pronunciation_rules(
        "La IA ya llegó. Historia e inteligencia artificial.",
        {"ia": "i a", "inteligencia artificial": "inteligensia artificial"},
    )
    assert result == "La i a ya llegó. Historia e inteligensia artificial."


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_normalization_creates_valid_wav_at_safe_peak(tmp_path, width):
    scale = (1 << (width * 8 - 1)) - 1
    path = tmp_path / f"audio-{width}.wav"
    _write_pcm(path, [0, scale // 10, -(scale // 5)], width)

    assert normalize_wav(path)
    frame_count, duration = validate_wav(path)
    assert frame_count == 3
    assert duration == pytest.approx(3 / 24_000)
    assert _peak(path) == round(scale * 0.89)


def test_silence_is_not_amplified_or_rewritten(tmp_path):
    path = tmp_path / "silence.wav"
    _write_pcm(path, [0, 0, 0])
    original = path.read_bytes()

    assert normalize_wav(path) is False
    assert path.read_bytes() == original


def test_bad_wav_is_rejected(tmp_path):
    path = tmp_path / "broken.wav"
    path.write_bytes(b"not a wav")
    with pytest.raises(ValueError, match="WAV"):
        validate_wav(path)


def test_bundled_engine_is_found(tmp_path):
    engine_dir = tmp_path / "bin" / "espeak-ng"
    engine_dir.mkdir(parents=True)
    executable = engine_dir / "espeak-ng.exe"
    executable.write_bytes(b"")

    assert resolve_espeak(tmp_path) == str(executable)


def test_user_settings_live_in_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert app_data_dir() == tmp_path / "ClassicVoice"
