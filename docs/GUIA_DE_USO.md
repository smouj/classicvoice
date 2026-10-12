# Guía de uso

ClassicVoice transforma texto en audio WAV con voces sintéticas en español. El flujo es: **escribir → ajustar → escuchar → guardar**.

## 1. Escribir o pegar texto

Escribe en el área **Texto** o pega contenido desde otra aplicación. El contador muestra palabras y caracteres. Se admiten textos de hasta 50.000 caracteres. El contenido no se guarda en la nube ni se conserva como proyecto.

## 2. Elegir y ajustar la voz

Escoge un preset en **Preset**:

| Preset | Carácter inicial |
| --- | --- |
| Clásica española | Equilibrado |
| Clásica grave | Más profundo y pausado |
| Clásica brillante | Más agudo y ligero |
| Narrador | Lectura más pausada |

Después puedes ajustar los controles aunque hayas elegido un preset:

- **Velocidad**: ritmo de lectura, en palabras por minuto.
- **Tono**: altura de la voz, desde grave a aguda.
- **Volumen**: amplitud de síntesis de eSpeak NG.

Los presets y controles son puntos de partida. Cambiar un control no altera el texto que escribiste.

## 3. Corregir pronunciaciones (opcional)

Pulsa **Pronunciación** para asociar una palabra o frase a la forma que debe leerse. Las coincidencias no distinguen mayúsculas y minúsculas y evitan reemplazar fragmentos dentro de otras palabras. Revisa el texto con **Escuchar** después de crear las reglas.

## 4. Escuchar

Pulsa **Escuchar** para sintetizar una previsualización local. La interfaz permanece disponible mientras trabaja. Pulsa **Detener** si quieres cancelar la síntesis o parar la reproducción.

Atajos: **Ctrl + Intro** para previsualizar y **Ctrl + S** para iniciar el guardado WAV.

## 5. Guardar el archivo

Pulsa **Guardar WAV**, elige nombre y ubicación, y espera a que el estado indique que terminó. La carpeta se recuerda para la siguiente sesión.

**Normalizar volumen** está activado por defecto. Ajusta el pico del WAV para que el nivel quede más uniforme; no cambia la voz ni la velocidad. Desmárcalo si prefieres conservar el nivel original de eSpeak NG.

## Ajustes y archivos

Los ajustes y reglas de pronunciación se guardan en `%LOCALAPPDATA%\ClassicVoice\settings.json`. Los WAV se guardan en la carpeta indicada en la ventana. La aplicación no guarda borradores ni sube contenido a Internet.

## Preguntas frecuentes

**¿Necesito una cuenta, un modelo de IA o Internet?** No. La voz se genera localmente con eSpeak NG. Solo necesitas Internet para descargar la aplicación o compilarla.

**¿Puedo obtener una voz natural?** ClassicVoice está centrada en voces sintéticas clásicas; no incluye síntesis neuronal, clonación, transcripción ni doblaje.

**¿Incluye voces de Loquendo?** No. Los presets son voces de eSpeak NG con nombres neutrales; no se distribuyen archivos propietarios.

**¿Qué hago si el WAV no se crea?** Confirma que la carpeta de salida existe y que tienes permiso para escribir en ella. Si sigue fallando, vuelve a abrir la app y consulta el mensaje de estado.
