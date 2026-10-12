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

ClassicVoice convierte texto en voz desde una aplicación de escritorio para Windows. Puedes usar **eSpeak NG**, rápido y ligero, o instalar opcionalmente **Kokoro**, un motor neuronal local con una entonación más natural. Elige el idioma, ajusta la voz, escucha una vista previa y guarda el WAV.

El motor clásico incluye **130 idiomas y variantes regionales**. Kokoro ofrece voces neuronales predefinidas en **9 idiomas**, incluido el español. El selector de idioma muestra solo los que admite el motor elegido. El texto se lee en ese idioma; la aplicación no lo traduce. Consulta el [catálogo de idiomas](docs/IDIOMAS.md).

**La síntesis se realiza localmente.** El motor clásico funciona sin modelos ni conexión. Kokoro es opcional: se descarga una vez desde la aplicación (unos 136 MiB) y luego también funciona sin conexión. No requiere cuentas ni claves API; la aplicación no envía el texto ni recopila telemetría.

En ordenadores antiguos, el motor natural puede tardar más que la duración del audio; la ventana sigue respondiendo y el motor clásico continúa disponible para generar con rapidez.

> ClassicVoice ofrece voces sintéticas clásicas. No incluye ni imita las voces propietarias de Loquendo.

## Capturas de la aplicación

Interfaz real de ClassicVoice en Windows, con texto en inglés y el estilo Narrador:

![Editor de ClassicVoice con texto de ejemplo y controles de voz](assets/screenshots/classicvoice-editor.png)

<details>
<summary>Ver más pantallas: ajustes, pronunciación, perfiles y audiolibros</summary>

**Pantalla inicial**

![Pantalla inicial de ClassicVoice](assets/screenshots/classicvoice-main.png)

**Ventana compacta, sin desplazamiento general**

![ClassicVoice en su tamaño mínimo de 860 por 620 píxeles](assets/screenshots/classicvoice-compact.png)

**Configuración de salida**

![Carpeta de salida, normalización y pronunciación](assets/screenshots/classicvoice-output.png)

**Reglas de pronunciación de ejemplo**

![Diccionario de pronunciación con dos reglas de ejemplo](assets/screenshots/classicvoice-pronunciation.png)

**Perfiles reutilizables**

![Perfiles que guardan el idioma, el estilo, los controles y las reglas](assets/screenshots/classicvoice-profiles.png)

**Cola por lotes y audiolibros por capítulos**

![Generación de capítulos y creación opcional de un WAV continuo](assets/screenshots/classicvoice-batch.png)

**Motor neuronal natural**

![Instalación local del modelo Kokoro para voces más naturales](assets/screenshots/classicvoice-natural-engine.png)

**Editor con una voz Kokoro seleccionada**

![Editor de ClassicVoice usando el motor natural en español](assets/screenshots/classicvoice-natural.png)

[Escuchar una muestra breve de voz natural en español](assets/samples/classicvoice-natural-es.wav) · Kokoro · voz Dora.

</details>

## Instalar en Windows

1. Descarga `ClassicVoice-<versión>-windows-x64.zip` desde [Releases](https://github.com/smouj/classicvoice/releases/latest).
2. Extrae el ZIP en una carpeta de tu elección.
3. Abre esa carpeta y haz doble clic en **Install-ClassicVoice.bat**.
4. ClassicVoice quedará disponible en el escritorio y en el menú Inicio. El instalador es por usuario y no necesita permisos de administrador.

El paquete contiene la aplicación, los runtimes de ambos motores y sus avisos de licencia. El modelo natural no se incluye: puedes descargarlo desde ClassicVoice cuando quieras, sin permisos de administrador. No necesitas instalar Python. También puedes ejecutar `ClassicVoice\ClassicVoice.exe` directamente desde la carpeta extraída para probar la versión portátil.

Consulta la [guía de instalación y actualización](docs/INSTALACION.md) si necesitas más detalle o ayuda para desinstalar.

## Uso rápido

1. Escribe o pega el texto en el editor.
2. En la pestaña **Voz**, elige el motor. **Clásico** da acceso a 130 idiomas y controles de tono y volumen. Para voces más naturales, abre **Motor: Natural**, descarga el modelo una vez y elige idioma y voz Kokoro.
3. Pulsa **Escuchar** para previsualizar la voz; **Detener** interrumpe el audio.
4. Pulsa **Guardar WAV** y elige el nombre y la ubicación del archivo.

En **Salida** puedes cambiar o abrir la carpeta de audio, normalizar el volumen y crear reglas de pronunciación por idioma. **Mis perfiles de voz** guarda el motor y sus ajustes. **Lote / libro** genera WAV por capítulo y, opcionalmente, un audiolibro continuo. Los ajustes se recuerdan; la cola no se conserva al cerrar la app. Usa **Ctrl + A** para seleccionar el texto y **Esc** para detener la voz. La interfaz se adapta sin desplazamiento general. La [guía de uso](docs/GUIA_DE_USO.md) explica cada control y resuelve problemas frecuentes.

## Qué incluye

- Selector clásico con 130 idiomas y variantes regionales.
- Kokoro ONNX opcional con voces neuronales predefinidas en español, inglés, francés, italiano, portugués brasileño, japonés, chino mandarín e hindi.
- Cuatro estilos clásicos con controles de velocidad, tono y volumen; controles de velocidad y voz neural para Kokoro.
- Editor adaptable, importación TXT y pestañas de voz y salida.
- Interfaz que sigue respondiendo mientras sintetiza, con controles de previsualización y detención.
- Exportación WAV validada y normalización de pico opcional.
- Reglas de pronunciación independientes por idioma y guardado de preferencias por usuario.
- Perfiles reutilizables de ajustes de voz con reglas de pronunciación por idioma.
- Lotes de TXT/Markdown a WAV, detección de capítulos y creación opcional de un audiolibro continuo.
- División acotada de textos largos; cancelar el lote limpia los archivos incompletos y conserva los archivos ya existentes.
- Descarga de modelos con SHA-256 fijado, cancelación segura y eliminación desde la app.
- Inferencia Kokoro limitada a dos hilos de CPU; el modelo se guarda en LocalAppData y no se inicia en segundo plano.
- Paquete de escritorio con los runtimes y eSpeak NG; el modelo opcional se descarga de forma independiente.

## Privacidad y licencias

ClassicVoice no envía el texto ni usa telemetría. El motor clásico no realiza solicitudes de red. Solo si eliges instalar Kokoro, la app descarga sus archivos desde GitHub y verifica ambos con SHA-256; la generación posterior permanece local. El código de ClassicVoice es MIT. Las licencias, avisos y fuentes de los componentes incluidos se detallan en [THIRD_PARTY.md](THIRD_PARTY.md).

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
py -3.11 -m pip install -e ".[test,natural]"
py -3.11 -m classicvoice
py -3.11 -m pytest
```

La compilación instala los runtimes opcionales de Kokoro y descarga el MSI oficial de eSpeak NG 1.52.0; comprueba su hash y extrae sus archivos sin instalar el motor para todo Windows. Los pesos del modelo Kokoro no se incluyen en la compilación.

## Proyecto

- [Cambios por versión](CHANGELOG.md) · [Alcance](docs/SCOPE.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Contribuir](CONTRIBUTING.md) · [Seguridad](SECURITY.md)
- Problemas y propuestas: [GitHub Issues](https://github.com/smouj/classicvoice/issues)
- Código: [smouj/classicvoice](https://github.com/smouj/classicvoice)

<p align="center">Creado por <a href="https://github.com/smouj">smouj</a> · ClassicVoice 0.4.0 · MIT</p>
