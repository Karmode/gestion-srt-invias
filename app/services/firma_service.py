"""Procesamiento y persistencia de firmas de usuario.

La firma que sube el usuario (foto/scan sobre papel claro) se convierte en un PNG
con fondo transparente, trazo recoloreado a tinta uniforme, recortado y redimensionado.
Solo se guarda el PNG procesado (unos pocos KB), nunca la imagen original.
"""

import io
from datetime import datetime, timezone

import numpy as np
from bson import ObjectId
from PIL import Image, ImageOps

from app.repositories.firma_repo import FirmaRepositorio

# ── Parámetros de procesamiento (ajustables) ──────────────────────────────────
MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # tope del archivo de entrada
MAX_ALTO_PX = 200                    # alto máximo del PNG resultante (solo reduce)
UMBRAL_LUMINANCIA = 200              # 0-255: por encima => fondo (transparente)
RAMPA = 40                           # ancho de la transición suave del borde
COLOR_TINTA = (20, 30, 70)           # tinta uniforme (azul oscuro tipo bolígrafo)
PREVIEW_CASILLA = 12                 # tamaño en px de cada cuadro del tablero de transparencia
PREVIEW_C1 = (255, 255, 255)         # color claro del tablero
PREVIEW_C2 = (205, 209, 217)         # color gris del tablero
FORMATOS_VALIDOS = {"png", "jpg", "jpeg"}


def procesar_firma(datos: bytes) -> bytes:
    """Convierte la imagen de entrada en un PNG con fondo transparente y tinta uniforme."""
    img = Image.open(io.BytesIO(datos))
    img = ImageOps.exif_transpose(img).convert("RGB")

    gris = np.asarray(img.convert("L"), dtype=np.float32)
    # alpha: opaco donde el píxel es oscuro (trazo), transparente donde es claro (papel),
    # con una rampa suave para que el borde no quede dentado.
    alpha = np.clip((UMBRAL_LUMINANCIA - gris) / RAMPA, 0.0, 1.0)
    alpha = (alpha * 255).astype(np.uint8)

    alto, ancho = alpha.shape
    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = COLOR_TINTA
    rgba[..., 3] = alpha
    out = Image.fromarray(rgba, mode="RGBA")

    # Recortar a la zona con trazo (ignora ruido tenue de la rampa).
    mascara = out.getchannel("A").point(lambda p: 255 if p > 20 else 0)
    bbox = mascara.getbbox()
    if bbox:
        out = out.crop(bbox)

    # Redimensionar a alto máximo (solo reducir).
    if out.height > MAX_ALTO_PX:
        ratio = MAX_ALTO_PX / out.height
        out = out.resize((max(1, int(out.width * ratio)), MAX_ALTO_PX), Image.LANCZOS)

    buffer = io.BytesIO()
    out.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def componer_sobre_fondo(png_bytes: bytes) -> bytes:
    """Compone el PNG (con transparencia) sobre un tablero ajedrezado, para la vista previa.

    El patrón de cuadros se ve a través de las zonas transparentes y, a la vez, da
    contraste a la tinta oscura. Si el fondo del papel no se eliminó bien, un bloque
    sólido tapa los cuadros: así el usuario detecta visualmente que la firma quedó mal.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    ancho, alto = img.size

    yy, xx = np.mgrid[0:alto, 0:ancho]
    patron = ((xx // PREVIEW_CASILLA + yy // PREVIEW_CASILLA) % 2).astype(bool)
    tablero = np.empty((alto, ancho, 3), dtype=np.uint8)
    tablero[patron] = PREVIEW_C2
    tablero[~patron] = PREVIEW_C1
    base = Image.fromarray(tablero, "RGB").convert("RGBA")

    comp = Image.alpha_composite(base, img).convert("RGB")
    buffer = io.BytesIO()
    comp.save(buffer, format="PNG")
    return buffer.getvalue()


def validar_y_procesar(nombre_archivo: str, datos: bytes) -> bytes:
    """Valida formato/tamaño y devuelve el PNG procesado, o lanza ValueError."""
    if not datos:
        raise ValueError("El archivo está vacío.")
    if len(datos) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen supera el tamaño máximo permitido (5 MB).")
    ext = nombre_archivo.rsplit(".", 1)[-1].lower() if "." in nombre_archivo else ""
    if ext not in FORMATOS_VALIDOS:
        raise ValueError("Formato no admitido. Sube un archivo PNG o JPG.")
    try:
        return procesar_firma(datos)
    except ValueError:
        raise
    except Exception:
        raise ValueError("No se pudo procesar la imagen. Verifica que sea un archivo válido.")


class FirmaService:
    def __init__(self) -> None:
        self.repo = FirmaRepositorio()

    def obtener_imagen(self, usuario_id: str):
        """PNG procesado en bytes, o None si el usuario no tiene firma."""
        doc = self.repo.obtener(usuario_id)
        if doc and doc.get("imagen"):
            return bytes(doc["imagen"])
        return None

    def tiene_firma(self, usuario_id: str) -> bool:
        return self.repo.obtener(usuario_id) is not None

    def guardar_firma(self, usuario_id: str, nombre_archivo: str, datos: bytes, usuario_actual: str = None) -> bytes:
        procesada = validar_y_procesar(nombre_archivo, datos)
        with Image.open(io.BytesIO(procesada)) as img:
            ancho, alto = img.width, img.height
        self.repo.guardar(usuario_id, {
            "usuario_id": ObjectId(usuario_id),
            "imagen": procesada,
            "ancho": ancho,
            "alto": alto,
            "bytes": len(procesada),
            "actualizado_en": datetime.now(timezone.utc),
            "actualizado_por": usuario_actual,
        })
        return procesada

    def eliminar_firma(self, usuario_id: str) -> None:
        self.repo.eliminar(usuario_id)
