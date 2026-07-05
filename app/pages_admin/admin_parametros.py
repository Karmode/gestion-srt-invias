"""Panel de administración de parámetros del sistema – SRTI INVIAS.

Permite al administrador ajustar valores que afectan el comportamiento del
sistema (p. ej. el día de inicio del período de certificación). Cada cambio:
  - se valida contra el rango permitido del parámetro,
  - exige confirmación explícita mostrando valor actual → nuevo + impacto,
  - queda registrado en auditoría.

Los parámetros se definen de forma declarativa en ParametrosService.PARAMETROS;
esta página los renderiza genéricamente.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_titulos import mostrar_titulo_decorado
from app.core.cache_datos import limpiar_cache_lecturas
from app.services.opciones_service import OpcionesService
from app.services.parametros_service import ParametrosService, PARAMETROS


# ── Diálogo de confirmación ──────────────────────────────────────────────────

@st.dialog("Confirmar cambio de parámetro", width="small")
def _dialog_confirmar(servicio: ParametrosService, sesion: dict) -> None:
    pend = st.session_state.get("_param_pendiente")
    if not pend:
        return

    clave = pend["clave"]
    nuevo = pend["valor"]
    meta = PARAMETROS[clave]
    actual = servicio.obtener(clave)

    st.markdown(f"**Parámetro:** {meta['etiqueta']}")
    c1, c2 = st.columns(2)
    c1.metric("Valor actual", actual)
    c2.metric("Nuevo valor", nuevo)

    st.warning(f"⚠️ **Impacto:** {meta['impacto']}")
    st.divider()

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Confirmar cambio", type="primary", use_container_width=True):
            usuario = sesion.get("usuario") or "sistema"
            try:
                servicio.actualizar(clave, nuevo, usuario)
                st.session_state.pop("_param_pendiente", None)
                st.session_state["_param_msg"] = (
                    f"'{meta['etiqueta']}' actualizado a **{nuevo}**."
                )
                limpiar_cache_lecturas()
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    with b2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_param_pendiente", None)
            st.rerun()


@st.dialog("⚠️ CONFIRMAR LIMPIEZA DE CERTIFICACIONES", width="medium")
def _dialog_confirmar_limpieza_certificaciones() -> None:
    st.error(
        "🚨 **¡ATENCIÓN!** Está a punto de eliminar permanentemente **todas** las certificaciones de la base de datos. "
        "Esta acción es irreversible y afectará el historial de todos los usuarios."
    )
    st.write("Para proceder, por favor ingrese la contraseña de seguridad especial:")
    confirmacion = st.text_input("Contraseña de seguridad", type="password", key="input_confirmar_eliminar_certs")
    
    b1, b2 = st.columns(2)
    with b1:
        disabled = confirmacion.strip() != "losmod@5"
        if st.button("Confirmar eliminación", type="primary", use_container_width=True, disabled=disabled):
            from app.repositories.certificacion_repo import CertificacionRepositorio
            try:
                repo = CertificacionRepositorio()
                res = repo.coleccion.delete_many({})
                st.session_state["_param_msg"] = f"Se eliminaron exitosamente {res.deleted_count} certificaciones de la base de datos."
            except Exception as e:
                st.session_state["_param_msg"] = f"❌ Error eliminando certificaciones: {e}"
            st.session_state.pop("show_eliminar_certs_dialog", None)
            st.rerun()
    with b2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("show_eliminar_certs_dialog", None)
            st.rerun()



# ── Render principal ─────────────────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    es_admin = any(r in {"admin", "administrador"} for r in sesion.get("roles", []))
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    servicio = ParametrosService()

    mostrar_titulo_decorado("Parámetros del sistema")
    st.caption(
        "Valores que afectan el comportamiento del sistema. Los cambios requieren "
        "confirmación y quedan registrados en auditoría."
    )

    msg = st.session_state.pop("_param_msg", None)
    if msg:
        st.success(msg)

    for clave, meta in PARAMETROS.items():
        actual = servicio.obtener(clave)
        with st.container(border=True):
            st.markdown(f"**{meta['etiqueta']}**")
            st.caption(meta["descripcion"])

            col_in, col_btn = st.columns([3, 1])
            with col_in:
                if meta["tipo"] == "int":
                    nuevo = st.number_input(
                        meta.get("unidad", "Valor"),
                        min_value=meta["min"],
                        max_value=meta["max"],
                        value=int(actual),
                        step=1,
                        key=f"inp_{clave}",
                    )
                else:
                    nuevo = st.text_input(
                        meta.get("unidad", "Valor"),
                        value=str(actual),
                        key=f"inp_{clave}",
                    )
            with col_btn:
                st.write("")
                st.write("")
                sin_cambio = nuevo == actual
                if st.button(
                    "Guardar",
                    key=f"btn_{clave}",
                    use_container_width=True,
                    disabled=sin_cambio,
                ):
                    st.session_state["_param_pendiente"] = {"clave": clave, "valor": nuevo}
                    st.rerun()

            if meta["tipo"] == "int":
                st.caption(
                    f"Valor actual: **{actual}** · Rango permitido: {meta['min']}–{meta['max']}"
                )
            else:
                st.caption(
                    f"Valor actual: **{actual}**"
                )

    if st.session_state.get("_param_pendiente"):
        _dialog_confirmar(servicio, sesion)

    if st.session_state.get("show_eliminar_certs_dialog"):
        _dialog_confirmar_limpieza_certificaciones()

    st.divider()
    with st.container(border=True):
        st.markdown("**Caché de catálogos (opciones de configuración)**")
        st.caption(
            "Los catálogos como EPS, ARL, bancos, etc. se cachean en memoria mientras "
            "la aplicación está en ejecución. Si agregaste o editaste una opción "
            "directamente en la base de datos, límpiala aquí para que se refleje sin "
            "reiniciar el servidor."
        )
        if st.button("Limpiar caché de catálogos", key="btn_limpiar_cache_opciones"):
            OpcionesService().limpiar_cache()
            limpiar_cache_lecturas()
            st.success("Caché de catálogos limpiada. Los cambios en la base de datos ya se reflejarán.")

    with st.container(border=True):
        st.markdown("**🗑️ Limpieza Anual de Certificaciones**")
        st.caption(
            "Elimina **todos** los registros de la colección de certificaciones en la base de datos. "
            "Esta operación es irreversible y se realiza típicamente al final de cada año para reiniciar el ciclo. "
            "La estructura de la colección y sus índices no se alterarán, solo se vaciarán sus documentos."
        )
        if st.button("Vaciar certificaciones", key="btn_vaciar_certificaciones", type="secondary"):
            st.session_state["show_eliminar_certs_dialog"] = True
            st.rerun()

