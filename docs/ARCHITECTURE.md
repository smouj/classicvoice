# Architecture

```text
Tkinter UI
   ↓
Preset + user controls
   ↓
eSpeak command builder
   ↓
eSpeak NG → WAV
   ↓
winsound preview / file export
```

- `app.py`: desktop UI and synthesis process lifecycle.
- `core.py`: presets, validation, executable discovery and command construction.

Core behavior is independently testable without audio hardware or eSpeak NG.
