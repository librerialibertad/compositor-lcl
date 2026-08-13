# -*- coding: utf-8 -*-
"""
API del Compositor LCL. Un solo endpoint:

POST /componer   (JSON)
{
  "escena_b64":  "<PNG/JPG en base64>",      # obligatorio: foto IA sin textos
  "logo_b64":    "<PNG en base64>",           # opcional: si falta usa assets/logo_lcl_blanco.png
  "portada_b64": "<imagen en base64>",        # opcional: solo para el color del CTA
  "titulo":   "DIOSES QUE FALLAN",
  "autor":    "Timothy Keller",               # puede ir vacío (Biblias, sopas de letras...)
  "precio":   "Q150.00",
  "whatsapp": "5700-4402",
  "cta":      "¡CONSÍGUELO HOY MISMO!"
}
Respuesta: { "imagen_b64": "<PNG 1080x1080 en base64>" }

GET /salud  → {"ok": true}   (para healthcheck de Easypanel)
"""
import base64
import io
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image

from componer import componer, logo_por_defecto

app = FastAPI(title="Compositor LCL", version="1.0")


class Peticion(BaseModel):
    escena_b64: str
    logo_b64: str | None = None
    portada_b64: str | None = None
    titulo: str
    autor: str = ""
    precio: str
    whatsapp: str = "5700-4402"
    cta: str = "¡CONSÍGUELO HOY MISMO!"


def _abrir_b64(dato_b64):
    if "," in dato_b64[:80]:  # tolerar data-URLs "data:image/png;base64,..."
        dato_b64 = dato_b64.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(dato_b64)))


@app.get("/salud")
def salud():
    return {"ok": True}


@app.post("/componer")
def endpoint_componer(p: Peticion):
    try:
        escena = _abrir_b64(p.escena_b64)
    except Exception:
        raise HTTPException(400, "escena_b64 no es una imagen válida")
    try:
        logo = _abrir_b64(p.logo_b64) if p.logo_b64 else logo_por_defecto()
    except Exception:
        raise HTTPException(400, "logo_b64 no es una imagen válida y no hay logo por defecto")
    portada = None
    if p.portada_b64:
        try:
            portada = _abrir_b64(p.portada_b64)
        except Exception:
            portada = None  # el color de acento usa el valor por defecto

    final = componer(escena, logo, portada, p.titulo, p.autor, p.precio, p.whatsapp, p.cta)
    buf = io.BytesIO()
    final.save(buf, format="PNG")
    return {"imagen_b64": base64.b64encode(buf.getvalue()).decode()}
