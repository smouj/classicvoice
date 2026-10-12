# Configuración del repositorio en GitHub

- Repositorio: `smouj/classicvoice` (público; rama principal `main`).
- Descripción: `Offline multilingual text-to-speech for Windows. Classic eSpeak NG voices, language-specific pronunciation, and WAV export.`
- Temas: `text-to-speech`, `tts`, `espeak-ng`, `multilingual`, `windows`, `offline`, `local-first`, `open-source`, `desktop-app`, `python`.
- Issues habilitados; mantener la guía y la arquitectura versionadas en `docs/`.
- Publicar versiones con tags SemVer `vMAJOR.MINOR.PATCH`. Un tag `vX.Y.Z` ejecuta el flujo de compilación de Windows, genera el ZIP y el SHA-256 y crea un GitHub Release.
- Cada paquete distribuido debe conservar los avisos de eSpeak NG y su código fuente correspondiente.
- La vista social debe usar una imagen fiel a las funciones locales de ClassicVoice; no anunciar voces naturales ni IA.

## Publicar una versión

1. Actualiza la versión en `pyproject.toml` y `src/classicvoice/__init__.py`.
2. Actualiza `CHANGELOG.md` y ejecuta `python -m pytest`.
3. Integra los cambios en `main` y crea un tag anotado, por ejemplo `git tag -a v0.2.0 -m "ClassicVoice 0.2.0"`.
4. Publica `main` y el tag. `.github/workflows/release.yml` compila el paquete, adjunta el ZIP y el SHA-256, y genera las notas de GitHub Release.
5. Revisa la página de Releases, los archivos y el estado de CI antes de anunciar la descarga.

`PUBLISH_GITHUB.ps1` sincroniza `main`, tags y los temas/descripción del repositorio si GitHub CLI está instalado y autenticado. No crea issues.
