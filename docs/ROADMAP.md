# Hoja de ruta

## v0.1 — Classic TTS utility

- [x] Text editor, four starter presets and independent voice controls
- [x] Local preview and WAV export
- [x] Offline-only operation

## v0.2 — Windows desktop polish

- [x] Remember the last preset, controls and output folder
- [x] Pronunciation replacements
- [x] Optional peak normalization before export
- [x] Responsive generation and stop controls
- [x] Per-user Windows package with eSpeak NG, license notices and shortcuts
- [x] Reproducible Windows ZIP, SHA-256 file and GitHub Actions release workflow
- [ ] Signed installer and automatic update flow

## v0.3 — Multilingual desktop

- [x] Discover the bundled languages and accents without external voice dependencies
- [x] Select the language independently from the voice style
- [x] Preserve pronunciation rules per language and migrate existing Spanish rules
- [x] Editor and tabbed settings without global scrolling
- [x] Numeric controls, voice reset, UTF-8/UTF-16 TXT import and output-folder access
- [x] Actual desktop screenshots and automated layout checks

## v0.4 — Natural speech and book workflows

- [x] Optional local Kokoro ONNX voices, separate from eSpeak presets
- [x] On-demand model download with pinned SHA-256 checks and local license notice
- [x] CPU-only inference with a two-thread limit and progress/cancel controls
- [x] Paragraph-aware chapter queue, individual WAVs, and optional merged audiobook
- [x] Reusable profiles for either engine and screenshots for the natural-voice flow
- [ ] Subtitle timing helpers
- [ ] Optional GPU acceleration after compatibility and stability checks

Voice cloning, transcription and video dubbing remain out of scope for this focused desktop release.

ClassicVoice remains a focused TTS utility, not a DAW.
