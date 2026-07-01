from datetime import datetime, timezone

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.catalogos import TIPOS_CONTRATO
from app.core.sesion import obtener_sesion
from app.core.ui_laboral import (
    boton_guardar_laboral,
    construir_mapas_catalogos,
    inputs_informacion_laboral,
    limpiar_estado_laboral,
    render_seccion_firma,
)
from app.services.auth_service import AuthService
from app.services.usuario_service import UsuarioService


mostrar_titulo_decorado("Mi perfil")
sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()


def _feedback(tipo: str, mensaje: str) -> None:
    """Guarda un mensaje de feedback para mostrarlo tras el rerun (persiste, no es toast)."""
    st.session_state["_perfil_msg"] = (tipo, mensaje)


# Mensaje de éxito/error persistente entre reruns (visible en cualquier pestaña).
if _msg := st.session_state.pop("_perfil_msg", None):
    getattr(st, _msg[0])(_msg[1])

TIPOS_DOCUMENTO = {
    "": "— Sin especificar —",
    "CC": "CC — Cédula de Ciudadanía",
    "CE": "CE — Cédula de Extranjería",
    "TI": "TI — Tarjeta de Identidad",
    "PA": "PA — Pasaporte",
}

_servicio = UsuarioService()
_usuario_doc = _servicio.obtener_usuario(sesion["id"]) or {}

tab_perfil, tab_laboral, tab_firma, tab_contrato, tab_password = st.tabs(
    ["👤 Perfil", "💼 Información laboral", "✍️ Firma", "📄 Contratos", "🔒 Contraseña"]
)

# ── TAB: PERFIL ──────────────────────────────────────────────────────────────

with tab_perfil:
    st.subheader("Datos de acceso")
    st.write(f"**Usuario:** {sesion['usuario']}")
    st.write(f"**Roles:** {', '.join(sesion.get('roles', [])) or 'Sin roles'}")

    st.divider()
    st.subheader("Editar datos personales")

    tipo_doc_actual = sesion.get("tipo_documento") or ""
    tipo_doc_idx = list(TIPOS_DOCUMENTO.keys()).index(tipo_doc_actual) if tipo_doc_actual in TIPOS_DOCUMENTO else 0

    with st.form("form_editar_perfil"):
        col1, col2 = st.columns(2)
        with col1:
            nuevo_nombre = st.text_input("Nombre completo", value=sesion.get("nombre_completo") or "")
            nuevo_email = st.text_input("Correo electrónico", value=sesion.get("email") or "")
        with col2:
            nuevo_tipo_doc = st.selectbox(
                "Tipo de documento",
                options=list(TIPOS_DOCUMENTO.keys()),
                format_func=lambda k: TIPOS_DOCUMENTO[k],
                index=tipo_doc_idx,
            )
            nuevo_num_doc = st.text_input("Número de documento", value=sesion.get("numero_documento") or "")
        nuevo_lugar_exp = st.text_input(
            "Lugar de expedición del documento",
            value=_usuario_doc.get("lugar_expedicion_documento") or "",
            placeholder="Ciudad de expedición de la cédula",
        )
        st.caption("Los cambios se guardan solo al pulsar el botón. Si sales sin pulsarlo, no se conservan.")
        guardar_perfil = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

    if guardar_perfil:
        try:
            _servicio.actualizar_usuario(
                sesion["id"],
                {
                    "nombre_completo": nuevo_nombre.strip(),
                    "email": nuevo_email.strip(),
                    "tipo_documento": nuevo_tipo_doc.strip(),
                    "numero_documento": nuevo_num_doc.strip(),
                    "lugar_expedicion_documento": nuevo_lugar_exp.strip(),
                    "actualizado_por": sesion["usuario"],
                },
                validar_permisos=False,
            )
            st.session_state["usuario_autenticado"].update({
                "nombre_completo": nuevo_nombre.strip(),
                "email": nuevo_email.strip(),
                "tipo_documento": nuevo_tipo_doc.strip(),
                "numero_documento": nuevo_num_doc.strip(),
            })
            _feedback("success", "✅ Datos personales actualizados correctamente.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

# ── TAB: INFORMACIÓN LABORAL ───────────────────────────────────────────────────

with tab_laboral:
    st.subheader("Información laboral")
    st.caption("Seguridad social, datos bancarios, tributarios y dependientes económicos.")

    _mapas = construir_mapas_catalogos()
    _il_actual = _usuario_doc.get("informacion_laboral") or {}
    _il_raw = inputs_informacion_laboral("perfil_lab", _il_actual, _mapas)

    st.divider()
    if boton_guardar_laboral("perfil_lab", _il_raw, key="guardar_lab_perfil"):
        try:
            _servicio.actualizar_usuario(
                sesion["id"],
                {"informacion_laboral": _il_raw, "actualizado_por": sesion["usuario"]},
                validar_permisos=False,
            )
            limpiar_estado_laboral("perfil_lab")
            _feedback("success", "✅ Información laboral guardada correctamente.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

# ── TAB: FIRMA ──────────────────────────────────────────────────────────────────

with tab_firma:
    st.subheader("Firma")
    st.caption("Sube una foto o escaneo de tu firma sobre papel blanco; se procesa para quitar el fondo.")
    render_seccion_firma(
        sesion["id"], sesion["usuario"], "perfil_firma",
        al_terminar=lambda m: _feedback("success", f"✅ {m}"),
    )

# ── TAB: CONTRATOS ────────────────────────────────────────────────────────────

with tab_contrato:
    _contratos = sorted(
        (_usuario_doc.get("contratos") or []),
        key=lambda c: c.get("fecha_inicio") or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    # Agregar nuevo contrato
    with st.expander("➕ Agregar nuevo contrato", expanded=len(_contratos) == 0):
        with st.form("form_nuevo_contrato"):
            _nc1, _nc2 = st.columns(2)
            with _nc1:
                _n_num = st.text_input("Número de contrato *")
                _n_tipo = st.selectbox(
                    "Tipo de contrato",
                    options=list(TIPOS_CONTRATO.keys()),
                    format_func=lambda k: TIPOS_CONTRATO[k],
                )
            with _nc2:
                _n_valor = st.number_input("Valor del contrato (COP)", min_value=0, step=100000, format="%d")
                _n_vm = st.number_input("Valor mensual (COP)", min_value=0, step=100000, format="%d")
            _n_rp = st.text_input("RP / compromiso presupuestal", placeholder="Código alfanumérico")
            _nc3, _nc4, _nc5 = st.columns(3)
            with _nc3:
                _n_frp = st.date_input("Fecha recurso presupuestal (opcional)", value=None, format="DD/MM/YYYY")
            with _nc4:
                _n_fi = st.date_input("Fecha de inicio", value=None, format="DD/MM/YYYY")
            with _nc5:
                _n_ff = st.date_input("Fecha de finalización (opcional)", value=None, format="DD/MM/YYYY")
            _n_obj = st.text_area("Objeto del contrato")
            st.caption("El contrato se registra solo al pulsar el botón.")
            _n_env = st.form_submit_button("➕ Agregar contrato", use_container_width=True, type="primary")

        if _n_env:
            try:
                _servicio.agregar_contrato(sesion["id"], {
                    "numero": _n_num.strip(),
                    "tipo": _n_tipo,
                    "valor": _n_valor if _n_valor > 0 else None,
                    "rp_compromiso_presupuestal": _n_rp.strip(),
                    "fecha_inicio": _n_fi,
                    "fecha_fin": _n_ff,
                    "fecha_recurso_presupuestal": _n_frp,
                    "valor_mensual": _n_vm if _n_vm > 0 else None,
                    "objeto": _n_obj.strip(),
                })
                _feedback("success", "✅ Contrato agregado correctamente.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # Listado de contratos
    if not _contratos:
        st.info("Aún no tienes contratos registrados.")
    else:
        for _c in _contratos:
            _c_fin = UsuarioService._contrato_finalizado(_c)
            _c_num = _c.get("numero", "")
            _c_fi = _c.get("fecha_inicio")
            _c_ff = _c.get("fecha_fin")
            _estado = "🔴 Finalizado" if _c_fin else "🟢 Activo"

            with st.expander(f"{_c_num} — {_estado}", expanded=not _c_fin):
                _d1, _d2 = st.columns(2)
                with _d1:
                    st.write(f"**Tipo:** {TIPOS_CONTRATO.get(_c.get('tipo') or '', '—')}")
                    _v = _c.get("valor")
                    st.write(f"**Valor:** {'${:,.0f}'.format(_v) if _v else '—'}")
                with _d2:
                    _vm = _c.get("valor_mensual")
                    st.write(f"**Valor mensual:** {'${:,.0f}'.format(_vm) if _vm else '—'}")
                    st.write(f"**RP / compromiso presupuestal:** {_c.get('rp_compromiso_presupuestal') or '—'}")
                _d3, _d4, _d5 = st.columns(3)
                with _d3:
                    _frp = _c.get("fecha_recurso_presupuestal")
                    st.write(f"**Fecha RP:** {_frp.strftime('%d/%m/%Y') if _frp else '—'}")
                with _d4:
                    st.write(f"**Inicio:** {_c_fi.strftime('%d/%m/%Y') if _c_fi else '—'}")
                with _d5:
                    st.write(f"**Fin:** {_c_ff.strftime('%d/%m/%Y') if _c_ff else '—'}")
                if _c.get("objeto"):
                    st.write(f"**Objeto:** {_c.get('objeto')}")

                if not _c_fin:
                    st.write("---")
                    _fi_ed = _c_fi.date() if _c_fi and hasattr(_c_fi, "date") else _c_fi
                    _ff_ed = _c_ff.date() if _c_ff and hasattr(_c_ff, "date") else _c_ff
                    with st.form(f"form_editar_contrato_{_c_num}"):
                        _ec1, _ec2 = st.columns(2)
                        with _ec1:
                            _e_num = st.text_input("Número", value=_c_num, key=f"e_num_{_c_num}")
                            _e_tipo_idx = list(TIPOS_CONTRATO.keys()).index(_c.get("tipo") or "") if (_c.get("tipo") or "") in TIPOS_CONTRATO else 0
                            _e_tipo = st.selectbox(
                                "Tipo",
                                options=list(TIPOS_CONTRATO.keys()),
                                format_func=lambda k: TIPOS_CONTRATO[k],
                                index=_e_tipo_idx,
                                key=f"e_tipo_{_c_num}",
                            )
                        with _ec2:
                            _e_valor = st.number_input(
                                "Valor (COP)", min_value=0, value=int(_c.get("valor") or 0),
                                step=100000, format="%d", key=f"e_val_{_c_num}",
                            )
                            _e_vm = st.number_input(
                                "Valor mensual (COP)", min_value=0, value=int(_c.get("valor_mensual") or 0),
                                step=100000, format="%d", key=f"e_vm_{_c_num}",
                            )
                        _e_rp = st.text_input(
                            "RP / compromiso presupuestal", value=_c.get("rp_compromiso_presupuestal") or "",
                            key=f"e_rp_{_c_num}", placeholder="Código alfanumérico",
                        )
                        _ec3, _ec4, _ec5 = st.columns(3)
                        with _ec3:
                            _e_frp_ed = _c.get("fecha_recurso_presupuestal")
                            if _e_frp_ed and hasattr(_e_frp_ed, "date"):
                                _e_frp_ed = _e_frp_ed.date()
                            _e_frp = st.date_input("Fecha recurso presupuestal (opcional)", value=_e_frp_ed, format="DD/MM/YYYY", key=f"e_frp_{_c_num}")
                        with _ec4:
                            _e_fi = st.date_input("Inicio", value=_fi_ed, format="DD/MM/YYYY", key=f"e_fi_{_c_num}")
                        with _ec5:
                            _e_ff = st.date_input("Fin (opcional)", value=_ff_ed, format="DD/MM/YYYY", key=f"e_ff_{_c_num}")
                        _e_obj = st.text_area("Objeto", value=_c.get("objeto") or "", key=f"e_obj_{_c_num}")
                        st.caption("Los cambios se guardan solo al pulsar el botón.")
                        _e_env = st.form_submit_button("💾 Guardar cambios", use_container_width=True, type="primary")

                    if _e_env:
                        try:
                            _servicio.editar_contrato(sesion["id"], _c_num, {
                                "numero": _e_num.strip(),
                                "tipo": _e_tipo,
                                "valor": _e_valor if _e_valor > 0 else None,
                                "rp_compromiso_presupuestal": _e_rp.strip(),
                                "fecha_inicio": _e_fi,
                                "fecha_fin": _e_ff,
                                "fecha_recurso_presupuestal": _e_frp,
                                "valor_mensual": _e_vm if _e_vm > 0 else None,
                                "objeto": _e_obj.strip(),
                            })
                            _feedback("success", f"✅ Contrato {_c_num} actualizado correctamente.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

# ── TAB: CONTRASEÑA ────────────────────────────────────────────────────────────

with tab_password:
    st.subheader("Cambiar contraseña")

    with st.form("form_cambiar_password"):
        pwd_actual = st.text_input("Contraseña actual", type="password")
        pwd_nueva = st.text_input("Contraseña nueva", type="password")
        pwd_confirmar = st.text_input("Confirmar contraseña nueva", type="password")
        enviar_pwd = st.form_submit_button("🔒 Cambiar contraseña", type="primary")

    if enviar_pwd:
        if pwd_nueva != pwd_confirmar:
            st.error("❌ Las contraseñas nuevas no coinciden.")
        else:
            auth_service = AuthService()
            exito, mensaje = auth_service.cambiar_password(sesion["id"], pwd_actual, pwd_nueva)
            if exito:
                _feedback("success", f"✅ {mensaje}")
                st.rerun()
            else:
                st.error(f"❌ {mensaje}")
