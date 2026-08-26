#!/usr/bin/env bash
# Alinea un audio ya generado con su guion y guarda los tiempos reales.
#
#   ./align.sh v1   -> assets/narration_v1.mp3 + narration_v1.txt
#                   -> narration_v1.alignment.json  (palabra a palabra)
#
# Usa /v1/forced-alignment, así que NO regenera la voz: los tiempos son los
# del audio que ya tienes. retime.py y montar_musica.py los usan en vez de
# estimar por número de palabras.

set -euo pipefail

VERSION="${1:-v1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for KEY_FILE in "${ELEVENLABS_KEY_FILE:-}" \
                "$HERE/.env" \
                "$HERE/../.env" \
                "${XDG_CONFIG_HOME:-$HOME/.config}/videos-ia/elevenlabs.env"; do
  [[ -n "${ELEVENLABS_API_KEY:-}" ]] && break
  if [[ -n "$KEY_FILE" && -f "$KEY_FILE" ]]; then
    set -a; source "$KEY_FILE"; set +a
  fi
done
if [[ -z "${ELEVENLABS_API_KEY:-}" ]]; then
  echo "ERROR: falta ELEVENLABS_API_KEY (guárdala en $HERE/.env)" >&2; exit 1
fi

MP3="$HERE/../assets/narration_${VERSION}.mp3"
TXT="$HERE/narration_${VERSION}.txt"
OUT="$HERE/narration_${VERSION}.alignment.json"
[[ -f "$MP3" ]] || { echo "ERROR: no existe $MP3" >&2; exit 1; }
[[ -f "$TXT" ]] || { echo "ERROR: no existe $TXT" >&2; exit 1; }

# el guion sin las etiquetas de emoción: es lo que realmente se oye
PLAIN="$(mktemp)"; trap 'rm -f "$PLAIN"' EXIT
python3 -c "
import re,sys
t=open(sys.argv[1],encoding='utf-8').read()
open(sys.argv[2],'w',encoding='utf-8').write(re.sub(r'\[[^\]]+\]\s*','',t).strip())
" "$TXT" "$PLAIN"

echo "→ alineando $(basename "$MP3") con $(basename "$TXT")..."
curl -s -X POST "https://api.elevenlabs.io/v1/forced-alignment" \
  -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
  -F "file=@${MP3};type=audio/mpeg" \
  -F "text=<${PLAIN}" \
  -o "$OUT"

python3 - "$OUT" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
if "words" not in d:
    print("ERROR: respuesta inesperada de la API:"); print(json.dumps(d, indent=2)[:800]); sys.exit(1)
w = d["words"]
print(f"✓ {len(w)} palabras alineadas · {w[0]['start']:.2f}s → {w[-1]['end']:.2f}s")
print(f"  guardado en {p}")
PY
