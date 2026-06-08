"""Vista del supervisor para monitorear y descargar certificaciones mensuales.

Requiere el permiso certificacion.aprobar.
La certificación ocurre automáticamente cuando se registran las 3 firmas
y el contratista cumple: sin vencidas + contrato activo.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_certificado import render_preview_cert
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES

TIPOS_FIRMA = ("corr", "gd", "secop")

_META_FIRMA = {
    "corr":  ("F. Corr",  "Correspondencia"),
    "gd":    ("F. GD",    "Gestión Documental"),
    "secop": ("F. SECOP", "SECOP II"),
}


# ── Badges ───────────────────────────────────────────────────────

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
        return (
            '<span style="background:#1b4721;color:#75db8b;border:1px solid #2d7a3e;'
            'border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">✅ Certificado</span>'
        )
    return (
        '<span style="background:#2c2c2c;color:#aaaaaa;border:1px solid #444;'
        'border-radius:4px;padding:2px 8px;font-size:.78em;font-weight:700;">⏳ Pendiente</span>'
    )


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
        f'border-radius:4px;padding:1px 7px;font-size:.75em;font-weight:700;">'
        f"{icono} {label}</span>"
    )


def _badge_contrato(tiene: bool) -> str:
    if tiene:
        return (
            '<span style="background:#1b2e4b;color:#74b9ff;border:1px solid #2d4a6e;'
            'border-radius:4px;padding:1px 7px;font-size:.75em;font-weight:700;">📄 Con contrato</span>'
        )
    return (
        '<span style="background:#511c1e;color:#ff9ca2;border:1px solid #8a2d32;'
        'border-radius:4px;padding:1px 7px;font-size:.75em;font-weight:700;">❌ Sin contrato</span>'
    )


# ── Diálogo de previsualización ──────────────────────────────────

@st.dialog("Vista previa del certificado", width="large")
def _dialog_preview(servicio: CertificacionService) -> None:
    data = st.session_state.get("_preview_cert")
    if not data:
        return

    cert = data["cert"]
    nombre = data["nombre"]
    año = data["año"]
    nombre_mes = data["nombre_mes"]

    pdf_bytes = servicio.generar_pdf(cert)
    render_preview_cert(
        pdf_bytes=pdf_bytes,
        caption=f"{nombre} — {nombre_mes} {año}",
        file_name=f"Certificado_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
        dl_key="_dl_preview_cert",
    )


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
        "Revisa el estado de correspondencia, firmas y contrato de cada colaborador "
        "y emite las certificaciones del período."
    )

    if es_anterior:
        st.warning(
            f"Estás certificando el **mes anterior: {nombre_mes} {año}** "
            f"(ventana disponible hasta el día 24 del mes en curso). "
            f"A partir del día 25 solo podrás certificar el mes actual."
        )
    else:
        st.success(
            f"Período de certificación abierto: **{nombre_mes} {año}** "
            f"(días 25 al fin de mes)"
        )

    # Resumen de firmantes designados
    config_firmantes = servicio.obtener_firmantes_config()
    firmantes_ok = all(config_firmantes.get(t) for t in TIPOS_FIRMA)

    with st.expander("👥 Firmantes designados para este período", expanded=not firmantes_ok):
        if not firmantes_ok:
            st.warning(
                "Aún no están configurados los 3 firmantes. "
                "Sin los 3 firmantes no se podrán aprobar certificaciones. "
                "Ve al módulo **Aprobaciones de Certificaciones** para configurarlos."
            )
        for tipo in TIPOS_FIRMA:
            dato = config_firmantes.get(tipo)
            label_largo = _META_FIRMA[tipo][1]
            if dato and dato.get("nombre"):
                st.markdown(f"- ✅ **{label_largo}:** {dato['nombre']}")
            else:
                st.markdown(f"- ❌ **{label_largo}:** *(sin designar)*")

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
    listos_para_cert = sum(
        1 for e in empleados
        if (
            e["al_dia"]
            and all(e.get("firmas", {}).get(t) for t in TIPOS_FIRMA)
            and e.get("tiene_contrato")
            and not (e.get("certificacion") and e["certificacion"].get("estado") == "aprobado")
        )
    )
    pendientes_cert = total - certificados

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total colaboradores", total)
    m2.metric("Certificados", certificados)
    m3.metric("Listos para certificar", listos_para_cert)
    m4.metric("Pendientes", pendientes_cert)

    st.divider()

    # Filtros y ordenamiento
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        buscar = st.text_input(
            "Buscar colaborador", placeholder="Nombre…", label_visibility="collapsed"
        )
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

    lista = empleados
    if buscar.strip():
        q = buscar.strip().lower()
        lista = [e for e in lista if q in e["nombre"].lower()]
    if filtro_cert == "Certificados":
        lista = [
            e for e in lista
            if e.get("certificacion") and e["certificacion"].get("estado") == "aprobado"
        ]
    elif filtro_cert == "Pendientes":
        lista = [
            e for e in lista
            if not (e.get("certificacion") and e["certificacion"].get("estado") == "aprobado")
        ]
    if filtro_corr == "Al día":
        lista = [e for e in lista if e["al_dia"]]
    elif filtro_corr == "Con vencidos":
        lista = [e for e in lista if not e["al_dia"]]

    if orden == "Nombre A→Z":
        lista = sorted(lista, key=lambda e: e["nombre"].lower())
    elif orden == "Nombre Z→A":
        lista = sorted(lista, key=lambda e: e["nombre"].lower(), reverse=True)
    elif orden == "Pendientes primero":
        lista = sorted(
            lista,
            key=lambda e: (
                e.get("certificacion", {}) and e["certificacion"].get("estado") == "aprobado",
                e["nombre"].lower(),
            ),
        )
    elif orden == "Certificados primero":
        lista = sorted(
            lista,
            key=lambda e: (
                not (e.get("certificacion") and e["certificacion"].get("estado") == "aprobado"),
                e["nombre"].lower(),
            ),
        )

    st.caption(f"Mostrando {len(lista)} de {total} colaboradores")

    if not lista:
        st.info("Ningún colaborador coincide con los filtros aplicados.")
    else:
        for emp in lista:
            uid = emp["usuario_id"]
            nombre = emp["nombre"]
            pendientes = emp["cantidad_pendientes"]
            vencidas = emp["cantidad_vencidas"]
            cert = emp.get("certificacion")
            estado_cert = cert.get("estado") if cert else None
            firmas = emp.get("firmas", {})
            tiene_contrato = emp.get("tiene_contrato", False)
            numero_contrato = emp.get("numero_contrato")

            with st.container(border=True):
                c_nom, c_badges, c_btn = st.columns([3, 5, 2])

                with c_nom:
                    st.markdown(f"**{nombre}**")
                    if estado_cert == "aprobado":
                        aprobado_por = cert.get("aprobado_por", {})
                        fecha_ap = aprobado_por.get("fecha")
                        fecha_str = formato_fecha_bogota(fecha_ap, "%d/%m/%Y %H:%M")
                        st.caption(
                            f"Certificado por {aprobado_por.get('nombre', '')} · {fecha_str}"
                        )
                    elif numero_contrato:
                        st.caption(f"Contrato: {numero_contrato}")

                with c_badges:
                    row1 = (
                        _badge_corr(pendientes, vencidas)
                        + "&nbsp;&nbsp;"
                        + _badge_cert(estado_cert)
                    )
                    row2 = (
                        "&nbsp;".join(_badge_firma(t, firmas.get(t)) for t in TIPOS_FIRMA)
                        + "&nbsp;&nbsp;"
                        + _badge_contrato(tiene_contrato)
                    )
                    st.markdown(row1, unsafe_allow_html=True)
                    st.markdown(row2, unsafe_allow_html=True)

                with c_btn:
                    if estado_cert == "aprobado":
                        pdf_bytes = servicio.generar_pdf(cert)
                        st.download_button(
                            "⬇️ Descargar",
                            data=pdf_bytes,
                            file_name=f"Certificado_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
                            mime="application/pdf",
                            key=f"dl_{uid}",
                            type="primary",
                            use_container_width=True,
                        )
                        if st.button("👁️ Ver", key=f"prev_{uid}", use_container_width=True):
                            st.session_state["_preview_cert"] = {
                                "cert": cert,
                                "nombre": nombre,
                                "año": año,
                                "nombre_mes": nombre_mes,
                            }
                            st.rerun()

    if st.session_state.get("_preview_cert"):
        _dialog_preview(servicio)
