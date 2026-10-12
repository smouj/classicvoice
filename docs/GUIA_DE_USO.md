# Guía de uso

ClassicVoice transforma texto en audio WAV con voces sintéticas en varios idiomas. El flujo es: **escribir → elegir idioma → ajustar → escuchar → guardar**.

## 1. Escribir o pegar texto

Escribe en el área **Texto** o pega contenido desde otra aplicación. El contador muestra palabras y caracteres. Se admiten textos de hasta 50.000 caracteres. El contenido del editor no se guarda en la nube ni se conserva como proyecto.

**Importar TXT** abre archivos en UTF-8 o UTF-16. La importación sustituye el contenido del editor; puedes deshacerla con **Ctrl + Z**. No se modifican los archivos originales.

## 2. Elegir el motor y ajustar la voz

En la pestaña **Voz**, el botón **Motor: Clásico** abre la selección del motor:

- **Clásico · eSpeak NG** es rápido, ligero y funciona sin descargar modelos. Incluye 130 idiomas y variantes, además de los controles de tono y volumen.
- **Natural · Kokoro 82M** usa voces neuronales predefinidas con una entonación más natural. Incluye variantes de inglés, español, francés, italiano, portugués brasileño, japonés, chino mandarín e hindi. No clona voces grabadas.

Para activar Kokoro, selecciona **Natural** y pulsa **Descargar e instalar · 136 MiB**. La descarga única se verifica con SHA-256 y se guarda en `%LOCALAPPDATA%\ClassicVoice\models`. Necesita Internet solo durante la descarga; una vez instalado, el modelo funciona sin conexión y sin cuenta. Usa hasta dos hilos de CPU para no monopolizar el PC. En procesadores antiguos puede tardar más que el audio final, aunque la ventana sigue respondiendo. **Eliminar modelo neuronal** quita los archivos del modelo y su licencia, y conserva cualquier otro archivo que hubiera en esa carpeta.

Elige **Idioma del texto** y una voz disponible para ese idioma. ClassicVoice no detecta ni traduce el texto automáticamente. Consulta el [catálogo de idiomas](IDIOMAS.md) para los idiomas del motor clásico.

En modo natural puedes cambiar la velocidad; el control se adapta de lento a rápido. Tono y volumen propios de eSpeak NG se desactivan porque Kokoro no los admite. La normalización de **Salida** sigue disponible.

En el motor clásico, escoge un **Estilo de voz**:

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

En el motor natural, el selector muestra voces Kokoro, no los estilos de eSpeak NG. **Restablecer voz natural** vuelve a la voz predeterminada del idioma y a velocidad normal. En el motor clásico, **Restablecer estilo** recupera los controles del preset elegido. Puedes usar los deslizadores o escribir valores en los campos numéricos. Al pulsar Intro o salir del campo se aplica un valor válido dentro del intervalo. Los campos vacíos o no numéricos recuperan el valor anterior.

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

Los ajustes y reglas de pronunciación se guardan en `%LOCALAPPDATA%\ClassicVoice\settings.json`. El motor, el idioma y la voz natural elegidos también se recuerdan. El modelo se guarda bajo `%LOCALAPPDATA%\ClassicVoice\models`; puedes quitarlo con **Eliminar modelo neuronal**. Los WAV se guardan en la carpeta indicada en la ventana. La aplicación no guarda borradores, sube contenido ni usa telemetría.

Al actualizar desde una versión anterior, las reglas existentes se conservan para español. Se recuerdan el idioma, el estilo, los controles, la normalización y la carpeta de salida.

## 6. Crear capítulos y audiolibros

Pulsa **Lote / libro…** encima del editor, añade uno o más archivos `.txt` o `.md` y elige la carpeta de destino. ClassicVoice reconoce encabezados que empiezan por **Capítulo**, **Parte**, **Prólogo**, **Epílogo** y sus equivalentes habituales en inglés. Si no hay encabezados, el documento se divide por párrafos cuando un fragmento supera 50.000 caracteres. En Markdown se omite formato habitual como enlaces, viñetas, negrita y bloques de código.

La app genera un WAV por capítulo. Puedes marcar **Crear también un WAV continuo** para unirlos con una pausa breve entre capítulos. Se usa la voz, idioma, normalización y reglas de pronunciación activos en la ventana principal. La síntesis se hace capítulo a capítulo; **Detener** cancela el lote y elimina sus archivos incompletos. Los archivos finales existentes nunca se reemplazan: se asigna un nombre disponible. El lote admite hasta 5 millones de caracteres en total; cada fuente tiene un límite de 2 millones.

## 7. Guardar perfiles de voz

En **Salida**, abre **Mis perfiles de voz…** y pulsa **Guardar ajustes actuales…**. El perfil guarda motor, idioma, estilo o voz natural, velocidad, controles compatibles, normalización y las reglas de pronunciación del idioma seleccionado. Elige uno y pulsa **Usar perfil** para recuperar sus ajustes. Se permiten hasta 24 perfiles por usuario; quedan guardados junto a las preferencias de ClassicVoice.

Un perfil conserva ajustes del motor elegido. No contiene una grabación ni clona la identidad de una voz.

## Preguntas frecuentes

**¿Necesito una cuenta o Internet para usar ClassicVoice?** No para el motor clásico. Kokoro es opcional y requiere una descarga única de unos 136 MiB; después, la síntesis neuronal también es local y funciona sin conexión.

**¿Por qué mi voz aún suena robótica?** Comprueba que el botón de la pestaña **Voz** indique **Motor: Natural**, que el estado muestre el modelo listo y que hayas elegido una voz Kokoro. Los cuatro estilos clásicos siguen usando eSpeak NG. La naturalidad también varía entre idiomas y voces; prueba otra voz disponible y escucha una frase de muestra antes de generar un texto largo.

**¿Puedo clonar una grabación?** No. Kokoro ofrece voces predefinidas; los perfiles guardan ajustes, no grabaciones ni identidades clonadas. ClassicVoice tampoco incorpora transcripción, dictado, aislamiento de voz ni doblaje de vídeo.

**¿Incluye voces de Loquendo?** No. Los presets son voces de eSpeak NG con nombres neutrales; no se distribuyen archivos propietarios.

**¿Qué hago si el WAV no se crea?** Confirma que la carpeta de salida existe y que tienes permiso para escribir en ella. Si sigue fallando, vuelve a abrir la app y consulta el mensaje de estado.
