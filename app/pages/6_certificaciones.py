"""Página de certificaciones mensuales — vista del colaborador.

Cada usuario ve el estado de su certificación del mes actual
y el historial de certificados anteriores con opción de descarga PDF.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.ui_certificado import render_preview_cert
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES


def _badge_estado(estado: str | None) -> str:
    if estado == "aprobado":
        return "✅ **Certificado**"
    return "⏳ Pendiente de aprobación"


@st.dialog("Vista previa del certificado", width="large")
def _dialog_preview_cert(servicio: CertificacionService) -> None:
    data = st.session_state.get("_preview_cert_user")
    if not data:
        return

    pdf_bytes = servicio.generar_pdf(data["cert"])
    mes_nombre = data["mes_nombre"]
    año = data["año"]

    render_preview_cert(
        pdf_bytes=pdf_bytes,
        caption=f"{mes_nombre} {año}",
        file_name=f"Certificado_correspondencia_{mes_nombre}_{año}.pdf",
        dl_key="_dl_preview_user",
    )


_META_FIRMA = {
    "corr":  ("F. Corr",  "Correspondencia"),
    "gd":    ("F. GD",    "Gestión Documental"),
    "secop": ("F. SECOP", "SECOP II"),
}


def _mostrar_avance(usuario_id: str, cert_actual) -> None:
    from app.repositories.usuario_repo import UsuarioRepositorio

    firmas = cert_actual.get("firmas", {}) if cert_actual else {}

    usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
    contratos = usuario_data.get("contratos") or []
    contrato = CertificacionService._contrato_vigente(contratos)
    tiene_contrato = bool(contrato.get("numero"))

    n_firmas = sum(1 for t in _META_FIRMA if firmas.get(t))
    total = len(_META_FIRMA)

    avance_extra = "" if tiene_contrato else " · ❌ Sin contrato"
    st.markdown(f"##### Avance: {n_firmas}/{total} aprobaciones{avance_extra}")

    if n_firmas == total and not tiene_contrato:
        st.warning(
            "✅ Tienes las **3 aprobaciones** del período, pero el certificado no pudo "
            "generarse porque **no tienes un contrato activo** registrado. "
            "Ve a **Mi Perfil** y registra tu contrato para completar el proceso."
        )

    col_firmas, col_contrato = st.columns([3, 2])

    with col_firmas:
        st.markdown("**Aprobaciones requeridas**")
        for tipo, (_, label_largo) in _META_FIRMA.items():
            f = firmas.get(tipo)
            if f:
                fecha_str = formato_fecha_bogota(f.get("fecha"), "%d/%m/%Y %H:%M")
                st.markdown(
                    f"✅ &nbsp;**{label_largo}**  \n"
                    f"<span style='font-size:.82em;color:#888;'>{f.get('firmante_nombre', '')} · {fecha_str}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"⏳ &nbsp;**{label_largo}** — pendiente")

    with col_contrato:
        st.markdown("**Contrato activo**")
        if tiene_contrato:
            st.markdown(f"✅ &nbsp;Contrato **{contrato['numero']}**")
        else:
            st.markdown("❌ &nbsp;Sin contrato activo")
            st.caption(
                "Para que tu certificado pueda generarse necesitas tener "
                "un contrato activo registrado."
            )
            st.page_link("pages/2_mi_perfil.py", label="Ir a Mi Perfil →", icon="👤")


def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = CertificacionService()
    usuario_id = sesion["id"]

    año_cert, mes_cert = servicio.periodo_certificable()
    nombre_mes_cert = MESES_ES[mes_cert - 1]
    es_anterior = servicio.es_mes_anterior()

    st.title("Mis Certificados")
    st.caption(
        "Aquí puedes consultar el estado de tu certificación mensual de correspondencia "
        "y descargar los certificados aprobados para tus cuentas de cobro."
    )

    # ── Estado del período certificable ──────────────────────────
    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id)

    # Recuperación: si tiene 3 firmas + contrato pero quedó en "pendiente" por
    # un fallo previo en auto-cert, certificar ahora y recargar.
    if cert_actual and cert_actual.get("estado") != "aprobado":
        if servicio.recuperar_auto_cert(usuario_id, cert_actual):
            cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id)

    if cert_actual and cert_actual.get("estado") == "aprobado":
        aprobado_por = cert_actual.get("aprobado_por", {})
        fecha_corte = aprobado_por.get("fecha")
        fecha_str = formato_fecha_bogota(fecha_corte, "%d/%m/%Y %H:%M")

        st.success(
            f"Tu certificado de **{nombre_mes_cert} {año_cert}** está aprobado.\n\n"
            f"Aprobado por **{aprobado_por.get('nombre', '')}** el {fecha_str}."
        )

        if cert_actual.get("observaciones"):
            st.info(f"Observación del supervisor: {cert_actual['observaciones']}")

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del certificado: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = f"Certificado_correspondencia_{nombre_mes_cert}_{año_cert}.pdf"
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver certificado", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    else:
        st.warning(f"Tu certificado de **{nombre_mes_cert} {año_cert}** aún está en proceso.")
        _mostrar_avance(usuario_id, cert_actual)

    # ── Historial ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Historial de certificados")

    historial = servicio.obtener_historial(usuario_id)

    # Excluir el período certificable del historial (ya se muestra arriba)
    historial_pasado = [
        c for c in historial
        if not (c.get("año") == año_cert and c.get("mes") == mes_cert)
    ]

    if not historial_pasado:
        st.caption("Aún no tienes certificados de meses anteriores.")
    else:
        for cert in historial_pasado:
            mes_num = cert.get("mes", 1)
            año_cert = cert.get("año", "")
            mes_nombre = MESES_ES[mes_num - 1]
            estado = cert.get("estado")

            with st.container(border=True):
                c_info, c_btn = st.columns([4, 1])

                with c_info:
                    st.markdown(
                        f"**{mes_nombre} {año_cert}** &nbsp; {_badge_estado(estado)}",
                        unsafe_allow_html=False,
                    )
                    if estado == "aprobado":
                        aprobado_por = cert.get("aprobado_por", {})
                        fecha_ap = aprobado_por.get("fecha")
                        fecha_str = formato_fecha_bogota(fecha_ap, "%d/%m/%Y")
                        st.caption(
                            f"Aprobado por {aprobado_por.get('nombre', '')} · {fecha_str}"
                        )
                    if cert.get("observaciones"):
                        st.caption(f"Obs: {cert['observaciones']}")

                with c_btn:
                    if estado == "aprobado":
                        pdf_bytes = servicio.generar_pdf(cert)
                        nombre_archivo = f"Certificado_correspondencia_{mes_nombre}_{año_cert}.pdf"
                        cert_id = str(cert.get("_id", ""))
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_bytes,
                            file_name=nombre_archivo,
                            mime="application/pdf",
                            key=f"dl_{cert_id}",
                            use_container_width=True,
                        )
                        if st.button("👁️ Ver", key=f"prev_{cert_id}", use_container_width=True):
                            st.session_state["_preview_cert_user"] = {
                                "cert": cert,
                                "mes_nombre": mes_nombre,
                                "año": año_cert,
                            }
                            st.rerun()

    if st.session_state.get("_preview_cert_user"):
        _dialog_preview_cert(servicio)


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
