#!/usr/bin/env python3
"""Monta la pieza musical completa del vídeo a partir de music-config.json.

    python3 montar_musica.py v1

Técnica (nace de un vídeo con un giro narrativo claro: primera mitad seria,
segunda mitad ligera — una sola cama para todo el vídeo sonaba a propaganda
infantil o a documental funerario; dos camas cruzadas en el pivote resuelven
las dos quejas a la vez. Generaliza a 1 o 2 moods; para timelines con más
giros, edita este script o encadena varias pasadas):

  1. Con 2 moods en music-config.json: el primero suena de 0 al pivote (+
     medio crossfade), el segundo del pivote en adelante. Con 1 solo mood,
     se loopea sin más para toda la duración.
  2. Acentos SFX en los tiempos de `highlights` (puedes usar "pivot",
     "pivot-1.0", etc. como expresión) + un whoosh en cada corte de escena
     (`scene_cut_sfx`) + cues opcionales en `animation_anchor_groups`
     (sincronizados a la primera aparición de un id en el timeline GSAP).
  3. Automatización de volumen: ducking guiado por la alineación forzada de
     la voz (no por detección de señal), con un pico breve en cada acento.

Ver config/music-config.example.json (raíz del kit) para el formato completo.
"""
import ast
import json
import operator
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent
INDEX = PROJ / "index.html"

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg}


def eval_expr(expr, pivot):
    """Evalúa expresiones simples tipo 'pivot-1.0' de music-config.json."""
    if isinstance(expr, (int, float)):
        return float(expr)
    node = ast.parse(str(expr).replace("pivot", str(pivot)), mode="eval").body

    def _ev(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.BinOp):
            return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return _OPS[type(n.op)](_ev(n.operand))
        raise ValueError(f"expresión no soportada: {expr}")
    return float(_ev(node))


def duracion(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration", "-of", "default=nw=1:nk=1", str(f)],
                                capture_output=True, text=True).stdout.strip())


def loopear_tramo(bed, dur_objetivo, destino, fade_in=0.0, fade_out=0.0):
    """Loopea `bed` (con crossfades entre copias) hasta cubrir dur_objetivo."""
    dur_bed = duracion(bed)
    copias = int(dur_objetivo / dur_bed) + 2
    xf = 2.0
    ins, filtros, prev = [], [], "[0:a]"
    for _ in range(copias):
        ins += ["-i", str(bed)]
    for i in range(1, copias):
        out = f"[x{i}]"
        filtros.append(f"{prev}[{i}:a]acrossfade=d={xf}:c1=tri:c2=tri{out}")
        prev = out
    fade = []
    if fade_in:
        fade.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out:
        fade.append(f"afade=t=out:st={dur_objetivo - fade_out}:d={fade_out}")
    cadena = ",".join(fade) if fade else "anull"
    filtros.append(f"{prev}{cadena}[fin]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(filtros),
                    "-map", "[fin]", "-t", str(dur_objetivo), str(destino)], check=True)


def cruzar(a, b, destino, cruce):
    """Une a→b con crossfade, resultado = dur(a) + dur(b) - cruce."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b),
                    "-filter_complex", f"[0:a][1:a]acrossfade=d={cruce}:c1=tri:c2=tri[fin]",
                    "-map", "[fin]", str(destino)], check=True)


def composition_id(html):
    m = re.search(r'data-composition-id="([^"]+)"', html)
    if not m:
        sys.exit('ERROR: no encuentro data-composition-id="..." en index.html')
    return m.group(1)


def fronteras_de_escena(html):
    """Momento de cada corte de escena, sacado del propio index.html."""
    starts = sorted(float(m) for m in re.findall(r'class="clip" id="[\w-]+" data-start="([\d.]+)"', html))
    return [t for t in starts if t > 0.05]   # el arranque en 0 no es un "corte"


def tiempo_de(html, selector_id, ventana=500):
    """Busca `"#id"` en el <script> del timeline y saca el tiempo absoluto (el
    último número) de esa misma llamada .fromTo/.to — estilo estándar de
    HyperFrames: `..., {...}, {...}, TIEMPO)`."""
    i = html.find(f'"#{selector_id}"')
    if i < 0:
        return None
    m = re.search(r',\s*([\d.]+)\)', html[i:i + ventana])
    return float(m.group(1)) if m else None


def capas_de_animacion(html, grupos):
    capas = []
    for g in grupos:
        for sid in g["ids"]:
            t = tiempo_de(html, sid)
            if t is not None:
                capas.append((t, g["sfx"], g["gain_db"]))
    return capas


def con_acentos(base, destino, total, sfx_dir, cortes, scene_cut_sfx, highlights, extra):
    capas = [(t, scene_cut_sfx["file"], scene_cut_sfx["gain_db"]) for t in cortes] + highlights + extra
    ins, filtros, mezclas = ["-i", str(base)], [], ["[0:a]"]
    for i, (t, sfx, db) in enumerate(capas, start=1):
        ins += ["-i", str(sfx_dir / sfx)]
        filtros.append(f"[{i}:a]volume={db}dB,adelay={int(t*1000)}|{int(t*1000)}[a{i}]")
        mezclas.append(f"[a{i}]")
    # normalize=0: por defecto amix divide el volumen entre el número de
    # inputs para evitar clipping — con muchas capas (base + whooshes +
    # acentos + cues) eso aplasta la música de fondo muy por debajo de la
    # voz. Sumamos sin normalizar y limitamos el pico al final en vez de
    # dejar que amix aplaste TODA la mezcla por tener muchas capas de SFX.
    filtros.append(f"{''.join(mezclas)}amix=inputs={len(mezclas)}:duration=first:dropout_transition=0:normalize=0,"
                   f"alimiter=limit=0.95,"
                   f"atrim=0:{total}[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(filtros),
                    "-map", "[out]", str(destino)], check=True)


def main():
    version = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "v1"
    config_path = next((pathlib.Path(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--config=")),
                        HERE / "music-config.json")
    if not config_path.exists():
        sys.exit(f"ERROR: no existe {config_path} — copia config/music-config.example.json de la "
                 f"raíz del kit y ajústalo a tu proyecto")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))

    html = INDEX.read_text(encoding="utf-8")
    cid = cfg.get("composition_id") or composition_id(html)
    total = float(re.search(rf'data-composition-id="{re.escape(cid)}"[^>]*?data-duration="([\d.]+)"', html).group(1))

    hook = float(cfg.get("hook", 3.5))
    pivot = eval_expr(cfg.get("pivot", total / 2), 0)
    crossfade = float(cfg.get("crossfade", 4.0))
    sfx_dir = PROJ / cfg.get("sfx_dir", ".media/audio/sfx")
    out = PROJ / cfg["moods"][0]["file"].rsplit("/", 1)[0] / "bed_full.wav" if cfg["moods"] else None

    moods = cfg["moods"]
    if not moods:
        sys.exit("ERROR: music-config.json no tiene ningún mood en 'moods'")

    highlights = [(eval_expr(h["at"], pivot), h["sfx"], h["gain_db"]) for h in cfg.get("highlights", [])]

    if len(moods) == 1:
        bed = PROJ / moods[0]["file"]
        tmp_cruzado = HERE / "_full.wav"
        print(f"mood único: {moods[0]['id']} en bucle para {total:.1f}s")
        loopear_tramo(bed, total, tmp_cruzado, fade_in=moods[0].get("fade_in", 0.0),
                      fade_out=moods[0].get("fade_out", 0.0))
    else:
        if len(moods) > 2:
            print(f"aviso: {len(moods)} moods en config, este script solo encadena los dos primeros "
                  f"en el pivote ({moods[0]['id']} → {moods[1]['id']})")
        m0, m1 = moods[0], moods[1]
        dur_0 = pivot + crossfade / 2
        dur_1 = total - pivot + crossfade / 2
        tmp_0, tmp_1 = HERE / "_mood0.wav", HERE / "_mood1.wav"
        tmp_cruzado = HERE / "_cruzado.wav"
        print(f"tramo 1: 0-{pivot:.1f}s ({m0['id']})")
        loopear_tramo(PROJ / m0["file"], dur_0, tmp_0, fade_in=m0.get("fade_in", 0.0))
        print(f"tramo 2: {pivot:.1f}-{total:.1f}s ({m1['id']})")
        loopear_tramo(PROJ / m1["file"], dur_1, tmp_1, fade_out=m1.get("fade_out", 0.0))
        print(f"cruzando en el pivote ({crossfade:.1f}s de crossfade)...")
        cruzar(tmp_0, tmp_1, tmp_cruzado, crossfade)
        tmp_0.unlink(); tmp_1.unlink()

    cortes = fronteras_de_escena(html)
    extra = capas_de_animacion(html, cfg.get("animation_anchor_groups", []))
    scene_cut_sfx = cfg.get("scene_cut_sfx", {"file": "whoosh-short.mp3", "gain_db": -14})
    print(f"añadiendo {len(cortes)} whooshes de transición + {len(highlights)} acentos narrativos "
          f"+ {len(extra)} cues de animación...")
    out.parent.mkdir(parents=True, exist_ok=True)
    con_acentos(tmp_cruzado, out, total, sfx_dir, cortes, scene_cut_sfx, highlights, extra)
    tmp_cruzado.unlink()

    # ---- ducking guiado por la alineación real de la voz ------------------
    duck_cfg = cfg.get("ducking", {})
    BASE = float(duck_cfg.get("base_volume", 0.66))
    DUCK = float(duck_cfg.get("duck_volume", 0.38))
    ATAQUE = float(duck_cfg.get("attack", 0.25))
    SOLTAR = float(duck_cfg.get("release", 0.60))
    HUECO_MIN = float(duck_cfg.get("min_gap", 1.10))
    BOOST = float(duck_cfg.get("highlight_boost", 0.42))
    align_version = duck_cfg.get("alignment_version", version)

    align_path = HERE / f"narration_{align_version}.alignment.json"
    if not align_path.exists():
        sys.exit(f"ERROR: falta {align_path} — pasa antes ./align.sh {align_version}")
    al = json.loads(align_path.read_text(encoding="utf-8"))
    pal = [x for x in al["words"] if x["text"].strip()]
    bloques, ini, fin = [], pal[0]["start"], pal[0]["end"]
    for a, b in zip(pal, pal[1:]):
        if b["start"] - a["end"] >= HUECO_MIN:
            bloques.append((ini, a["end"]))
            ini = b["start"]
        fin = b["end"]
    bloques.append((ini, fin))

    puntos = [(0.0, BASE)]
    for a, b in bloques:
        ta, tb = a + hook, b + hook
        puntos += [(max(0.0, ta - ATAQUE), BASE), (ta, DUCK), (tb, DUCK), (tb + SOLTAR, BASE)]
    puntos.append((total, BASE))
    puntos.sort()

    def valor_en(t):
        prev = puntos[0]
        for q in puntos:
            if q[0] >= t:
                if q[0] == prev[0]:
                    return q[1]
                f = (t - prev[0]) / (q[0] - prev[0])
                return prev[1] + f * (q[1] - prev[1])
            prev = q
        return prev[1]

    # los acentos (riser/pop/chime...) van mezclados dentro de la propia
    # cama, así que necesitan un pico breve de volumen para oírse aunque
    # estemos duckeados
    for t, _, _ in highlights:
        alto = min(1.0, valor_en(t) + BOOST)
        puntos += [(max(0.0, t - 0.12), valor_en(t - 0.12)), (t, alto), (t + 0.45, valor_en(t + 0.45))]
    puntos.sort()

    print(f"  ducking: {len(bloques)} bloques de habla · música {DUCK} bajo la voz / {BASE} en los huecos")

    lane = {"version": 1, "lanes": [{"target": "volume",
                                     "points": [{"t": round(t, 2), "v": round(v, 3)} for t, v in puntos]}]}
    attr = json.dumps(lane, separators=(",", ":")).replace('"', "&quot;")

    rel_out = str(out.relative_to(PROJ))
    html = re.sub(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="music-bed"[^>]*?src=")[^"]*(")',
                  rf'\g<1>{rel_out}\g<2>', html)
    html = re.sub(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="music-bed"[^>]*?data-duration=")[\d.]+(")',
                  rf'\g<1>{total:.2f}\g<2>', html)
    html, n = re.subn(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="music-bed"[^>]*?)(\s*data-automation="[^"]*")?(></audio>)',
                      lambda m: f'{m.group(1)} data-automation="{attr}"{m.group(3)}', html)
    if not n:
        raise SystemExit('no encuentro <audio id="music-bed">')
    INDEX.write_text(html, encoding="utf-8")

    print(f"\n{out}  ({duracion(out):.1f}s)")
    if len(moods) >= 2:
        print(f"  {moods[0]['id']} 0-{pivot:.1f}s -> cruce -> {moods[1]['id']} {pivot:.1f}-{total:.1f}s")
    print(f"  {len(highlights)} acentos")
    print("  siguiente: npx hyperframes check   (desde la raíz del proyecto)")


if __name__ == "__main__":
    main()
