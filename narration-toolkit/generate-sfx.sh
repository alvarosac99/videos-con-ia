#!/usr/bin/env bash
# Genera un set de SFX de transición con ElevenLabs Sound Effects.
#
#   ./generate-sfx.sh              -> genera los 8 SFX de la librería base
#   ./generate-sfx.sh riser        -> solo uno (riser|pop|chime|sparkle|whoosh|sticker|tick|slide)
#
# Usa la misma clave que generate.sh (narration/.env, ELEVENLABS_API_KEY=sk_...).
# La lista de abajo es un punto de partida genérico (riser de tensión, pop de
# interfaz, chime positivo, sparkle de cierre, whoosh de corte, etc.) — edítala
# libremente o añade tus propios casos con la misma función `generate_sfx`.

set -euo pipefail

WHICH="${1:-all}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)"
SFX_DIR="$PROJ/.media/audio/sfx"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

for KEY_FILE in "${ELEVENLABS_KEY_FILE:-}" \
                "$HERE/.env" \
                "$HERE/../.env" \
                "${XDG_CONFIG_HOME:-$HOME/.config}/videos-ia/elevenlabs.env"; do
  [[ -n "${ELEVENLABS_API_KEY:-}" ]] && break
  if [[ -n "$KEY_FILE" && -f "$KEY_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$KEY_FILE"; set +a
  fi
done

if [[ -z "${ELEVENLABS_API_KEY:-}" ]]; then
  echo "ERROR: falta ELEVENLABS_API_KEY (mira narration/.env)" >&2
  exit 1
fi

is_audio() { file -b --mime-type "$1" | grep -q '^audio/'; }

generate_sfx() {
  local id="$1" filename="$2" duration="$3" prompt="$4"
  local out="$SFX_DIR/$filename"
  echo "→ ${filename}: generando (${duration}s)..."

  python3 - "$TMP_DIR/${id}.json" "$duration" "$prompt" <<'PY'
import json, sys
out, duration, prompt = sys.argv[1], float(sys.argv[2]), sys.argv[3]
json.dump({
    "text": prompt,
    "duration_seconds": duration,
    "prompt_influence": 0.35,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY

  curl -s -X POST "https://api.elevenlabs.io/v1/sound-generation" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary @"$TMP_DIR/${id}.json" \
    -o "$TMP_DIR/${filename}"

  if ! is_audio "$TMP_DIR/${filename}"; then
    echo "ERROR: la API no devolvió audio para ${filename}. Respuesta:" >&2
    sed 's/^/    /' "$TMP_DIR/${filename}" >&2
    return 1
  fi

  mkdir -p "$SFX_DIR"
  cp "$TMP_DIR/${filename}" "$out"
  local dur
  dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$out")"
  echo "  ✓ $out (${dur}s)"
}

case "$WHICH" in
  riser)   generate_sfx riser   "riser.mp3"        1.8 "riser de tensión sintético y contenido, subida corta, cinematográfico y sutil, sin percusión fuerte, para marcar un giro narrativo" ;;
  pop)     generate_sfx pop     "pop.mp3"          0.5 "pequeño pop de burbuja, sonido de interfaz limpio y corto, positivo" ;;
  chime)   generate_sfx chime   "chime.mp3"        1.0 "campanilla cálida y suave, chime corto de notificación positiva" ;;
  sparkle) generate_sfx sparkle "sparkle.mp3"      1.2 "destello mágico brillante, sparkle corto y ligero, sonido positivo de cierre" ;;
  whoosh)  generate_sfx whoosh  "whoosh-short.mp3" 0.5 "whoosh corto y seco de transición entre escenas de vídeo, sin eco largo, limpio y sutil" ;;
  sticker) generate_sfx sticker "sticker_pop.mp3"  0.5 "pop diminuto y burbujeante, muy corto y agudo, tipo sticker apareciendo en pantalla, juguetón" ;;
  tick)    generate_sfx tick    "text_tick.mp3"    0.5 "tic seco y suave de un solo golpe, tipo click de teclado o stamp de texto apareciendo en pantalla, minimal, no musical" ;;
  slide)   generate_sfx slide   "phone_slide.mp3"  0.7 "deslizamiento suave y rápido tipo swoosh de una tarjeta o pantalla de móvil entrando en cuadro, corto y limpio" ;;
  all)
    generate_sfx riser   "riser.mp3"        1.8 "riser de tensión sintético y contenido, subida corta, cinematográfico y sutil, sin percusión fuerte, para marcar un giro narrativo"
    generate_sfx pop     "pop.mp3"          0.5 "pequeño pop de burbuja, sonido de interfaz limpio y corto, positivo"
    generate_sfx chime   "chime.mp3"        1.0 "campanilla cálida y suave, chime corto de notificación positiva"
    generate_sfx sparkle "sparkle.mp3"      1.2 "destello mágico brillante, sparkle corto y ligero, sonido positivo de cierre"
    generate_sfx whoosh  "whoosh-short.mp3" 0.5 "whoosh corto y seco de transición entre escenas de vídeo, sin eco largo, limpio y sutil"
    generate_sfx sticker "sticker_pop.mp3"  0.5 "pop diminuto y burbujeante, muy corto y agudo, tipo sticker apareciendo en pantalla, juguetón"
    generate_sfx tick    "text_tick.mp3"    0.5 "tic seco y suave de un solo golpe, tipo click de teclado o stamp de texto apareciendo en pantalla, minimal, no musical"
    generate_sfx slide   "phone_slide.mp3"  0.7 "deslizamiento suave y rápido tipo swoosh de una tarjeta o pantalla de móvil entrando en cuadro, corto y limpio"
    ;;
  *)
    echo "uso: $0 [riser|pop|chime|sparkle|whoosh|sticker|tick|slide|all]" >&2
    exit 1
    ;;
esac

echo
echo "siguiente paso: python3 montar_musica.py <version>   (desde narration/)"
