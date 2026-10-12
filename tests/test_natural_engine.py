import hashlib
from io import BytesIO
from pathlib import Path
import re
import threading

import pytest

import classicvoice.natural_engine as natural


def test_kokoro_language_catalog_has_spanish_and_never_guesses_unavailable_languages():
    assert natural.canonical_language("es") == "es"
    assert natural.canonical_language("pt") == "pt-br"
    assert natural.canonical_language("de") is None
    assert [voice for voice, _label in natural.voices_for_language("es")] == ["ef_dora", "em_alex", "em_santa"]
    assert natural.voices_for_language("fr-ca") == ()


def test_kokoro_text_chunks_keep_all_words_and_split_at_sentence_boundaries():
    text = "Primera frase. " + ("palabra " * 240) + " Fin.\n\nOtro párrafo completo."
    chunks = natural._text_chunks(text, limit=180)

    assert len(chunks) > 2
    assert all(len(chunk) <= 180 for chunk in chunks)
    assert re.sub(r"\s+", " ", " ".join(chunks)) == re.sub(r"\s+", " ", text)


def test_kokoro_text_chunks_keep_paragraph_boundaries_for_breathing_pauses():
    assert natural._text_chunks("Primera idea.\n\nSegunda idea.") == (
        "Primera idea.",
        "Segunda idea.",
    )


class _FakeResponse(BytesIO):
    def __init__(self, body: bytes):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_model_download_verifies_both_files_before_publishing(tmp_path: Path, monkeypatch):
    model_data = b"onnx weights"
    voices_data = b"voice pack"
    downloads = {
        "https://example.test/model": model_data,
        "https://example.test/voices": voices_data,
    }

    monkeypatch.setattr(natural, "KOKORO_MODEL_BYTES", len(model_data))
    monkeypatch.setattr(natural, "KOKORO_VOICES_BYTES", len(voices_data))
    monkeypatch.setattr(natural, "KOKORO_MODEL_URL", "https://example.test/model")
    monkeypatch.setattr(natural, "KOKORO_VOICES_URL", "https://example.test/voices")
    monkeypatch.setattr(natural, "KOKORO_MODEL_SHA256", hashlib.sha256(model_data).hexdigest())
    monkeypatch.setattr(natural, "KOKORO_VOICES_SHA256", hashlib.sha256(voices_data).hexdigest())
    monkeypatch.setattr(natural.urllib.request, "urlopen", lambda request, timeout: _FakeResponse(downloads[request.full_url]))
    destination = tmp_path / "model"
    progress = []

    result = natural.install_kokoro_model(destination, on_progress=lambda *entry: progress.append(entry))

    assert result == destination
    model_path, voices_path = natural.model_paths(destination)
    assert model_path.read_bytes() == model_data
    assert voices_path.read_bytes() == voices_data
    assert (destination / natural.KOKORO_LICENSE_NAME).is_file()
    assert natural.model_is_installed(destination)
    assert {entry[0] for entry in progress} == {"modelo", "voces"}
    assert not list(tmp_path.glob(".model.install-*"))


def test_existing_verified_model_gets_its_license_without_another_download(tmp_path: Path, monkeypatch):
    model_data = b"valid model"
    voices_data = b"valid voice pack"
    monkeypatch.setattr(natural, "KOKORO_MODEL_BYTES", len(model_data))
    monkeypatch.setattr(natural, "KOKORO_VOICES_BYTES", len(voices_data))
    monkeypatch.setattr(natural, "KOKORO_MODEL_SHA256", hashlib.sha256(model_data).hexdigest())
    monkeypatch.setattr(natural, "KOKORO_VOICES_SHA256", hashlib.sha256(voices_data).hexdigest())
    monkeypatch.setattr(natural.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("unexpected model download"))
    destination = tmp_path / "model"
    destination.mkdir()
    model_path, voices_path = natural.model_paths(destination)
    model_path.write_bytes(model_data)
    voices_path.write_bytes(voices_data)

    assert natural.install_kokoro_model(destination) == destination
    assert natural.model_is_installed(destination)


def test_remove_kokoro_keeps_unexpected_files_in_the_model_directory(tmp_path: Path):
    destination = tmp_path / "model"
    destination.mkdir()
    model_path, voices_path = natural.model_paths(destination)
    model_path.write_bytes(b"model")
    voices_path.write_bytes(b"voices")
    (destination / natural.KOKORO_LICENSE_NAME).write_text("license", encoding="utf-8")
    notes = destination / "user-notes.txt"
    notes.write_text("keep this", encoding="utf-8")

    natural.remove_kokoro_model(destination)

    assert not model_path.exists()
    assert not voices_path.exists()
    assert not (destination / natural.KOKORO_LICENSE_NAME).exists()
    assert notes.read_text(encoding="utf-8") == "keep this"


def test_invalid_model_download_keeps_previous_install_intact(tmp_path: Path, monkeypatch):
    model_data = b"valid model"
    voices_data = b"bad voice data"
    monkeypatch.setattr(natural, "KOKORO_MODEL_BYTES", len(model_data))
    monkeypatch.setattr(natural, "KOKORO_VOICES_BYTES", len(voices_data))
    monkeypatch.setattr(natural, "KOKORO_MODEL_URL", "https://example.test/model")
    monkeypatch.setattr(natural, "KOKORO_VOICES_URL", "https://example.test/voices")
    monkeypatch.setattr(natural, "KOKORO_MODEL_SHA256", hashlib.sha256(model_data).hexdigest())
    monkeypatch.setattr(natural, "KOKORO_VOICES_SHA256", "0" * 64)
    monkeypatch.setattr(
        natural.urllib.request,
        "urlopen",
        lambda request, timeout: _FakeResponse(model_data if request.full_url.endswith("model") else voices_data),
    )
    destination = tmp_path / "model"
    destination.mkdir()
    (destination / "previous.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        natural.install_kokoro_model(destination)

    assert (destination / "previous.txt").read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".model.install-*"))


def test_model_download_can_be_cancelled_without_publishing_partial_files(tmp_path: Path, monkeypatch):
    body = b"123456789"
    monkeypatch.setattr(natural, "KOKORO_MODEL_BYTES", len(body))
    monkeypatch.setattr(natural, "KOKORO_VOICES_BYTES", len(body))
    monkeypatch.setattr(natural, "KOKORO_MODEL_URL", "https://example.test/model")
    monkeypatch.setattr(natural, "KOKORO_VOICES_URL", "https://example.test/voices")
    monkeypatch.setattr(natural, "KOKORO_MODEL_SHA256", hashlib.sha256(body).hexdigest())
    monkeypatch.setattr(natural, "KOKORO_VOICES_SHA256", hashlib.sha256(body).hexdigest())
    monkeypatch.setattr(natural, "_DOWNLOAD_BLOCK", 2)
    monkeypatch.setattr(natural.urllib.request, "urlopen", lambda request, timeout: _FakeResponse(body))
    cancel = threading.Event()
    destination = tmp_path / "model"

    with pytest.raises(natural.SynthesisCancelled):
        natural.install_kokoro_model(destination, cancel, lambda *_entry: cancel.set())

    assert not destination.exists()
    assert not list(tmp_path.glob(".model.install-*"))
