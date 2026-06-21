"""Página: 7 - ADRES · SECOP II · KLIC 2 · AZ Digital · Her. PDF

Acceso rápido a las plataformas externas utilizadas en la gestión de
contratos de la SRTI. Cada tarjeta abre la URL configurada en el .env.
"""

import base64
import os

import streamlit as st

from app.config import configuracion
from app.core.ui_titulos import mostrar_titulo_decorado

st.set_page_config(
    page_title="Herramientas Externas SRTI",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS de tarjetas premium
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Animación de aparición ── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(22px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ── Tarjeta contenedora ── */
    .tool-card {
        background: linear-gradient(145deg, #1e1e2e 0%, #16213e 100%);
        border: 1px solid rgba(255, 140, 0, 0.25);
        border-radius: 18px;
        padding: 28px 20px 22px;
        text-align: center;
        transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
        animation: fadeInUp 0.45s ease both;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }
    .tool-card::before {
        content: "";
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at 60% 20%, rgba(255,140,0,0.07) 0%, transparent 65%);
        pointer-events: none;
    }
    .tool-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 12px 40px rgba(255,140,0,0.22);
        border-color: rgba(255,140,0,0.55);
    }

    /* ── Imagen dentro de la tarjeta ── */
    .tool-card img {
        max-height: 72px;
        max-width: 100%;
        object-fit: contain;
        margin-bottom: 14px;
        filter: drop-shadow(0 3px 8px rgba(0,0,0,0.45));
        transition: transform 0.22s ease;
    }
    .tool-card:hover img {
        transform: scale(1.06);
    }

    /* ── Número de viñeta ── */
    .tool-badge {
        position: absolute;
        top: 12px;
        left: 14px;
        background: rgba(255,140,0,0.15);
        border: 1px solid rgba(255,140,0,0.4);
        color: #FF8C00;
        font-size: 0.72em;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 20px;
        letter-spacing: 0.04em;
    }

    /* ── Nombre de la plataforma ── */
    .tool-name {
        color: #f0f0f0;
        font-size: 1em;
        font-weight: 700;
        margin: 0 0 4px;
        letter-spacing: 0.03em;
    }

    /* ── Descripción corta ── */
    .tool-desc {
        color: #a0a0b8;
        font-size: 0.79em;
        margin: 0 0 16px;
    }

    /* ── Indicador "Clic para abrir" ── */
    .tool-cta {
        display: inline-block;
        background: linear-gradient(90deg, #FF8C00, #FF9800);
        color: #fff;
        font-size: 0.78em;
        font-weight: 600;
        padding: 5px 16px;
        border-radius: 20px;
        letter-spacing: 0.04em;
        box-shadow: 0 3px 12px rgba(255,140,0,0.30);
    }

    /* ── Aviso sin URL ── */
    .tool-nourl {
        color: #f07070;
        font-size: 0.78em;
        font-style: italic;
    }

    /* ── Separador animado ── */
    .fancy-divider {
        height: 3px;
        background: linear-gradient(90deg, transparent, #FF8C00 40%, #FF9800 60%, transparent);
        border-radius: 2px;
        margin: 24px 0 28px;
        opacity: 0.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _img_b64(rel_path: str) -> str:
    """Convierte una imagen del proyecto en base64 para embeber en HTML."""
    abs_path = os.path.join("app", "assets", rel_path)
    if not os.path.exists(abs_path):
        return ""
    with open(abs_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _render_card(
    col,
    badge: str,
    img_file: str,
    name: str,
    description: str,
    url: str,
    delay_ms: int = 0,
) -> None:
    """Renderiza una tarjeta de plataforma en la columna dada."""
    img_b64 = _img_b64(img_file)
    img_tag = (
        f'<img src="data:image/png;base64,{img_b64}" alt="{name}" />'
        if img_b64
        else f'<div style="height:72px;display:flex;align-items:center;justify-content:center;color:#666">Sin imagen</div>'
    )

    if url:
        cta_html = '<span class="tool-cta">🔗 Clic para abrir</span>'
        link_open = f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">'
        link_close = "</a>"
    else:
        cta_html = '<span class="tool-nourl">⚙️ URL no configurada</span>'
        link_open = ""
        link_close = ""

    style_delay = f"animation-delay:{delay_ms}ms;" if delay_ms else ""

    html = f"""
    {link_open}
    <div class="tool-card" style="{style_delay}">
        <span class="tool-badge">{badge}</span>
        {img_tag}
        <div class="tool-name">{name}</div>
        <div class="tool-desc">{description}</div>
        {cta_html}
    </div>
    {link_close}
    """

    with col:
        st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Definición de las plataformas
# ---------------------------------------------------------------------------
PLATAFORMAS = [
    {
        "badge": "7A",
        "img_file": "az_digital.png",
        "name": "AZ Digital",
        "description": "Carpeta digital de gestión documental",
        "url": configuracion.az_digital_url,
    },
    {
        "badge": "7B",
        "img_file": "klic_2.png",
        "name": "KLIC 2",
        "description": "Sistema de correspondencia INVIAS",
        "url": configuracion.klic_2_url,
    },
    {
        "badge": "7C",
        "img_file": "adres.png",
        "name": "ADRES",
        "description": "Administradora de los Recursos del SGSSS",
        "url": configuracion.adres_url,
    },
    {
        "badge": "7D",
        "img_file": "secop.png",
        "name": "SECOP II",
        "description": "Sistema Electrónico de Contratación Pública",
        "url": configuracion.secop_url,
    },
    {
        "badge": "7E",
        "img_file": "pdf_h.png",
        "name": "Her. PDF",
        "description": "Herramienta de edición y gestión de archivos PDF",
        "url": configuracion.pdf_h_url,
    },
]


# ---------------------------------------------------------------------------
# Layout principal
# ---------------------------------------------------------------------------
mostrar_titulo_decorado("🌐 Herramientas Externas — ADRES · SECOP II · KLIC 2 · AZ Digital · PDF")

st.caption(
    "Acceso directo a las plataformas externas utilizadas en la gestión de contratos de la SRTI. "
    "Haz clic en cualquier tarjeta para abrir la plataforma en una nueva pestaña."
)

st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

# --- Primera fila: 3 plataformas ---
cols_row1 = st.columns(3, gap="large")
for i, plat in enumerate(PLATAFORMAS[:3]):
    _render_card(
        col=cols_row1[i],
        badge=plat["badge"],
        img_file=plat["img_file"],
        name=plat["name"],
        description=plat["description"],
        url=plat["url"],
        delay_ms=i * 80,
    )

st.write("")  # Espaciado entre filas

# --- Segunda fila: 2 plataformas centradas ---
col_spacer_l, col_c1, col_c2, col_spacer_r = st.columns([0.5, 1, 1, 0.5], gap="large")
for i, plat in enumerate(PLATAFORMAS[3:]):
    target_col = col_c1 if i == 0 else col_c2
    _render_card(
        col=target_col,
        badge=plat["badge"],
        img_file=plat["img_file"],
        name=plat["name"],
        description=plat["description"],
        url=plat["url"],
        delay_ms=(3 + i) * 80,
    )

st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

# Nota de configuración al pie
with st.expander("⚙️ Configuración de URLs", expanded=False):
    st.caption(
        "Las URLs de cada plataforma se configuran en el archivo `.env` del proyecto. "
        "Si una tarjeta muestra '⚙️ URL no configurada', agrega la variable correspondiente:"
    )
    st.code(
        "AZ_DIGITAL=https://...\n"
        "KLIC_2=https://...\n"
        "ADRES=https://...\n"
        "SECOP=https://...\n"
        "PDF_H=https://...",
        language="ini",
    )
