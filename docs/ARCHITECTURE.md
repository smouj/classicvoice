# Architecture

~~~text
Tkinter UI
   ├── language catalog and per-language pronunciation replacements
   ├── two-column editor and tabbed voice/output settings
   ├── synthesis worker thread + cancellation
   └── event queue back to the UI
          ↓
UTF-8 temporary text file
          ↓
Bundled eSpeak NG + voice data → validated PCM WAV
          ├── winsound preview / stop
          └── optional peak normalization → atomic WAV export
~~~

- app.py: desktop UI, saved preferences, background synthesis lifecycle and playback.
- core.py: voice styles, native language discovery (excluding MBROLA), engine discovery, command validation, pronunciation replacements, WAV validation and normalization.
- launcher.py: PyInstaller entry point.
- tools/build_windows.ps1: checksum-pinned engine retrieval, license/source packaging, verification and app build.
- tools/install_windows.ps1: per-user files, shortcuts and Add/Remove Programs entry.

Settings live in the current user's LocalAppData profile, not beside the executable. The packaged engine is read-only and each child process receives its own data-path environment; no machine-wide PATH or registry setting is changed by the engine setup.

Core behavior is testable without audio hardware. The Windows build includes the complete eSpeak NG distribution and third-party license materials.

Settings schema 3 stores the selected language code and separate pronunciation dictionaries by language. Existing schema 2 Spanish rules are migrated on load. Changing the language preserves the current voice parameters. A synthesis job captures its language and processed text before starting, so later UI changes apply to the next job.

The synthesis command uses the native voice file identifier plus the style variant, avoiding language-priority resolution to an external MBROLA voice. Text files are explicitly interpreted as UTF-8. `tools/smoke_languages.py` validates WAV output for every advertised native voice and all four styles for representative languages.
