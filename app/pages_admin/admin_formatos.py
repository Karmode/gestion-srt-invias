"""
Gestión Formatos – página de administración SRTI-INVIAS.
Muestra el estado de correspondencia pendiente de cada responsable activo,
permite al admin marcar la firma y descargar el formato DOCX personalizado.
"""
import io
import os
import re
import zipfile
import tempfile
from datetime import datetime

import mammoth
import streamlit as st

from app.core.sesion import obtener_sesion
from app.services.correspondencia_service import CorrespondenciaService


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _personalizar_docx(template_bytes: bytes, nombre: str) -> bytes:
    """Sustituye {responsable}, {numero_dia}, {mes}, {año} en el DOCX."""
    from app.core.zona_horaria import datetime, ZONA_BOGOTA
    hoy = datetime.now(ZONA_BOGOTA)
    numero_dia = hoy.strftime("%d")
    meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    mes = meses[hoy.month - 1]
    ano = hoy.strftime("%Y")

    nombre_upper = nombre.upper()
    buf_in  = io.BytesIO(template_bytes)
    buf_out = io.BytesIO()
    with zipfile.ZipFile(buf_in, "r") as zin, \
         zipfile.ZipFile(buf_out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".xml"):
                try:
                    text = data.decode("utf-8")
                    text = re.sub(r"\{[^{}]*?responsable[^{}]*?\}", nombre_upper, text, flags=re.IGNORECASE)
                    text = re.sub(r"\{[^{}]*?numero_dia[^{}]*?\}", numero_dia + " ", text, flags=re.IGNORECASE)
                    text = re.sub(r"\{[^{}]*?mes[^{}]*?\}", mes, text, flags=re.IGNORECASE)
                    text = re.sub(r"\{[^{}]*?a(?:ñ|n|&#241;||[^a-zA-Z0-9{}])o[^{}]*?\}", ano, text, flags=re.IGNORECASE)
                    data = text.encode("utf-8")
                except Exception:
                    pass
            zout.writestr(item, data)
    buf_out.seek(0)
    return buf_out.getvalue()

def _preview_html(filepath: str) -> str:
    """Convierte el DOCX a HTML estilizado para el visor lateral."""
    with open(filepath, "rb") as f:
        body = mammoth.convert_to_html(f).value
    return f"""
    <style>
      body {{ margin:0; padding:0; }}
      .dw {{
        background:#fff; color:#222;
        font-family:'Segoe UI',Arial,sans-serif;
        font-size:.82em; line-height:1.45;
        padding:16px 20px;
        border-radius:6px; border:1px solid #ccc;
        box-shadow:0 2px 10px rgba(0,0,0,.07);
        height:572px; overflow-y:auto; box-sizing:border-box;
      }}
      .dw h1,.dw h2,.dw h3,.dw h4 {{ color:#111; margin:10px 0 5px; }}
      .dw table {{ border-collapse:collapse; width:100%; margin:7px 0; }}
      .dw th,.dw td {{ border:1px solid #ccc; padding:5px 8px; color:#222; font-size:.9em; }}
      .dw th {{ background:#f2f2f2; font-weight:700; }}
      .dw p  {{ margin-bottom:6px; }}
      .dw img {{ max-width:100%; display:block; margin:8px auto; }}
    </style>
    <div class="dw">{body}</div>"""


def _badge(pend: int, venc: int, dark: bool) -> str:
    """Devuelve HTML del badge coloreado para la columna 'Correspondencia pendiente'."""
    if pend == 0:
        bg, fg, bd = ("#1b4721","#75db8b","#2d7a3e") if dark else ("#d4edda","#155724","#c3e6cb")
        txt = "✅ Al Día"
    elif venc > 0:
        bg, fg, bd = ("#511c1e","#ff9ca2","#8a2d32") if dark else ("#f8d7da","#721c24","#f5c6cb")
        txt = f"❌&nbsp;{pend}&nbsp;pend.&nbsp;({venc}&nbsp;venc.)"
    else:
        bg, fg, bd = ("#4d3d0f","#ffe69c","#7a6010") if dark else ("#fff3cd","#856404","#ffeeba")
        txt = f"⚠️&nbsp;{pend}&nbsp;pend."
    return (
        f'<div style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:3px 4px;font-weight:700;font-size:.75em;'
        f'line-height:1.2;text-align:center;white-space:nowrap;">{txt}</div>'
    )

def _badge_vencer_fin_mes(cant: int, dark: bool) -> str:
    """Devuelve HTML del badge para la columna 'Pendientes a vencer fin de mes'."""
    if cant == 0:
        bg, fg, bd = ("#1b4721","#75db8b","#2d7a3e") if dark else ("#d4edda","#155724","#c3e6cb")
        txt = "✅ 0 a vencer"
    else:
        bg, fg, bd = ("#4d3d0f","#ffe69c","#7a6010") if dark else ("#fff3cd","#856404","#ffeeba")
        txt = f"⚠️&nbsp;{cant}&nbsp;a&nbsp;vencer"
    return (
        f'<div style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:3px 4px;font-weight:700;font-size:.75em;'
        f'line-height:1.2;text-align:center;white-space:nowrap;">{txt}</div>'
    )



# ──────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def render(sesion=None):
    servicio = CorrespondenciaService()
    sesion   = sesion or obtener_sesion()

    st.title("📋 Formatos")
    st.caption("Control de correspondencia vencida y descarga de formatos oficiales de la SRTI.")

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    # ── Archivo DOCX ──────────────────────────────────────────────
    _PATH = "app/assets/Formato_control_de_correspondencia_y_SECOP II.docx"
    _EXISTS = os.path.exists(_PATH)
    _BYTES  = open(_PATH, "rb").read() if _EXISTS else b""

    # ── Toggle ────────────────────────────────────────────────────
    if "formato_activo" not in st.session_state:
        st.session_state.formato_activo = None

    st.write("")
    col_btn1, col_btn2 = st.columns(2)
    
    if col_btn1.button("📄 Formato control correspondencia y SECOP II", 
                       type="primary" if st.session_state.formato_activo == "secop" else "secondary",
                       use_container_width=True):
        st.session_state.formato_activo = None if st.session_state.formato_activo == "secop" else "secop"
        st.rerun()
        
    if col_btn2.button("📄 Formato prueba WIP", 
                       type="primary" if st.session_state.formato_activo == "wip" else "secondary",
                       use_container_width=True):
        st.session_state.formato_activo = None if st.session_state.formato_activo == "wip" else "wip"
        st.rerun()

    if not st.session_state.formato_activo:
        return

    if st.session_state.formato_activo == "wip":
        st.divider()
        st.info("🚧 Sección en construcción: Formato prueba WIP")
        return

    # ── Carga de datos ────────────────────────────────────────────
    st.divider()
    with st.spinner("Consultando base de datos…"):
        try:
            resultados = servicio.obtener_estado_formatos()
        except Exception as e:
            st.error(f"Error al consultar datos: {e}")
            return

    dark = st.session_state.get("dark_mode", False)

    # ── Layout: izquierda (tabla) | derecha (previsualizador) ─────
    col_tbl, col_prev = st.columns([5, 6], gap="medium")

    # ╔══════════════════════════════════════╗
    # ║        COLUMNA IZQUIERDA – TABLA     ║
    # ╚══════════════════════════════════════╝
    with col_tbl:
        st.markdown("##### 📊 Estado por Responsable")

        # ── Estilos CSS para vista de Tarjetas (Compactas) ────────────────────
        st.markdown("""
        <style>
        .card-title { font-size: 0.85em; font-weight: 600; margin-bottom: 2px; line-height: 1.1; color: var(--text-color); }
        .card-badges { display: flex; gap: 4px; margin-bottom: 4px; flex-wrap: wrap; }
        /* Reducir padding de las tarjetas y el espacio entre elementos */
        div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 0.5rem 0.75rem !important; gap: 0.2rem !important; }
        /* Reducir márgenes inferiores dentro de la tarjeta */
        div[data-testid="stVerticalBlockBorderWrapper"] p { margin-bottom: 0 !important; }
        </style>
        """, unsafe_allow_html=True)

        # ── Filas con scroll (Diseño Adaptable en Tarjetas) ───────
        with st.container(height=550, border=False):
            for idx, row in enumerate(resultados):
                uid    = row["usuario_id"]
                pend   = row["cantidad_pendientes"]
                venc   = row["cantidad_vencidas"]
                vencer_fin_mes = row.get("cantidad_vencer_fin_mes", 0)
                nombre = row["responsable"]

                # Clave de firma persistente en session_state
                fkey_doc = f"firma_doc_{uid}"
                fkey_gd = f"firma_gd_{uid}"
                fkey_secop = f"firma_secop_{uid}"
                
                if fkey_doc not in st.session_state:
                    st.session_state[fkey_doc] = False
                if fkey_gd not in st.session_state:
                    st.session_state[fkey_gd] = False
                if fkey_secop not in st.session_state:
                    st.session_state[fkey_secop] = False

                with st.container(border=True):
                    # Cabecera de la tarjeta: Nombre y Badges integrados
                    badge_corr = _badge(pend, venc, dark)
                    badge_venc = _badge_vencer_fin_mes(vencer_fin_mes, dark)
                    
                    st.markdown(
                        f"<div class='card-title'>{nombre}</div>"
                        f"<div class='card-badges'>{badge_corr}{badge_venc}</div>",
                        unsafe_allow_html=True
                    )

                    # Controles de firma y descarga en una fila inferior
                    c_f1, c_f2, c_f3, c_btn = st.columns([1, 1, 1, 1.2])

                    firma_doc = c_f1.checkbox("F. Corr", key=fkey_doc)
                    firma_gd  = c_f2.checkbox("F. GD", key=fkey_gd)
                    firma_secop = c_f3.checkbox("F. SECOP", key=fkey_secop)

                    puede = firma_doc and firma_gd and firma_secop and (venc == 0) and _EXISTS and _BYTES

                    if puede:
                        docx_pers   = _personalizar_docx(_BYTES, nombre)
                        nombre_arch = (
                            "Formato_SECOP_"
                            + re.sub(r"[^A-Za-z0-9_]", "_", nombre.upper())
                            + ".docx"
                        )
                        c_btn.download_button(
                            label="⬇️ Descargar",
                            data=docx_pers,
                            file_name=nombre_arch,
                            mime=(
                                "application/vnd.openxmlformats-officedocument"
                                ".wordprocessingml.document"
                            ),
                            key=f"dl_{uid}_{idx}",
                            use_container_width=True,
                        )
                    else:
                        if venc > 0:
                            tip = "Tiene correspondencias vencidas."
                        elif not (firma_doc and firma_gd and firma_secop):
                            tip = "Activa todas las firmas para habilitar."
                        else:
                            tip = "Archivo no disponible."
                        c_btn.button(
                            "🔒 Bloqueado",
                            disabled=True,
                            help=tip,
                            key=f"lk_{uid}_{idx}",
                            use_container_width=True,
                        )

    # ╔══════════════════════════════════════╗
    # ║     COLUMNA DERECHA – PREVISUALIZADOR ║
    # ╚══════════════════════════════════════╝
    with col_prev:
        st.markdown("##### 🔍 Previsualización del Formato")
        if _EXISTS:
            try:
                st.html(_preview_html(_PATH))
            except Exception as e:
                st.error(f"Error al renderizar el documento: {e}")
        else:
            st.warning("Archivo de formato no disponible.")
