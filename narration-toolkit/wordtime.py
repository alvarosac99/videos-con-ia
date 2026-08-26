#!/usr/bin/env python3
"""En qué segundo del VÍDEO se dice una frase concreta.

    ./wordtime.py v1 "la frase exacta que buscas"

Busca la frase en la alineación forzada y devuelve el instante ya sumado el
hueco del hook (por defecto 3.5s, ajusta HOOK si tu composición usa otro),
que es el número que se pone en el timeline de GSAP. Sirve para clavar cada
beat de una escena en la palabra exacta que lo justifica, en vez de repartir
a ojo.
"""
import json
import os
import pathlib
import re
import sys

HOOK = float(os.environ.get("HOOK", "3.5"))
HERE = pathlib.Path(__file__).resolve().parent


def norm(s):
    s = s.lower()
    for a, b in zip("áéíóúü", "aeiouu"):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9ñ ]", "", s)


def main():
    version, frase = sys.argv[1], " ".join(sys.argv[2:])
    toks = [w for w in json.load(open(HERE / f"narration_{version}.alignment.json",
                                     encoding="utf-8"))["words"] if w["text"].strip()]
    palabras = [norm(w["text"]) for w in toks]
    objetivo = norm(frase).split()

    for i in range(len(palabras) - len(objetivo) + 1):
        if palabras[i:i + len(objetivo)] == objetivo:
            ini, fin = toks[i]["start"] + HOOK, toks[i + len(objetivo) - 1]["end"] + HOOK
            print(f"{ini:.2f}  →  {fin:.2f}   \"{frase}\"")
            return
    print(f"no encontrada: \"{frase}\"", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
