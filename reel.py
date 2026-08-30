# -*- coding: utf-8 -*-
"""
Reel / TikTok del Compositor LCL: convierte la portada de un libro + un guion de texto
en un video vertical narrado (1080x1920), con subtitulos animados estilo LCL y una barra
fija de contacto abajo. Reutiliza las mismas fuentes y el mismo estilo de texto
(_texto_con_sombra, _partir_lineas) que ya usa /componer para las imagenes, asi el reel
se ve de la misma familia visual que el resto del contenido.

Este modulo NO llama a ninguna IA de texto: el guion (que linea decir y en que orden)
lo genera otro paso (n8n / LCL AutoPost). Aqui solo se convierte ese guion en voz
(Microsoft Edge TTS, gratis) y se arma el video de forma 100% deterministica.

Uso como funcion:  generar_reel(portada_bytes, lineas_guion, whatsapp, sitio, voz) -> (bytes_mp4, duracion_seg)
"""
import asyncio
import os
import subprocess
import tempfile

import edge_tts
from PIL import Image, ImageDraw

from componer import _fuente_anton, _partir_lineas, _texto_con_sombra

ANCHO, ALTO = 1080, 1920
VOZ_DEFECTO = "es-GT-MartaNeural"  # voz nativa guatemalteca, gratis (Microsoft Edge TTS)


def _tarjeta_texto(texto, ancho_max=920, pt_inicial=68, pt_minimo=40, max_lineas=3,
                    color_caja=(0, 0, 0, 150)):
    """PNG transparente 1080x1920 con el texto centrado en pantalla, mismo estilo
    (blanco + contorno + sombra) que usan los titulos en /componer."""
    lienzo = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(lienzo)
    lineas, f, pt = [texto], None, pt_inicial
    for pt in range(pt_inicial, pt_minimo - 1, -4):
        f = _fuente_anton(pt)
        lineas = _partir_lineas(d, texto.upper(), f, ancho_max)
        if len(lineas) <= max_lineas:
            break
    alto_linea = int(pt * 1.15)
    alto_bloque = alto_linea * len(lineas)
    y0 = (ALTO - alto_bloque) // 2

    anchos = [d.textlength(l, font=f) for l in lineas]
    ancho_caja = int(max(anchos)) + 90
    caja = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(caja)
    dc.rounded_rectangle(
        ((ANCHO - ancho_caja) // 2, y0 - 26, (ANCHO + ancho_caja) // 2, y0 + alto_bloque + 26),
        radius=22, fill=color_caja,
    )
    lienzo.alpha_composite(caja)

    y = y0
    for l in lineas:
        w = d.textlength(l, font=f)
        _texto_con_sombra(lienzo, ((ANCHO - w) // 2, y), l, f)
        y += alto_linea
    return lienzo


def _barra_inferior(sitio, whatsapp, alto_barra=110, pt=42):
    """Barra fija abajo con el sitio y el WhatsApp, visible todo el video (aunque
    lo vean sin sonido, que es la mayoria en TikTok)."""
    lienzo = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    d = ImageDraw.Draw(lienzo)
    dc = ImageDraw.Draw(lienzo)
    dc.rectangle((0, ALTO - alto_barra, ANCHO, ALTO), fill=(0, 0, 0, 190))
    f = _fuente_anton(pt)
    texto = f"{sitio}   ·   WHATSAPP {whatsapp}"
    w = d.textlength(texto, font=f)
    if w > ANCHO - 60:
        pt2 = int(pt * (ANCHO - 60) / w)
        f = _fuente_anton(pt2)
        w = d.textlength(texto, font=f)
    d.text(((ANCHO - w) // 2, ALTO - alto_barra // 2 - pt // 2), texto, font=f, fill=(255, 255, 255, 255))
    return lienzo


async def _tts_linea(texto, voz, ruta_mp3):
    comunicador = edge_tts.Communicate(texto, voz)
    await comunicador.save(ruta_mp3)


def _duracion_audio(ruta):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ruta],
        capture_output=True, text=True, check=True,
    )
    return float(salida.stdout.strip())


def generar_reel(portada_bytes, lineas_guion, whatsapp="5700-4402", sitio="guatelibros.com",
                  voz=VOZ_DEFECTO):
    """
    portada_bytes : bytes de la portada real del libro (JPG/PNG)
    lineas_guion  : lista de strings, cada una es un "beat" narrado (gancho, presentacion,
                    precio, CTA...). Se narran en orden y cada una tiene su propia tarjeta
                    de texto en pantalla mientras se dice.
    Devuelve (video_bytes_mp4, duracion_seg).
    """
    with tempfile.TemporaryDirectory() as tmp:
        portada_path = os.path.join(tmp, "portada.jpg")
        with open(portada_path, "wb") as f:
            f.write(portada_bytes)

        # 1) una linea de audio por beat (asi la sincronizacion con la tarjeta es exacta,
        #    sin depender de subtitulos aproximados de un audio unico)
        audios, duraciones = [], []
        for i, linea in enumerate(lineas_guion):
            ruta = os.path.join(tmp, f"audio_{i}.mp3")
            asyncio.run(_tts_linea(linea, voz, ruta))
            audios.append(ruta)
            duraciones.append(_duracion_audio(ruta))

        lista_path = os.path.join(tmp, "lista.txt")
        with open(lista_path, "w") as f:
            for a in audios:
                f.write(f"file '{a}'\n")
        audio_final = os.path.join(tmp, "narracion.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_path, "-c", "copy", audio_final],
            check=True, capture_output=True,
        )

        duracion_total = sum(duraciones) + 1.2  # respiro final antes de cortar

        # 2) tarjeta de texto por beat + barra fija
        tarjetas = []
        for i, linea in enumerate(lineas_guion):
            ruta = os.path.join(tmp, f"tarjeta_{i}.png")
            _tarjeta_texto(linea).save(ruta)
            tarjetas.append(ruta)
        barra_path = os.path.join(tmp, "barra.png")
        _barra_inferior(sitio, whatsapp).save(barra_path)

        # 3) ffmpeg: Ken Burns sobre la portada + overlay de cada tarjeta en su ventana
        #    de tiempo + barra fija + audio narrado
        inputs = ["-loop", "1", "-i", portada_path]
        for t in tarjetas:
            inputs += ["-loop", "1", "-i", t]
        inputs += ["-loop", "1", "-i", barra_path, "-i", audio_final]

        filtro_fondo = (
            f"[0:v]scale={int(ANCHO*1.3)}:{int(ALTO*1.3)}:force_original_aspect_ratio=increase,"
            f"crop={int(ANCHO*1.3)}:{int(ALTO*1.3)},"
            f"zoompan=z='min(zoom+0.0006,1.13)':d={int(duracion_total*25)}:s={ANCHO}x{ALTO}:fps=25[bg]"
        )
        partes = [filtro_fondo]
        capa = "bg"
        t_acum = 0.0
        for i, dur in enumerate(duraciones):
            idx_input = i + 1
            nueva = f"ov{i}"
            partes.append(
                f"[{capa}][{idx_input}:v]overlay=0:0:enable='between(t,{t_acum:.2f},{t_acum+dur:.2f})'[{nueva}]"
            )
            capa = nueva
            t_acum += dur
        idx_barra = len(duraciones) + 1
        partes.append(f"[{capa}][{idx_barra}:v]overlay=0:0[vout]")
        filtro_completo = ";".join(partes)

        idx_audio = len(duraciones) + 2
        salida = os.path.join(tmp, "reel.mp4")
        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filtro_completo,
            "-map", "[vout]", "-map", f"{idx_audio}:a",
            "-t", str(duracion_total),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-shortest", salida,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        with open(salida, "rb") as f:
            video_bytes = f.read()
        return video_bytes, duracion_total
