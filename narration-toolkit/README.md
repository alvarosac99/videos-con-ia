# narration-toolkit

Scripts del pipeline, en el orden en que se usan normalmente. Todos se
ejecutan desde `narration/` dentro de tu proyecto (después de copiarlos ahí,
ver `../CLAUDE.md`). Ninguno lleva contenido de proyecto hardcodeado — leen
`narration_<version>.txt`, `scene-map.json`, `music-config.json` y
`voices.env` del proyecto donde se han copiado.

| script | qué hace | entrada | salida |
|---|---|---|---|
| `generate.sh <v> [voz]` | TTS de una tirada (guiones cortos) | `narration_<v>.txt` | `assets/narration_<v>.mp3` |
| `generate-chunked.sh <v> [voz]` | TTS por bloques (guiones largos; evita que `eleven_v3` aplane la emoción) | `narration_<v>.txt` | `assets/narration_<v>.mp3` |
| `_split_chunks.py` / `_build_payload.py` | helpers internos de `generate-chunked.sh` | — | — |
| `align.sh <v>` | alineación forzada palabra a palabra | `assets/narration_<v>.mp3` + `.txt` | `narration_<v>.alignment.json` |
| `apretar.py <v>` | recorta aire muerto + masteriza la voz | `assets/narration_<v>.mp3` + alineación | reescribe el mp3 (guarda crudo en `_crudo.mp3`) |
| `retime.py <v>` | reparte la duración real del audio entre escenas y remapea el timeline GSAP | alineación + `scene-map.json` + `index.html` | reescribe `index.html` (backup `.bak`) |
| `wordtime.py <v> "frase"` | en qué segundo del vídeo se dice una frase | alineación | tiempo en stdout |
| `generate-music.sh [mood]` | genera camas musicales con ElevenLabs Music | `music-config.json` | `.media/audio/bgm/*.wav` |
| `generate-sfx.sh [nombre]` | genera SFX de transición con ElevenLabs | — | `.media/audio/sfx/*.mp3` |
| `montar_musica.py <v>` | loop + crossfade de moods + acentos SFX + ducking guiado por voz | `music-config.json` + alineación + `index.html` | `.media/audio/bgm/bed_full.wav`, reescribe `index.html` |
| `duck.py <v>` | solo el ducking (si no usas `montar_musica.py` completo) | alineación + `index.html` | reescribe `index.html` |
| `list-voices.sh [mine\|market] [gender]` | busca voces en tu cuenta o el marketplace | — | `previews/*.mp3` |
| `try-voices.sh` | prueba el mismo fragmento con varias voces | `voices.env` + `sample-text.txt` | `previews-es/*.mp3` |
| `clonar.py <v>` | clonado local con Chatterbox (GPU, sin cuota) | `assets/voz-ref/ref_*.wav` + `voice-registry.json` | `assets/narration_<v>.mp3` |

## Convención de claves

Todos los scripts que llaman a ElevenLabs buscan `ELEVENLABS_API_KEY` en
este orden: variable de entorno → `narration/.env` → `<proyecto>/.env` →
`~/.config/videos-ia/elevenlabs.env`. Nunca la pidas por línea de comandos
en texto plano si puedes evitarlo.

## Convención de voces

`generate.sh`, `generate-chunked.sh` y `try-voices.sh` resuelven alias de
voz contra `voices.env` (copia `voices.env.example`). Si no defines ningún
alias, pasa el `voice_id` directamente como variable `VOICE_ID`.

## Orden recomendado completo

Ver `../CLAUDE.md` sección 2 — es la misma tabla pero como receta paso a
paso con los comandos exactos.
