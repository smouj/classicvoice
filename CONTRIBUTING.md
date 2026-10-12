# Contributing

Thanks for helping improve ClassicVoice. Please keep contributions focused on the local text-to-speech workflow and read `AGENTS.md` before changing product behavior.

## Before opening a pull request

1. Use Python 3.11 or newer and install the test extra: `py -3.11 -m pip install -e ".[test]"`.
2. Run `py -3.11 -m pytest` and `py -3.11 -m compileall -q src tests`.
3. For changes to the Windows UI or package, run `tools/smoke_ui.py` and `tools/build_windows.ps1` on Windows.
4. Describe the change, how you checked it, and the Windows/eSpeak NG versions used.

Keep synthesis local, avoid unnecessary dependencies, and add tests for preset, command-building, and WAV behavior. Do not submit proprietary voice files or assets without redistribution rights. Preserve all third-party notices when changing the Windows distribution.
