"""Assets estaticos codificados en base64, cacheados por proceso."""

import base64
import os

import streamlit as st


@st.cache_data(show_spinner=False)
def imagen_b64(ruta: str) -> str:
    """Contenido base64 de una imagen local, o cadena vacia si no existe."""
    if not os.path.exists(ruta):
        return ""
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
