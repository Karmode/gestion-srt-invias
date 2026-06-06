"""Página de certificaciones mensuales — vista del colaborador.

Cada usuario ve el estado de su certificación del mes actual
y el historial de certificados anteriores con opción de descarga PDF.
"""

import streamlit as st

from app.core.sesion import obtener_sesion
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES


def _badge_estado(estado: str | None) -> str:
    if estado == "aprobado":
        return "✅ **Certificado**"
    return "⏳ Pendiente de aprobación"


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

        pdf_bytes = servicio.generar_pdf(cert_actual)
        nombre_archivo = f"Certificado_correspondencia_{nombre_mes_cert}_{año_cert}.pdf"
        st.download_button(
            label="⬇️ Descargar certificado PDF",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            type="primary",
        )
    else:
        st.warning(
            f"Tu certificado de **{nombre_mes_cert} {año_cert}** aún no ha sido emitido. "
            f"Contacta a tu supervisor."
        )

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
                        nombre_archivo = (
                            f"Certificado_correspondencia_{mes_nombre}_{año_cert}.pdf"
                        )
                        st.download_button(
                            label="⬇️ PDF",
                            data=pdf_bytes,
                            file_name=nombre_archivo,
                            mime="application/pdf",
                            key=f"dl_{cert.get('_id')}",
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            "—",
                            key=f"na_{cert.get('_id')}",
                            disabled=True,
                            use_container_width=True,
                        )


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
