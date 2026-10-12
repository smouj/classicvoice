"""Create release notes from the versioned changelog and installation guides."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/smouj/classicvoice"


def release_notes(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("A stable MAJOR.MINOR.PATCH version is required.")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.MULTILINE | re.DOTALL)
    if entry is None or not entry.group(1).strip():
        raise ValueError(f"CHANGELOG.md has no release entry for {version}.")
    tag = f"v{version}"
    package = f"ClassicVoice-{version}-windows-x64.zip"
    download = f"{REPOSITORY}/releases/download/{tag}"
    source = f"{REPOSITORY}/blob/{tag}"
    return f"""ClassicVoice {version} para **Windows x64**: texto a voz multilingüe con procesamiento local, estilos sintéticos y exportación WAV.

No requiere Python, cuentas, claves API ni modelos de IA. El motor eSpeak NG está incluido.

## Cambios de esta versión

{entry.group(1).strip()}

## Descargar e instalar

1. Descarga **[{package}]({download}/{package})**.
2. Extrae el ZIP completo y abre la carpeta extraída.
3. Haz doble clic en **Install-ClassicVoice.bat**. No requiere permisos de administrador.
4. Abre ClassicVoice desde el escritorio o el menú Inicio.

Para actualizar, cierra la app antes de instalar. Tus ajustes, reglas de pronunciación y WAV exportados se conservan. También puedes ejecutar `ClassicVoice/ClassicVoice.exe` desde la carpeta extraída para usar la copia portátil.

## Verificar la descarga

El archivo **[{package.removesuffix('.zip')}.sha256]({download}/{package.removesuffix('.zip')}.sha256)** contiene el SHA-256 del ZIP. Compáralo con el resultado de:

```powershell
Get-FileHash .\\{package} -Algorithm SHA256
```

## Documentación

[Instalación y actualización]({source}/docs/INSTALACION.md) · [Guía de uso]({source}/docs/GUIA_DE_USO.md) · [Idiomas disponibles]({source}/docs/IDIOMAS.md) · [English README]({source}/README.en.md)

ClassicVoice: MIT. El paquete conserva la licencia GPL-3.0-or-later y el código fuente correspondiente de eSpeak NG; consulta [THIRD_PARTY.md]({source}/THIRD_PARTY.md).
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    options.output.write_text(release_notes(options.version), encoding="utf-8")
    print(f"Release notes written: {options.output}")


if __name__ == "__main__":
    main()
