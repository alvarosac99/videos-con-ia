#!/usr/bin/env python3
"""Baja la música cuando habla la voz, a partir de la alineación forzada.

    ./duck.py v1

Escribe una automatización de volumen (`data-automation`) sobre la pista de
música (`<audio id="music-bed">`). Esto podría hacerlo un análisis de señal
clásico (voiceover carve), pero aquí hay algo mejor: los tiempos exactos de
cada palabra, sacados de la alineación forzada.

Frente a un ducking por detección de señal esto tiene una ventaja: sube la
música en los huecos REALES entre frases, no cuando un detector cree que ha
acabado la voz.

Si ya usas `montar_musica.py` para montar la pieza completa, este script
sobra — monta ducking + acentos + crossfade de moods en un solo paso. Úsalo
suelto solo si tu música es una única cama sin cortes de mood.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
INDEX = HERE.parent / "index.html"

INICIO_VOZ = 3.5     # a qué segundo del vídeo entra la narración (= hook)
ALTO = 0.55          # volumen de la cama cuando nadie habla
BAJO = 0.20          # volumen mientras se habla
BAJADA = 0.35        # lo que tarda en apartarse
SUBIDA = 0.90        # lo que tarda en volver (lento: si sube de golpe canta)
HUECO_MIN = 1.20     # solo sube en pausas largas de verdad: con huecos cortos
                     # la cama bombearía en cada respiración, que canta más
                     # que dejarla estable y baja


def tramos_de_voz(alineacion):
    palabras = [w for w in json.load(open(alineacion, encoding="utf-8"))["words"]
                if w["text"].strip()]
    tramos = [[palabras[0]["start"] + INICIO_VOZ, palabras[0]["end"] + INICIO_VOZ]]
    for w in palabras[1:]:
        ini, fin = w["start"] + INICIO_VOZ, w["end"] + INICIO_VOZ
        if ini - tramos[-1][1] < HUECO_MIN:
            tramos[-1][1] = fin
        else:
            tramos.append([ini, fin])
    return tramos


def envolvente(tramos, total):
    pts = [(0.0, ALTO)]
    for ini, fin in tramos:
        pts.append((max(0.0, ini - BAJADA), ALTO))
        pts.append((ini, BAJO))
        pts.append((fin, BAJO))
        pts.append((min(total, fin + SUBIDA), ALTO))
    pts.append((total, ALTO))
    pts.sort(key=lambda p: (p[0], p[1]))
    limpio = []
    for t, v in pts:
        if limpio and abs(limpio[-1][0] - t) < 0.02:
            limpio[-1] = (t, min(limpio[-1][1], v))
        else:
            limpio.append((t, v))
    return limpio


def composition_id(html):
    m = re.search(r'data-composition-id="([^"]+)"', html)
    if not m:
        sys.exit('ERROR: no encuentro data-composition-id="..." en index.html')
    return m.group(1)


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    alineacion = HERE / f"narration_{version}.alignment.json"
    if not alineacion.exists():
        sys.exit(f"ERROR: falta {alineacion} — pasa antes ./align.sh {version}")

    html = INDEX.read_text(encoding="utf-8")
    cid = composition_id(html)
    total = float(re.search(rf'data-composition-id="{re.escape(cid)}"[^>]*?data-duration="([\d.]+)"', html).group(1))

    tramos = tramos_de_voz(alineacion)
    pts = envolvente(tramos, total)
    lane = {"version": 1, "lanes": [{"target": "volume",
                                     "points": [{"t": round(t, 2), "v": round(v, 3)} for t, v in pts]}]}
    attr = json.dumps(lane, separators=(",", ":")).replace('"', "&quot;")

    html = re.sub(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="music-bed"[^>]*?data-duration=")[\d.]+(")',
                  rf'\g<1>{total:.2f}\g<2>', html)
    nuevo, n = re.subn(r'(<audio(?:\s+data-hf-id="[^"]*")?\s+id="music-bed"[^>]*?)(\s*data-automation="[^"]*")?(></audio>)',
                       lambda m: f'{m.group(1)} data-automation="{attr}"{m.group(3)}', html)
    if not n:
        sys.exit('ERROR: no encuentro el elemento <audio id="music-bed">')
    INDEX.write_text(nuevo, encoding="utf-8")

    habla = sum(f - i for i, f in tramos)
    print(f"{len(tramos)} tramos de voz · {habla:.1f}s hablando de {total:.1f}s")
    print(f"cama a {ALTO} en silencio y {BAJO} bajo la voz · {len(pts)} puntos de automatización")
    print(f"huecos donde la música sube: {len(tramos) - 1}")


if __name__ == "__main__":
    main()
