# Instalación de ClassicVoice

## Requisitos

- Windows 10 u 11 de 64 bits.
- No necesitas instalar Python, eSpeak NG ni permisos de administrador.
- Para descargar una versión desde GitHub necesitas conexión a Internet. Una vez instalada, la síntesis funciona sin conexión.

## Instalar

1. Abre [Releases](https://github.com/smouj/classicvoice/releases/latest) y descarga `ClassicVoice-<versión>-windows-x64.zip`.
2. En el Explorador, haz clic derecho en el ZIP y selecciona **Extraer todo…**.
3. En la carpeta extraída, haz doble clic en `Install-ClassicVoice.bat`.
4. La aplicación se instala en `%LOCALAPPDATA%\Programs\ClassicVoice` y crea accesos directos en el escritorio y en Inicio.

No se instala nada para otros usuarios del PC y no se cambia la configuración global de Windows. El paquete ofrece también `ClassicVoice\ClassicVoice.exe` para probarlo de forma portátil sin instalarlo.

## Verificar la descarga

Cada Release incluye un archivo `.sha256`. Para verificarlo con PowerShell, abre PowerShell en la carpeta donde descargaste el ZIP y ejecuta:

```powershell
Get-FileHash .\ClassicVoice-0.2.0-windows-x64.zip -Algorithm SHA256
```

Compara el campo `Hash` con la línea del archivo `.sha256` que corresponde a ese ZIP. Usa únicamente los archivos publicados en [Releases](https://github.com/smouj/classicvoice/releases).

El paquete no está firmado digitalmente. Descárgalo solo desde el repositorio oficial y no ignores una advertencia de seguridad inesperada.

## Actualizar

Descarga y extrae la versión nueva y vuelve a ejecutar `Install-ClassicVoice.bat`. Cierra ClassicVoice antes de actualizar. La instalación sustituye los archivos de la aplicación y conserva tus preferencias, reglas de pronunciación y WAV exportados.

## Desinstalar

- Desde **Configuración de Windows → Aplicaciones → Aplicaciones instaladas**, busca ClassicVoice y selecciona **Desinstalar**; o
- Ejecuta `uninstall_windows.ps1` dentro de `%LOCALAPPDATA%\Programs\ClassicVoice`.

El desinstalador confirma la operación antes de quitar la aplicación y sus accesos directos. Conserva tus ajustes y archivos WAV.

## Solución de problemas

### No aparece el instalador

Comprueba que extraíste el ZIP completo; no ejecutes el instalador desde la vista previa del archivo comprimido.

### ClassicVoice no se abre o indica que falta el motor

Instala desde el ZIP oficial de una Release y comprueba que el antivirus no haya puesto en cuarentena archivos del paquete. El motor eSpeak NG debe estar dentro de la carpeta de la aplicación.

### El audio no se oye

Comprueba el dispositivo de salida de Windows y el volumen de la aplicación. Usa **Escuchar** para previsualizar y **Detener** para interrumpir la reproducción.

### Una palabra se pronuncia mal

Abre **Pronunciación**, añade el término y su forma hablada, y genera otra vista previa. Las reglas se guardan en tu perfil de usuario.

### No puedes actualizar

Cierra ClassicVoice y vuelve a iniciar `Install-ClassicVoice.bat`. Si sigue fallando, abre un issue con la versión de Windows y el mensaje de error; no adjuntes datos privados ni texto sensible.
