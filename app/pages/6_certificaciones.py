"""Página de certificaciones mensuales — vista del colaborador.

Cada usuario ve el estado de su certificación del mes actual
y el historial de certificados anteriores con opción de descarga PDF.
"""

import os

import streamlit as st
from app.config import configuracion
from app.core.ui_titulos import mostrar_titulo_decorado

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
    data = st.session_state.pop("_preview_cert_user", None)
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


def _render_verificador_codigo(servicio: CertificacionService):
    mostrar_titulo_decorado("Verificar formato")
    st.caption(
        "Ingresa el código que aparece en el recuadro inferior del certificado PDF "
        "para comprobar su autenticidad. Un certificado genuino siempre devuelve "
        "resultado positivo con los datos exactos del titular."
    )
    codigo = st.text_input("Código de verificación", placeholder="XXXX-XXXX-XXXX-XXXX", max_chars=19)
    if st.button("Verificar autenticidad", type="primary"):
        codigo_limpio = codigo.strip().upper().replace(" ", "")
        if not codigo_limpio:
            st.warning("Ingresa el código de verificación antes de continuar.")
            return

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
                st.markdown(f"**Emitido por:** {aprobado_por.get('nombre', '—')} · {fecha_str}")
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
            st.error("Código no encontrado. El certificado puede ser falso, haber sido revocado o el código fue transcrito incorrectamente.")
            st.caption("Revisa que el código esté completo y en el formato XXXX-XXXX-XXXX-XXXX.")


def _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, es_anterior):
    mostrar_titulo_decorado("Formato de control a la correspondencia - Gestión documental - SECOP II")
    
    etiqueta = (
        f"Período anterior — {nombre_mes_cert} {año_cert} (ponerse al día)"
        if es_anterior
        else f"Período actual — {nombre_mes_cert} {año_cert}"
    )
    st.subheader(etiqueta)

    cert_actual = servicio.obtener_certificacion_periodo_actual(usuario_id)

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


def _render_opcion_7_herramientas():
    """Viñeta 7 — acceso a plataformas externas (ADRES, SECOP II, KLIC 2, AZ Digital, Her. PDF)."""
    import base64

    mostrar_titulo_decorado("🌐 ADRES · SECOP II · KLIC 2 · AZ Digital · Her. PDF")
    st.caption("Haz clic en cualquier imagen para abrir la plataforma en una nueva pestaña.")
    st.write("")

    PLATAFORMAS = [
        {
            "img": os.path.join("app", "assets", "az_digital.png"),
            "name": "AZ Digital",
            "desc": "Carpeta digital de gestión documental",
            "url": configuracion.az_digital_url,
        },
        {
            "img": os.path.join("app", "assets", "klic_2.png"),
            "name": "KLIC 2",
            "desc": "Sistema de correspondencia INVIAS",
            "url": configuracion.klic_2_url,
        },
        {
            "img": os.path.join("app", "assets", "adres.png"),
            "name": "ADRES",
            "desc": "Administradora de Recursos del SGSSS",
            "url": configuracion.adres_url,
        },
        {
            "img": os.path.join("app", "assets", "secop.png"),
            "name": "SECOP II",
            "desc": "Sistema Electrónico de Contratación Pública",
            "url": configuracion.secop_url,
        },
        {
            "img": os.path.join("app", "assets", "pdf_h.png"),
            "name": "Her. PDF",
            "desc": "Herramienta de edición y gestión PDF",
            "url": configuracion.pdf_h_url,
        },
    ]

    def _img_b64(path: str) -> str:
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def _card(plat: dict, delay_ms: int = 0) -> str:
        b64 = _img_b64(plat["img"])
        img_tag = (
            f'<img src="data:image/png;base64,{b64}" alt="{plat["name"]}" '
            f'style="max-height:80px;max-width:100%;object-fit:contain;'
            f'transition:transform 0.22s ease;" />'
            if b64 else ""
        )
        # Si hay URL, toda la imagen es un enlace; si no, solo muestra la imagen
        if plat["url"]:
            content = (
                f'<a href="{plat["url"]}" target="_blank" rel="noopener noreferrer" '
                f'style="display:block;text-decoration:none;">'
                f'{img_tag}'
                f'</a>'
            )
        else:
            content = img_tag

        return f"""
        <div style="
            border: 1.5px solid rgba(255,140,0,0.28);
            border-radius: 16px;
            padding: 22px 16px 16px;
            text-align: center;
            background: transparent;
            transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
            animation: fadeCardIn7 0.4s ease {delay_ms}ms both;
            cursor: {'pointer' if plat['url'] else 'default'};
        " onmouseover="this.style.transform='translateY(-5px)';this.style.boxShadow='0 10px 32px rgba(255,140,0,0.22)';this.style.borderColor='rgba(255,140,0,0.60)'"
           onmouseout="this.style.transform='';this.style.boxShadow='';this.style.borderColor='rgba(255,140,0,0.28)'">
            {content}
            <div style="font-weight:700;font-size:0.96em;margin:10px 0 3px;color:#FF8C00;">{plat["name"]}</div>
            <div style="font-size:0.78em;color:#888;">{plat["desc"]}</div>
        </div>
        """

    # CSS de animación (una sola vez)
    st.markdown(
        """
        <style>
        @keyframes fadeCardIn7 {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Primera fila: 3 plataformas ──────────────────────────────────────────
    cols1 = st.columns(3, gap="medium")
    for i, plat in enumerate(PLATAFORMAS[:3]):
        with cols1[i]:
            st.markdown(_card(plat, delay_ms=i * 80), unsafe_allow_html=True)

    st.write("")

    # ── Segunda fila: 2 plataformas centradas ───────────────────────────────
    _, col_d, col_e, _ = st.columns([0.5, 1, 1, 0.5], gap="medium")
    for col, plat, delay in zip([col_d, col_e], PLATAFORMAS[3:], [240, 320]):
        with col:
            st.markdown(_card(plat, delay_ms=delay), unsafe_allow_html=True)


def _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert):
    mostrar_titulo_decorado("Historial de formatos")

    historial = servicio.obtener_historial(usuario_id)

    historial_pasado = [
        c for c in historial
        if not (c.get("año") == año_cert and c.get("mes") == mes_cert)
    ]

    if not historial_pasado:
        st.caption("Aún no tienes formatos de meses anteriores.")
    else:
        for cert in historial_pasado:
            mes_num = cert.get("mes", 1)
            año_cert_hist = cert.get("año", "")
            mes_nombre = MESES_ES[mes_num - 1]
            estado = cert.get("estado")

            with st.container(border=True):
                c_info, c_btn = st.columns([4, 1])

                with c_info:
                    st.markdown(
                        f"**{mes_nombre} {año_cert_hist}** &nbsp; {_badge_estado(estado)}",
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
                        nombre_archivo = f"Certificado_correspondencia_{mes_nombre}_{año_cert_hist}.pdf"
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
                                "año": año_cert_hist,
                            }
                            st.rerun()


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

    mostrar_titulo_decorado("Formatos de contrato")

    col_menu, col_contenido = st.columns([1, 2], gap="large")

    with col_menu:
        with st.container(border=True):
            st.markdown("### Formatos - Cuenta de cobro SRTI")
            st.button("1- Cuenta de cobro.", disabled=True, use_container_width=True)
            st.button("2- Form. retención en la fuente Primera cuenta.", disabled=True, use_container_width=True)
            st.button("3- Form. retención en la fuente Segunda cuenta ++", disabled=True, use_container_width=True)
            st.button("4- Form. condicion de declarante y dep. Economica.", disabled=True, use_container_width=True)
            st.button("5- Form. Acta de compromiso.", disabled=True, use_container_width=True)
            
            if st.button("6– Form. Gestión Corr – GD – SECOP II.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 6
                st.rerun()

            if st.button("7– ADRES · SECOP II · KLIC 2 · AZ · Her. PDF.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 7
                st.rerun()
            
            if st.button("8- Historial de formatos.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 8
                st.rerun()
                
            if st.button("9- Verificar formato.", type="primary", disabled=False, use_container_width=True):
                st.session_state["tab_formato_activo"] = 9
                st.rerun()

    with col_contenido:
        tab_activa = st.session_state.get("tab_formato_activo")
        if tab_activa == 6:
            _render_opcion_6_gestion_corr(servicio, usuario_id, año_cert, mes_cert, nombre_mes_cert, es_anterior)
        elif tab_activa == 7:
            _render_opcion_7_herramientas()
        elif tab_activa == 8:
            _render_opcion_8_historial(servicio, usuario_id, año_cert, mes_cert)
        elif tab_activa == 9:
            _render_verificador_codigo(servicio)
        else:
            st.info("👈 Selecciona un formato en el menú de la izquierda para visualizar su contenido.")

    if st.session_state.get("_preview_cert_user"):
        _dialog_preview_cert(servicio)


# Punto de entrada cuando Streamlit carga la página directamente
render(obtener_sesion())
