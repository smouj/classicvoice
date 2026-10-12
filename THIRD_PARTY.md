# Third-party software included with Windows builds

## ClassicVoice

The ClassicVoice source code is distributed under the MIT License in LICENSE.

## eSpeak NG

Windows builds contain the unmodified eSpeak NG 1.52.0 x64 executable, shared library and voice data. eSpeak NG is a separate open-source project distributed under GPL-3.0-or-later. Its license text is included as licenses/eSpeak-NG-COPYING.txt; the build places the corresponding upstream 1.52.0 source archive in the installed licenses directory.

The engine comes from the [official eSpeak NG 1.52.0 release](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0). The MSI is downloaded from the project's official GitHub release and checked against SHA-256 7F673C709EA5DD579D3B5EBB98688CC575328A6AB7438D2BC405B88CEDAEAFB9, as recorded in the [Microsoft WinGet manifest](https://github.com/microsoft/winget-pkgs/blob/master/manifests/e/eSpeak-NG/eSpeak-NG/1.52.0/eSpeak-NG.eSpeak-NG.installer.yaml). The MSI is not Authenticode-signed; the pinned checksum is checked before its files are extracted. The build does not run the MSI installer or modify machine-wide software settings.

No proprietary Loquendo voices, names or branding are bundled. Anyone redistributing a combined build must preserve these notices and comply with each component's license.
