# Agent instructions

## Product contract
ClassicVoice converts typed text to local classic-style speech and exports WAV.

## v0.1 freeze
Do not add cloud APIs, model downloads, accounts, telemetry, timeline editing, project databases, Kokoro, Piper, Electron, Tauri or a web server during v0.1.

## Legal boundary
Never bundle, imitate by name, or claim to provide proprietary Loquendo voices. Use neutral original preset names.

## Engineering rules
- Keep synthesis local.
- Keep preset/command logic pure and tested.
- Prefer fewer dependencies.
- Run `python -m pytest` before merging.
