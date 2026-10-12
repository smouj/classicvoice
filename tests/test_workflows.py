from pathlib import Path
import wave

import pytest

from classicvoice.workflows import (
    markdown_to_speech,
    merge_wav_files,
    normalize_voice_profiles,
    read_text_document,
    safe_audio_stem,
    split_book_text,
)


def _write_wav(path: Path, samples: bytes, rate: int = 8_000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)


def test_split_book_detects_chapters_and_bounds_long_parts():
    chapters = split_book_text("Introducción.\n\nCapítulo 1: Inicio\n" + "uno " * 16 + "\n\nCapitulo 2\nfin", "Mi libro", limit=20)

    assert chapters[0].title == "Mi libro"
    assert chapters[1].title.startswith("Capítulo 1: Inicio")
    assert all(chapter.text and len(chapter.text) <= 20 for chapter in chapters)


def test_split_book_falls_back_to_text_chunks_and_empty_is_empty():
    chapters = split_book_text("párrafo uno\n\npárrafo dos con bastante contenido", "Libro", limit=17)

    assert len(chapters) > 1
    assert all(len(chapter.text) <= 17 for chapter in chapters)
    assert split_book_text(" \n ", "Libro") == ()


def test_markdown_is_simplified_for_speech():
    text = markdown_to_speech("# Título\n\n**Hola** [mundo](https://example.com)\n\n- otro")

    assert "Título" in text and "Hola mundo" in text and "otro" in text
    assert "https://" not in text and "**" not in text


@pytest.mark.parametrize(
    ("suffix", "raw", "expected"),
    [
        (".txt", "hola".encode("utf-8"), "hola"),
        (".txt", "hola".encode("utf-16"), "hola"),
        (".md", b"# hola", "hola"),
    ],
)
def test_read_bounded_text_formats(tmp_path: Path, suffix: str, raw: bytes, expected: str):
    source = tmp_path / f"book{suffix}"
    source.write_bytes(raw)
    assert read_text_document(source) == expected


def test_read_text_rejects_invalid_encoding_and_unsafe_size(tmp_path: Path, monkeypatch):
    import classicvoice.workflows as workflows

    source = tmp_path / "bad.txt"
    source.write_bytes(b"\xff\xff\xff")
    with pytest.raises(UnicodeError):
        read_text_document(source)
    monkeypatch.setattr(workflows, "MAX_BOOK_BYTES", 2)
    source.write_bytes(b"long")
    with pytest.raises(ValueError, match="supera el límite"):
        read_text_document(source)


def test_safe_audio_stem_removes_windows_reserved_characters():
    assert safe_audio_stem(' Capítulo: "Uno"/Parte? ') == "Capítulo Uno Parte"
    assert safe_audio_stem("... ") == "audio"


def test_merge_wav_files_adds_silence_and_streams_compatible_pcm(tmp_path: Path):
    first = tmp_path / "one.wav"
    second = tmp_path / "two.wav"
    merged = tmp_path / "book.wav"
    _write_wav(first, b"\x01\x00" * 4)
    _write_wav(second, b"\x02\x00" * 4)

    frames, seconds = merge_wav_files([first, second], merged, silence_ms=100)

    with wave.open(str(merged), "rb") as audio:
        result = audio.readframes(audio.getnframes())
        assert audio.getnframes() == frames
        assert result[:8] == b"\x01\x00" * 4
        assert result[8:808] == b"\x00\x00" * 400
        assert result[-8:] == b"\x02\x00" * 4
    assert frames == 808 and seconds == pytest.approx(0.101)


def test_merge_wav_files_rejects_mismatched_formats(tmp_path: Path):
    first = tmp_path / "one.wav"
    second = tmp_path / "two.wav"
    _write_wav(first, b"\x01\x00" * 4)
    _write_wav(second, b"\x02\x00" * 4, rate=16_000)

    with pytest.raises(ValueError, match="no coincide"):
        merge_wav_files([first, second], tmp_path / "book.wav")


def test_merge_wav_files_needs_at_least_one_input(tmp_path: Path):
    with pytest.raises(ValueError, match="No hay capítulos"):
        merge_wav_files([], tmp_path / "book.wav")


def test_voice_profiles_are_bounded_and_malformed_settings_are_sanitized():
    profiles = normalize_voice_profiles({
        "Narración": {"preset_key": "narrator", "speed": 999, "pitch": -2, "volume": "abc", "normalize": False,
                      "pronunciation_rules": {" API ": " a-pe-i ", "": "ignorar"}},
        "": {"speed": 200},
        "no válida": "broken",
    })

    assert profiles["Narración"] == {
        "tts_engine": "espeak", "natural_voice": "ef_dora",
        "language_code": "es", "preset_key": "narrator", "speed": 450, "pitch": 0, "volume": 105,
        "normalize": False, "pronunciation_rules": {"API": "a-pe-i"},
    }
    assert len(normalize_voice_profiles([1, 2])) == 0
