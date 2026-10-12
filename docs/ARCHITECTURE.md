# Architecture

~~~text
Tkinter UI
   ├── per-user settings and pronunciation replacements
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
- core.py: presets, engine discovery, command validation, pronunciation replacements, WAV validation and normalization.
- launcher.py: PyInstaller entry point.
- tools/build_windows.ps1: checksum-pinned engine retrieval, license/source packaging, verification and app build.
- tools/install_windows.ps1: per-user files, shortcuts and Add/Remove Programs entry.

Settings live in the current user's LocalAppData profile, not beside the executable. The packaged engine is read-only and each child process receives its own data-path environment; no machine-wide PATH or registry setting is changed by the engine setup.

Core behavior is testable without audio hardware. The Windows build includes the complete eSpeak NG distribution and third-party license materials.
