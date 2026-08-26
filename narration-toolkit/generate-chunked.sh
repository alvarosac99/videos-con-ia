#!/usr/bin/env bash
# Genera la narración por BLOQUES, no de una sola petición.
#
#   ./generate-chunked.sh v1
#   ./generate-chunked.sh v1 mivoz      -> con el alias "mivoz" de voices.env
#
# Por qué por bloques: eleven_v3 aplana la emoción cuando le mandas un texto
# largo de golpe. Troceado, cada bloque conserva su propio registro
# emocional. Para que no se note el corte, los cortes caen siempre entre
# párrafos, donde ya hay silencio.
#
# OJO: con eleven_v3 la API rechaza TANTO `previous_request_ids` (stitching)
# COMO `previous_text`/`next_text` — responde `unsupported_model`. No hay
# forma de dar contexto entre bloques; por eso los cortes van en pausas
# naturales.
#
# Cada bloque se cachea en parts_<version>/: si ya existe, no se vuelve a
# generar ni a facturar. Con `--solo=N` genera únicamente ese bloque, para
# validar la voz antes de gastar el saldo entero.
#
# Cuesta exactamente los mismos caracteres que una petición única.

set -euo pipefail

VERSION="${1:-v1}"
ALIAS="${2:-default}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for KEY_FILE in "${ELEVENLABS_KEY_FILE:-}" "$HERE/.env" "$HERE/../.env" \
                "${XDG_CONFIG_HOME:-$HOME/.config}/videos-ia/elevenlabs.env"; do
  [[ -n "${ELEVENLABS_API_KEY:-}" ]] && break
  [[ -n "$KEY_FILE" && -f "$KEY_FILE" ]] && { set -a; source "$KEY_FILE"; set +a; }
done
[[ -n "${ELEVENLABS_API_KEY:-}" ]] || { echo "ERROR: falta ELEVENLABS_API_KEY" >&2; exit 1; }

if [[ -z "${VOICE_ID:-}" && -f "$HERE/voices.env" ]]; then
  VOICE_ID="$(grep -m1 "^${ALIAS}:" "$HERE/voices.env" | cut -d: -f2- || true)"
fi
[[ -n "${VOICE_ID:-}" ]] || { echo "ERROR: no hay VOICE_ID (define un alias en $HERE/voices.env o exporta VOICE_ID)" >&2; exit 1; }

SCRIPT_TXT="$HERE/narration_${VERSION}.txt"
OUT_MP3="$HERE/../assets/narration_${VERSION}.mp3"
SPLITTER="$HERE/_split_chunks.py"
BUILDER="$HERE/_build_payload.py"
[[ -f "$SCRIPT_TXT" ]] || { echo "ERROR: no existe $SCRIPT_TXT" >&2; exit 1; }

SOLO=""
for a in "$@"; do [[ "$a" == --solo=* ]] && SOLO="${a#--solo=}"; done

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
PARTS="$HERE/parts_${VERSION}"; mkdir -p "$PARTS"

python3 "$SPLITTER" "$SCRIPT_TXT" "$WORK"

i=0
for CHUNK in "$WORK"/chunk*.txt; do
  DEST="$PARTS/part$i.mp3"
  if [[ -n "$SOLO" && "$SOLO" != "$i" ]]; then i=$((i+1)); continue; fi
  if [[ -s "$DEST" ]]; then
    printf "  · bloque %d ya generado, no se refactura\n" "$i"; i=$((i+1)); continue
  fi
  python3 "$BUILDER" "$CHUNK" "$WORK/payload$i.json" "$WORK" "$i"
  curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" -H "Content-Type: application/json" \
    --data-binary @"$WORK/payload$i.json" -o "$DEST"
  if ! file -b --mime-type "$DEST" | grep -q '^audio/'; then
    echo "ERROR en el bloque $i:" >&2; head -c 400 "$DEST" >&2; echo >&2; rm -f "$DEST"; exit 1
  fi
  printf "  ✓ bloque %d  %ss\n" "$i" \
    "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$DEST" | cut -c1-5)"
  i=$((i+1))
done

TOTAL=$(ls "$WORK"/chunk*.txt | wc -l)
HECHOS=$(ls "$PARTS"/part*.mp3 2>/dev/null | wc -l)
if [[ "$HECHOS" -lt "$TOTAL" ]]; then
  echo; echo "→ $HECHOS de $TOTAL bloques generados. Sin unir todavía."
  echo "  para completar: $0 $VERSION $ALIAS"
  exit 0
fi

: > "$WORK/list.txt"
for f in "$PARTS"/part*.mp3; do echo "file '$f'" >> "$WORK/list.txt"; done
mkdir -p "$(dirname "$OUT_MP3")"
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/list.txt" -c:a libmp3lame -q:a 2 "$OUT_MP3"

DUR="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT_MP3")"
echo
echo "✓ $OUT_MP3"
echo "  duración: ${DUR}s · $(du -h "$OUT_MP3" | cut -f1)"
echo "  siguiente: ./align.sh $VERSION"
