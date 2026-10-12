# Historial de cambios

Los cambios notables de ClassicVoice se documentan aquí. Las versiones siguen [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-10-12

- Motor neuronal Kokoro ONNX opcional y local, con voces predefinidas en nueve idiomas y descarga bajo demanda verificada por SHA-256.
- La selección del motor y la voz natural se guardan en los ajustes y perfiles; la instalación usa Kokoro por defecto solo si ya hay un modelo local.
- Corrección de pausas entre párrafos y fragmentos largos para evitar uniones abruptas en el audio neuronal.
- Síntesis neuronal CPU limitada a dos hilos, con controles de descarga/cancelación y retirada segura de los archivos del modelo.
- Flujo por lotes para libros: importación TXT/Markdown, detección de capítulos, WAV por capítulo y combinación opcional.
- Avisos de licencias y código fuente de las dependencias GPL incluidos en el paquete; documentación y capturas del motor natural.

## [0.3.1] - 2026-10-12

- Logo del README visible en temas claros y oscuros, conservando el diseño original.
- Descripción multilingüe de los accesos directos de Windows.
- Ejemplos de instalación, formulario de errores, catálogo y capturas sincronizados con la versión publicada.
- Notas de release generadas desde el changelog, con instrucciones de descarga, instalación y verificación.

## [0.3.0] - 2026-10-12

- Selector de los 130 idiomas y variantes regionales incluidos en el motor local; las voces externas MBROLA quedan excluidas.
- Editor y ajustes en dos columnas, con pestañas de voz y salida y sin desplazamiento general.
- Entrada numérica de velocidad, tono y volumen; velocidad de 80 a 450 palabras por minuto y botón para restablecer la voz.
- Importación TXT UTF-8/UTF-16, apertura de la carpeta de salida e indicador de síntesis.
- Reglas de pronunciación por idioma, con migración de las reglas existentes a español.
- Capturas renovadas y documentación multilingüe; pie de README simplificado a «Creado por smouj».

## [0.2.2] - 2026-10-12

- Indicadores de velocidad, tono y volumen con mayor contraste y valores enteros.
- Ruta de salida abreviada con `~` cuando está dentro del perfil del usuario.
- Tres capturas reales de la interfaz en los README en español e inglés.
- Herramientas para regenerar las capturas sin modificar las preferencias del usuario.

## [0.2.1] - 2026-10-12

- Distribución adaptable con desplazamiento vertical y controles accesibles al reducir la ventana.
- Carpeta de salida, normalización y pronunciación distribuidas en filas independientes.
- Estado y descripciones con ajuste de línea; diálogo de pronunciación con barra de desplazamiento.
- Corrección de la vista previa: el WAV se conserva hasta finalizar o detener la reproducción.
- Atajos Ctrl + A y Esc, guardado bloqueado durante la síntesis y eliminación del placeholder del historial de deshacer.
- Comprobaciones de geometría y ausencia de solapamientos en tres tamaños de ventana.

## [0.2.0] - 2026-10-12

- Aplicación de escritorio para Windows con instalación por usuario, accesos directos y desinstalador.
- Motor eSpeak NG y voces en español incluidos en el paquete, con licencias y código fuente correspondiente.
- Ajustes persistentes, reglas de pronunciación y normalización de audio opcional.
- Síntesis en segundo plano, cancelación, validación de WAV y escritura de exportación segura.
- Guías de instalación y uso, compilación reproducible y publicación automatizada de versiones.

## [0.1.0-alpha] - 2026-09-16

- Primera versión pública experimental del frontend local de eSpeak NG.
- Cuatro presets iniciales y controles de velocidad, tono y volumen.
- Previsualización y exportación WAV.

[0.4.0]: https://github.com/smouj/classicvoice/releases/tag/v0.4.0
[0.3.1]: https://github.com/smouj/classicvoice/releases/tag/v0.3.1
[0.3.0]: https://github.com/smouj/classicvoice/releases/tag/v0.3.0
[0.2.2]: https://github.com/smouj/classicvoice/releases/tag/v0.2.2
[0.2.1]: https://github.com/smouj/classicvoice/releases/tag/v0.2.1
[0.2.0]: https://github.com/smouj/classicvoice/releases/tag/v0.2.0
[0.1.0-alpha]: https://github.com/smouj/classicvoice/releases/tag/v0.1.0-alpha
