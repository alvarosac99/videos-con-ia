#!/usr/bin/env bash
# Genera las camas musicales del vídeo con ElevenLabs Music (eleven-music-v1),
# a partir de los moods definidos en music-config.json.
#
#   ./generate-music.sh              -> genera todos los moods de music-config.json
#   ./generate-music.sh mood_a       -> solo el mood con ese id
#
# Usa la misma clave que generate.sh (narration/.env, ELEVENLABS_API_KEY=sk_...).

set -euo pipefail

WHICH="${1:-all}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ="$(cd "$HERE/.." && pwd)"
CONFIG="$HERE/music-config.json"
MANIFEST="$PROJ/.media/manifest.jsonl"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

[[ -f "$CONFIG" ]] || { echo "ERROR: no existe $CONFIG (copia config/music-config.example.json de la raíz del kit)" >&2; exit 1; }

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

generate_track() {
  local id="$1" out="$2" length_ms="$3" prompt="$4"
  echo "→ ${id}: generando ${length_ms}ms con ElevenLabs Music..."

  python3 - "$TMP_DIR/${id}.json" "$length_ms" "$prompt" <<'PY'
import json, sys
out, length_ms, prompt = sys.argv[1], int(sys.argv[2]), sys.argv[3]
json.dump({
    "prompt": prompt,
    "music_length_ms": length_ms,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
PY

  curl -s -X POST "https://api.elevenlabs.io/v1/music" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary @"$TMP_DIR/${id}.json" \
    -o "$TMP_DIR/${id}.mp3"

  if ! is_audio "$TMP_DIR/${id}.mp3"; then
    echo "ERROR: la API no devolvió audio para ${id}. Respuesta:" >&2
    sed 's/^/    /' "$TMP_DIR/${id}.mp3" >&2
    return 1
  fi

  mkdir -p "$(dirname "$out")"
  # backup de la cama anterior, si la había
  if [[ -f "$out" ]]; then
    cp "$out" "${out%.wav}_prev.wav.bak"
  fi
  ffmpeg -v error -y -i "$TMP_DIR/${id}.mp3" -ar 44100 -ac 2 -sample_fmt s16 "$out"

  local dur
  dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$out")"
  echo "  ✓ $out (${dur}s)"

  # actualiza (o añade) la línea del manifest para este id, si el proyecto usa uno
  if [[ -f "$MANIFEST" || -d "$(dirname "$MANIFEST")" ]]; then
    python3 - "$MANIFEST" "$id" "$out" "$dur" "$prompt" "$PROJ" <<'PY'
import json, pathlib, sys
manifest_path, track_id, out_path, dur, prompt, proj = sys.argv[1:7]
manifest_path = pathlib.Path(manifest_path)
proj = pathlib.Path(proj)
rel = str(pathlib.Path(out_path).relative_to(proj))

lines = []
if manifest_path.exists():
    lines = [l for l in manifest_path.read_text(encoding="utf-8").splitlines() if l.strip()]

entry = {
    "id": track_id, "type": "bgm", "path": rel, "source": "generate",
    "description": prompt[:120], "duration": round(float(dur), 1),
    "provenance": {"provider": "elevenlabs.music", "model": "eleven-music-v1", "prompt": prompt},
}

kept, replaced = [], False
for l in lines:
    try:
        obj = json.loads(l)
    except json.JSONDecodeError:
        kept.append(l); continue
    if obj.get("id") == track_id:
        kept.append(json.dumps(entry, ensure_ascii=False)); replaced = True
    else:
        kept.append(l)
if not replaced:
    kept.append(json.dumps(entry, ensure_ascii=False))

manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
PY
  fi
}

python3 - "$CONFIG" "$WHICH" "$TMP_DIR" "$PROJ" <<'PY'
import json, pathlib, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
which, tmp, proj = sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
moods = [m for m in cfg["moods"] if which in ("all", "both") or m["id"] == which]
if not moods:
    sys.exit(f"ERROR: ningún mood con id '{which}' en {sys.argv[1]}")
(pathlib.Path(tmp) / "moods.txt").write_text(
    "\n".join(f"{m['id']}\t{proj / m['file']}\t{m['length_ms']}\t{m['prompt']}" for m in moods),
    encoding="utf-8")
PY

while IFS=$'\t' read -r id out length_ms prompt; do
  generate_track "$id" "$out" "$length_ms" "$prompt"
done < "$TMP_DIR/moods.txt"

echo
echo "siguiente paso: python3 montar_musica.py <version>   (desde narration/, monta la pieza completa)"
