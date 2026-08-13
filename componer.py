# -*- coding: utf-8 -*-
"""
Compositor de artes para posts de Librería Cristiana de Libertad (LCL).
Estampa textos sobre la escena generada por IA siguiendo el patrón Z:
  arriba-izq: título / autor / precio   arriba-der: logo LCL
  abajo-izq:  WhatsApp                  abajo-der:  caja CTA (color de la portada)

Uso como módulo:  componer(escena, logo, portada, titulo, autor, precio, whatsapp, cta) -> PIL.Image
Este módulo NO llama a ninguna IA: es 100% determinista.
"""
import base64
import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from activos import ICONO_WA_B64, cargar_logo

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE_TITULO = os.path.join(AQUI, "fonts", "Anton-Regular.ttf")
FUENTE_TEXTO = os.path.join(AQUI, "fonts", "Montserrat.ttf")


def logo_por_defecto():
    return cargar_logo()

LADO = 1080          # lienzo cuadrado
MARGEN = 40          # margen seguro
ANCHO_TITULO = 620   # ancho máximo del bloque de título
ANCHO_LOGO = 240     # ancho del logo arriba-derecha


def _fuente_anton(pt):
    return ImageFont.truetype(FUENTE_TITULO, pt)


def _fuente_mont(pt, peso="Bold"):
    f = ImageFont.truetype(FUENTE_TEXTO, pt)
    try:
        f.set_variation_by_name(peso)
    except Exception:
        pass
    return f


def _partir_lineas(draw, texto, fuente, ancho_max):
    """Parte el texto en líneas que quepan en ancho_max."""
    palabras = texto.split()
    lineas, actual = [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if draw.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def _ajustar_titulo(draw, texto, ancho_max, pt_inicial=92, pt_minimo=54, max_lineas=3):
    """Baja el tamaño de fuente hasta que el título quepa en max_lineas."""
    for pt in range(pt_inicial, pt_minimo - 1, -4):
        f = _fuente_anton(pt)
        lineas = _partir_lineas(draw, texto, f, ancho_max)
        if len(lineas) <= max_lineas and all(draw.textlength(l, font=f) <= ancho_max for l in lineas):
            return f, lineas, pt
    f = _fuente_anton(pt_minimo)
    return f, _partir_lineas(draw, texto, f, ancho_max)[:max_lineas], pt_minimo


def _texto_con_sombra(base, xy, texto, fuente, relleno=(255, 255, 255, 255),
                      contorno=6, sombra=(3, 3), alfa_sombra=150):
    """Dibuja texto blanco con contorno negro y sombra suave (legible sobre foto)."""
    capa = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    d.text((xy[0] + sombra[0], xy[1] + sombra[1]), texto, font=fuente,
           fill=(0, 0, 0, alfa_sombra), stroke_width=contorno, stroke_fill=(0, 0, 0, alfa_sombra))
    capa = capa.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(capa)
    d.text(xy, texto, font=fuente, fill=relleno, stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    base.alpha_composite(capa)


def _color_acento(portada, por_defecto=(30, 30, 90)):
    """Color dominante saturado de la portada; se oscurece si es muy claro."""
    try:
        im = portada.convert("RGB").resize((60, 60))
        pal = im.quantize(colors=8).convert("RGB").getcolors(3600)
        pal.sort(key=lambda c: -c[0])
        mejor, mejor_sat = por_defecto, -1
        for cuenta, (r, g, b) in pal:
            mx, mn = max(r, g, b), min(r, g, b)
            sat = (mx - mn) / max(mx, 1)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if 25 < lum < 235 and sat * cuenta > mejor_sat:
                mejor_sat, mejor = sat * cuenta, (r, g, b)
        r, g, b = mejor
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if lum > 150:  # muy claro para texto blanco: oscurecer 35%
            r, g, b = int(r * 0.65), int(g * 0.65), int(b * 0.65)
        return (r, g, b)
    except Exception:
        return por_defecto


def componer(escena, logo, portada, titulo, autor, precio, whatsapp, cta):
    """
    escena  : PIL.Image  (foto IA, cualquier tamaño; se recorta a cuadrado 1080)
    logo    : PIL.Image RGBA (logo blanco con transparencia)
    portada : PIL.Image  (solo para extraer el color de acento) o None
    titulo, autor, precio, whatsapp, cta : str  (autor puede ser "")
    Devuelve PIL.Image RGB 1080x1080.
    """
    # --- lienzo: escena recortada a cuadrado y escalada a 1080 ---
    im = escena.convert("RGB")
    lado_min = min(im.size)
    cx, cy = im.width // 2, im.height // 2
    im = im.crop((cx - lado_min // 2, cy - lado_min // 2,
                  cx + lado_min // 2, cy + lado_min // 2)).resize((LADO, LADO), Image.LANCZOS)
    base = im.convert("RGBA")
    d = ImageDraw.Draw(base)

    acento = _color_acento(portada) if portada else (30, 30, 90)

    # --- arriba-izquierda: título / autor / precio ---
    y = MARGEN
    f_tit, lineas, pt = _ajustar_titulo(d, titulo.upper(), ANCHO_TITULO)
    for linea in lineas:
        _texto_con_sombra(base, (MARGEN, y), linea, f_tit)
        y += int(pt * 1.12)
    if autor:
        y += 6
        f_aut = _fuente_mont(44, "Bold")
        _texto_con_sombra(base, (MARGEN, y), autor, f_aut, contorno=4)
        y += 58
    y += 8
    f_pre = _fuente_anton(80)
    _texto_con_sombra(base, (MARGEN, y), precio, f_pre)

    # --- arriba-derecha: logo ---
    lg = logo.convert("RGBA")
    escala = ANCHO_LOGO / lg.width
    lg = lg.resize((ANCHO_LOGO, int(lg.height * escala)), Image.LANCZOS)
    sombra_lg = Image.new("RGBA", base.size, (0, 0, 0, 0))
    alfa = lg.getchannel("A").point(lambda a: int(a * 0.5))
    neg = Image.new("RGBA", lg.size, (0, 0, 0, 255)); neg.putalpha(alfa)
    sombra_lg.paste(neg, (LADO - MARGEN - lg.width + 3, MARGEN + 3), neg)
    base.alpha_composite(sombra_lg.filter(ImageFilter.GaussianBlur(3)))
    base.alpha_composite(lg, (LADO - MARGEN - lg.width, MARGEN))

    # --- abajo-izquierda: WhatsApp ---
    f_wa = _fuente_mont(56, "ExtraBold")
    alto_wa = 64
    y_wa = LADO - MARGEN - alto_wa
    try:
        ic = Image.open(io.BytesIO(base64.b64decode(ICONO_WA_B64)))
        ic = ic.convert("RGBA").resize((alto_wa, alto_wa), Image.LANCZOS)
        base.alpha_composite(ic, (MARGEN, y_wa))
        x_num = MARGEN + alto_wa + 18
    except Exception:
        x_num = MARGEN
    _texto_con_sombra(base, (x_num, y_wa - 2), whatsapp, f_wa, contorno=4)

    # --- abajo-derecha: caja CTA ---
    texto_cta = cta.upper()
    for pt_cta in (46, 40, 34):
        f_cta = _fuente_mont(pt_cta, "ExtraBold")
        lineas_cta = _partir_lineas(d, texto_cta, f_cta, 360)
        if len(lineas_cta) <= 2:
            break
    ancho_txt = max(d.textlength(l, font=f_cta) for l in lineas_cta)
    alto_linea = int(pt_cta * 1.25)
    pad_x, pad_y = 28, 20
    w_caja = int(ancho_txt) + pad_x * 2
    h_caja = alto_linea * len(lineas_cta) + pad_y * 2
    x0 = LADO - MARGEN - w_caja
    y0 = LADO - MARGEN - h_caja
    caja = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(caja)
    dc.rounded_rectangle((x0 + 4, y0 + 4, x0 + w_caja + 4, y0 + h_caja + 4),
                         radius=14, fill=(0, 0, 0, 110))          # sombra de la caja
    caja = caja.filter(ImageFilter.GaussianBlur(3))
    dc = ImageDraw.Draw(caja)
    dc.rounded_rectangle((x0, y0, x0 + w_caja, y0 + h_caja), radius=14, fill=(*acento, 255))
    ty = y0 + pad_y
    for l in lineas_cta:
        lw = dc.textlength(l, font=f_cta)
        dc.text((x0 + (w_caja - lw) / 2, ty), l, font=f_cta, fill=(255, 255, 255, 255))
        ty += alto_linea
    base.alpha_composite(caja)

    return base.convert("RGB")
