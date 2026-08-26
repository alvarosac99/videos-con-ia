#!/usr/bin/env python3
"""Retima la composición a la duración real de una narración.

    ./retime.py v1                 # usa assets/narration_v1.mp3 + narration_v1.txt
    ./retime.py v1 --dry-run       # solo enseña la tabla, no toca index.html
    ./retime.py v1 --dry-run --duration=138   # ensaya con una duración inventada

Reparte la duración real del audio entre las escenas en proporción a las
palabras que narra cada una (o, si hay alineación forzada, usa los tiempos
reales palabra a palabra), y remapea TODAS las posiciones del timeline de
GSAP con una interpolación lineal por tramos vieja→nueva. Así no hay que
retocar a mano cada número del timeline, que es donde salen la mayoría de
fallos de lint tras un cambio de guion.

Qué escena narra qué párrafo se define en `scene-map.json` (junto a este
script, o pásalo con --map=ruta) — ver config/scene-map.example.json en la
raíz del kit para el formato.
"""
import json
import re
import subprocess
import sys
import pathlib
import shutil

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
INDEX = PROJ / "index.html"


def audio_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def paragraphs(txt_path):
    raw = txt_path.read_text(encoding="utf-8").strip()
    return [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]


def words(p):
    return len(re.sub(r"\[[^\]]+\]", " ", p).split())


def aligned_spans(align_path, paras):
    """Tiempos reales (inicio, fin) de cada párrafo a partir de la alineación."""
    d = json.load(open(align_path, encoding="utf-8"))
    toks = [w for w in d.get("words", []) if w.get("text", "").strip()]
    expected = sum(len(re.sub(r"\[[^\]]+\]", " ", p).split()) for p in paras)
    if len(toks) != expected:
        print(f"  aviso: la alineación trae {len(toks)} palabras y el guion {expected}; "
              f"vuelvo a estimar por proporción")
        return None
    spans, i = [], 0
    for para in paras:
        n = len(re.sub(r"\[[^\]]+\]", " ", para).split())
        spans.append((toks[i]["start"], toks[i + n - 1]["end"]))
        i += n
    return spans


def old_bounds(html):
    b = {}
    for m in re.finditer(r'id="([\w-]+)" data-start="([\d.]+)" data-duration="([\d.]+)"', html):
        sid, st, du = m.group(1), float(m.group(2)), float(m.group(3))
        b[sid] = (st, st + du)
    return b


def margen_de_salida(tl_src, bounds, margen=0.15):
    """Aparta los tweens que terminan pegados al final de su escena.

    El checker de HyperFrames (`gsap_exit_missing_hard_kill`) exige que entre
    el fin de un tween de salida y el `tl.set` de hard-kill haya hueco: no le
    vale con que sea matemáticamente <=. Al retimar, cualquier escena que se
    comprima deja algún tween rozando el límite, así que se corrigen aquí en
    vez de a mano.
    """
    finales = sorted(e for _, e in bounds.values())
    tocados = [0]

    def arregla(m):
        head, pos, tail = m.group(1), float(m.group(2)), m.group(3)
        dur = re.search(r"duration:\s*([\d.]+)", m.group(0))
        if not dur:
            return m.group(0)
        fin = pos + float(dur.group(1))
        for lim in finales:
            if 0 <= lim - fin < margen:
                nueva = max(0.0, pos - (margen - (lim - fin)))
                tocados[0] += 1
                return f"{head}{nueva:.2f}{tail}"
        return m.group(0)

    tl_src = re.sub(r"(\.(?:to|fromTo)\([^;]*?,\s*)(\d+(?:\.\d+)?)(\)\s*;?\s*$)",
                    arregla, tl_src, flags=re.M | re.S)
    return tl_src, tocados[0]


def load_scene_map(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    scene_map = [(s["id"], s["paragraphs"]) for s in cfg["scenes"]]
    hook = float(cfg.get("hook", 3.5))
    tail = float(cfg.get("tail", 1.3))
    lead = float(cfg.get("lead", 0.18))
    intro_id = cfg.get("intro_scene")  # id de una escena fija de 0 a HOOK (logo/título antes de la voz), si la hay
    return scene_map, hook, tail, lead, intro_id


def main():
    version = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "v1"
    dry = "--dry-run" in sys.argv
    forced = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--duration=")), None)
    map_path = next((pathlib.Path(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--map=")),
                     HERE / "scene-map.json")

    if not map_path.exists():
        sys.exit(f"ERROR: no existe {map_path} — copia config/scene-map.example.json de la raíz "
                 f"del kit y ajústalo a tu composición")
    SCENE_MAP, HOOK, TAIL, LEAD, INTRO_ID = load_scene_map(map_path)

    txt = HERE / f"narration_{version}.txt"
    mp3 = PROJ / "assets" / f"narration_{version}.mp3"
    needed = (txt, INDEX) if forced else (txt, mp3, INDEX)
    for f in needed:
        if not f.exists():
            sys.exit(f"ERROR: no existe {f}")

    paras = paragraphs(txt)
    need = max(i for _, idx in SCENE_MAP for i in idx) + 1
    if len(paras) != need:
        sys.exit(f"ERROR: el guion tiene {len(paras)} párrafos y {map_path.name} espera {need}. "
                 f"Ajusta 'scenes' en {map_path}.")

    dur = forced if forced else audio_duration(mp3)
    weights = [sum(words(paras[i]) for i in idx) for _, idx in SCENE_MAP]
    total_w = sum(weights)

    align = HERE / f"narration_{version}.alignment.json"
    spans = None
    if align.exists() and "--no-align" not in sys.argv and not forced:
        spans = aligned_spans(align, paras)

    html = INDEX.read_text(encoding="utf-8")
    old = old_bounds(html)

    new = {}
    if spans:
        # Tiempos reales. La frontera NO cae en mitad del silencio: eso deja
        # la imagen nueva sonando en vacío media pausa entera, y como las
        # pausas suelen crecer hacia el final del guion, el corte llegaría a
        # adelantarse a la voz — se percibe como audio desfasado. El corte
        # entra LEAD segundos antes de la primera palabra de la frase
        # siguiente (un pelín por delante, que es lo que se lee como
        # sincronizado), sin comerse nunca la cola de la frase anterior.
        print("modo: tiempos reales de la alineación forzada\n")
        sc = [(sid, spans[idx[0]][0], spans[idx[-1]][1]) for sid, idx in SCENE_MAP]
        cortes = [0.0] * (len(sc) + 1)
        cortes[0] = 0.0
        for i in range(1, len(sc)):
            cortes[i] = max(sc[i - 1][2], sc[i][1] - LEAD)
        cortes[len(sc)] = sc[-1][2]
        for i, (sid, _a, _b) in enumerate(sc):
            new[sid] = (HOOK + cortes[i], HOOK + cortes[i + 1])
    else:
        print("modo: estimación por proporción de palabras\n")
        t = HOOK
        for (sid, _), w in zip(SCENE_MAP, weights):
            span = dur * w / total_w
            new[sid] = (t, t + span)
            t += span
    last = SCENE_MAP[-1][0]
    new[last] = (new[last][0], new[last][1] + TAIL)   # aire final
    if INTRO_ID:
        new[INTRO_ID] = (0.0, HOOK)
    total = new[last][1]

    print(f"audio {mp3.name}{' (simulado)' if forced else ''}: {dur:.2f}s · vídeo: {total:.2f}s "
          f"(antes {max((e for _, e in old.values()), default=total):.2f}s)\n")
    print(f"{'escena':16} {'palabras':>8}  {'antes':>16}  {'ahora':>16}   factor")
    for (sid, _), w in zip(SCENE_MAP, weights):
        if sid not in old:
            continue
        (os_, oe), (ns, ne) = old[sid], new[sid]
        f = (ne - ns) / (oe - os_) if oe != os_ else 1.0
        flag = "  ⚠" if abs(f - 1) > 0.15 else ""
        print(f"{sid:16} {w:8}  {os_:7.2f}–{oe:7.2f}  {ns:7.2f}–{ne:7.2f}   {f:5.2f}{flag}")

    if dry:
        print("\n(dry-run: no se ha tocado index.html)")
        return

    # ---- remapeo de posiciones del timeline -------------------------------
    pieces = sorted(((old[s][0], old[s][1], new[s][0], new[s][1])
                     for s in new if s in old), key=lambda p: p[0])
    if not pieces:
        sys.exit("ERROR: ningún id de scene-map.json aparece en index.html — revisa los ids")

    def remap(x):
        for os_, oe, ns, ne in pieces:
            if os_ - 1e-6 <= x <= oe + 1e-6:
                k = 0 if oe == os_ else (x - os_) / (oe - os_)
                return ns + k * (ne - ns)
        return x * (total / pieces[-1][1])   # fuera de rango: escala global

    head, sep, tail_src = html.partition("window.__timelines")
    tl_src = sep + tail_src

    def sub_pos(m):
        return f"{m.group(1)}{remap(float(m.group(2))):.2f}{m.group(3)}"
    tl_src, n = re.subn(r"(,\s*)(\d+(?:\.\d+)?)(\)\s*;?\s*$)", sub_pos, tl_src, flags=re.M)

    tl_src, nudged = margen_de_salida(tl_src, new)
    html = head + tl_src

    # ---- atributos de las escenas y del root ------------------------------
    def sub_clip(m):
        sid = m.group(1)
        if sid not in new:
            return m.group(0)
        ns, ne = new[sid]
        return f'id="{sid}" data-start="{ns:.2f}" data-duration="{ne - ns:.2f}"'
    html = re.sub(r'id="([\w-]+)" data-start="[\d.]+" data-duration="[\d.]+"', sub_clip, html)
    html = re.sub(r'(data-composition-id="[^"]*"[^>]*?data-duration=")[\d.]+(")',
                  rf'\g<1>{total:.2f}\g<2>', html)
    html = re.sub(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="narration"\s+src="assets/)narration_v\d+\.mp3',
                  rf'\g<1>narration_{version}.mp3', html)

    shutil.copy(INDEX, INDEX.with_suffix(".html.bak"))
    INDEX.write_text(html, encoding="utf-8")
    print(f"\n✓ index.html retimado ({n} posiciones del timeline remapeadas)")
    if nudged:
        print(f"  {nudged} tween(s) de salida apartados del límite de su escena")
    print(f"  copia de seguridad: {INDEX.with_suffix('.html.bak').name}")
    print("  siguiente: npx hyperframes check")


if __name__ == "__main__":
    main()
