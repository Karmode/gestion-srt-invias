"""
Gestión Formatos – página de administración SRTI-INVIAS.
Muestra el estado de correspondencia pendiente de cada responsable activo,
permite al admin marcar la firma y descargar el formato DOCX personalizado.
"""
import io
import os
import re
import zipfile
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
                    text = re.sub(r"\{responsable\}", nombre_upper, text, flags=re.IGNORECASE)
                    text = re.sub(r"\{numero_dia\}", numero_dia, text, flags=re.IGNORECASE)
                    text = re.sub(r"\{mes\}", mes, text, flags=re.IGNORECASE)
                    text = re.sub(r"\{a(ñ|n)o\}", ano, text, flags=re.IGNORECASE)
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
    if "mostrar_formatos" not in st.session_state:
        st.session_state.mostrar_formatos = False

    st.write("")
    if st.button("📄 Formato control de correspondencia y SECOP II",
                 type="primary", key="btn_toggle_fmt"):
        st.session_state.mostrar_formatos = not st.session_state.mostrar_formatos
        st.rerun()

    if not st.session_state.mostrar_formatos:
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

        # ── Cabecera fija (fuera del scroll) ──────────────────────
        hdr1, hdr2, hdr_venc, hdr3, hdr_secop, hdr4 = st.columns([1.8, 1.8, 1.3, 1.3, 1.0, 1.0])
        hdr1.markdown("<span style='font-size:0.7em; font-weight:bold'>Responsable</span>", unsafe_allow_html=True)
        hdr2.markdown("<span style='font-size:0.7em; font-weight:bold'>Pendiente</span>", unsafe_allow_html=True)
        hdr_venc.markdown("<span style='font-size:0.7em; font-weight:bold'>Vencen Fin Mes</span>", unsafe_allow_html=True)
        hdr3.markdown("<span style='font-size:0.7em; font-weight:bold'>Firma Corr/GD</span>", unsafe_allow_html=True)
        hdr_secop.markdown("<span style='font-size:0.7em; font-weight:bold'>Firma SECOP</span>", unsafe_allow_html=True)
        hdr4.markdown("<span style='font-size:0.7em; font-weight:bold'>Descarga</span>", unsafe_allow_html=True)
        st.markdown(
            "<hr style='margin:3px 0 5px;border:0;border-top:2px solid rgba(150,150,150,.3);'>",
            unsafe_allow_html=True,
        )

        # ── Filas con scroll ──────────────────────────────────────
        with st.container(height=520, border=False):
            for idx, row in enumerate(resultados):
                uid    = row["usuario_id"]
                pend   = row["cantidad_pendientes"]
                venc   = row["cantidad_vencidas"]
                vencer_fin_mes = row.get("cantidad_vencer_fin_mes", 0)
                nombre = row["responsable"]

                # Clave de firma persistente en session_state
                fkey_doc = f"firma_doc_{uid}"
                fkey_secop = f"firma_secop_{uid}"
                if fkey_doc not in st.session_state:
                    st.session_state[fkey_doc] = False
                if fkey_secop not in st.session_state:
                    st.session_state[fkey_secop] = False

                c1, c2, c_venc, c3, c_secop, c4 = st.columns([1.8, 1.8, 1.3, 1.3, 1.0, 1.0])

                # Col 1 – Nombre
                c1.markdown(
                    f"<div style='padding-top:7px;font-size:.78em;word-break:break-word;'>"
                    f"{nombre}</div>",
                    unsafe_allow_html=True,
                )

                # Col 2 – Badge coloreado correspondencia
                c2.markdown(_badge(pend, venc, dark), unsafe_allow_html=True)
                
                # Col 2.5 - Badge coloreado próximos a vencer fin de mes
                c_venc.markdown(_badge_vencer_fin_mes(vencer_fin_mes, dark), unsafe_allow_html=True)

                # Col 3 – Checkbox "Firmar Correspondencia..."
                firma_doc = c3.checkbox("Firmar Correspondencia", key=fkey_doc, label_visibility="collapsed")
                
                # Col 3.5 - Checkbox "Firmar SECOP"
                firma_secop = c_secop.checkbox("Firmar SECOP", key=fkey_secop, label_visibility="collapsed")

                # Col 4 – Botón de descarga condicional
                #   HABILITADO  : firma_doc == True Y firma_secop == True Y venc == 0
                #                 (pendientes o sin pendientes, pero sin vencidas)
                #   BLOQUEADO   : cualquier otro caso
                puede = firma_doc and firma_secop and (venc == 0) and _EXISTS and _BYTES

                if puede:
                    docx_pers   = _personalizar_docx(_BYTES, nombre)
                    nombre_arch = (
                        "Formato_SECOP_"
                        + re.sub(r"[^A-Za-z0-9_]", "_", nombre.upper())
                        + ".docx"
                    )
                    c4.download_button(
                        label="⬇️",
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
                    elif not (firma_doc and firma_secop):
                        tip = "Activa ambas firmas para habilitar la descarga."
                    else:
                        tip = "Archivo no disponible."
                    c4.button(
                        "🔒",
                        disabled=True,
                        help=tip,
                        key=f"lk_{uid}_{idx}",
                        use_container_width=True,
                    )

                # Separador sutil entre filas
                st.markdown(
                    "<div style='border-bottom:1px solid rgba(128,128,128,.12);"
                    "margin:3px 0 5px;'></div>",
                    unsafe_allow_html=True,
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
