#!/usr/bin/env python3
"""Reparte los párrafos del guion en bloques de ~500 caracteres.

eleven_v3 es inestable por debajo de unos 250 caracteres, así que no vale
trocear párrafo a párrafo: se agrupan párrafos enteros hasta llegar al
objetivo, sin partir ninguno por la mitad.
"""
import os
import pathlib
import re
import sys

OBJETIVO = 500
MINIMO = 250


def main():
    src, work = sys.argv[1], pathlib.Path(sys.argv[2])
    paras = [p.strip() for p in re.split(r"\n\s*\n", open(src, encoding="utf-8").read().strip()) if p.strip()]

    # SPLIT_AFTER="3,8" corta DESPUÉS de esos índices de párrafo (0-based) en
    # vez del agrupado genérico por tamaño. Úsalo cuando los cortes tienen
    # que caer en pivotes narrativos concretos (p.ej. donde ya hay un cambio
    # de música/escena que disimula el salto de prosodia entre peticiones,
    # que eleven_v3 no puede evitar porque no soporta contexto entre bloques).
    forzado = os.environ.get("SPLIT_AFTER", "").strip()
    if forzado:
        cortes = sorted(int(x) for x in forzado.split(","))
        chunks, cur = [], []
        for i, p in enumerate(paras):
            cur.append(p)
            if i in cortes:
                chunks.append("\n\n".join(cur))
                cur = []
        if cur:
            chunks.append("\n\n".join(cur))
    else:
        chunks, cur = [], []
        for p in paras:
            cur.append(p)
            if sum(len(x) for x in cur) >= OBJETIVO:
                chunks.append("\n\n".join(cur))
                cur = []
        if cur:
            cola = "\n\n".join(cur)
            if chunks and len(cola) < MINIMO:
                chunks[-1] += "\n\n" + cola      # una cola corta se pega al bloque anterior
            else:
                chunks.append(cola)

    for i, c in enumerate(chunks):
        (work / f"chunk{i:02d}.txt").write_text(c, encoding="utf-8")
    print(f"{len(paras)} párrafos → {len(chunks)} bloques "
          f"({', '.join(str(len(c)) for c in chunks)} caracteres)")


if __name__ == "__main__":
    main()
