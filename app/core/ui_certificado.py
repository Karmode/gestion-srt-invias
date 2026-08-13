"""Componentes de UI reutilizables para la previsualización de certificados PDF."""

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer


@st.cache_data(show_spinner=False)
def obtener_pdf_certificado_cacheado(_servicio, cert_id: str, hash_verificacion: str, _certificacion: dict, version_key: str = "") -> bytes:
    """PDF de un certificado ya aprobado no cambia una vez emitido (el hash se
    preserva). Se cachea por id + hash para no regenerarlo con ReportLab
    (más su consulta a usuario) en cada rerun de Streamlit.
    El parámetro version_key (sin guión bajo) sirve para invalidar la caché cuando cambian las firmas."""
    return _servicio.generar_pdf(_certificacion)


def render_preview_cert(
    pdf_bytes: bytes,
    caption: str,
    file_name: str,
    dl_key: str,
) -> None:
    """Renderiza el visor PDF + botón de descarga dentro de un diálogo de certificado."""
    st.caption(caption)
    pdf_viewer(input=pdf_bytes, width=800, height=620)
    st.download_button(
        "⬇️ Descargar PDF",
        data=pdf_bytes,
        file_name=file_name,
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        key=dl_key,
    )
