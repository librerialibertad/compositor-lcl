# -*- coding: utf-8 -*-
"""
Activos del compositor, sin binarios embebidos:
- Icono de WhatsApp: assets/whatsapp.svg (lo descarga el Dockerfile desde Font Awesome)
  y se convierte a PNG blanco con cairosvg al arrancar.
- Logo LCL: NO va embebido. N8N lo envia en cada peticion como logo_b64
  (el archivo original vive en Google Drive / carpeta Auto Post: Logo Transparente.png).
"""
import base64
import os

import cairosvg

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RUTA_SVG = os.path.join(_AQUI, "assets", "whatsapp.svg")


def _icono_wa_b64():
    svg = open(_RUTA_SVG).read().replace("<path ", '<path fill="white" ')
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=110, output_height=110)
    return base64.b64encode(png).decode()


try:
    ICONO_WA_B64 = _icono_wa_b64()
except Exception:
    ICONO_WA_B64 = ""  # componer.py tolera icono ausente: pone el numero sin icono


def cargar_logo():
    raise RuntimeError(
        "No hay logo embebido en el servicio: la peticion a /componer debe incluir logo_b64. "
        "El logo oficial es 'Logo Transparente.png' (Drive / carpeta Auto Post)."
    )
