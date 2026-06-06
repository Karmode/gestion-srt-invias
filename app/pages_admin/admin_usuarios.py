import pandas as pd
import streamlit as st

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.streamlit_compat import show_dataframe
from app.services.usuario_service import UsuarioService


def render(sesion=None):
    servicio = UsuarioService()
    sesion = sesion or obtener_sesion()

    st.title("Administración de usuarios")

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    try:
        validar_permiso(sesion.get("permisos", []), "usuario.ver")
    except ValidacionAutorizacion:
        st.error("No tienes permisos para ver este módulo.")
        st.stop()

    permisos = sesion.get("permisos", [])
    usuarios = servicio.listar_usuarios()

    # Determinar qué tabs mostrar según permisos
    tabs_labels = ["👥 Usuarios"]
    if "usuario.crear" in permisos:
        tabs_labels.append("➕ Crear usuario")
    if "usuario.editar" in permisos or "usuario.desactivar" in permisos:
        tabs_labels.append("✏️ Editar usuario")

    tabs = st.tabs(tabs_labels)
    tab_idx = 0

    # ── TAB: LISTADO ────────────────────────────────────────────────────────────
    with tabs[tab_idx]:
        tab_idx += 1
        col_h1, col_h2 = st.columns([3, 1])
        with col_h1:
            st.subheader("Listado de usuarios")
        with col_h2:
            if st.button("🔄 Actualizar", width="stretch", key="refresh_usuarios"):
                st.rerun()

        if not usuarios:
            st.info("Todavía no hay usuarios registrados.")
        else:
            datos = [
                {
                    "Usuario": u.get("usuario", ""),
                    "Nombre": u.get("nombre_completo", ""),
                    "Correo": u.get("email", ""),
                    "Estado": "Activo" if u.get("activo", False) else "Inactivo",
                    "Roles": ", ".join(u.get("roles", [])),
                }
                for u in usuarios
            ]
            show_dataframe(pd.DataFrame(datos), hide_index=True)

    # ── TAB: CREAR USUARIO ──────────────────────────────────────────────────────
    if "➕ Crear usuario" in tabs_labels:
        with tabs[tab_idx]:
            tab_idx += 1
            st.subheader("Nuevo usuario")

            roles_disponibles = [r.get("nombre", "") for r in servicio.repositorio.listar_roles()]
            permisos_disponibles = [p.get("clave", "") for p in servicio.repositorio.listar_permisos()]

            with st.form("form_crear_usuario"):
                col1, col2 = st.columns(2)
                with col1:
                    nuevo_usuario = st.text_input("Usuario")
                    nuevo_email = st.text_input("Correo electrónico")
                    nuevo_activo = st.checkbox("Activo", value=True)
                with col2:
                    nuevo_nombre = st.text_input("Nombre completo")
                    nuevo_password = st.text_input("Contraseña", type="password")

                nuevos_roles = st.multiselect("Roles", options=roles_disponibles)
                nuevos_permisos_extra = st.multiselect("Permisos extra", options=permisos_disponibles)
                enviar = st.form_submit_button("Crear usuario", use_container_width=True)

            if enviar:
                try:
                    servicio.crear_usuario(
                        {
                            "usuario": nuevo_usuario.strip(),
                            "nombre_completo": nuevo_nombre.strip(),
                            "email": nuevo_email.strip(),
                            "password": nuevo_password,
                            "activo": nuevo_activo,
                            "roles": nuevos_roles,
                            "permisos_extra": nuevos_permisos_extra,
                            "creado_por": sesion["usuario"],
                        },
                        permisos_usuario=permisos,
                    )
                    st.success("Usuario creado correctamente.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    # ── TAB: EDITAR USUARIO ─────────────────────────────────────────────────────
    if "✏️ Editar usuario" in tabs_labels:
        with tabs[tab_idx]:
            if not usuarios:
                st.info("Todavía no hay usuarios registrados.")
            else:
                roles_disponibles = [r.get("nombre", "") for r in servicio.repositorio.listar_roles()]
                permisos_disponibles = [p.get("clave", "") for p in servicio.repositorio.listar_permisos()]

                mapa_usuarios = {
                    f"{u.get('usuario', '')} — {u.get('nombre_completo', '')}": u
                    for u in usuarios
                }
                seleccion = st.selectbox(
                    "Selecciona un usuario",
                    options=list(mapa_usuarios.keys()),
                    key="select_editar",
                )
                uo = mapa_usuarios[seleccion]

                # Estado + acción de activar/desactivar
                col_estado, col_toggle = st.columns([2, 1])
                with col_estado:
                    estado_txt = "🟢 Activo" if uo.get("activo", False) else "🔴 Inactivo"
                    st.markdown(f"**Estado actual:** {estado_txt}")
                with col_toggle:
                    if "usuario.desactivar" in permisos:
                        if uo.get("activo", False):
                            if st.button("Desactivar", key=f"des_{uo.get('_id')}", use_container_width=True):
                                try:
                                    servicio.desactivar_usuario(
                                        str(uo["_id"]),
                                        permisos_usuario=permisos,
                                        usuario_actual=sesion["usuario"],
                                    )
                                    st.success("Usuario desactivado.")
                                    st.rerun()
                                except ValueError as error:
                                    st.error(str(error))
                        else:
                            if st.button("Activar", key=f"act_{uo.get('_id')}", use_container_width=True):
                                try:
                                    servicio.activar_usuario(
                                        str(uo["_id"]),
                                        permisos_usuario=permisos,
                                        usuario_actual=sesion["usuario"],
                                    )
                                    st.success("Usuario activado.")
                                    st.rerun()
                                except ValueError as error:
                                    st.error(str(error))

                if "usuario.editar" not in permisos:
                    st.warning("No tienes permiso para editar usuarios.")
                else:
                    st.divider()
                    with st.form("form_editar_usuario"):
                        col1, col2 = st.columns(2)
                        with col1:
                            usuario_editado = st.text_input("Usuario", value=uo.get("usuario", ""))
                            email_editado = st.text_input("Correo electrónico", value=uo.get("email", ""))
                        with col2:
                            nombre_editado = st.text_input("Nombre completo", value=uo.get("nombre_completo", ""))
                            password_nueva = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password")

                        roles_sel = st.multiselect(
                            "Roles",
                            options=roles_disponibles,
                            default=uo.get("roles", []),
                        )
                        permisos_sel = st.multiselect(
                            "Permisos extra",
                            options=permisos_disponibles,
                            default=uo.get("permisos_extra", []),
                        )
                        enviar_edicion = st.form_submit_button("Guardar cambios", use_container_width=True)

                    if enviar_edicion:
                        try:
                            servicio.actualizar_usuario(
                                str(uo["_id"]),
                                {
                                    "usuario": usuario_editado.strip(),
                                    "nombre_completo": nombre_editado.strip(),
                                    "email": email_editado.strip(),
                                    "password": password_nueva,
                                    "activo": uo.get("activo", False),
                                    "roles": roles_sel,
                                    "permisos_extra": permisos_sel,
                                    "actualizado_por": sesion["usuario"],
                                },
                                permisos_usuario=permisos,
                            )
                            st.success("Usuario actualizado correctamente.")
                            st.rerun()
                        except ValueError as error:
                            st.error(str(error))
