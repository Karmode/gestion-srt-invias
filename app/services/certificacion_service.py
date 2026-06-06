"""Servicio de certificaciones mensuales SRTI-INVIAS.

El período de certificación va del día 25 al último día de cada mes.
El supervisor revisa el estado de correspondencia y emite el certificado
que le sirve al colaborador como soporte para su cuenta de cobro.
"""

import hashlib
import hmac
import io
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from app.config import configuracion
from app.repositories.certificacion_repo import CertificacionRepositorio
from app.core.zona_horaria import ZONA_BOGOTA, utc_a_bogota

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


class CertificacionService:
    def __init__(self) -> None:
        self.repo = CertificacionRepositorio()

    # ──────────────────────────────────────────────────────────────
    # Helpers de período
    # ──────────────────────────────────────────────────────────────

    def _ahora_bogota(self) -> datetime:
        return datetime.now(ZONA_BOGOTA)

    def periodo_certificable(self) -> tuple:
        """Devuelve (año, mes) del período que se puede certificar hoy.

        Días 1–24: mes anterior (ventana de ponerse al día).
        Días 25–31: mes actual (ventana normal).
        """
        ahora = self._ahora_bogota()
        if ahora.day >= 25:
            return ahora.year, ahora.month
        if ahora.month == 1:
            return ahora.year - 1, 12
        return ahora.year, ahora.month - 1

    def es_mes_anterior(self) -> bool:
        """True si el período certificable es el mes anterior (día 1–24)."""
        return self._ahora_bogota().day < 25

    def _generar_hash(self, usuario_id: str, año: int, mes: int, supervisor_id: str, ts_iso: str) -> str:
        """HMAC-SHA256 firmado con SECRET_KEY. Toma los primeros 16 hex → XXXX-XXXX-XXXX-XXXX."""
        mensaje = f"{usuario_id}:{año}:{mes}:{supervisor_id}:{ts_iso}"
        digest = hmac.new(
            configuracion.secret_key.encode("utf-8"),
            mensaje.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16].upper()
        return f"{digest[:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"

    def es_periodo_abierto(self) -> bool:
        """Siempre abierto: antes del 25 se certifica el mes anterior,
        del 25 en adelante se certifica el mes actual."""
        return True

    # ──────────────────────────────────────────────────────────────
    # Consultas de certificaciones
    # ──────────────────────────────────────────────────────────────

    def obtener_certificacion_periodo_actual(self, usuario_id: str) -> Optional[Dict]:
        """Devuelve la certificación del período certificable hoy (mes actual o anterior)."""
        año, mes = self.periodo_certificable()
        return self.repo.buscar_por_usuario_periodo(usuario_id, año, mes)

    def obtener_historial(self, usuario_id: str) -> List[Dict]:
        return self.repo.listar_por_usuario(usuario_id)

    def verificar_certificado(self, codigo: str) -> Optional[Dict]:
        """Busca un certificado por su hash de verificación. Retorna el doc o None."""
        codigo_normalizado = codigo.strip().upper().replace(" ", "")
        return self.repo.buscar_por_hash(codigo_normalizado)

    def obtener_empleados_para_certificar(self) -> List[Dict]:
        """Lista todos los colaboradores con su estado de correspondencia
        y el estado de su certificación en el período actual."""
        from app.services.correspondencia_service import CorrespondenciaService

        corr_service = CorrespondenciaService()
        año, mes = self.periodo_certificable()

        estado_formatos = corr_service.obtener_estado_formatos()

        certs_mes = {
            str(c["usuario_id"]): c
            for c in self.repo.listar_por_periodo(año, mes)
        }

        resultados = []
        for estado in estado_formatos:
            uid = estado["usuario_id"]
            resultados.append({
                "usuario_id": uid,
                "nombre": estado["responsable"],
                "cantidad_pendientes": estado["cantidad_pendientes"],
                "cantidad_vencidas": estado["cantidad_vencidas"],
                "al_dia": estado["cantidad_vencidas"] == 0,
                "certificacion": certs_mes.get(uid),
            })

        return resultados

    # ──────────────────────────────────────────────────────────────
    # Acción de certificar
    # ──────────────────────────────────────────────────────────────

    def certificar_empleado(
        self,
        usuario_id_empleado: str,
        nombre_empleado: str,
        supervisor_id: str,
        supervisor_nombre: str,
        observaciones: str = "",
    ) -> bool:
        """El supervisor certifica que un colaborador está al día.
        Si ya existe una certificación para el período, la sobreescribe."""
        año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        hash_code = self._generar_hash(
            usuario_id_empleado, año, mes, supervisor_id, ahora_utc.isoformat()
        )

        campos = {
            "estado": "aprobado",
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "observaciones": observaciones.strip() or None,
            "hash_verificacion": hash_code,
            "aprobado_por": {
                "usuario_id": ObjectId(supervisor_id),
                "nombre": supervisor_nombre,
                "fecha": ahora_utc,
            },
        }

        cert_existente = self.repo.buscar_por_usuario_periodo(
            usuario_id_empleado, año, mes
        )

        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id_empleado),
                "nombre_usuario": nombre_empleado,
                "año": año,
                "mes": mes,
                "creado_en": ahora_utc,
            })
            self.repo.crear(campos)

        return True

    # ──────────────────────────────────────────────────────────────
    # Generación de PDF
    # ──────────────────────────────────────────────────────────────

    def generar_pdf(self, certificacion: Dict) -> bytes:
        """Genera el PDF del certificado con ReportLab en memoria."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable,
        )

        NARANJA = HexColor("#FF8C00")
        CAFE = HexColor("#3D1E0A")
        GRIS = HexColor("#777777")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        estilos = getSampleStyleSheet()

        s_titulo = ParagraphStyle(
            "titulo", parent=estilos["Heading1"],
            fontSize=17, textColor=NARANJA, alignment=TA_CENTER,
            spaceAfter=4, fontName="Helvetica-Bold",
        )
        s_inst = ParagraphStyle(
            "inst", parent=estilos["Normal"],
            fontSize=10, textColor=CAFE, alignment=TA_CENTER, spaceAfter=2,
        )
        s_cuerpo = ParagraphStyle(
            "cuerpo", parent=estilos["Normal"],
            fontSize=11, alignment=TA_JUSTIFY, leading=18, spaceAfter=10,
        )
        s_nombre = ParagraphStyle(
            "nombre", parent=estilos["Normal"],
            fontSize=14, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=CAFE, spaceAfter=6,
        )
        s_pie = ParagraphStyle(
            "pie", parent=estilos["Normal"],
            fontSize=7, textColor=GRIS, alignment=TA_CENTER,
        )

        nombre = certificacion.get("nombre_usuario", "")
        año = certificacion.get("año", "")
        mes_num = certificacion.get("mes", 1)
        mes_nombre = MESES_ES[mes_num - 1]
        hash_code = certificacion.get("hash_verificacion", "")

        def _watermark(canvas_obj, _doc):
            from reportlab.lib.colors import Color
            w, h = letter

            # 1. Fondo de seguridad: texto INVIAS repetido en diagonal
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 7.5)
            canvas_obj.setFillColor(Color(0.68, 0.68, 0.68, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(38)
            for xi in range(-5, 6):
                for yi in range(-14, 15):
                    canvas_obj.drawCentredString(xi * 112, yi * 42, "INVIAS  SRTI")
            canvas_obj.restoreState()

            # 2. Marca de agua principal: nombre + mes/año
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica-Bold", 48)
            canvas_obj.setFillColor(Color(0.58, 0.58, 0.58, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 42, nombre.upper())
            canvas_obj.drawCentredString(0, -32, f"{mes_nombre.upper()} {año}")
            canvas_obj.restoreState()

            # 3. Doble borde institucional
            canvas_obj.saveState()
            nb = Color(1.0, 0.549, 0.0, alpha=0.55)
            canvas_obj.setStrokeColor(nb)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.rect(18, 18, w - 36, h - 36)
            canvas_obj.setLineWidth(0.35)
            canvas_obj.rect(23, 23, w - 46, h - 46)
            canvas_obj.restoreState()

            # 4. Ornamentos en esquinas (diamante + brazos en L) y marcas de registro
            canvas_obj.saveState()
            nf = Color(1.0, 0.549, 0.0, alpha=0.58)
            canvas_obj.setFillColor(nf)
            canvas_obj.setStrokeColor(nf)
            canvas_obj.setLineWidth(0.9)
            dm = 7
            arm = 20
            for cx, cy, dx, dy in [
                (28, 28, 1, 1), (w - 28, 28, -1, 1),
                (28, h - 28, 1, -1), (w - 28, h - 28, -1, -1),
            ]:
                p = canvas_obj.beginPath()
                p.moveTo(cx, cy + dm)
                p.lineTo(cx + dm, cy)
                p.lineTo(cx, cy - dm)
                p.lineTo(cx - dm, cy)
                p.close()
                canvas_obj.drawPath(p, stroke=1, fill=1)
                canvas_obj.line(cx, cy, cx + dx * arm, cy)
                canvas_obj.line(cx, cy, cx, cy + dy * arm)
            canvas_obj.setLineWidth(0.7)
            tk = 5
            for mx, my in [(w / 2, h - 18), (w / 2, 18), (18, h / 2), (w - 18, h / 2)]:
                canvas_obj.line(mx - tk, my, mx + tk, my)
                canvas_obj.line(mx, my - tk, mx, my + tk)
            canvas_obj.restoreState()

        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            fc_bogota = utc_a_bogota(fecha_corte)
            dia = fc_bogota.strftime("%d")
            mes_corte = MESES_ES[fc_bogota.month - 1].lower()
            año_corte = fc_bogota.strftime("%Y")
            fecha_str = f"{dia} de {mes_corte} de {año_corte}"
        else:
            fecha_str = "fecha no disponible"

        aprobado_por = certificacion.get("aprobado_por", {})
        supervisor = aprobado_por.get("nombre", "Supervisor SRTI")
        obs = certificacion.get("observaciones") or ""

        story = []

        # Logo
        logo = os.path.join("app", "assets", "INVIAS_login_logo.png")
        if os.path.exists(logo):
            from reportlab.platypus import Image
            img = Image(logo, width=5 * cm, height=2.5 * cm, kind="proportional")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.3 * cm))

        story.append(HRFlowable(width="100%", thickness=2, color=NARANJA))
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS — INVIAS", s_inst))
        story.append(Paragraph(
            "Subdirección de Reglamentación Técnica e Innovación — SRTI", s_inst
        ))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("CERTIFICADO DE CORRESPONDENCIA", s_titulo))
        story.append(Paragraph(f"Período: {mes_nombre.upper()} {año}", s_inst))
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.8 * cm))

        story.append(Paragraph(
            "La Subdirección de Reglamentación Técnica e Innovación (SRTI) del "
            "Instituto Nacional de Vías (INVIAS) <b>CERTIFICA</b> que:",
            s_cuerpo,
        ))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(nombre.upper(), s_nombre))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            f"se encuentra <b>AL DÍA</b> con la correspondencia asignada a su cargo, "
            f"habiendo atendido oportunamente los radicados dentro de los términos "
            f"establecidos, a la fecha del <b>{fecha_str}</b>.",
            s_cuerpo,
        ))
        story.append(Paragraph(
            f"El presente certificado se expide para efectos de <b>sustento de cuenta "
            f"de cobro</b> correspondiente al mes de <b>{mes_nombre.upper()} de {año}</b>.",
            s_cuerpo,
        ))

        if obs:
            story.append(Paragraph(f"<i>Observaciones: {obs}</i>", s_cuerpo))

        story.append(Spacer(1, 1.5 * cm))

        firma = Table(
            [
                ["_" * 38],
                [supervisor.upper()],
                ["Supervisor — SRTI"],
                ["Instituto Nacional de Vías — INVIAS"],
            ],
            colWidths=[9 * cm],
        )
        firma.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (0, 0), 10),
            ("FONTSIZE", (0, 1), (0, 1), 11),
            ("FONTSIZE", (0, 2), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (0, 1), CAFE),
        ]))
        firma.hAlign = "CENTER"
        story.append(firma)

        story.append(Spacer(1, 1 * cm))

        # Código de verificación
        if hash_code:
            from reportlab.lib.colors import HexColor as _HC
            from reportlab.platypus import Table as _T, TableStyle as _TS
            cod_tabla = _T(
                [[f"Código de verificación: {hash_code}"]],
                colWidths=[doc.width],
            )
            cod_tabla.setStyle(_TS([
                ("BACKGROUND", (0, 0), (-1, -1), _HC("#FFF3E0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), CAFE),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 1.2, NARANJA),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(cod_tabla)
            story.append(Spacer(1, 0.25 * cm))

        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            f"Documento generado automáticamente por el Sistema de Gestión de "
            f"Correspondencia SRTI-INVIAS · {fecha_str}",
            s_pie,
        ))

        doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
        buf.seek(0)
        return buf.getvalue()
