"""Página de verificación de autenticidad de certificados.

Cualquier usuario autenticado puede ingresar el código impreso en el
certificado PDF y comprobar que es original e inalterado.
"""

import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.sesion import obtener_sesion
from app.core.zona_horaria import formato_fecha_bogota
from app.services.certificacion_service import CertificacionService, MESES_ES


def render(sesion=None):
    sesion = sesion or obtener_sesion()

    if not sesion:
        st.warning("Debes iniciar sesión.")
        st.stop()

    servicio = CertificacionService()

    mostrar_titulo_decorado("Verificar Certificado")
    st.caption(
        "Ingresa el código que aparece en el recuadro inferior del certificado PDF "
        "para comprobar su autenticidad. Un certificado genuino siempre devuelve "
        "resultado positivo con los datos exactos del titular."
    )

    st.divider()

    codigo = st.text_input(
        "Código de verificación",
        placeholder="XXXX-XXXX-XXXX-XXXX",
        max_chars=19,
    )

    if st.button("Verificar autenticidad", type="primary"):
        codigo_limpio = codigo.strip().upper().replace(" ", "")
        if not codigo_limpio:
            st.warning("Ingresa el código de verificación antes de continuar.")
            st.stop()

        cert = servicio.verificar_certificado(codigo_limpio)

        if cert:
            nombre = cert.get("nombre_usuario", "")
            año = cert.get("año", "")
            mes_num = cert.get("mes", 1)
            mes_nombre = MESES_ES[mes_num - 1]
            aprobado_por = cert.get("aprobado_por", {})
            fecha_ap = aprobado_por.get("fecha")
            fecha_str = formato_fecha_bogota(fecha_ap, "%d de %B de %Y a las %H:%M") if fecha_ap else "—"

            st.success("Certificado válido — documento auténtico")

            with st.container(border=True):
                st.markdown(f"**Titular:** {nombre}")
                st.markdown(f"**Período certificado:** {mes_nombre} {año}")
                st.markdown(
                    f"**Emitido por:** {aprobado_por.get('nombre', '—')} · {fecha_str}"
                )
                if cert.get("observaciones"):
                    st.caption(f"Observaciones: {cert['observaciones']}")

            pdf_bytes = servicio.generar_pdf(cert)
            nombre_archivo = f"Certificado_correspondencia_{mes_nombre}_{año}.pdf"
            st.download_button(
                label="⬇️ Descargar certificado verificado",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary",
            )
        else:
            st.error(
                "Código no encontrado. El certificado puede ser falso, "
                "haber sido revocado o el código fue transcrito incorrectamente."
            )
            st.caption("Revisa que el código esté completo y en el formato XXXX-XXXX-XXXX-XXXX.")


render(obtener_sesion())
