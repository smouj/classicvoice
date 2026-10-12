# Contributing

Thanks for helping improve ClassicVoice. Please keep contributions focused on the local text-to-speech workflow and read [AGENTS.md](AGENTS.md) before changing product behavior.

## Before opening a pull request

1. Use Python 3.11 or newer and install the test extra: `py -3.11 -m pip install -e ".[test]"`.
2. Run `py -3.11 -m pytest` and `py -3.11 -m compileall -q src tests`.
3. For changes to the Windows UI or package, run `.\tools\build_windows.ps1` on Windows. It verifies the desktop startup, bundled languages and WAV exports before packaging.
4. Describe the change, how you checked it, and the Windows/eSpeak NG versions used.

For UI changes, regenerate the actual desktop screenshots with `.\.venv\Scripts\python.exe tools/capture_screenshots.py` and review the full and compact layouts. The capture script keeps sample settings separate from user preferences. See the [architecture](docs/ARCHITECTURE.md) and [product scope](docs/SCOPE.md) for the supported workflow.

For a release, update the package version and [CHANGELOG.md](CHANGELOG.md) together. `tools/release_notes.py` uses the matching changelog entry to generate download instructions and documentation links. Follow [GITHUB.md](GITHUB.md) for tagging and publication.

Keep synthesis local, avoid unnecessary dependencies, and add tests for preset, command-building, and WAV behavior. Do not submit proprietary voice files or assets without redistribution rights. Preserve all third-party notices when changing the Windows distribution.
