"""Módulo de aprobaciones de certificaciones – SRTI INVIAS.

Accesible para los 3 firmantes designados y para el administrador.
  - Firmantes: pueden aprobar o revocar su tipo de firma específico.
  - Admin: vista de solo lectura + gestión de quiénes son los firmantes.
"""

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.sesion import obtener_sesion
from app.core.ui_certificado import obtener_pdf_certificado_cacheado
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES

TIPOS_FIRMA = ("corr", "gd", "secop")

_META_FIRMA = {
    "corr":   ("F. Corr",  "Correspondencia",        "certificacion.firmar_corr"),
    "gd":     ("F. GD",    "Gestión Documental",      "certificacion.firmar_gd"),
    "secop":  ("F. SECOP", "SECOP II",                "certificacion.firmar_secop"),
}

MAPA_TIPOS_CONTRATO = {
    "termino_indefinido": "Término indefinido",
    "termino_fijo": "Término fijo",
    "obra_labor": "Obra o labor",
    "prestacion_servicios": "Prestación de servicios",
    "aprendizaje": "Aprendizaje",
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

    mostrar_titulo_decorado("Sup. Formatos")
    st.caption(f"Período certificable: **{nombre_mes} {año}**")

    if es_anterior:
        _dia_cierre = servicio._dia_inicio_periodo() - 1
        st.warning(
            f"Estás aprobando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana disponible hasta el día {_dia_cierre} del mes en curso)."
        )

    # Inicializar estado para mostrar/ocultar el formato de control
    if "ver_formato_control" not in st.session_state:
        st.session_state["ver_formato_control"] = False

    # Botones de navegación
    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("1-Formato de control Corr-GP-SECOP", type="primary", use_container_width=True, key="btn_formato_control"):
            st.session_state["ver_formato_control"] = not st.session_state["ver_formato_control"]
            st.rerun()
    with col2:
        st.button("2- Formato de acta de recibo y entrega CPS", disabled=True, use_container_width=True, key="btn_acta_recibo")
    with col3:
        st.button("3- Balance General CPS", disabled=True, use_container_width=True, key="btn_balance_general")

    st.write("")

    # Selector de rol cuando el usuario tiene más de un permiso de firma
    if st.session_state["ver_formato_control"]:
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
        else:
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
                m3.metric("Aprobados", mis_aprobados)
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Total contratistas", total)
                m2.metric("Con las 3 firmas", con_3_firmas)
                m3.metric("Pendientes de firmas", total - con_3_firmas)

            st.divider()

            # Filtros
            fc1, fc2, fc3 = st.columns([3, 3, 2])
            with fc1:
                contratistas_unicos = sorted(list(set(e["nombre"] for e in empleados)))
                opciones_contratista = ["Todos"] + contratistas_unicos
                buscar = st.selectbox(
                    "Filtro por Gestor",
                    options=opciones_contratista,
                    index=0,
                    key="filtro_contratista_aprob",
                )
            with fc2:
                opciones_tipo = ["Todos"] + list(MAPA_TIPOS_CONTRATO.values()) + ["Sin contrato"]
                filtro_tipo = st.selectbox(
                    "Filtro por Contrato",
                    options=opciones_tipo,
                    index=0,
                    key="filtro_tipo_contrato_aprob",
                )
            with fc3:
                if tipo_mi_firma:
                    filtro = st.selectbox(
                        "Filtro por Aprobados",
                        options=["Todos", "Pendientes mi aprobación", "Aprobados"],
                        index=0,
                        key="filtro_estado_firma_aprob",
                    )
                else:
                    filtro = st.selectbox(
                        "Filtro por Aprobados",
                        options=["Todos", "Con las 3 firmas", "Faltan firmas"],
                        index=0,
                        key="filtro_estado_firma_aprob",
                    )

            lista = empleados
            if buscar != "Todos":
                lista = [e for e in lista if e["nombre"] == buscar]

            if filtro_tipo != "Todos":
                if filtro_tipo == "Sin contrato":
                    lista = [e for e in lista if not e.get("tiene_contrato")]
                else:
                    inv_map = {v: k for k, v in MAPA_TIPOS_CONTRATO.items()}
                    clave_tecnica = inv_map.get(filtro_tipo)
                    lista = [e for e in lista if e.get("tipo_contrato") == clave_tecnica]

            if tipo_mi_firma:
                if filtro == "Pendientes mi aprobación":
                    lista = [e for e in lista if not e.get("firmas", {}).get(tipo_mi_firma)]
                elif filtro == "Aprobados":
                    lista = [e for e in lista if e.get("firmas", {}).get(tipo_mi_firma)]
            else:
                if filtro == "Con las 3 firmas":
                    lista = [e for e in lista if all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]
                elif filtro == "Faltan firmas":
                    lista = [e for e in lista if not all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)]

            st.caption(f"Mostrando {len(lista)} de {total} contratistas")

            if not lista:
                st.info("Ningún contratista coincide con los filtros aplicados.")
            else:
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
                                pdf_bytes = obtener_pdf_certificado_cacheado(
                                    servicio,
                                    str(cert_emp["_id"]),
                                    cert_emp.get("hash_verificacion", ""),
                                    cert_emp,
                                )
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
