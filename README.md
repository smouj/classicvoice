<p align="center">
  <img src="assets/logo-readme.svg" alt="Logotipo de ClassicVoice" width="220">
</p>

<h1 align="center">ClassicVoice</h1>

<p align="center"><strong>Texto a voz en varios idiomas. Local, sencillo y en WAV.</strong></p>

<p align="center">
  <a href="https://github.com/smouj/classicvoice/releases/latest"><img alt="Última versión" src="https://img.shields.io/github/v/release/smouj/classicvoice?label=versi%C3%B3n"></a>
  <a href="https://github.com/smouj/classicvoice/actions/workflows/ci.yml"><img alt="Estado de CI" src="https://github.com/smouj/classicvoice/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/smouj/classicvoice/stargazers"><img alt="Estrellas en GitHub" src="https://img.shields.io/github/stars/smouj/classicvoice?style=social"></a>
  <a href="https://github.com/smouj/classicvoice/blob/main/LICENSE"><img alt="Licencia MIT" src="https://img.shields.io/github/license/smouj/classicvoice"></a>
  <a href="https://github.com/smouj/classicvoice/releases"><img alt="Descargas" src="https://img.shields.io/github/downloads/smouj/classicvoice/total"></a>
</p>

<p align="center"><a href="README.en.md">English</a> · <a href="https://github.com/smouj/classicvoice/releases/latest">Descargar para Windows</a></p>

ClassicVoice convierte texto en voz sintética usando **eSpeak NG**. Elige el idioma del texto, ajusta una voz, escucha una vista previa y guarda el resultado como WAV desde una aplicación de escritorio para Windows.

La distribución actual incluye **130 idiomas y variantes regionales**. El selector muestra las voces locales disponibles, incluyendo español, inglés, francés, alemán, portugués, árabe, chino, japonés y muchos más. Consulta el [catálogo de idiomas](docs/IDIOMAS.md). El texto se lee en el idioma seleccionado; la aplicación no traduce el contenido.

**Todo el procesamiento de voz se realiza localmente.** La aplicación no requiere cuenta, clave API, conexión a Internet ni modelos de IA.

> ClassicVoice ofrece voces sintéticas clásicas. No incluye ni imita las voces propietarias de Loquendo.

## Capturas de la aplicación

Interfaz real de ClassicVoice en Windows, con texto en inglés y el estilo Narrador:

![Editor de ClassicVoice con texto de ejemplo y controles de voz](assets/screenshots/classicvoice-editor.png)

<details>
<summary>Ver la pantalla inicial y el diccionario de pronunciación</summary>

**Pantalla inicial**

![Pantalla inicial de ClassicVoice](assets/screenshots/classicvoice-main.png)

**Ventana compacta, sin desplazamiento general**

![ClassicVoice en su tamaño mínimo de 860 por 620 píxeles](assets/screenshots/classicvoice-compact.png)

**Configuración de salida**

![Carpeta de salida, normalización y pronunciación](assets/screenshots/classicvoice-output.png)

**Reglas de pronunciación de ejemplo**

![Diccionario de pronunciación con dos reglas de ejemplo](assets/screenshots/classicvoice-pronunciation.png)

</details>

## Instalar en Windows

1. Descarga `ClassicVoice-<versión>-windows-x64.zip` desde [Releases](https://github.com/smouj/classicvoice/releases/latest).
2. Extrae el ZIP en una carpeta de tu elección.
3. Abre esa carpeta y haz doble clic en **Install-ClassicVoice.bat**.
4. ClassicVoice quedará disponible en el escritorio y en el menú Inicio. El instalador es por usuario y no necesita permisos de administrador.

El paquete contiene la aplicación, el motor de voz eSpeak NG y sus avisos de licencia. No necesitas instalar Python. También puedes ejecutar `ClassicVoice\ClassicVoice.exe` directamente desde la carpeta extraída para probar la versión portátil.

Consulta la [guía de instalación y actualización](docs/INSTALACION.md) si necesitas más detalle o ayuda para desinstalar.

## Uso rápido

1. Escribe o pega el texto en el editor.
2. En la pestaña **Voz**, elige el idioma del texto y uno de los cuatro estilos. Ajusta velocidad, tono y volumen con los deslizadores o sus campos numéricos.
3. Pulsa **Escuchar** para previsualizar la voz; **Detener** interrumpe el audio.
4. Pulsa **Guardar WAV** y elige el nombre y la ubicación del archivo.

En **Salida** puedes cambiar o abrir la carpeta de audio, normalizar el volumen y crear reglas de pronunciación por idioma. **Importar TXT** abre archivos UTF-8 o UTF-16. Los ajustes se recuerdan para la próxima vez. Usa **Ctrl + A** para seleccionar todo el texto y **Esc** para detener la voz. El editor y el panel de ajustes se adaptan a la ventana, sin desplazamiento general; solo el texto largo y la lista de pronunciación utilizan sus propias barras. La [guía de uso](docs/GUIA_DE_USO.md) explica cada control y resuelve problemas frecuentes.

## Qué incluye

- Selector de idiomas y variantes regionales incluidos en el motor local.
- Cuatro estilos sintéticos y controles independientes de velocidad, tono y volumen, con entrada numérica y restablecimiento de voz.
- Editor adaptable, importación TXT y pestañas de voz y salida.
- Interfaz que sigue respondiendo mientras sintetiza, con controles de previsualización y detención.
- Exportación WAV validada y normalización de pico opcional.
- Reglas de pronunciación independientes por idioma y guardado de preferencias por usuario.
- Paquete de escritorio con eSpeak NG y datos de voz incluidos.
- Código de la aplicación basado en la biblioteca estándar de Python; PyInstaller solo se utiliza para crear el paquete de Windows.

## Privacidad y licencias

La aplicación instalada no realiza solicitudes de red. La descarga de eSpeak NG solo ocurre durante la compilación del paquete, desde su publicación oficial y con una comprobación SHA-256 fijada. ClassicVoice usa licencia MIT; eSpeak NG conserva su licencia GPL-3.0-or-later y sus avisos y código fuente se incluyen en el paquete. Consulta [THIRD_PARTY.md](THIRD_PARTY.md).

## Compilar desde el código

Requisitos para crear la versión de escritorio: Windows x64, Python 3.11 y PowerShell.

```powershell
.\tools\build_windows.ps1
```

Para compilar, instalar en el perfil actual y verificar la exportación WAV:

```powershell
.\tools\build_windows.ps1 -Install
```

Para desarrollar la aplicación sin crear el ejecutable:

```powershell
py -3.11 -m pip install -e ".[test]"
py -3.11 -m classicvoice
py -3.11 -m pytest
```

La primera compilación descarga el MSI oficial de eSpeak NG 1.52.0, comprueba su hash y extrae los archivos sin instalar el motor para todo Windows.

## Proyecto

- [Cambios por versión](CHANGELOG.md) · [Alcance](docs/SCOPE.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Contribuir](CONTRIBUTING.md) · [Seguridad](SECURITY.md)
- Problemas y propuestas: [GitHub Issues](https://github.com/smouj/classicvoice/issues)
- Código: [smouj/classicvoice](https://github.com/smouj/classicvoice)

<p align="center">Creado por <a href="https://github.com/smouj">smouj</a> · ClassicVoice 0.3.1 · MIT</p>
