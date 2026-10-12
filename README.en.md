<table align="center" bgcolor="#151722"><tr><td align="center">
  <img src="assets/logo.png" alt="ClassicVoice logo" width="220">
</td></tr></table>

<h1 align="center">ClassicVoice</h1>

<p align="center"><strong>Classic Spanish text to speech. Local, simple, and exported as WAV.</strong></p>

<p align="center">
  <a href="https://github.com/smouj/classicvoice/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/smouj/classicvoice?label=release"></a>
  <a href="https://github.com/smouj/classicvoice/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/smouj/classicvoice/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/smouj/classicvoice/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/smouj/classicvoice?style=social"></a>
  <a href="https://github.com/smouj/classicvoice/blob/main/LICENSE"><img alt="MIT license" src="https://img.shields.io/github/license/smouj/classicvoice"></a>
  <a href="https://github.com/smouj/classicvoice/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/smouj/classicvoice/total"></a>
</p>

<p align="center"><a href="README.md">Español</a> · <a href="https://github.com/smouj/classicvoice/releases/latest">Download for Windows</a></p>

ClassicVoice turns text into synthetic Spanish speech with **eSpeak NG**. Type, tune a voice, preview it, and save a WAV file from a focused Windows desktop app.

**Speech is processed locally.** No account, API key, internet connection, or AI model is required.

> ClassicVoice provides classic synthetic voices. It does not include or imitate proprietary Loquendo voices.

## App screenshots

The actual ClassicVoice desktop interface on Windows, with sample text and the Narrador preset:

![ClassicVoice editor with sample text and voice controls](assets/screenshots/classicvoice-editor.png)

<details>
<summary>View the initial screen and pronunciation dictionary</summary>

**Initial screen**

![ClassicVoice initial screen](assets/screenshots/classicvoice-main.png)

**Sample pronunciation rules**

![Pronunciation dictionary with two example rules](assets/screenshots/classicvoice-pronunciation.png)

</details>

## Install on Windows

1. Download `ClassicVoice-<version>-windows-x64.zip` from [Releases](https://github.com/smouj/classicvoice/releases/latest).
2. Extract the ZIP to a folder of your choice.
3. Open that folder and double-click **Install-ClassicVoice.bat**.
4. ClassicVoice appears on your desktop and in the Start menu. Installation is per-user and does not require administrator rights.

The package includes the application, the eSpeak NG speech engine, and its license notices. Python is not required. You can also run `ClassicVoice\ClassicVoice.exe` directly from the extracted folder as a portable copy.

See the [installation guide](docs/INSTALACION.md) for updates, uninstall steps, and troubleshooting.

## Quick start

1. Type or paste text into the editor.
2. Choose one of the four presets and tune speed, pitch, and volume.
3. Press **Escuchar** to preview. **Detener** stops playback.
4. Press **Guardar WAV** and choose a file name and location.

You can add pronunciation replacements and optionally normalize the audio peak before saving. Preferences are remembered. The [user guide](docs/GUIA_DE_USO.md) describes every control and common fixes.

## Features

- Four Spanish synthetic voice presets with independent speed, pitch, and volume controls.
- Responsive interface, background synthesis, preview, and stop control.
- Validated WAV export with optional peak normalization.
- Pronunciation replacement rules and per-user saved preferences.
- Windows desktop package with the eSpeak NG engine and voice data included.
- Standard-library application code; PyInstaller is only used to build the Windows package.

## Privacy and licensing

The installed application makes no network requests. eSpeak NG is fetched only at build time from its official release and verified against a pinned SHA-256 hash. ClassicVoice is MIT-licensed. eSpeak NG remains GPL-3.0-or-later; its notices and corresponding source are included in the package. See [THIRD_PARTY.md](THIRD_PARTY.md).

## Build from source

Requirements: Windows x64, Python 3.11, and PowerShell.

```powershell
.\tools\build_windows.ps1
.\tools\build_windows.ps1 -Install
```

For source development without building the executable:

```powershell
py -3.11 -m pip install -e ".[test]"
py -3.11 -m classicvoice
py -3.11 -m pytest
```

The first build downloads the official eSpeak NG 1.52.0 MSI, verifies its hash, and extracts its files without installing the engine system-wide.

## Project

- [Changelog](CHANGELOG.md) · [Scope](docs/SCOPE.md) · [Architecture](docs/ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
- Issues and feature requests: [GitHub Issues](https://github.com/smouj/classicvoice/issues)
- Source: [smouj/classicvoice](https://github.com/smouj/classicvoice)

<p align="center">Made with care by <a href="https://github.com/smouj">smouj</a> · ClassicVoice 0.2.2 · MIT</p>
