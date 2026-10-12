# Guía de uso

ClassicVoice transforma texto en audio WAV con voces sintéticas en varios idiomas. El flujo es: **escribir → elegir idioma → ajustar → escuchar → guardar**.

## 1. Escribir o pegar texto

Escribe en el área **Texto** o pega contenido desde otra aplicación. El contador muestra palabras y caracteres. Se admiten textos de hasta 50.000 caracteres. El contenido no se guarda en la nube ni se conserva como proyecto.

**Importar TXT** abre archivos en UTF-8 o UTF-16. La importación sustituye el contenido del editor; puedes deshacerla con **Ctrl + Z**. No se modifican los archivos originales.

## 2. Elegir y ajustar la voz

En la pestaña **Voz**, elige **Idioma del texto**. El selector muestra los idiomas y variantes incluidos en el motor instalado. Consulta el [catálogo](IDIOMAS.md). Para texto en inglés, elige una variante de inglés; para texto en español, elige español. La aplicación no detecta ni traduce idiomas automáticamente.

Después escoge un **Estilo de voz**:

| Preset | Carácter inicial |
| --- | --- |
| Clásica | Equilibrado |
| Clásica grave | Más profundo y pausado |
| Clásica brillante | Más agudo y ligero |
| Narrador | Lectura más pausada |

Después puedes ajustar los controles aunque hayas elegido un preset:

- **Velocidad**: de 80 a 450 palabras por minuto.
- **Tono**: de 0 (grave) a 99 (agudo).
- **Volumen**: de 0 a 200 % de amplitud de síntesis; 100 % es el nivel estándar.

Puedes usar los deslizadores o escribir valores en los campos numéricos. Al pulsar Intro o salir del campo se aplica un valor válido dentro del intervalo. Los campos vacíos o no numéricos recuperan el valor anterior. **Restablecer voz** recupera los valores del estilo seleccionado y conserva el idioma.

Los presets y controles son puntos de partida. Cambiar un control no altera el texto que escribiste.

## 3. Corregir pronunciaciones (opcional)

En **Salida**, pulsa **Pronunciación** para asociar una palabra o frase a la forma que debe leerse. Las reglas son independientes por idioma: un reemplazo en español no cambia una lectura en inglés. Las coincidencias no distinguen mayúsculas y minúsculas y evitan reemplazar fragmentos dentro de otras palabras. Revisa el texto con **Escuchar** después de crear las reglas.

## 4. Escuchar

Pulsa **Escuchar** para sintetizar una previsualización local. La interfaz permanece disponible mientras trabaja. Pulsa **Detener** si quieres cancelar la síntesis o parar la reproducción.

Atajos: **Ctrl + Intro** para previsualizar, **Ctrl + S** para iniciar el guardado WAV, **Ctrl + O** para importar TXT, **Ctrl + A** para seleccionar el texto y **Esc** para detener la síntesis o reproducción. El guardado permanece bloqueado mientras se está generando audio.

El editor y las pestañas de ajustes se adaptan a la ventana, cuyo tamaño mínimo es de 860 × 620 píxeles. No hay desplazamiento general de la interfaz. El texto largo y las listas de pronunciación mantienen sus propias barras de desplazamiento. Puedes recorrer los controles con **Tab**.

## 5. Guardar el archivo

Pulsa **Guardar WAV**, elige nombre y ubicación, y espera a que el estado indique que terminó. La carpeta se recuerda para la siguiente sesión.

En **Salida**, **Cambiar…** elige la carpeta que se propone al guardar y **Abrir carpeta** la muestra en el explorador.

**Normalizar volumen** está activado por defecto. Ajusta el pico del WAV para que el nivel quede más uniforme; no cambia la voz ni la velocidad. Desmárcalo si quieres conservar la intensidad elegida con el control **Volumen**. La normalización no hace que el audio sea perceptualmente igual de alto en todos los idiomas o frases.

## Ajustes y archivos

Los ajustes y reglas de pronunciación se guardan en `%LOCALAPPDATA%\ClassicVoice\settings.json`. Los WAV se guardan en la carpeta indicada en la ventana. La aplicación no guarda borradores ni sube contenido a Internet.

Al actualizar desde una versión anterior, las reglas existentes se conservan para español. Se recuerdan el idioma, el estilo, los controles, la normalización y la carpeta de salida.

## Preguntas frecuentes

**¿Necesito una cuenta, un modelo de IA o Internet?** No. La voz se genera localmente con eSpeak NG. Solo necesitas Internet para descargar la aplicación o compilarla.

**¿Puedo obtener una voz natural?** ClassicVoice está centrada en voces sintéticas clásicas; no incluye síntesis neuronal, clonación, transcripción ni doblaje.

**¿Incluye voces de Loquendo?** No. Los presets son voces de eSpeak NG con nombres neutrales; no se distribuyen archivos propietarios.

**¿Qué hago si el WAV no se crea?** Confirma que la carpeta de salida existe y que tienes permiso para escribir en ella. Si sigue fallando, vuelve a abrir la app y consulta el mensaje de estado.
