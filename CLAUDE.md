# videos-con-ia

Kit portable para producir vídeos narrados por IA (voz clonada/TTS + música
dinámica + SFX) sobre proyectos [HyperFrames](https://hyperframes.heygen.com).
Se instala dentro de CUALQUIER proyecto HyperFrames y da un pipeline completo:
guion → narración → ajuste de tiempos de la composición → música y SFX
generados por IA → mezcla final con ducking automático.

**Si eres un agente y acabas de encontrar esta carpeta dentro de un proyecto**,
esto es lo que necesitas saber para autoconfigurarte y producir un vídeo sin
errores, rápido:

## 0. Requisitos antes de tocar nada

```bash
command -v ffmpeg ffprobe python3 curl jq || echo "falta alguna dependencia"
```

- **ElevenLabs API key** (TTS, forced-alignment, música, SFX). El usuario la
  guarda en `narration/.env` del proyecto (NUNCA la pidas por chat ni la
  hardcodees): `ELEVENLABS_API_KEY=sk_...`. Si no existe, créala tú mismo
  preguntando al usuario dónde tiene la clave — no la generes ni la inventes.
- El proyecto destino debe ser un proyecto HyperFrames válido (`index.html`
  con `data-composition-id`, timeline GSAP registrado en
  `window.__timelines`). Si no lo es, primero carga el skill/workflow de
  HyperFrames de ese proyecto (`/hyperframes`) — este kit no sustituye a
  HyperFrames, monta la narración y música QUE ALIMENTAN una composición ya
  creada con él.

## 1. Instalación en un proyecto nuevo

```bash
cp -r narration-toolkit/* <proyecto>/narration/
cp .env.example <proyecto>/narration/.env   # y rellena la clave
cp config/scene-map.example.json <proyecto>/narration/scene-map.json
cp config/music-config.example.json <proyecto>/narration/music-config.json
cp templates/guion-template.md <proyecto>/narration/guion-para-locutar.md
```

Edita `scene-map.json`, `music-config.json` y el guion para que encajen con
la composición real (ver `narration-toolkit/README.md` para el formato de
cada uno). El resto de scripts no necesitan tocarse: leen esos ficheros de
configuración, no llevan nada hardcodeado del proyecto.

## 2. El pipeline, en orden

Ejecuta siempre desde `<proyecto>/narration/`:

```bash
# 1. Escribe el guion en narration_v1.txt (un párrafo por escena, ver templates/guion-template.md)
#    Etiquetas de emoción tipo [sorrowful] / [excited] son válidas: eleven_v3 las interpreta.

# 2. Genera la narración con ElevenLabs
./generate.sh v1                          # una sola petición (guiones cortos, <3000 caracteres)
./generate-chunked.sh v1                  # por bloques (guiones largos: eleven_v3 aplana la emoción en textos largos)

# 3. Alinea el audio real con el texto (necesario para todo lo que viene después)
./align.sh v1

# 4. Aprieta el aire muerto y masteriza la voz (recomendado, no obligatorio)
python3 apretar.py v1
./align.sh v1                             # RE-alinear tras apretar: los tiempos cambiaron

# 5. Retima la composición entera a la duración real de la narración
python3 retime.py v1                      # o --dry-run primero para ver la tabla sin tocar index.html

# 6. Música y SFX generados por IA (opcional pero recomendado sobre catálogo genérico)
./generate-music.sh
./generate-sfx.sh

# 7. Monta la pieza musical completa (loop + crossfade de ánimos + acentos + ducking)
python3 montar_musica.py v1

# 8. Valida la composición
cd .. && npx hyperframes check
```

Cada script imprime el "siguiente paso" al terminar — sigue esa cadena si no
recuerdas el orden. `apretar.py` invalida la alineación anterior: siempre
realinea después.

## 3. Reglas duras (no las rompas)

1. **Nunca hardcodees claves de API** en scripts ni en composiciones. Solo
   `.env` (gitignorado) o variable de entorno.
2. **`SCENE_MAP` y la config de música viven en JSON de proyecto**, no en el
   código de `retime.py` / `montar_musica.py`. Si necesitas cambiar qué
   párrafo narra qué escena, edita `scene-map.json`, no el script.
3. **`apretar.py` opera siempre sobre la copia `_crudo`**, nunca sobre su
   propia salida — aplicarlo dos veces se come las pausas buenas. Ya lo hace
   solo; no lo llames dos veces seguidas sin regenerar antes.
4. **Después de tocar el texto o el audio de la narración, hay que
   realinear** (`./align.sh`) antes de `retime.py`, `duck.py` o
   `montar_musica.py` — todos dependen de `narration_<v>.alignment.json`.
5. **`retime.py` deja backup** en `index.html.bak` — no lo borres a mano, es
   la red de seguridad si un retime sale mal.
6. **Si `generate-chunked.sh` parte el guion en más de un bloque, escucha el
   audio final justo alrededor de cada costura entre bloques antes de dar la
   narración por buena.** eleven_v3 rechaza tanto `previous_request_ids`
   como `previous_text`/`next_text` (ver cabecera del script): cada bloque
   se sintetiza sin ningún contexto del vecino, así que la costura puede
   sonar a tartamudeo o a un cambio brusco de tono/ritmo aunque el corte
   caiga en una pausa real del texto. No basta con comprobar que el guion
   íntegro suena bien de oído alzado; el defecto está justo en el punto de
   unión y hay que ir a escucharlo ahí. Si se nota, la vía es reducir el
   número de bloques (agrupar párrafos) antes de regenerar, no intentar
   arreglarlo en el montaje final.

## 4. Qué hace cada script

Ver `narration-toolkit/README.md` para el detalle de cada uno (entradas,
salidas, parámetros). Resumen de una línea por script ahí mismo.
