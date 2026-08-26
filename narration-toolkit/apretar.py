#!/usr/bin/env python3
"""Aprieta y masteriza la narración: recorta el aire muerto y limpia la voz.

    python3 apretar.py v1            # sobre assets/narration_v1.mp3
    python3 apretar.py v1 --dry-run  # solo enseña cuánto recortaría

Dos problemas que arregla (típicos de cualquier TTS, no solo ElevenLabs):

1. **Aire muerto.** El TTS deja silencios largos entre frases. Se recortan,
   pero NO todos por igual: los silencios dentro de un mismo párrafo se
   aprietan a INTRA y los que caen entre párrafos (que son los cortes de
   escena, donde hace falta respirar) a INTER, más generoso. El corte se hace
   por el CENTRO del silencio, así se conserva la caída natural de la palabra
   anterior y la entrada de la siguiente.

2. **Voz sin masterizar.** La toma suele salir plana y con algo de retumbe.
   Se le pasa un paso alto, un recorte del barro en 300 Hz, un realce de
   presencia, un de-esser suave y normalización de sonoridad.

Después de esto hay que rehacer la alineación (los tiempos han cambiado):
    ./align.sh v1
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent

INTRA = 0.26   # silencio máximo dentro de un párrafo
INTER = 0.52   # silencio máximo entre párrafos (cortes de escena)

# paso alto + menos barro + presencia + de-esser + sonoridad estándar de web
MASTER = ("highpass=f=70,"
          "equalizer=f=300:t=q:w=1.0:g=-1.5,"
          "equalizer=f=3200:t=q:w=1.2:g=2,"
          "deesser=i=0.4:m=0.5:f=0.5,"
          "loudnorm=I=-16:TP=-1.5:LRA=9")


def palabras_por_parrafo(txt):
    paras = [p.strip() for p in re.split(r"\n\s*\n", txt.strip()) if p.strip()]
    return [len(re.sub(r"\[[^\]]+\]", " ", p).split()) for p in paras]


def main():
    version = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "v1"
    dry = "--dry-run" in sys.argv

    mp3 = PROJ / "assets" / f"narration_{version}.mp3"
    crudo = PROJ / "assets" / f"narration_{version}_crudo.mp3"
    align = HERE / f"narration_{version}.alignment.json"
    txt = HERE / f"narration_{version}.txt"
    for f in (mp3, align, txt):
        if not f.exists():
            sys.exit(f"ERROR: no existe {f}")

    # la fuente es la toma cruda: si ya se apretó una vez, se vuelve a partir
    # de ella, no del resultado (apretar dos veces se come las pausas buenas)
    if not crudo.exists() and not dry:
        crudo.write_bytes(mp3.read_bytes())
        print(f"toma cruda guardada en {crudo.name}")
    # SIEMPRE se lee de la copia cruda: ffmpeg no puede leer y escribir el
    # mismo fichero, y además apretar sobre lo ya apretado se comería las
    # pausas buenas
    fuente = crudo if crudo.exists() else mp3

    d = json.load(open(align, encoding="utf-8"))
    w = [x for x in d["words"] if x["text"].strip()]
    cuentas = palabras_por_parrafo(txt.read_text(encoding="utf-8"))
    if sum(cuentas) != len(w):
        sys.exit(f"ERROR: la alineación trae {len(w)} palabras y el guion {sum(cuentas)}; "
                 f"vuelve a lanzar ./align.sh {version} antes de apretar")

    # índice de la última palabra de cada párrafo -> ese hueco es "entre escenas"
    fin_parrafo, acc = set(), 0
    for n in cuentas:
        acc += n
        fin_parrafo.add(acc - 1)

    cortes, ahorro = [], 0.0
    for i, (a, b) in enumerate(zip(w, w[1:])):
        hueco = b["start"] - a["end"]
        tope = INTER if i in fin_parrafo else INTRA
        if hueco > tope + 0.02:
            medio = (a["end"] + b["start"]) / 2
            cortes.append((medio - tope / 2, medio + tope / 2))
            ahorro += hueco - tope

    print(f"{len(cortes)} silencios recortados · se ahorran {ahorro:.1f}s")
    if dry:
        for ini, fin in cortes[:10]:
            print(f"  quita {fin - ini:.2f}s en {ini:7.2f}")
        return

    # segmentos que SÍ se conservan
    trozos, prev = [], 0.0
    for ini, fin in cortes:
        trozos.append((prev, ini))
        prev = fin
    trozos.append((prev, None))

    partes = []
    for i, (ini, fin) in enumerate(trozos):
        t = f"atrim=start={ini:.4f}" + (f":end={fin:.4f}" if fin else "")
        partes.append(f"[0:a]{t},asetpts=PTS-STARTPTS[s{i}]")
    concat = "".join(f"[s{i}]" for i in range(len(trozos)))
    filtro = ";".join(partes) + f";{concat}concat=n={len(trozos)}:v=0:a=1[j];[j]{MASTER}[out]"

    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fuente),
                    "-filter_complex", filtro, "-map", "[out]",
                    "-c:a", "libmp3lame", "-q:a", "2", str(mp3)], check=True)

    def dur(f):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(f)], capture_output=True, text=True).stdout.strip())

    print(f"\n✓ {mp3.name}: {dur(fuente):.2f}s -> {dur(mp3):.2f}s")
    print(f"  siguiente: ./align.sh {version}")


if __name__ == "__main__":
    main()
