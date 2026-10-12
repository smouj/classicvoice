# Architecture

~~~text
Tkinter UI
   ├── language catalog and per-language pronunciation replacements
   ├── reusable voice profiles and TXT/Markdown chapter queue
   ├── two-column editor and tabbed voice/output settings
   ├── single-job and batch synthesis worker threads + cancellation
   └── event queue back to the UI
          ├── classic: eSpeak NG + voice data
          └── natural: Kokoro ONNX + verified local model + eSpeak phonemizer
                  ↓
             temporary PCM WAV per chapter
          ├── winsound preview / stop
          ├── optional peak normalization → atomic single WAV export
          └── bounded-memory WAV concatenation → optional audiobook file
~~~

- app.py: desktop UI, saved preferences/profiles, batch workflow, background synthesis lifecycle and playback.
- core.py: voice styles, native language discovery (excluding MBROLA), engine discovery, command validation, pronunciation replacements, WAV validation and normalization.
- workflows.py: bounded TXT/Markdown loading, chapter detection/splitting, reusable profile sanitation, cancellable engine execution, and streaming PCM WAV concatenation.
- natural_engine.py: on-demand Kokoro model download with size/SHA-256 verification, local license placement, safe model removal, paragraph-aware synthesis, and a two-thread CPU-only ONNX session.
- launcher.py: PyInstaller entry point.
- tools/build_windows.ps1: checksum-pinned engine retrieval, license/source packaging, verification and app build.
- tools/install_windows.ps1: per-user files, shortcuts and Add/Remove Programs entry.

Settings live in the current user's LocalAppData profile, not beside the executable. The packaged engine is read-only and each child process receives its own data-path environment; no machine-wide PATH or registry setting is changed by the engine setup.

Core behavior is testable without audio hardware. The Windows build includes the complete eSpeak NG distribution and third-party license materials.

Settings schema 5 stores the selected engine, natural voice, language code, separate pronunciation dictionaries, and up to 24 named voice-setting profiles. Existing settings continue to load without discarding pronunciation rules. The classic engine is selected on a fresh installation unless a Kokoro model already exists. A synthesis job captures its engine, voice, language and processed text before starting, so later UI changes apply to the next job. Batch work is not persisted across app restarts; chapters are staged in the destination folder and only published when the render succeeds.

The classic synthesis command uses the native voice file identifier plus the style variant, avoiding language-priority resolution to an external MBROLA voice. Text files are explicitly interpreted as UTF-8. `tools/smoke_languages.py` validates WAV output for every advertised native voice and all four styles for representative languages. Kokoro is optional and local after its one-time verified model download; the Windows package includes its runtime but not the model weights. Neural inference is capped at two CPU threads and can take longer than the resulting audio on older computers.
