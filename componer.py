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

from activos import ICONO_WA_B64, LOGO_LCL_B64

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE_TITULO = os.path.join(AQUI, "fonts", "Anton-Regular.ttf")
FUENTE_TEXTO = os.path.join(AQUI, "fonts", "Montserrat.ttf")


def logo_por_defecto():
    return Image.open(io.BytesIO(base64.b64decode(LOGO_LCL_B64)))

LADO = 1080          # lienzo cuadrado
MARGEN = 40          # margen seguro (lados y abajo)
MARGEN_SUP = 26      # arriba se aprovecha más espacio: sube título y logo
ANCHO_LOGO = 240     # ancho del logo arriba-derecha
AIRE_LOGO = 24       # separación mínima entre el título y el logo
# el título usa TODO el ancho disponible hasta justo antes del logo
ANCHO_TITULO = LADO - MARGEN - ANCHO_LOGO - AIRE_LOGO - MARGEN   # = 740
ANCHO_AUTOR = 380    # el autor es dato secundario: banda angosta, nunca sobre la modelo
TOLERANCIA_PELO = 60 # px de la coronilla que SÍ puede pisar el título (pelo sí, cara no)


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


def _mapa_zona_libre(base, bloque=20):
    """Devuelve, por cada banda horizontal de la imagen, la coordenada X donde empieza
    el sujeto (persona/libro). Se apoya en que el fondo va desenfocado y el sujeto en foco:
    el sujeto tiene mucha más energía de bordes. Si una banda no tiene sujeto, devuelve None.
    Es 100% determinista, sin modelos ni dependencias nuevas."""
    import numpy as np
    g = np.asarray(base.convert("L").filter(ImageFilter.GaussianBlur(1)), dtype=float)
    energia = np.abs(np.diff(g, axis=1, prepend=g[:, :1])) + np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    n = LADO // bloque
    h = energia[:n * bloque, :n * bloque].reshape(n, bloque, n, bloque).mean(axis=(1, 3))
    umbral = float(np.percentile(h, 72))
    mapa = []
    for r in range(n):
        fila = h[r]
        borde = None
        for c in range(len(fila) - 2):                      # 3 bloques seguidos = sujeto real, no ruido
            if fila[c] > umbral and fila[c + 1] > umbral and fila[c + 2] > umbral:
                borde = c * bloque
                break
        mapa.append(borde)
    # La coronilla es PELO, y Carlos permite texto sobre el pelo (nunca sobre la cara).
    # Las primeras bandas del sujeto se liberan para no desperdiciar ancho arriba.
    primera = next((r for r, v in enumerate(mapa) if v is not None), None)
    if primera is not None:
        for r in range(primera, min(len(mapa), primera + TOLERANCIA_PELO // bloque)):
            mapa[r] = None
    return mapa, bloque


def _ancho_libre(mapa, bloque, y0, y1, aire=24, minimo=320):
    """Ancho de texto utilizable entre las alturas y0 e y1 sin tocar al sujeto."""
    r0, r1 = max(0, y0 // bloque), min(len(mapa) - 1, y1 // bloque)
    bordes = [mapa[r] for r in range(r0, r1 + 1) if mapa[r] is not None]
    if not bordes:
        return ANCHO_TITULO
    return max(minimo, min(ANCHO_TITULO, min(bordes) - MARGEN - aire))


def _ajustar_titulo(draw, texto, mapa, bloque, y_inicio, pt_inicial=104, pt_minimo=44,
                    max_lineas=3, pt_min_una_linea=60, interlinea=1.04):
    """Busca el mayor tamaño de letra que quepa SIN invadir al sujeto.
    Prefiere 1 línea, luego 2, y solo si hace falta 3 (los artes aprobados de Carlos
    usan 3 líneas sin problema cuando el texto vive en la columna libre).
    El ancho permitido de cada línea depende de la altura donde cae esa línea."""
    for tope in (1, 2, max_lineas):
        pt_piso = pt_min_una_linea if tope == 1 else pt_minimo
        for pt in range(pt_inicial, pt_piso - 1, -2):
            f = _fuente_anton(pt)
            alto_linea = int(pt * interlinea)
            ancho_arriba = _ancho_libre(mapa, bloque, y_inicio, y_inicio + alto_linea)
            lineas = _partir_lineas(draw, texto, f, ancho_arriba)
            if len(lineas) > tope:
                continue
            # cada línea se revisa contra el ancho libre de SU propia altura
            cabe = True
            y = y_inicio
            for l in lineas:
                permitido = _ancho_libre(mapa, bloque, y, y + alto_linea)
                if draw.textlength(l, font=f) > permitido:
                    cabe = False
                    break
                y += alto_linea
            if cabe:
                return f, lineas, pt
    f = _fuente_anton(pt_minimo)
    ancho = _ancho_libre(mapa, bloque, y_inicio, y_inicio + int(pt_minimo * interlinea) * max_lineas)
    return f, _partir_lineas(draw, texto, f, ancho)[:max_lineas], pt_minimo


def _ajustar_una_linea(draw, texto, ancho_max, fuente_fn, pt_inicial, pt_minimo):
    """Encaja un texto en UNA sola línea dentro de ancho_max, bajando el tamaño."""
    for pt in range(pt_inicial, pt_minimo - 1, -2):
        f = fuente_fn(pt)
        if draw.textlength(texto, font=f) <= ancho_max:
            return f, texto, pt
    f = fuente_fn(pt_minimo)
    t = texto
    while t and draw.textlength(t + "…", font=f) > ancho_max:
        t = t[:-1].rstrip()
    return f, (t + "…") if t != texto else texto, pt_minimo


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


def componer(escena, logo, portada, titulo, autor, precio, whatsapp, cta, subtitulo=""):
    """
    escena  : PIL.Image  (foto IA, cualquier tamaño; se recorta a cuadrado 1080)
    logo    : PIL.Image RGBA (logo blanco con transparencia)
    portada : PIL.Image  (solo para extraer el color de acento) o None
    titulo, autor, precio, whatsapp, cta : str  (autor puede ser "")
    subtitulo : str opcional (ej. "RV60"): segunda fila corta debajo del título
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
    # --- arriba-izquierda: bloque de texto ---
    # El espaciado es PROPORCIONAL al tamaño del título, no en píxeles fijos: el título
    # puede salir de 44 a 104 pt y un hueco fijo de 4 px se ve microscópico a 104 pt.
    # Agrupación por proximidad (Gestalt): [TÍTULO + versión] · AUTOR · PRECIO.
    mapa, bloque = _mapa_zona_libre(base)
    f_tit, lineas, pt = _ajustar_titulo(d, titulo.upper(), mapa, bloque, MARGEN_SUP)

    interlinea   = 1.04
    hueco_ver    = int(pt * 0.12)  # la versión pertenece al título: hueco mínimo
    hueco_autor  = int(pt * 0.34)  # frontera de grupo: el autor es otro dato
    hueco_precio = int(pt * 0.50)  # el precio es el segundo imán: necesita aislarse

    alto_tit = int(pt * interlinea) * len(lineas)
    libre_bajo_titulo = _ancho_libre(mapa, bloque, MARGEN_SUP + alto_tit, MARGEN_SUP + alto_tit + 160)
    f_sub = txt_sub = None
    if subtitulo:
        f_sub, txt_sub, pt_sub = _ajustar_una_linea(
            d, subtitulo.upper(), libre_bajo_titulo, _fuente_anton, max(34, int(pt * 0.46)), 30)
    f_aut = txt_aut = None
    if autor:
        f_aut, txt_aut, pt_aut = _ajustar_una_linea(
            d, autor, min(ANCHO_AUTOR, libre_bajo_titulo), lambda p: _fuente_mont(p, "Bold"), 36, 20)
    f_pre = _fuente_anton(80)

    # Si el bloque se pasa de ALTO_BLOQUE_MAX, se encogen SOLO los huecos (nunca las letras),
    # para que con títulos de 2 líneas el precio no se monte sobre el libro.
    def alto_total(h_ver, h_aut, h_pre):
        a = int(pt * interlinea) * len(lineas)
        if f_sub: a += h_ver + int(pt_sub * 1.10)
        if f_aut: a += h_aut + int(pt_aut * 1.10)
        return a + h_pre + 80
    ALTO_BLOQUE_MAX = 470
    factor = 1.0
    while alto_total(int(hueco_ver * factor), int(hueco_autor * factor),
                     int(hueco_precio * factor)) > ALTO_BLOQUE_MAX and factor > 0.3:
        factor -= 0.05
    hueco_ver, hueco_autor, hueco_precio = (int(hueco_ver * factor), int(hueco_autor * factor),
                                            int(hueco_precio * factor))

    y = MARGEN_SUP
    for linea in lineas:
        _texto_con_sombra(base, (MARGEN, y), linea, f_tit)
        y += int(pt * interlinea)
    if f_sub:
        y += hueco_ver
        _texto_con_sombra(base, (MARGEN, y), txt_sub, f_sub)
        y += int(pt_sub * 1.10)
    if f_aut:
        y += hueco_autor
        _texto_con_sombra(base, (MARGEN, y), txt_aut, f_aut, contorno=4)
        y += int(pt_aut * 1.10)
    y += hueco_precio
    _texto_con_sombra(base, (MARGEN, y), precio, f_pre)

    # --- arriba-derecha: logo ---
    lg = logo.convert("RGBA")
    escala = ANCHO_LOGO / lg.width
    lg = lg.resize((ANCHO_LOGO, int(lg.height * escala)), Image.LANCZOS)
    sombra_lg = Image.new("RGBA", base.size, (0, 0, 0, 0))
    alfa = lg.getchannel("A").point(lambda a: int(a * 0.5))
    neg = Image.new("RGBA", lg.size, (0, 0, 0, 255)); neg.putalpha(alfa)
    sombra_lg.paste(neg, (LADO - MARGEN - lg.width + 3, MARGEN_SUP + 3), neg)
    base.alpha_composite(sombra_lg.filter(ImageFilter.GaussianBlur(3)))
    base.alpha_composite(lg, (LADO - MARGEN - lg.width, MARGEN_SUP))

    # --- abajo-derecha: caja CTA (se calcula primero para poder alinear el WhatsApp con ella) ---
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

    # --- abajo-izquierda: WhatsApp, centrado verticalmente contra la caja del CTA ---
    # Los dos objetos tienen alturas muy distintas; alinear por el borde inferior hace que
    # el número "se hunda". Centrarlo con la caja arma una franja inferior equilibrada.
    f_wa = _fuente_mont(56, "ExtraBold")
    alto_wa = 64
    centro_cta = y0 + h_caja // 2
    y_wa = centro_cta - alto_wa // 2
    y_wa = min(y_wa, LADO - MARGEN - alto_wa)      # nunca por debajo del margen seguro
    try:
        ic = Image.open(io.BytesIO(base64.b64decode(ICONO_WA_B64)))
        ic = ic.convert("RGBA").resize((alto_wa, alto_wa), Image.LANCZOS)
        base.alpha_composite(ic, (MARGEN, y_wa))
        x_num = MARGEN + alto_wa + 18
    except Exception:
        x_num = MARGEN
    _texto_con_sombra(base, (x_num, y_wa - 2), whatsapp, f_wa, contorno=4)

    return base.convert("RGB")
