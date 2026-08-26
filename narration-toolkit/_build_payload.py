#!/usr/bin/env python3
"""Construye el payload de TTS de un bloque (helper de generate-chunked.sh)."""
import json
import os
import pathlib
import re
import sys


def main():
    chunk, out, work, idx = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]), int(sys.argv[4])

    body = {
        "text": open(chunk, encoding="utf-8").read().strip(),
        "model_id": "eleven_v3",
        "voice_settings": {
            # style 0.20: por encima de ~0.25 sobreactúa. 0.0 ("Creative")
            # suena erráticamente plano: la voz pierde consistencia y acaba
            # leyendo de corrido. 0.30-0.50 es el rango donde v3 interpreta
            # de verdad las etiquetas.
            "stability": float(os.environ.get("EL_STABILITY", "0.35")),
            "style": float(os.environ.get("EL_STYLE", "0.20")),
            "similarity_boost": 0.75,
            "use_speaker_boost": True,
        },
    }

    # eleven_v3 rechaza previous_text / next_text (unsupported_model), así que
    # los bloques van sin contexto entre sí. Los cortes caen entre párrafos.
    del work, idx

    json.dump(body, open(out, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
