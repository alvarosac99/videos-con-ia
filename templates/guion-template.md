# Guion para locutar — plantilla

Formato: **un párrafo en blanco separa cada escena** en `narration_v1.txt`.
Cada párrafo de este fichero (el que lee `retime.py` vía `scene-map.json`) se
corresponde con una o varias escenas de la composición.

Convenciones:

- Las etiquetas de emoción entre corchetes al principio de una frase —
  `[sorrowful]`, `[excited]`, `[whispering]`, `[hopeful]`... — las interpreta
  `eleven_v3` (no `eleven_multilingual_v2`, que las leería en voz alta;
  `generate.sh` ya gestiona el fallback quitándolas si hace falta).
- Bajo cada párrafo, una línea de dirección de interpretación en cursiva
  (no se narra, es una nota para quien revise o para el propio modelo si la
  pegas en el prompt) ayuda a mantener consistencia de tono entre tomas.
- Escribe para oído, no para lectura: frases cortas, sin paréntesis, cifras
  dichas como se dirían en voz alta.

---

## p01

> *Nota de tono: cómo debe sonar este párrafo, y qué NO debe hacer (p. ej. "sin dramatizar", "sube la energía aquí, no antes").*

[warm] Primera frase del guion — el gancho. Va directa, sin rodeos.

## p02

> *Nota de tono.*

Segundo párrafo — desarrollo o giro.

## p03

> *Nota de tono.*

Tercer párrafo — cierre o llamada a la acción.

---

Cuando el guion esté cerrado, mapea qué párrafos narra cada escena en
`scene-map.json` (ver `config/scene-map.example.json`) y arranca el pipeline
desde `CLAUDE.md`.
