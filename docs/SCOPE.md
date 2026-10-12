# Product contract

## User story

As a Windows user, I can enter Spanish text, choose and tune a classic synthetic voice, hear a responsive local preview, adjust pronunciation, and export a clean WAV file.

## Acceptance criteria

1. Four neutral Spanish presets are available and their settings can be tuned.
2. Preview generation and export do not freeze the interface.
3. Playback can be stopped.
4. Export writes a readable WAV to a user-selected path and optionally normalizes its peak.
5. Per-user settings and pronunciation replacements survive upgrades and remain outside the installation folder.
6. Long text is passed to the local engine through a UTF-8 input file.
7. Normal runtime makes no network request and requires no account, API key, model download or administrator permission.
8. Missing eSpeak NG produces an actionable error instead of a crash.
9. Windows packaging includes the complete engine distribution, its license and corresponding source.
10. No proprietary Loquendo voice files or branding are bundled.

ClassicVoice remains a focused synthetic voice utility. Natural-voice models, cloud synthesis, timeline editing and batch dialogue export require a separate product decision.
