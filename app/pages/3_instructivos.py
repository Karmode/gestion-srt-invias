import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import streamlit as st

from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.sesion import obtener_sesion
from app.services.instructivo_service import InstructivoService

st.set_page_config(
    page_title="Instructivos",
    page_icon="app/assets/invias_fav_ico_3.ico",
    layout="wide",
)

sesion = obtener_sesion()
is_admin = "admin" in (sesion.get("roles", []) if sesion else [])

svc = InstructivoService()


def _embed_url(share_url: str) -> str:
    """Convierte URL /view de Google Drive a /preview para embedding en iframe."""
    return share_url.split("?")[0].replace("/view", "/preview")


def _icono_por_tipo(item: dict) -> str:
    if item.get("icono"):
        return item["icono"]
    return {"pdf": "📄", "video": "▶️", "enlace": "🔗"}.get(item.get("tipo", "enlace"), "🔗")


# ---------- Tab Recursos ----------

def _render_recursos() -> None:
    if "recurso_activo" not in st.session_state:
        st.session_state.recurso_activo = None

    instructivos = svc.listar_activos()

    if not instructivos:
        st.info("No hay recursos disponibles aún.")
        return

    col_controles, col_vista = st.columns([1, 3])

    with col_controles:
        st.subheader("Recursos")
        for item in instructivos:
            key = str(item["_id"])
            label = f"{_icono_por_tipo(item)} {item['titulo']}"
            if st.button(label, use_container_width=True, key=f"btn_{key}"):
                st.session_state.recurso_activo = key

        if st.session_state.recurso_activo is not None:
            st.divider()
            if st.button("✖ Cerrar vista previa", use_container_width=True):
                st.session_state.recurso_activo = None

    with col_vista:
        activo_id = st.session_state.recurso_activo

        if activo_id is None:
            st.info("Selecciona un recurso del panel izquierdo para visualizarlo aquí.")
            return

        item = next((i for i in instructivos if str(i["_id"]) == activo_id), None)
        if item is None:
            st.warning("Recurso no encontrado.")
            st.session_state.recurso_activo = None
            return

        st.subheader(f"{_icono_por_tipo(item)} {item['titulo']}")
        if item.get("descripcion"):
            st.caption(item["descripcion"])

        url = item.get("url", "")
        tipo = item.get("tipo", "enlace")

        if not url:
            st.warning("URL no configurada para este recurso.")
        elif tipo == "enlace":
            st.link_button("🔗 Abrir enlace", url)
        else:
            embed_url = _embed_url(url)
            
            st.info(
                "💡 **¿No puedes visualizar el recurso aquí abajo?**\n\n"
                "Esto suele ocurrir si tu navegador bloquea cookies de terceros (o estás en modo incógnito) "
                "o si tienes múltiples cuentas de Google iniciadas. "
                "Haz clic en el botón de abajo para abrirlo directamente en una pestaña nueva sin restricciones."
            )
            
            st.link_button("Abrir instructivo", url, type="primary", use_container_width=True)
            st.divider()
            
            altura = item.get("embed_height") or (850 if tipo == "pdf" else 540)
            st.iframe(embed_url, height=altura + 10)


# ---------- Dialog de edición ----------

@st.dialog("Editar instructivo", width="large")
def _dialog_editar(item: dict) -> None:
    id_str = str(item["_id"])
    nombre_usuario = (sesion.get("nombre_completo") or sesion.get("usuario")) if sesion else "admin"

    titulo = st.text_input("Título *", value=item.get("titulo", ""))
    descripcion = st.text_input("Descripción (opcional)", value=item.get("descripcion") or "")
    url = st.text_input("URL *", value=item.get("url", ""))

    col_tipo, col_icono = st.columns(2)
    with col_tipo:
        tipos = ["pdf", "video", "enlace"]
        tipo = st.selectbox("Tipo", tipos, index=tipos.index(item.get("tipo", "enlace")))
    with col_icono:
        icono = st.text_input("Icono (emoji, opcional)", value=item.get("icono") or "")

    if tipo != "enlace":
        altura_default = item.get("embed_height") or (850 if tipo == "pdf" else 540)
        embed_height = st.number_input(
            "Altura del iframe (px)", value=altura_default, min_value=200, max_value=2000, step=50
        )
    else:
        embed_height = None

    orden = st.number_input("Orden de aparición", value=item.get("orden", 1), min_value=1, step=1)

    col_ok, col_cancel = st.columns(2)
    with col_ok:
        if st.button("💾 Guardar cambios", type="primary", use_container_width=True):
            if not titulo.strip():
                st.error("El título es obligatorio.")
            elif not url.strip():
                st.error("La URL es obligatoria.")
            else:
                svc.actualizar(
                    id_str,
                    {
                        "titulo": titulo.strip(),
                        "descripcion": descripcion.strip() or None,
                        "url": url.strip(),
                        "tipo": tipo,
                        "icono": icono.strip() or None,
                        "embed_height": int(embed_height) if embed_height else None,
                        "orden": int(orden),
                    },
                    actualizado_por=nombre_usuario,
                )
                st.success("Instructivo actualizado.")
                st.rerun()
    with col_cancel:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()


# ---------- Tab Administrar ----------

def _render_admin() -> None:
    nombre_usuario = (sesion.get("nombre_completo") or sesion.get("usuario")) if sesion else "admin"

    # --- Crear nuevo ---
    st.subheader("Crear nuevo instructivo")
    with st.form("form_nuevo_instructivo", clear_on_submit=True):
        titulo = st.text_input("Título *")
        descripcion = st.text_input("Descripción (opcional)")
        url = st.text_input("URL del recurso *", placeholder="https://drive.google.com/...")

        col_tipo, col_icono = st.columns(2)
        with col_tipo:
            tipo = st.selectbox("Tipo", ["pdf", "video", "enlace"])
        with col_icono:
            icono = st.text_input("Icono (emoji, opcional)", placeholder="📄")

        embed_height = st.number_input(
            "Altura del iframe en px (solo para PDF/video)",
            value=850,
            min_value=200,
            max_value=2000,
            step=50,
        )
        submitted = st.form_submit_button("➕ Crear instructivo", type="primary")

    if submitted:
        if not titulo.strip():
            st.error("El título es obligatorio.")
        elif not url.strip():
            st.error("La URL es obligatoria.")
        else:
            svc.crear(
                titulo=titulo.strip(),
                url=url.strip(),
                tipo=tipo,
                descripcion=descripcion.strip() or None,
                icono=icono.strip() or None,
                embed_height=int(embed_height) if tipo != "enlace" else None,
                creado_por=nombre_usuario,
            )
            st.success(f"Instructivo '{titulo.strip()}' creado.")
            st.rerun()

    # --- Lista ---
    st.divider()
    st.subheader("Instructivos registrados")
    todos = svc.listar_todos()

    if not todos:
        st.info("No hay instructivos registrados aún.")
        return

    for item in todos:
        id_str = str(item["_id"])
        activo = item.get("activo", True)
        tipo = item.get("tipo", "enlace")
        icono = _icono_por_tipo(item)
        badge = "🟢" if activo else "🔴"
        url_display = item.get("url", "")
        url_corta = url_display[:70] + ("…" if len(url_display) > 70 else "")

        with st.container(border=True):
            col_info, col_acciones = st.columns([4, 2])
            with col_info:
                st.markdown(f"**{badge} {icono} {item['titulo']}**")
                st.caption(f"Tipo: `{tipo}` · Orden: {item.get('orden', '?')}")
                st.caption(url_corta)
                if item.get("descripcion"):
                    st.caption(item["descripcion"])
            with col_acciones:
                col_edit, col_toggle = st.columns(2)
                with col_edit:
                    if st.button("✏️ Editar", key=f"edit_{id_str}", use_container_width=True):
                        _dialog_editar(item)
                with col_toggle:
                    label_toggle = "🔴 Desactivar" if activo else "🟢 Activar"
                    if st.button(label_toggle, key=f"toggle_{id_str}", use_container_width=True):
                        svc.toggle_activo(id_str, not activo, actualizado_por=nombre_usuario)
                        st.rerun()


# ---------- Layout principal ----------

mostrar_titulo_decorado("📚 Instructivos")
st.caption("Recursos de capacitación y documentación oficial.")

if is_admin:
    tab_recursos, tab_admin = st.tabs(["📋 Recursos", "⚙️ Administrar"])
    with tab_recursos:
        _render_recursos()
    with tab_admin:
        _render_admin()
else:
    _render_recursos()
