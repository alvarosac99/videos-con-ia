# videos-con-ia

Kit reutilizable para hacer vídeos narrados por IA — voz clonada o TTS,
música dinámica generada, SFX de transición y mezcla con ducking automático
guiado por los tiempos reales de la voz — pensado para dejarlo caer dentro
de cualquier proyecto [HyperFrames](https://hyperframes.heygen.com) y que un
agente de IA (Claude Code u otro) se autoconfigure a partir de `CLAUDE.md`.

Nace de la producción del vídeo de presentación de
[BROcate](https://github.com/alvarosac99/BROcate); esta es la versión
generalizada, sin nada específico de ese proyecto.

## Qué resuelve

Producir un vídeo narrado bien hecho a mano tiene fricción repetida en cada
proyecto: silencios muertos en la voz generada, escenas que no cuadran con
la duración real del audio, música que tapa la voz, SFX que no llegan justo
al golpe visual. Este kit automatiza ese ciclo completo una vez y lo deja
parametrizado para el siguiente proyecto.

## Qué incluye

- **`narration-toolkit/`** — los scripts del pipeline (generación TTS,
  alineación forzada, recorte de silencios + masterización, retimer de
  composición, generación de música/SFX con IA, montaje musical con ducking
  guiado por voz, herramientas de exploración de voces).
- **`templates/guion-template.md`** — el formato de guion (un párrafo por
  escena, con anotaciones de tono entre líneas) que usan los scripts.
- **`config/*.example.json`** — plantillas de configuración por proyecto
  (mapa de escenas, moods musicales, registro emocional de voz).
- **`CLAUDE.md`** — instrucciones para que un agente de IA se autoconfigure
  al encontrar este kit dentro de un proyecto.

## Requisitos

- `ffmpeg` / `ffprobe`, `python3`, `curl`
- Cuenta de [ElevenLabs](https://elevenlabs.io) (TTS, forced-alignment,
  música, SFX) — o, para clonado local sin cuota, GPU + `chatterbox-tts`
  (`clonar.py`).
- Un proyecto HyperFrames existente (composición con timeline GSAP).

## Instalación rápida

```bash
git clone <esta-url> videos-con-ia
cp -r videos-con-ia/narration-toolkit/* <tu-proyecto>/narration/
cp videos-con-ia/.env.example <tu-proyecto>/narration/.env   # y rellena tu clave
cp videos-con-ia/config/*.example.json <tu-proyecto>/narration/
cp videos-con-ia/templates/guion-template.md <tu-proyecto>/narration/guion.md
```

Luego sigue `CLAUDE.md` — es la guía paso a paso del pipeline completo.

## Licencia / alcance

Los scripts son tuyos para adaptar libremente. No incluye datasets, voces
clonadas ni claves de API de nadie — cada proyecto trae las suyas.
