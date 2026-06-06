"""Vista del supervisor para emitir certificaciones mensuales.

Solo accesible para usuarios con el permiso certificacion.aprobar.
El período de certificación está abierto del día 25 al fin de mes.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES


def _badge_corr(pendientes: int, vencidas: int) -> str:
    if pendientes == 0:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        txt = "✅ Al Día"
    elif vencidas > 0:
        bg, fg, bd = "#511c1e", "#ff9ca2", "#8a2d32"
        txt = f"❌ {pendientes} pend. ({vencidas} venc.)"
    else:
        bg, fg, bd = "#4d3d0f", "#ffe69c", "#7a6010"
        txt = f"⚠️ {pendientes} pend."
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">'
        f"{txt}</span>"
    )


def _badge_cert(estado: str | None) -> str:
    if estado == "aprobado":
        return '<span style="background:#1b4721;color:#75db8b;border:1px solid #2d7a3e;border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">✅ Certificado</span>'
    return '<span style="background:#2c2c2c;color:#aaaaaa;border:1px solid #444;border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">⏳ Pendiente</span>'


# ── Diálogo de confirmación ───────────────────────────────────────

@st.dialog("Confirmar certificación", width="small")
def _dialog_certificar(servicio: CertificacionService, sesion: dict):
    emp = st.session_state.get("_cert_emp")
    if not emp:
        st.warning("Sin datos del colaborador.")
        return

    nombre = emp["nombre"]
    uid = emp["uid"]

    st.markdown(
        f"Confirma que **{nombre}** se encuentra al día con su correspondencia "
        f"y se le emite el certificado para cuenta de cobro."
    )
    obs = st.text_area(
        "Observaciones (opcional)",
        placeholder="Ej: Sin novedades en el período.",
        key="_obs_cert",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Certificar", type="primary", use_container_width=True):
            supervisor_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            ok = servicio.certificar_empleado(
                uid,
                nombre,
                sesion["id"],
                supervisor_nombre,
                obs,
            )
            if ok:
                st.session_state.pop("_cert_emp", None)
                st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_cert_emp", None)
            st.rerun()


# ── Render principal ─────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    if "certificacion.aprobar" not in sesion.get("permisos", []):
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    servicio = CertificacionService()
    año, mes = servicio.periodo_certificable()
    nombre_mes = MESES_ES[mes - 1]
    es_anterior = servicio.es_mes_anterior()

    st.title("Certificaciones Mensuales")
    st.caption(
        "Revisa el estado de correspondencia de cada colaborador "
        "y emite las certificaciones del período."
    )

    if es_anterior:
        st.warning(
            f"Estás certificando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana de ponerse al día, disponible hasta el día 24 del mes en curso). "
            f"A partir del día 25 solo podrás certificar el mes actual."
        )
    else:
        st.success(
            f"Período de certificación abierto: **{nombre_mes} {año}** "
            f"(días 25 al fin de mes)"
        )

    st.divider()

    with st.spinner("Consultando estado de correspondencia…"):
        empleados = servicio.obtener_empleados_para_certificar()

    if not empleados:

        st.info("No hay colaboradores con correspondencia registrada.")
        return

    # Resumen rápido
    total = len(empleados)
    certificados = sum(
        1 for e in empleados
        if e.get("certificacion") and e["certificacion"].get("estado") == "aprobado"
    )
    pendientes_cert = total - certificados

    m1, m2, m3 = st.columns(3)
    m1.metric("Total colaboradores", total)
    m2.metric("Certificados", certificados)
    m3.metric("Pendientes", pendientes_cert)

    st.divider()

    # ── Filtros y ordenamiento ────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        buscar = st.text_input("Buscar colaborador", placeholder="Nombre…", label_visibility="collapsed")
    with fc2:
        filtro_cert = st.selectbox(
            "Estado certificación",
            ["Todos", "Certificados", "Pendientes"],
            label_visibility="collapsed",
        )
    with fc3:
        filtro_corr = st.selectbox(
            "Estado correspondencia",
            ["Todos", "Al día", "Con vencidos"],
            label_visibility="collapsed",
        )
    with fc4:
        orden = st.selectbox(
            "Ordenar por",
            ["Nombre A→Z", "Nombre Z→A", "Pendientes primero", "Certificados primero"],
            label_visibility="collapsed",
        )

    # Aplicar filtros
    lista = empleados
    if buscar.strip():
        q = buscar.strip().lower()
        lista = [e for e in lista if q in e["nombre"].lower()]
    if filtro_cert == "Certificados":
        lista = [e for e in lista if e.get("certificacion") and e["certificacion"].get("estado") == "aprobado"]
    elif filtro_cert == "Pendientes":
        lista = [e for e in lista if not (e.get("certificacion") and e["certificacion"].get("estado") == "aprobado")]
    if filtro_corr == "Al día":
        lista = [e for e in lista if e["al_dia"]]
    elif filtro_corr == "Con vencidos":
        lista = [e for e in lista if not e["al_dia"]]

    # Aplicar orden
    if orden == "Nombre A→Z":
        lista = sorted(lista, key=lambda e: e["nombre"].lower())
    elif orden == "Nombre Z→A":
        lista = sorted(lista, key=lambda e: e["nombre"].lower(), reverse=True)
    elif orden == "Pendientes primero":
        lista = sorted(lista, key=lambda e: (
            e.get("certificacion", {}) and e["certificacion"].get("estado") == "aprobado",
            e["nombre"].lower(),
        ))
    elif orden == "Certificados primero":
        lista = sorted(lista, key=lambda e: (
            not (e.get("certificacion") and e["certificacion"].get("estado") == "aprobado"),
            e["nombre"].lower(),
        ))

    st.caption(f"Mostrando {len(lista)} de {total} colaboradores")

    if not lista:
        st.info("Ningún colaborador coincide con los filtros aplicados.")
    else:
        for emp in lista:
            uid = emp["usuario_id"]
            nombre = emp["nombre"]
            pendientes = emp["cantidad_pendientes"]
            vencidas = emp["cantidad_vencidas"]
            al_dia = emp["al_dia"]
            cert = emp.get("certificacion")
            estado_cert = cert.get("estado") if cert else None

            with st.container(border=True):
                c_nom, c_badges, c_btn = st.columns([3, 3, 2])

                with c_nom:
                    st.markdown(f"**{nombre}**")
                    if estado_cert == "aprobado":
                        aprobado_por = cert.get("aprobado_por", {})
                        fecha_ap = aprobado_por.get("fecha")
                        fecha_str = formato_fecha_bogota(fecha_ap, "%d/%m/%Y %H:%M")
                        st.caption(
                            f"Certificado por {aprobado_por.get('nombre', '')} "
                            f"· {fecha_str}"
                        )

                with c_badges:
                    st.markdown(
                        _badge_corr(pendientes, vencidas) + "&nbsp;&nbsp;" + _badge_cert(estado_cert),
                        unsafe_allow_html=True,
                    )

                with c_btn:
                    if estado_cert == "aprobado":
                        st.button(
                            "✅ Certificado",
                            key=f"cert_{uid}",
                            disabled=True,
                            use_container_width=True,
                        )
                    elif not al_dia:
                        st.button(
                            "🔒 Tiene vencidos",
                            key=f"cert_{uid}",
                            disabled=True,
                            help="No se puede certificar con correspondencias vencidas.",
                            use_container_width=True,
                        )
                    else:
                        if st.button(
                            "Certificar",
                            key=f"cert_{uid}",
                            type="primary",
                            use_container_width=True,
                        ):
                            st.session_state["_cert_emp"] = {
                                "uid": uid,
                                "nombre": nombre,
                            }
                            st.rerun()

    # Abrir diálogo si hay un empleado seleccionado
    if st.session_state.get("_cert_emp"):
        _dialog_certificar(servicio, sesion)
