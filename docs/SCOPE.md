# Product contract

## User story

As a Windows user, I can enter text, select a supported language and tune a classic synthetic voice, hear a responsive local preview, adjust pronunciation, and export a clean WAV file.

## Acceptance criteria

1. The language selector lists the local engine's built-in voices, excluding external MBROLA backends. Four neutral voice styles are available with sliders and numeric controls.
2. Preview generation and export do not freeze the interface.
3. Playback can be stopped.
4. Export writes a readable WAV to a user-selected path and optionally normalizes its peak.
5. Per-user settings and pronunciation replacements per language survive upgrades and remain outside the installation folder. Existing Spanish replacements are migrated.
6. Long text is passed to the local engine through a UTF-8 input file.
7. Normal runtime makes no network request and requires no account, API key, model download or administrator permission.
8. Missing eSpeak NG produces an actionable error instead of a crash.
9. Windows packaging includes the complete engine distribution, its license and corresponding source.
10. No proprietary Loquendo voice files or branding are bundled.
11. The editor and tabbed voice/output controls fit the supported window sizes without page scrolling, clipping or overlaps.
12. TXT import supports UTF-8 and UTF-16 and can be undone; the source file is unchanged.

ClassicVoice supports classic eSpeak NG and an optional local Kokoro neural voice mode, plus chapter-based batch export and reusable voice profiles. Cloud synthesis, voice cloning, transcription, video dubbing and timeline editing are outside the current product scope.
