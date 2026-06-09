"""Componentes de UI reutilizables para la previsualización de certificados PDF."""

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer


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
