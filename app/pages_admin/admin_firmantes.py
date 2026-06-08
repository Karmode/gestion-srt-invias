"""Módulo de aprobaciones de certificaciones – SRTI INVIAS.

Accesible para los 3 firmantes designados y para el administrador.
  - Firmantes: pueden aprobar o revocar su tipo de firma específico.
  - Admin: vista de solo lectura + gestión de quiénes son los firmantes.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES

TIPOS_FIRMA = ("corr", "gd", "secop")

_META_FIRMA = {
    "corr":   ("F. Corr",  "Correspondencia",        "certificacion.firmar_corr"),
    "gd":     ("F. GD",    "Gestión Documental",      "certificacion.firmar_gd"),
    "secop":  ("F. SECOP", "SECOP II",                "certificacion.firmar_secop"),
}


# ── Helpers de badges ────────────────────────────────────────────

def _badge_firma(tipo: str, firma: dict | None) -> str:
    label = _META_FIRMA[tipo][0]
    if firma:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        icono = "✅"
    else:
        bg, fg, bd = "#2c2c2c", "#aaaaaa", "#444"
        icono = "⏳"
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">'
        f"{icono} {label}</span>"
    )


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


# ── Diálogo de confirmación para firma de Correspondencia ────────

@st.dialog("Confirmar aprobación — Correspondencia", width="small")
def _dialog_confirmar_firma_corr(
    servicio: CertificacionService, sesion: dict, año: int, mes: int, nombre_mes: str
) -> None:
    from app.services.correspondencia_service import CorrespondenciaService

    emp = st.session_state.get("_confirmar_firma_corr")
    if not emp:
        return

    uid = emp["uid"]
    nombre = emp["nombre"]

    st.markdown(f"**Contratista:** {nombre}")
    st.markdown(f"**Período a certificar:** {nombre_mes} {año}")
    st.divider()

    with st.spinner("Consultando correspondencia del período…"):
        stats = CorrespondenciaService().obtener_correspondencia_del_periodo(uid, año, mes)

    pendientes = stats["pendientes"]
    vencidas = stats["vencidas"]

    if pendientes == 0:
        st.success("✅ Esta persona está al día en correspondencia para este período.")
    elif vencidas > 0:
        st.error(
            f"⚠️ Esta persona tiene **{pendientes} solicitud(es)** con vencimiento en {nombre_mes} {año}, "
            f"de las cuales **{vencidas} están vencidas**.\n\n"
            "Al aprobar, aceptas la responsabilidad de esta decisión como firmante de Correspondencia."
        )
    else:
        st.warning(
            f"⚠️ Esta persona tiene **{pendientes} solicitud(es) pendiente(s)** con vencimiento en "
            f"{nombre_mes} {año} (ninguna vencida aún)."
        )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            servicio.registrar_firma(uid, nombre, "corr", sesion["id"], firmante_nombre)
            st.session_state.pop("_confirmar_firma_corr", None)
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("_confirmar_firma_corr", None)
            st.rerun()


# ── Render principal ─────────────────────────────────────────────

def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = CertificacionService()
    permisos = sesion.get("permisos", [])
    roles = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles)

    # Recopilar todos los tipos de firma que tiene este usuario.
    # Un mismo usuario puede tener más de un permiso de firma (ej. corr + gd).
    mis_tipos_firma = [t for t in TIPOS_FIRMA if _META_FIRMA[t][2] in permisos]

    if not es_admin and not mis_tipos_firma:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    año, mes = servicio.periodo_certificable()
    nombre_mes = MESES_ES[mes - 1]
    es_anterior = servicio.es_mes_anterior()

    st.title("✍️ Aprobaciones de Certificaciones")
    st.caption(f"Período certificable: **{nombre_mes} {año}**")

    if es_anterior:
        st.warning(
            f"Estás aprobando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana disponible hasta el día 24 del mes en curso)."
        )

    # Selector de rol cuando el usuario tiene más de un permiso de firma
    if len(mis_tipos_firma) > 1:
        opciones_firma = {t: _META_FIRMA[t][1] for t in mis_tipos_firma}
        tipo_mi_firma = st.radio(
            "Estás actuando como firmante de:",
            options=list(opciones_firma.keys()),
            format_func=lambda t: f"✍️ {opciones_firma[t]}",
            horizontal=True,
            key="sel_tipo_firma_activo",
        )
    elif mis_tipos_firma:
        tipo_mi_firma = mis_tipos_firma[0]
    else:
        tipo_mi_firma = None

    # Banner de rol
    if es_admin and tipo_mi_firma is None:
        st.info(
            "🛡️ **Administrador** — Vista de solo lectura. "
            "Para configurar los firmantes ve a **Seguimiento de Certificaciones**."
        )
    elif tipo_mi_firma:
        _, label_largo, _ = _META_FIRMA[tipo_mi_firma]
        roles_txt = (
            " · ".join(_META_FIRMA[t][1] for t in mis_tipos_firma)
            if len(mis_tipos_firma) > 1
            else label_largo
        )
        st.info(f"✍️ **Actuando como:** Firma de {label_largo}  ·  Tienes permiso para: {roles_txt}")

    st.divider()

    with st.spinner("Consultando estado de correspondencia…"):
        empleados = servicio.obtener_empleados_para_certificar()

    if not empleados:
        st.info("No hay colaboradores con correspondencia registrada.")
        return

    # Métricas
    total = len(empleados)
    con_3_firmas = sum(
        1 for e in empleados
        if all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)
    )

    if tipo_mi_firma:
        mis_pendientes = sum(
            1 for e in empleados
            if not e.get("firmas", {}).get(tipo_mi_firma)
        )
        mis_aprobados = sum(
            1 for e in empleados
            if e.get("firmas", {}).get(tipo_mi_firma)
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Total contratistas", total)
        m2.metric("Pendientes mi aprobación", mis_pendientes)
        m3.metric("Aprobados por mí", mis_aprobados)
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total contratistas", total)
        m2.metric("Con las 3 firmas", con_3_firmas)
        m3.metric("Pendientes de firmas", total - con_3_firmas)

    st.divider()

    # Filtros
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        buscar = st.text_input(
            "Buscar", placeholder="Nombre del contratista…", label_visibility="collapsed"
        )
    with fc2:
        if tipo_mi_firma:
            filtro = st.selectbox(
                "Filtrar",
                ["Todos", "Pendientes mi aprobación", "Ya aprobados por mí"],
                label_visibility="collapsed",
            )
        else:
            filtro = st.selectbox(
                "Filtrar",
                ["Todos", "Con las 3 firmas", "Faltan firmas"],
                label_visibility="collapsed",
            )

    lista = empleados
    if buscar.strip():
        q = buscar.strip().lower()
        lista = [e for e in lista if q in e["nombre"].lower()]
    if tipo_mi_firma:
        if filtro == "Pendientes mi aprobación":
            lista = [e for e in lista if not e.get("firmas", {}).get(tipo_mi_firma)]
        elif filtro == "Ya aprobados por mí":
            lista = [e for e in lista if e.get("firmas", {}).get(tipo_mi_firma)]
    else:
        if filtro == "Con las 3 firmas":
            lista = [e for e in lista if all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]
        elif filtro == "Faltan firmas":
            lista = [e for e in lista if not all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]

    st.caption(f"Mostrando {len(lista)} de {total} contratistas")

    if not lista:
        st.info("Ningún contratista coincide con los filtros aplicados.")
        return

    for emp in lista:
        uid = emp["usuario_id"]
        nombre = emp["nombre"]
        pendientes = emp["cantidad_pendientes"]
        vencidas = emp["cantidad_vencidas"]
        firmas = emp.get("firmas", {})
        tiene_contrato = emp.get("tiene_contrato", False)
        mi_firma_dada = firmas.get(tipo_mi_firma) if tipo_mi_firma else None

        with st.container(border=True):
            c_nom, c_badges, c_accion = st.columns([3, 5, 2])

            with c_nom:
                st.markdown(f"**{nombre}**")
                if mi_firma_dada:
                    fecha_firma = mi_firma_dada.get("fecha")
                    fecha_str = formato_fecha_bogota(fecha_firma, "%d/%m/%Y %H:%M") if fecha_firma else ""
                    st.caption(f"Aprobado · {fecha_str}")
                elif not tiene_contrato:
                    st.caption("⚠️ Sin contrato activo")

            with c_badges:
                badges = (
                    _badge_corr(pendientes, vencidas)
                    + "&nbsp;&nbsp;"
                    + "&nbsp;".join(_badge_firma(t, firmas.get(t)) for t in TIPOS_FIRMA)
                )
                st.markdown(badges, unsafe_allow_html=True)

                # Detalle de cada firma existente
                detalles = []
                for t in TIPOS_FIRMA:
                    f = firmas.get(t)
                    if f:
                        fecha_f = formato_fecha_bogota(f.get("fecha"), "%d/%m %H:%M")
                        detalles.append(f"{_META_FIRMA[t][0]}: {f.get('firmante_nombre', '')} · {fecha_f}")
                if detalles:
                    st.caption(" · ".join(detalles))

            with c_accion:
                cert_emp = emp.get("certificacion") or {}
                ya_certificado = cert_emp.get("estado") == "aprobado"

                if ya_certificado:
                    pdf_bytes = servicio.generar_pdf(cert_emp)
                    st.download_button(
                        "⬇️ Certificado",
                        data=pdf_bytes,
                        file_name=f"Certificado_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
                        mime="application/pdf",
                        key=f"dl_{uid}",
                        use_container_width=True,
                    )
                elif not tipo_mi_firma:
                    # Admin sin designación solo visualiza
                    pass
                elif mi_firma_dada:
                    if st.button(
                        "↩ Revocar",
                        key=f"firma_{uid}",
                        use_container_width=True,
                        help="Revocar mi aprobación.",
                    ):
                        servicio.revocar_firma(uid, tipo_mi_firma)
                        st.rerun()
                else:
                    if st.button(
                        "✅ Aprobar",
                        key=f"firma_{uid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        if tipo_mi_firma == "corr":
                            st.session_state["_confirmar_firma_corr"] = {"uid": uid, "nombre": nombre}
                            st.rerun()
                        else:
                            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
                            servicio.registrar_firma(uid, nombre, tipo_mi_firma, sesion["id"], firmante_nombre)
                            st.rerun()

    if st.session_state.get("_confirmar_firma_corr"):
        _dialog_confirmar_firma_corr(servicio, sesion, año, mes, nombre_mes)
