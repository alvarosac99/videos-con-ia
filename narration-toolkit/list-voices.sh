#!/usr/bin/env bash
# Busca voces en ElevenLabs.
#
#   ELEVENLABS_API_KEY=sk_xxx ./list-voices.sh             -> marketplace: jóvenes en español (femeninas)
#   ELEVENLABS_API_KEY=sk_xxx ./list-voices.sh mine        -> las voces de tu cuenta
#   ELEVENLABS_API_KEY=sk_xxx ./list-voices.sh market male -> marketplace, voces masculinas
#
# En modo marketplace descarga las muestras a ./previews/ para que las escuches.
# Cuando elijas una, añádela como alias a voices.env (o pásala suelta):
#   ELEVENLABS_API_KEY=sk_xxx VOICE_ID=<id> ./generate.sh v1

set -euo pipefail

MODE="${1:-market}"
GENDER="${2:-female}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  echo "ERROR: falta ELEVENLABS_API_KEY" >&2; exit 1
fi
if [[ "$ELEVENLABS_API_KEY" == "TU_API_KEY" || "$ELEVENLABS_API_KEY" != sk_* ]]; then
  echo "ERROR: ELEVENLABS_API_KEY no parece una clave real (empiezan por 'sk_')." >&2; exit 1
fi

# ---------------------------------------------------------------- cuenta -----
if [[ "$MODE" == "mine" ]]; then
  curl -s -X GET "https://api.elevenlabs.io/v1/voices" \
    -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
  | python3 - <<'PY'
import json, sys
d = json.load(sys.stdin)
if "voices" not in d:
    print("Respuesta inesperada:"); print(json.dumps(d, indent=2)[:1500]); sys.exit(1)
print(f"{len(d['voices'])} voces en tu cuenta\n")
for v in sorted(d["voices"], key=lambda x: x.get("name","")):
    lab = v.get("labels") or {}
    meta = " · ".join(filter(None, [lab.get("gender"), lab.get("age"),
                                    lab.get("accent"), lab.get("description")]))
    print(f"  {v.get('name')}\n    voice_id: {v.get('voice_id')}")
    if meta: print(f"    {meta}")
    print()
PY
  exit 0
fi

# ----------------------------------------------------------- marketplace -----
echo "Buscando voces jóvenes en español (gender=${GENDER})..."
OUT="$HERE/previews"; mkdir -p "$OUT"

# Varias consultas: acento español de España primero, luego latino, luego
# cualquier voz joven marcada como español. Ajusta LOCALE/language si narras
# en otro idioma.
{
  for LOCALE in "es-ES" "es-MX" ""; do
    URL="https://api.elevenlabs.io/v1/shared-voices?page_size=100&language=es&age=young&gender=${GENDER}"
    [[ -n "$LOCALE" ]] && URL="${URL}&locale=${LOCALE}"
    curl -s -X GET "$URL" -H "xi-api-key: ${ELEVENLABS_API_KEY}"
    echo
  done
} > "$OUT/_raw.jsonl"

python3 - "$OUT" <<'PY'
import json, os, subprocess, sys
out = sys.argv[1]
seen, rows = set(), []
for line in open(f"{out}/_raw.jsonl", encoding="utf-8"):
    line = line.strip()
    if not line: continue
    try: d = json.loads(line)
    except Exception: continue
    if "voices" not in d:
        det = (d.get("detail") or {})
        if det: print("  aviso API:", det.get("message", det));
        continue
    for v in d["voices"]:
        vid = v.get("voice_id")
        if vid in seen: continue
        seen.add(vid); rows.append(v)

if not rows:
    print("\nSin resultados. Prueba: ./list-voices.sh market male")
    sys.exit(0)

# más usadas primero: buena señal de calidad
rows.sort(key=lambda v: -(v.get("cloned_by_count") or 0))
rows = rows[:12]

print(f"\n{len(rows)} candidatas (descargando muestras a previews/)\n")
for i, v in enumerate(rows, 1):
    name, vid = v.get("name","?"), v.get("voice_id","?")
    print(f"  {i:2d}. {name}")
    print(f"      voice_id: {vid}")
    print(f"      {v.get('gender')} · {v.get('age')} · {v.get('accent')} · {v.get('locale')}")
    print(f"      {v.get('descriptive')} · uso: {v.get('use_case')} · usada por {v.get('cloned_by_count') or 0}")
    desc = (v.get("description") or "").replace("\n"," ").strip()[:120]
    if desc: print(f"      {desc}")
    url = v.get("preview_url")
    if url:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:40]
        path = f"{out}/{i:02d}_{safe}.mp3"
        subprocess.run(["curl","-s","-m","30",url,"-o",path], check=False)
        print(f"      muestra: {path}")
    print()

json.dump(rows, open(f"{out}/_candidatas.json","w"), ensure_ascii=False, indent=2)
print("Escúchalas y quédate con una:")
print("  ELEVENLABS_API_KEY=sk_xxx VOICE_ID=<voice_id> ./generate.sh v1")
PY
