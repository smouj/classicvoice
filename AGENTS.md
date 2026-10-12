# Agent instructions

## Product contract
ClassicVoice converts typed text to local classic-style speech and exports WAV. The Windows app is installed per user and keeps all settings and generated files in user-writable locations.

## Product boundaries
Keep synthesis local. Do not add cloud APIs, accounts, telemetry, timeline editing, project databases, Electron, Tauri or a web server without an explicit product decision. Keep natural-voice engines separate from the classic eSpeak NG presets.

## Legal boundary
Never bundle, imitate by name, or claim to provide proprietary Loquendo voices. Use neutral original preset names.

## Engineering rules
- Keep synthesis local.
- Keep preset/command logic pure and tested.
- Prefer fewer dependencies.
- Run `python -m pytest` before merging.
