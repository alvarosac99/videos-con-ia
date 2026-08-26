#!/usr/bin/env bash
# Prueba el MISMO fragmento con varias voces, para comparar de verdad.
#
#   ./try-voices.sh            -> genera previews-es/<alias>.mp3 para cada voz de voices.env
#
# Texto de prueba: sample-text.txt (copia sample-text.example.txt y edítalo).
# Voces a comparar: todos los alias definidos en voices.env (copia
# voices.env.example) — un alias por línea, formato "alias:voice_id".

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for KEY_FILE in "$HERE/.env" "${XDG_CONFIG_HOME:-$HOME/.config}/videos-ia/elevenlabs.env"; do
  [[ -n "${ELEVENLABS_API_KEY:-}" ]] && break
  [[ -f "$KEY_FILE" ]] && { set -a; source "$KEY_FILE"; set +a; }
done
[[ -n "${ELEVENLABS_API_KEY:-}" ]] || { echo "ERROR: falta ELEVENLABS_API_KEY" >&2; exit 1; }

TEXT_FILE="$HERE/sample-text.txt"
[[ -f "$TEXT_FILE" ]] || TEXT_FILE="$HERE/sample-text.example.txt"
[[ -f "$TEXT_FILE" ]] || { echo "ERROR: no existe sample-text.txt (copia sample-text.example.txt)" >&2; exit 1; }
TEXT="$(cat "$TEXT_FILE")"

VOICES_FILE="$HERE/voices.env"
[[ -f "$VOICES_FILE" ]] || { echo "ERROR: no existe voices.env (copia voices.env.example y añade tus alias)" >&2; exit 1; }

OUT="$HERE/previews-es"; mkdir -p "$OUT"

PAY="$(mktemp)"; trap 'rm -f "$PAY"' EXIT
python3 - "$PAY" "$TEXT" <<'PY'
import json, sys
out, text = sys.argv[1], sys.argv[2]
json.dump({"text": text.strip(),
           "model_id": "eleven_v3",
           "voice_settings": {"stability": 0.0, "similarity_boost": 0.75, "use_speaker_boost": True}},
          open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY

N_VOICES="$(grep -c "^[^#].*:" "$VOICES_FILE" || true)"
echo "fragmento de $(wc -c < "$TEXT_FILE") caracteres × ${N_VOICES} voces"

while IFS=: read -r alias vid; do
  [[ -z "$alias" || "$alias" == \#* ]] && continue
  curl -s -X POST "https://api.elevenlabs.io/v1/text-to-speech/${vid}" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" -H "Content-Type: application/json" \
    --data-binary @"$PAY" -o "$OUT/${alias}.mp3"
  if file -b --mime-type "$OUT/${alias}.mp3" | grep -q '^audio/'; then
    printf "  ✓ %-10s %ss\n" "$alias" "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/${alias}.mp3" | cut -c1-4)"
  else
    printf "  ✗ %-10s %s\n" "$alias" "$(head -c 160 "$OUT/${alias}.mp3")"
  fi
done < "$VOICES_FILE"
