#!/usr/bin/env python3
"""Locuta el guion con la voz clonada de una referencia, en local con la GPU.

    ~/.venvs/f5tts/bin/python clonar.py --prueba
        genera solo el primer párrafo, para oír si el clon vale

    ~/.venvs/f5tts/bin/python clonar.py v1
        genera el guion entero, un fichero por párrafo, y los une con los
        silencios entre párrafos ya puestos

Sin cuota, sin cuenta y sin límite de tomas: se puede repetir las veces que
haga falta. Los párrafos ya generados no se repiten (caché en parts_local_<v>/).

Requiere `chatterbox-tts` instalado (normalmente en un venv aparte, ver el
comando de arriba) y una referencia de voz por registro emocional en
assets/voz-ref/ref_<registro>.wav — qué párrafo usa qué registro se define
en voice-registry.json (ver config/voice-registry.example.json en la raíz
del kit). Sin ese fichero, todos los párrafos usan el registro "neutral".
"""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REFS = HERE.parent / "assets" / "voz-ref"

SILENCIO_ENTRE_PARRAFOS = 0.45   # segundos
SILENCIO_ENTRE_FRASES = 0.14
MAX_PALABRAS = 26                # Chatterbox trunca por encima de esto


def cargar_registro():
    """Chatterbox clona el ESTADO EMOCIONAL del prompt, no solo el timbre.
    Con una única referencia sacada de un pasaje triste, todo el vídeo suena
    deprimido. voice-registry.json mapea cada párrafo a un registro; cada
    registro necesita su propia referencia recortada de la misma grabación."""
    cfg_path = HERE / "voice-registry.json"
    if not cfg_path.exists():
        return {}, "neutral"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in cfg.get("registry", {}).items()}, cfg.get("default", "neutral")


def parrafos(version):
    txt = (HERE / f"narration_{version}.txt").read_text(encoding="utf-8").strip()
    crudos = [p.strip() for p in re.split(r"\n\s*\n", txt) if p.strip()]
    # Chatterbox no interpreta las etiquetas de emoción de ElevenLabs: las
    # leería en alto. Se quitan; la emoción la pone el estilo de la referencia.
    return [re.sub(r"\[[^\]]+\]\s*", "", p).replace("\n", " ").strip() for p in crudos]


def frases(parrafo):
    """Trocea un párrafo en unidades que el modelo pueda decir sin truncar.

    Chatterbox fuerza el final cuando el texto es largo (se le va la alineación
    y salta el detector de repeticiones), así que se le dan frases sueltas. Si
    una frase pasa de MAX_PALABRAS se parte por comas o dos puntos.
    """
    trozos = [f.strip() for f in re.split(r"(?<=[.!?])\s+", parrafo) if f.strip()]
    salida = []
    for f in trozos:
        if len(f.split()) <= MAX_PALABRAS:
            salida.append(f)
            continue
        acumulado = ""
        for cacho in re.split(r"(?<=[,:;])\s+", f):
            if acumulado and len((acumulado + " " + cacho).split()) > MAX_PALABRAS:
                salida.append(acumulado.strip())
                acumulado = cacho
            else:
                acumulado = (acumulado + " " + cacho).strip()
        if acumulado:
            salida.append(acumulado)
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", nargs="?", default="v1")
    ap.add_argument("--prueba", action="store_true", help="solo el primer párrafo")
    ap.add_argument("--ref", default=None, help="fuerza una única referencia")
    ap.add_argument("--exageracion", type=float, default=0.6,
                    help="0.3 sobrio · 0.5 por defecto · 0.8 muy interpretado")
    ap.add_argument("--cfg", type=float, default=0.5,
                    help="más bajo = más despacio y pausado; más alto = más ágil")
    ap.add_argument("--velocidad", type=float, default=1.0,
                    help="reajuste fino de tempo al final (1.08 = un 8%% más rápido)")
    args = ap.parse_args()

    registro, default_reg = cargar_registro()

    def referencia(indice):
        if args.ref:
            return pathlib.Path(args.ref)
        f = REFS / f"ref_{registro.get(indice, default_reg)}.wav"
        return f if f.exists() else REFS / "referencia_corta.wav"

    faltan = [f for f in {referencia(i) for i in registro} if not f.exists()]
    if faltan:
        sys.exit(f"ERROR: faltan referencias: {', '.join(str(f) for f in faltan)}")

    import torch
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"cargando modelo en {dev}...", flush=True)
    modelo = ChatterboxMultilingualTTS.from_pretrained(device=dev)

    ps = parrafos(args.version)
    if args.prueba:
        ps = ps[:1]
    salida = HERE / f"parts_local_{args.version}"
    salida.mkdir(exist_ok=True)

    for i, parrafo in enumerate(ps):
        for j, texto in enumerate(frases(parrafo)):
            destino = salida / f"p{i:02d}_{j:02d}.wav"
            if destino.exists():
                print(f"  · p{i:02d}_{j:02d} ya estaba", flush=True)
                continue
            reg = registro.get(i, default_reg)
            print(f"  → p{i:02d}_{j:02d} [{reg}] {texto[:48]}", flush=True)
            wav = modelo.generate(
                texto,
                language_id="es",
                audio_prompt_path=str(referencia(i)),
                exaggeration=args.exageracion,
                cfg_weight=args.cfg,
            )
            torchaudio.save(str(destino), wav.cpu(), modelo.sr)

    if args.prueba:
        partes = sorted(salida.glob("p00_*.wav"))
        _unir(partes, salida, modelo.sr, salida / "prueba.wav")
        print(f"\n✓ {salida/'prueba.wav'}  ({len(partes)} frases)")
        return

    final = HERE.parent / "assets" / f"narration_{args.version}.mp3"
    _unir(sorted(salida.glob("p[0-9][0-9]_*.wav")), salida, modelo.sr, final,
          velocidad=args.velocidad)
    import subprocess
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(final)],
                         capture_output=True, text=True).stdout.strip()
    print(f"\n✓ {final}  ({float(dur):.1f}s)")
    print(f"  siguiente: ./align.sh {args.version} && python3 duck.py {args.version} && ./retime.py {args.version}")


def _unir(partes, dir_trabajo, sr, destino, velocidad=1.0):
    """Pega las frases con silencio real: corto dentro del párrafo, largo entre párrafos."""
    import subprocess
    for nombre, segundos in (("_corto.wav", SILENCIO_ENTRE_FRASES),
                             ("_largo.wav", SILENCIO_ENTRE_PARRAFOS)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"anullsrc=r={sr}:cl=mono", "-t", str(segundos),
                        str(dir_trabajo / nombre)], check=True)
    lista = dir_trabajo / "_lista.txt"
    with open(lista, "w", encoding="utf-8") as f:
        anterior = None
        for parte in partes:
            parrafo = parte.stem.split("_")[0]
            if anterior is not None:
                hueco = "_largo.wav" if parrafo != anterior else "_corto.wav"
                f.write(f"file '{dir_trabajo / hueco}'\n")
            f.write(f"file '{parte}'\n")
            anterior = parrafo
    codec = ["-c:a", "libmp3lame", "-q:a", "2"] if destino.suffix == ".mp3" else []
    tempo = ["-af", f"atempo={velocidad}"] if abs(velocidad - 1.0) > 0.001 else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lista), *tempo, *codec, str(destino)], check=True)


if __name__ == "__main__":
    main()
