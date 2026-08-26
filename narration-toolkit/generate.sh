#!/usr/bin/env bash
# Genera la narración con ElevenLabs a partir de narration_<version>.txt.
#
#   ./generate.sh            -> narration_v1.txt  -> assets/narration_v1.mp3
#   ./generate.sh v2         -> narration_v2.txt  -> assets/narration_v2.mp3
#   ./generate.sh v2 mivoz   -> con el alias "mivoz" definido en voices.env
#   VOICE_ID=xxx ./generate.sh v2   -> con un voice_id suelto, sin alias
#
# Intenta primero eleven_v3 (el único modelo que interpreta las etiquetas de
# emoción tipo [sorrowful] / [excited] que puede llevar el guion). Si la
# cuenta no tiene acceso a v3, reintenta con eleven_multilingual_v2 quitando
# las etiquetas del texto (v2 las leería en voz alta) y subiendo la
# expresividad.

set -euo pipefail

VERSION="${1:-v1}"
ALIAS="${2:-default}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_TXT="$HERE/narration_${VERSION}.txt"
OUT_MP3="$HERE/../assets/narration_${VERSION}.mp3"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# --- clave: fichero local primero, variable de entorno después ---------------
# Guarda la clave en narration/.env (o ~/.config/videos-ia/elevenlabs.env) con
# la línea ELEVENLABS_API_KEY=sk_... Así no hay que pasarla por la línea de
# comandos ni pegarla en ningún chat.
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
  echo "ERROR: falta ELEVENLABS_API_KEY" >&2
  echo "  guárdala en $HERE/.env  (línea: ELEVENLABS_API_KEY=sk_...)" >&2
  echo "  o: ELEVENLABS_API_KEY=sk_xxx $0 [${VERSION}]" >&2
  exit 1
fi
if [[ "$ELEVENLABS_API_KEY" == "TU_API_KEY" || "$ELEVENLABS_API_KEY" != sk_* ]]; then
  echo "ERROR: ELEVENLABS_API_KEY no parece una clave real (las de ElevenLabs empiezan por 'sk_')." >&2
  echo "  Sustituye el placeholder por tu clave de https://elevenlabs.io/app/settings/api-keys" >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_TXT" ]]; then
  echo "ERROR: no existe el guion $SCRIPT_TXT" >&2
  exit 1
fi

# --- resuelve el voice_id: VOICE_ID explícito > alias en voices.env --------
if [[ -z "${VOICE_ID:-}" && -f "$HERE/voices.env" ]]; then
  VOICE_ID="$(grep -m1 "^${ALIAS}:" "$HERE/voices.env" | cut -d: -f2- || true)"
fi
if [[ -z "${VOICE_ID:-}" ]]; then
  echo "ERROR: no hay VOICE_ID. Define un alias en $HERE/voices.env (copia voices.env.example)" >&2
  echo "  o exporta VOICE_ID=<id> a mano. Busca voces con ./list-voices.sh" >&2
  exit 1
fi

# --- construye los dos payloads a partir del guion ---------------------------
python3 - "$SCRIPT_TXT" "$TMP_DIR" <<'PY'
import json, os, re, sys
src, out = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read().strip()

# v3: etiquetas de emoción tal cual. stability 0.0 ("Creative") suena
# erráticamente plano/encapsulado en textos largos; 0.30-0.50 es el rango
# donde v3 interpreta de verdad las etiquetas sin desestabilizarse.
json.dump({
    "text": text,
    "model_id": "eleven_v3",
    "voice_settings": {
        "stability": float(os.environ.get("EL_STABILITY", "0.35")),
        "style": float(os.environ.get("EL_STYLE", "0.20")),
        "similarity_boost": 0.75,
        "use_speaker_boost": True,
    },
}, open(f"{out}/v3.json", "w", encoding="utf-8"), ensure_ascii=False)

# v2: sin etiquetas (las leería en alto), con style alto para exprimir emoción.
json.dump({
    "text": re.sub(r"\[[^\]]+\]\s*", "", text),
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.18,
        "similarity_boost": 0.75,
        "style": 0.9,
        "use_speaker_boost": True,
        "speed": 1.12,
    },
}, open(f"{out}/v2.json", "w", encoding="utf-8"), ensure_ascii=False)
PY

# --- llamada -----------------------------------------------------------------
call_tts() {  # $1 = payload, $2 = destino
  curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary @"$1" -o "$2"
}

is_audio() { file -b --mime-type "$1" | grep -q '^audio/'; }

mkdir -p "$(dirname "$OUT_MP3")"

echo "→ intentando eleven_v3 (con etiquetas de emoción)..."
call_tts "$TMP_DIR/v3.json" "$TMP_DIR/out.mp3"

if is_audio "$TMP_DIR/out.mp3"; then
  MODEL="eleven_v3"
else
  echo "  v3 no disponible. Respuesta de la API:"
  sed 's/^/    /' "$TMP_DIR/out.mp3"; echo
  echo "→ reintentando con eleven_multilingual_v2..."
  call_tts "$TMP_DIR/v2.json" "$TMP_DIR/out.mp3"
  if ! is_audio "$TMP_DIR/out.mp3"; then
    echo "ERROR: también falló v2. Respuesta:" >&2
    sed 's/^/    /' "$TMP_DIR/out.mp3" >&2
    exit 1
  fi
  MODEL="eleven_multilingual_v2"
fi

mv "$TMP_DIR/out.mp3" "$OUT_MP3"

DUR="$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$OUT_MP3")"

echo
echo "✓ listo"
echo "  modelo:   $MODEL"
echo "  archivo:  $OUT_MP3"
echo "  duración: ${DUR}s"
echo "  tamaño:   $(du -h "$OUT_MP3" | cut -f1)"
echo
echo "siguiente paso: ./align.sh $VERSION"
