"""Servicio de certificaciones mensuales SRTI-INVIAS.

El período de certificación va del día 29 al último día de cada mes.
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

# Día del mes en que se abre la ventana normal de certificación del mes actual.
# Días 1 a (DIA_INICIO_PERIODO - 1): se certifica el mes anterior (ventana de ponerse al día).
# Días DIA_INICIO_PERIODO en adelante: se certifica el mes actual (ventana normal).
# Es el valor DEFAULT/fallback: el admin puede sobreescribirlo en runtime
# (ver ParametrosService, parámetro "dia_inicio_periodo_certificacion").
DIA_INICIO_PERIODO = 29


class CertificacionService:
    def __init__(self) -> None:
        self.repo = CertificacionRepositorio()

    # ──────────────────────────────────────────────────────────────
    # Helpers de período
    # ──────────────────────────────────────────────────────────────

    def _ahora_bogota(self) -> datetime:
        return datetime.now(ZONA_BOGOTA)

    def _dia_inicio_periodo(self) -> int:
        """Día del mes en que se abre la ventana normal de certificación.
        Configurable por el admin; cae a DIA_INICIO_PERIODO si no está definido."""
        try:
            from app.services.parametros_service import ParametrosService
            return ParametrosService().obtener("dia_inicio_periodo_certificacion")
        except Exception:
            return DIA_INICIO_PERIODO

    def periodo_certificable(self) -> tuple:
        """Devuelve (año, mes) del período que se puede certificar hoy.

        Antes del día de inicio: mes anterior (ventana de ponerse al día).
        Desde el día de inicio: mes actual (ventana normal).
        """
        ahora = self._ahora_bogota()
        if ahora.day >= self._dia_inicio_periodo():
            return ahora.year, ahora.month
        if ahora.month == 1:
            return ahora.year - 1, 12
        return ahora.year, ahora.month - 1

    def es_mes_anterior(self) -> bool:
        """True si el período certificable es el mes anterior (antes del día de inicio)."""
        return self._ahora_bogota().day < self._dia_inicio_periodo()

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
        """Siempre abierto: antes del 29 se certifica el mes anterior,
        del 29 en adelante se certifica el mes actual."""
        return True

    # ──────────────────────────────────────────────────────────────
    # Consultas de certificaciones
    # ──────────────────────────────────────────────────────────────

    def obtener_certificacion_periodo_actual(self, usuario_id: str, tipo_formato: str = None) -> Optional[Dict]:
        """Devuelve la certificación del período certificable hoy (mes actual o anterior)."""
        año, mes = self.periodo_certificable()
        return self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)

    def firmar_y_generar_dependencia(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)
        
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "dependencia_economica")
        
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id, año, mes, usuario_id, ahora_utc.isoformat())
        )
        
        campos = {
            "estado": "aprobado",  # Ya queda aprobado porque lo firma el contratista
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "dependencia_economica",
            "hash_verificacion": hash_code,
            "creado_en": ahora_utc,
        }
        
        if cert_existente:
            self.repo.actualizar(str(cert_existente["_id"]), campos)
        else:
            campos.update({
                "usuario_id": ObjectId(usuario_id),
                "nombre_usuario": nombre_usuario,
                "año": año,
                "mes": mes,
            })
            self.repo.crear(campos)
        return True

    def obtener_historial(self, usuario_id: str) -> List[Dict]:
        return self.repo.listar_por_usuario(usuario_id)

    def verificar_certificado(self, codigo: str) -> Optional[Dict]:
        """Busca un certificado por su hash de verificación. Retorna el doc o None."""
        codigo_normalizado = codigo.strip().upper().replace(" ", "")
        return self.repo.buscar_por_hash(codigo_normalizado)

    def obtener_empleados_para_certificar(self) -> List[Dict]:
        """Lista todos los colaboradores con correspondencia, estado de firmas y contrato activo."""
        from app.services.correspondencia_service import CorrespondenciaService
        from app.repositories.usuario_repo import UsuarioRepositorio

        corr_service = CorrespondenciaService()
        usuario_repo = UsuarioRepositorio()
        año, mes = self.periodo_certificable()

        estado_formatos = corr_service.obtener_estado_formatos()
        todos_usuarios = {str(u["_id"]): u for u in usuario_repo.listar()}
        certs_mes = {
            str(c["usuario_id"]): c
            for c in self.repo.listar_por_periodo(año, mes)
        }

        resultados = []
        for estado in estado_formatos:
            uid = estado["usuario_id"]
            cert = certs_mes.get(uid)
            firmas = cert.get("firmas", {}) if cert else {}

            usuario_data = todos_usuarios.get(uid, {})
            contratos = usuario_data.get("contratos") or []
            contrato = self._contrato_vigente(contratos)
            tiene_contrato = bool(contrato.get("numero"))

            resultados.append({
                "usuario_id": uid,
                "nombre": estado["responsable"],
                "cantidad_pendientes": estado["cantidad_pendientes"],
                "cantidad_vencidas": estado["cantidad_vencidas"],
                "al_dia": estado["cantidad_vencidas"] == 0,
                "certificacion": cert,
                "firmas": firmas,
                "tiene_contrato": tiene_contrato,
                "numero_contrato": contrato.get("numero"),
            })

        return resultados

    # ──────────────────────────────────────────────────────────────
    # Configuración de firmantes designados
    # ──────────────────────────────────────────────────────────────

    def obtener_firmantes_config(self) -> Dict:
        """Devuelve los 3 firmantes designados desde opciones_configuracion."""
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        doc = ConfiguracionRepositorio().obtener("firmantes_certificacion")
        vacio = {"corr": None, "gd": None, "secop": None}
        return doc.get("firmantes", vacio) if doc else vacio

    def guardar_firmante(self, tipo: str, usuario_id: Optional[str], nombre: Optional[str]) -> bool:
        """Admin designa quién es el firmante de un tipo dado.
        Sincroniza el permiso certificacion.firmar_<tipo> en permisos_extra del usuario.
        """
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        from app.repositories.usuario_repo import UsuarioRepositorio

        perm = f"certificacion.firmar_{tipo}"
        config = self.obtener_firmantes_config()
        repo_conf = ConfiguracionRepositorio()
        repo_usr = UsuarioRepositorio()

        old = config.get(tipo) or {}
        old_uid = str(old.get("usuario_id", "")) if old and old.get("usuario_id") else None

        # Remover permiso del firmante anterior si cambia
        if old_uid and old_uid != usuario_id:
            old_user = repo_usr.buscar_por_id(old_uid)
            if old_user:
                permisos_limpios = [p for p in old_user.get("permisos_extra", []) if p != perm]
                repo_usr.actualizar(old_uid, {"permisos_extra": permisos_limpios})

        # Asignar permiso al nuevo firmante
        if usuario_id:
            new_user = repo_usr.buscar_por_id(usuario_id)
            if new_user:
                permisos_new = list(set(new_user.get("permisos_extra", []) + [perm]))
                repo_usr.actualizar(usuario_id, {"permisos_extra": permisos_new})

        valor = {"usuario_id": usuario_id, "nombre": nombre} if usuario_id else None
        repo_conf.upsert(
            "firmantes_certificacion",
            {
                "categoria": "firmantes_certificacion",
                f"firmantes.{tipo}": valor,
            },
        )
        return True

    # ──────────────────────────────────────────────────────────────
    # Registro de firmas por período
    # ──────────────────────────────────────────────────────────────

    def registrar_firma(
        self,
        empleado_id: str,
        empleado_nombre: str,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
    ) -> bool:
        """Registra la aprobación del firmante. Si con esta firma se completan
        las 3 y el contratista cumple requisitos, se certifica automáticamente."""
        año, mes = self.periodo_certificable()
        self.repo.registrar_firma(
            empleado_id, empleado_nombre, año, mes, tipo, firmante_id, firmante_nombre
        )
        self._intentar_auto_certificar(
            empleado_id, empleado_nombre, firmante_id, firmante_nombre, año, mes
        )
        return True

    def _intentar_auto_certificar(
        self,
        empleado_id: str,
        empleado_nombre: str,
        firmante_id: str,
        firmante_nombre: str,
        año: int,
        mes: int,
    ) -> None:
        """Auto-certifica cuando hay 3 firmas + contrato activo (sin importar estado de correspondencia)."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        cert = self.repo.buscar_por_usuario_periodo(empleado_id, año, mes)
        if not cert or cert.get("estado") == "aprobado":
            return

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return

        self.certificar_empleado(empleado_id, empleado_nombre, firmante_id, firmante_nombre)

    def revocar_firma(self, empleado_id: str, tipo: str) -> bool:
        """Revoca una firma previamente registrada."""
        año, mes = self.periodo_certificable()
        return self.repo.revocar_firma(empleado_id, año, mes, tipo)

    def recuperar_auto_cert(self, empleado_id: str, cert: dict) -> bool:
        """Certifica retroactivamente si el cert ya tiene las 3 firmas + contrato activo
        pero quedó en 'pendiente' por un fallo anterior en _intentar_auto_certificar.
        Retorna True si se certificó ahora."""
        from app.repositories.usuario_repo import UsuarioRepositorio

        if not cert or cert.get("estado") == "aprobado":
            return False

        firmas = cert.get("firmas", {})
        if not all(firmas.get(t) for t in ("corr", "gd", "secop")):
            return False

        usuario = UsuarioRepositorio().buscar_por_id(empleado_id)
        contratos = (usuario.get("contratos") or []) if usuario else []
        if not self._contrato_vigente(contratos).get("numero"):
            return False

        # Usar la última firma como firmante registrado en el certificado
        ultima_firma = next(
            (firmas[t] for t in ("secop", "gd", "corr") if firmas.get(t)), None
        )
        firmante_id = str(ultima_firma.get("firmante_id", "")) if ultima_firma else ""
        firmante_nombre = ultima_firma.get("firmante_nombre", "") if ultima_firma else ""
        nombre_empleado = cert.get("nombre_usuario", "")

        self.certificar_empleado(empleado_id, nombre_empleado, firmante_id, firmante_nombre)
        return True

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
        """Certifica al colaborador para el período actual.
        Si ya existe un hash previo, lo preserva para que los PDFs ya entregados
        sigan siendo verificables con el código original."""
        año, mes = self.periodo_certificable()
        ahora_utc = datetime.now(timezone.utc)

        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id_empleado, año, mes)

        # Preservar el hash si ya existe — un PDF descargado debe seguir siendo válido
        hash_code = (
            cert_existente["hash_verificacion"]
            if cert_existente and cert_existente.get("hash_verificacion")
            else self._generar_hash(usuario_id_empleado, año, mes, supervisor_id, ahora_utc.isoformat())
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

    @staticmethod
    def _contrato_vigente(contratos: list) -> dict:
        """Devuelve el contrato activo (sin fecha_fin o con fecha_fin futura).
        Si hay varios activos, retorna el de fecha_inicio más reciente."""
        if not contratos:
            return {}
        hoy = datetime.now(ZONA_BOGOTA).date()
        activos = []
        for c in contratos:
            fecha_fin = c.get("fecha_fin")
            if fecha_fin:
                if fecha_fin.tzinfo is None:
                    from datetime import timezone as _tz
                    fecha_fin = fecha_fin.replace(tzinfo=_tz.utc)
                if fecha_fin.astimezone(ZONA_BOGOTA).date() >= hoy:
                    activos.append(c)
            else:
                activos.append(c)
        pool = activos or contratos
        # Usar datetime.min (naive) como fallback para que la comparación sea homogénea:
        # PyMongo devuelve datetimes naive; datetime.min.replace(tzinfo=...) sería aware y
        # lanzaría TypeError cuando se mezclan contratos con y sin fecha_inicio.
        pool.sort(
            key=lambda c: c.get("fecha_inicio") or datetime.min,
            reverse=True,
        )
        return pool[0]

    def generar_pdf(self, certificacion: Dict) -> bytes:
        """Genera el PDF del certificado con ReportLab en memoria."""
        if certificacion.get("tipo_formato") == "dependencia_economica":
            return self.generar_pdf_dependencia(certificacion)

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
        NEGRO = HexColor("#000000")
        GRIS = HexColor("#777777")
        GRIS_TABLA = HexColor("#F5F5F5")

        # ── datos del usuario (contrato activo, cédula) ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass
        contratos = usuario_data.get("contratos") or []
        contrato = self._contrato_vigente(contratos)
        numero_contrato = contrato.get("numero") or "—"
        cedula = usuario_data.get("numero_documento") or "—"

        nombre = certificacion.get("nombre_usuario", "")
        año = certificacion.get("año", "")
        mes_num = certificacion.get("mes", 1)
        mes_nombre = MESES_ES[mes_num - 1]
        hash_code = certificacion.get("hash_verificacion", "")
        obs = certificacion.get("observaciones") or ""

        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            fc_bogota = utc_a_bogota(fecha_corte)
            dia_expedicion = fc_bogota.strftime("%d").lstrip("0") or "1"
            mes_expedicion = MESES_ES[fc_bogota.month - 1]
            año_expedicion = fc_bogota.strftime("%Y")
        else:
            ahora = datetime.now(ZONA_BOGOTA)
            dia_expedicion = str(ahora.day)
            mes_expedicion = MESES_ES[ahora.month - 1]
            año_expedicion = str(ahora.year)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=0.8 * cm,
            bottomMargin=1.5 * cm,
        )

        estilos = getSampleStyleSheet()

        s_inst_bold = ParagraphStyle(
            "inst_bold", parent=estilos["Normal"],
            fontSize=9, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=1, leading=12,
        )
        s_titulo = ParagraphStyle(
            "titulo", parent=estilos["Normal"],
            fontSize=10, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=2, leading=13,
        )
        s_cuerpo = ParagraphStyle(
            "cuerpo", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=5,
        )
        s_bullet = ParagraphStyle(
            "bullet", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=3,
            leftIndent=12,
        )
        s_pie = ParagraphStyle(
            "pie", parent=estilos["Normal"],
            fontSize=7, textColor=GRIS, alignment=TA_CENTER,
        )

        def _watermark(canvas_obj, _doc):
            from reportlab.lib.colors import Color
            w, h = letter

            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 7.5)
            canvas_obj.setFillColor(Color(0.68, 0.68, 0.68, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(38)
            for xi in range(-5, 6):
                for yi in range(-14, 15):
                    canvas_obj.drawCentredString(xi * 112, yi * 42, "INVIAS  SRTI")
            canvas_obj.restoreState()

            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica-Bold", 48)
            canvas_obj.setFillColor(Color(0.58, 0.58, 0.58, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 42, nombre.upper())
            canvas_obj.drawCentredString(0, -32, f"{mes_nombre.upper()} {año}")
            canvas_obj.restoreState()

            canvas_obj.saveState()
            nb = Color(1.0, 0.549, 0.0, alpha=0.55)
            canvas_obj.setStrokeColor(nb)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.rect(18, 18, w - 36, h - 36)
            canvas_obj.setLineWidth(0.35)
            canvas_obj.rect(23, 23, w - 46, h - 46)
            canvas_obj.restoreState()

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

        story = []

        # ── Logo ──
        logo = os.path.join("app", "assets", "INVIAS_login_logo.png")
        if os.path.exists(logo):
            from reportlab.platypus import Image
            img = Image(logo, width=4 * cm, height=2 * cm, kind="proportional")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.2 * cm))

        story.append(HRFlowable(width="100%", thickness=2, color=NARANJA))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS – INVIAS", s_inst_bold))
        story.append(Paragraph("SUBDIRECCIÓN DE REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_inst_bold))
        story.append(Paragraph("FORMATO DE CONTROL DE CORRESPONDENCIA Y PLATAFORMA SECOP II", s_titulo))
        story.append(Spacer(1, 0.25 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.3 * cm))

        # ── Tabla de identificación ──
        col_lbl = 5.2 * cm
        col_val = doc.width - col_lbl
        id_tabla = Table(
            [
                ["Número de contrato", numero_contrato],
                ["Contratista", nombre],
                ["Cédula del contratista", cedula],
            ],
            colWidths=[col_lbl, col_val],
            rowHeights=0.6 * cm,
        )
        id_tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), GRIS_TABLA),
            ("TEXTCOLOR", (0, 0), (-1, -1), NEGRO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(id_tabla)
        story.append(Spacer(1, 0.35 * cm))

        # ── Cuerpo principal ──
        story.append(Paragraph(
            f"En cumplimiento y ejercicio de la función de supervisión y/o ordenación del gasto "
            f"(según corresponda) procede la suscrita con la verificación del cumplimiento adecuado "
            f"de las obligaciones establecidas en el Anexo del Contrato Electrónico – Clausulado "
            f"General de Contrato de Prestación de Servicios Profesionales y/o de Apoyo a la Gestión, "
            f"para el periodo del mes de <b>{mes_nombre}</b> de <b>{año}</b>; en consecuencia, se deja "
            f"constancia de que, una vez efectuada la revisión correspondiente a los soportes "
            f"documentales, matrices de seguimiento y plataforma SECOP II, el(a) contratista:",
            s_cuerpo,
        ))

        # ── Obligaciones (bullets) ──
        obligaciones = [
            "Mantuvo actualizada la información relacionada con la correspondencia, oficios, "
            "memorandos y demás asuntos a su cargo en las bases de datos y sistemas de información "
            "dispuestos por el INVIAS, conforme a los lineamientos institucionales y a los parámetros "
            "definidos para el seguimiento contractual. (Obligación general 5)",

            "Cumplió con las actividades de gestión documental y archivo derivadas de la ejecución "
            "contractual, de acuerdo con los lineamientos institucionales y las disposiciones aplicables "
            "del Archivo General de la Nación – AGN. (Obligación general 21)",

            "Registró / actualizó en la plataforma SECOP II la información correspondiente al "
            "\"Plan de Pagos\", ubicada en la pestaña \"Ejecución del Contrato\", adjuntando el "
            "informe mensual de actividades, sus soportes y la planilla de aportes al Sistema de "
            "Seguridad Social Integral, para efectos de revisión y aprobación por parte del supervisor "
            "del contrato. (Obligación general 32)",

            "Se encuentra al día con la proyección, revisión, tramité y atención conforme los "
            "lineamientos establecidos en la Ley, respecto las solicitudes, peticiones, quejas, "
            "reclamos, sugerencias (PQRS), memorandos, comunicaciones internas o externas, que le "
            "sean asignados por el supervisor del contrato y que tengan relación con el objeto "
            "contractual y el alcance de la Subdirección de Reglamentación Técnica e Innovación "
            "(Obligación Especifica No. 5)",
        ]
        for ob in obligaciones:
            story.append(Paragraph(f"• {ob}", s_bullet))

        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            "La presente constancia se expide como soporte de verificación de cumplimiento de "
            "actividades objeto de seguimiento administrativo y documental, y constituye un insumo "
            "para el ejercicio de supervisión contractual para efectos del trámite de pago.",
            s_cuerpo,
        ))

        if obs:
            story.append(Paragraph(f"<i>Observaciones: {obs}</i>", s_cuerpo))

        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(
            f"Se expide a los <b>{dia_expedicion}</b> días del mes de "
            f"<b>{mes_expedicion}</b> de <b>{año_expedicion}</b>",
            s_cuerpo,
        ))

        story.append(Spacer(1, 0.25 * cm))

        # ── Firma: imagen pegada a la línea en una sola tabla ──
        ruta_firma = os.path.join("app", "assets", "Firma_Nestor.png")
        if os.path.exists(ruta_firma):
            from reportlab.platypus import Image as _Img
            firma_img = _Img(ruta_firma, width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                ["Néstor Alfonso Navarro Tovar"],
                ["Contratista Subdirección de Reglamentación Técnica e Innovación"],
            ]
            firma_tabla = Table(filas_firma, colWidths=[doc.width])
            firma_tabla.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (0, 1), CAFE),
                # línea entre imagen y nombre — la firma la "toca"
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor("#AAAAAA")),
                ("TOPPADDING", (0, 0), (-1, 0), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
            ]))
        else:
            filas_firma = [
                [""],
                ["Néstor Alfonso Navarro Tovar"],
                ["Contratista Subdirección de Reglamentación Técnica e Innovación"],
            ]
            firma_tabla = Table(filas_firma, colWidths=[doc.width], rowHeights=[1.5 * cm, None, None])
            firma_tabla.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (0, 1), CAFE),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, HexColor("#AAAAAA")),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
            ]))
        story.append(firma_tabla)

        story.append(Spacer(1, 0.4 * cm))

        # ── Código de verificación ──
        if hash_code:
            cod_tabla = Table(
                [[f"Código de verificación: {hash_code}"]],
                colWidths=[doc.width],
            )
            cod_tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFF3E0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), CAFE),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 1.2, NARANJA),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(cod_tabla)
            story.append(Spacer(1, 0.2 * cm))

        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(
            f"Documento generado automáticamente por el Sistema de Gestión de "
            f"Correspondencia SRTI-INVIAS · {dia_expedicion} de {mes_expedicion} de {año_expedicion}",
            s_pie,
        ))

        doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
        buf.seek(0)
        return buf.getvalue()

    def generar_pdf_dependencia(self, certificacion: Dict) -> bytes:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor, Color
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable, Image,
        )

        # ── Paleta idéntica al formato 6 ──
        NARANJA   = HexColor("#FF8C00")
        CAFE      = HexColor("#3D1E0A")
        NEGRO     = HexColor("#000000")
        GRIS      = HexColor("#777777")
        GRIS_TABLA = HexColor("#F5F5F5")

        # ── Datos del usuario ──
        from app.repositories.usuario_repo import UsuarioRepositorio
        usuario_id   = str(certificacion.get("usuario_id", ""))
        usuario_data: dict = {}
        if usuario_id:
            try:
                usuario_data = UsuarioRepositorio().buscar_por_id(usuario_id) or {}
            except Exception:
                pass

        nombre    = usuario_data.get("nombre_completo", "")
        tipo_doc  = usuario_data.get("tipo_documento", "")
        cedula    = usuario_data.get("numero_documento")    or "—"
        lugar_exp = usuario_data.get("lugar_expedicion_documento") or "—"

        info_laboral     = usuario_data.get("informacion_laboral") or {}
        tributaria       = info_laboral.get("tributaria") or {}
        declarante_renta = tributaria.get("declarante_renta", False)
        dependientes     = info_laboral.get("dependientes") or []

        año       = certificacion.get("año", "")
        mes_num   = certificacion.get("mes", 1)
        mes_nombre = MESES_ES[mes_num - 1]
        hash_code = certificacion.get("hash_verificacion", "")

        fecha_corte = certificacion.get("fecha_corte")
        if fecha_corte:
            fc_bogota = utc_a_bogota(fecha_corte)
            dia_exp   = fc_bogota.strftime("%d").lstrip("0") or "1"
            mes_exp   = MESES_ES[fc_bogota.month - 1]
            año_exp   = fc_bogota.strftime("%Y")
            fecha_fmt = fc_bogota.strftime("%d/%m/%Y")
        else:
            ahora     = datetime.now(ZONA_BOGOTA)
            dia_exp   = str(ahora.day)
            mes_exp   = MESES_ES[ahora.month - 1]
            año_exp   = str(ahora.year)
            fecha_fmt = ahora.strftime("%d/%m/%Y")

        # ── Documento — mismos márgenes que formato 6 ──
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2.3 * cm,
            rightMargin=2.3 * cm,
            topMargin=0.8 * cm,
            bottomMargin=1.5 * cm,
        )

        estilos = getSampleStyleSheet()

        # ── Estilos — mismos tamaños que formato 6 ──
        s_inst_bold = ParagraphStyle(
            "dep4_inst", parent=estilos["Normal"],
            fontSize=9, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=1, leading=12,
        )
        s_titulo = ParagraphStyle(
            "dep4_tit", parent=estilos["Normal"],
            fontSize=10, textColor=CAFE, alignment=TA_CENTER,
            fontName="Helvetica-Bold", spaceAfter=2, leading=13,
        )
        s_cuerpo = ParagraphStyle(
            "dep4_cuerpo", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_JUSTIFY, leading=12, spaceAfter=5,
        )
        s_renta = ParagraphStyle(
            "dep4_renta", parent=estilos["Normal"],
            fontSize=9.5, alignment=TA_CENTER, leading=13, spaceAfter=5,
            fontName="Helvetica-Bold", textColor=CAFE,
        )
        s_bullet = ParagraphStyle(
            "dep4_bullet", parent=estilos["Normal"],
            fontSize=8, alignment=TA_JUSTIFY, leading=11, spaceAfter=2,
            leftIndent=12,
        )
        s_cell = ParagraphStyle(
            "dep4_cell", parent=estilos["Normal"],
            fontSize=8, alignment=TA_CENTER, leading=10,
        )
        s_cellhdr = ParagraphStyle(
            "dep4_cellhdr", parent=estilos["Normal"],
            fontSize=8, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10,
        )
        s_pie = ParagraphStyle(
            "dep4_pie", parent=estilos["Normal"],
            fontSize=7, textColor=GRIS, alignment=TA_CENTER,
        )

        # ── Decoraciones de página — IDÉNTICAS al formato 6 ──
        def _watermark(canvas_obj, _doc):
            w, h = letter

            # Texto INVIAS SRTI en malla diagonal
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 7.5)
            canvas_obj.setFillColor(Color(0.68, 0.68, 0.68, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(38)
            for xi in range(-5, 6):
                for yi in range(-14, 15):
                    canvas_obj.drawCentredString(xi * 112, yi * 42, "INVIAS  SRTI")
            canvas_obj.restoreState()

            # Nombre + período en grande diagonal
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica-Bold", 48)
            canvas_obj.setFillColor(Color(0.58, 0.58, 0.58, alpha=0.30))
            canvas_obj.translate(w / 2, h / 2)
            canvas_obj.rotate(45)
            canvas_obj.drawCentredString(0, 42, nombre.upper())
            canvas_obj.drawCentredString(0, -32, f"{mes_nombre.upper()} {año}")
            canvas_obj.restoreState()

            # Doble borde naranja
            canvas_obj.saveState()
            nb = Color(1.0, 0.549, 0.0, alpha=0.55)
            canvas_obj.setStrokeColor(nb)
            canvas_obj.setLineWidth(1.2)
            canvas_obj.rect(18, 18, w - 36, h - 36)
            canvas_obj.setLineWidth(0.35)
            canvas_obj.rect(23, 23, w - 46, h - 46)
            canvas_obj.restoreState()

            # Rombos decorativos en las esquinas
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
            # Marcas de centro
            canvas_obj.setLineWidth(0.7)
            tk = 5
            for mx, my in [(w / 2, h - 18), (w / 2, 18), (18, h / 2), (w - 18, h / 2)]:
                canvas_obj.line(mx - tk, my, mx + tk, my)
                canvas_obj.line(mx, my - tk, mx, my + tk)
            canvas_obj.restoreState()

        # ── Story ──
        story = []

        # Logo — mismo que formato 6
        logo = os.path.join("app", "assets", "INVIAS_login_logo.png")
        if os.path.exists(logo):
            img = Image(logo, width=4 * cm, height=2 * cm, kind="proportional")
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.2 * cm))

        story.append(HRFlowable(width="100%", thickness=2, color=NARANJA))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("INSTITUTO NACIONAL DE VÍAS – INVIAS", s_inst_bold))
        story.append(Paragraph("SUBDIRECCIÓN DE REGLAMENTACIÓN TÉCNICA E INNOVACIÓN", s_inst_bold))
        story.append(Paragraph("CONDICIÓN DE DECLARANTE Y EXISTENCIA Y DEPENDENCIA ECONÓMICA", s_titulo))
        story.append(Spacer(1, 0.2 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.25 * cm))

        # Párrafo 1
        story.append(Paragraph(
            f"Yo, <b>{nombre.upper()}</b> identificado con <b>{tipo_doc}</b> No. <b>{cedula}</b>, "
            f"expedida en <b>{lugar_exp.upper()}</b>, ubicada en BOGOTÁ D.C. "
            f"En cumplimiento al parágrafo 2° del artículo 15 de la Ley 1607 de 2012, por el cual se modifica "
            f"el artículo 387 del E.T. y en concordancia con el parágrafo 4° de los artículos 2° y 3° del Decreto "
            f"0099 del 25 de enero del 2013, certifico a ustedes bajo la gravedad de juramento, mi condición:",
            s_cuerpo,
        ))

        # Condición tributaria
        renta_txt = "SI, DECLARANTE DE IMPUESTO SOBRE LA RENTA" if declarante_renta else "NO DECLARANTE DE IMPUESTO SOBRE LA RENTA"
        story.append(Paragraph(f"<u>{renta_txt}</u>", s_renta))

        # Párrafo 2
        story.append(Paragraph(
            "Declaro que mi ingreso en una proporción igual o superior a un ochenta por ciento (80%), "
            "corresponde a la prestación de servicios de manera personal o de la realización de una actividad "
            "económica por cuenta y riesgo del empleador o contratante, mediante una vinculación laboral o legal y "
            "reglamentaria o de cualquier otra naturaleza, independientemente de su denominación.",
            s_cuerpo,
        ))

        # Párrafo 3
        story.append(Paragraph(
            "Que la(s) siguiente(s) persona(s) se encuentra(n) a mi cargo en la calidad de dependiente(s):",
            s_cuerpo,
        ))

        # ── Tabla de dependientes — ancho completo ──
        t_data = [[
            Paragraph("<b>NOMBRE</b>",                          s_cellhdr),
            Paragraph("<b>TIPO DOC. ID.<br/>(C.C. / T.I.)</b>", s_cellhdr),
            Paragraph("<b>NÚMERO<br/>DOCUMENTO</b>",             s_cellhdr),
            Paragraph("<b>TIPO</b>",                             s_cellhdr),
        ]]
        for dep in dependientes:
            t_raw = (dep.get("tipo") or "").strip()
            letra = t_raw.replace("tipo_", "").replace("tipo", "").strip().upper()
            t_fmt = f"TIPO {letra}" if letra else "—"
            t_data.append([
                Paragraph((dep.get("nombre") or "").upper(), s_cell),
                Paragraph(dep.get("tipo_documento") or "—",  s_cell),
                Paragraph(dep.get("numero_documento") or "—", s_cell),
                Paragraph(t_fmt, s_cell),
            ])
        if len(t_data) == 1:
            t_data.append([Paragraph(" ", s_cell)] * 4)

        cw = doc.width
        dep_tbl = Table(t_data, colWidths=[cw * 0.36, cw * 0.22, cw * 0.24, cw * 0.18], rowHeights=0.55 * cm)
        dep_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  GRIS_TABLA),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",          (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#FFF9F0")]),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]))
        story.append(dep_tbl)
        story.append(Spacer(1, 0.15 * cm))

        # Lista de tipos de dependientes
        story.append(Paragraph("<b>TIPO DE DEPENDIENTES:</b>", s_cuerpo))
        for txt in [
            "<b>A.</b> Hijo(s) de hasta 18 años que dependen económicamente de mí.",
            "<b>B.</b> Hijo(s) entre 18 y 23 años con educación formal a mi cargo, certificada por el ICFES o autoridad competente.",
            "<b>C.</b> Hijo(s) mayor(es) de 23 años con dependencia por factores físicos o psicológicos certificados por Medicina Legal.",
            "<b>D.</b> Cónyuge o compañero permanente con dependencia por ausencia de ingresos (menos de 260 UVT/año) o factores físicos/psicológicos, certificados.",
            "<b>E.</b> Padres y/o hermanos con dependencia por ausencia de ingresos (menos de 260 UVT/año) o factores físicos/psicológicos, certificados.",
        ]:
            story.append(Paragraph(txt, s_bullet))

        story.append(Spacer(1, 0.15 * cm))

        # Párrafo 4
        story.append(Paragraph(
            "Que de conformidad con lo ordenado en el inciso 2° del parágrafo 4° del Decreto 099 del 25 de enero "
            "del 2013, nadie más solicitará la deducción de la base de la retención en la fuente por el mismo dependiente.",
            s_cuerpo,
        ))

        # Párrafo 5 – expedición
        story.append(Paragraph(
            f"La presente certificación se expide en la ciudad de Bogotá, en el mes de <b>{mes_exp.upper()}</b> "
            f"del año <b>{año_exp}</b>, para efectos de la depuración de la base del cálculo de la retención "
            f"establecida en los artículos 383 y 387 del Estatuto Tributario.",
            s_cuerpo,
        ))

        story.append(Spacer(1, 0.25 * cm))

        # ── Firma: CENTRADA, imagen sobre la línea gris — igual que formato 6 ──
        from app.services.firma_service import FirmaService
        firma_bytes = FirmaService().obtener_imagen(usuario_id)

        s_firma_nombre = ParagraphStyle(
            "dep4_fn", parent=estilos["Normal"],
            fontSize=9, fontName="Helvetica-Bold", alignment=TA_CENTER,
            textColor=CAFE, leading=12,
        )
        s_firma_sub = ParagraphStyle(
            "dep4_fs", parent=estilos["Normal"],
            fontSize=8.5, alignment=TA_CENTER, leading=11,
        )

        if firma_bytes:
            firma_img = Image(io.BytesIO(firma_bytes), width=5.2 * cm, height=2.6 * cm, kind="proportional")
            filas_firma = [
                [firma_img],
                [Paragraph(f"C.C.: <b>{cedula}</b> de <b>{lugar_exp.upper()}</b>", s_firma_sub)],
                [Paragraph(f"Fecha: Bogotá, <b>{fecha_fmt}</b>", s_firma_sub)],
            ]
        else:
            filas_firma = [
                [""],
                [Paragraph(f"C.C.: <b>{cedula}</b> de <b>{lugar_exp.upper()}</b>", s_firma_sub)],
                [Paragraph(f"Fecha: Bogotá, <b>{fecha_fmt}</b>", s_firma_sub)],
            ]

        firma_tabla = Table(filas_firma, colWidths=[doc.width])
        firma_tabla.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("FONTNAME",      (0, 0), (0, 0),   "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            # Línea gris debajo de la imagen de firma
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, HexColor("#AAAAAA")),
            ("TOPPADDING",    (0, 0), (-1, 0),  0),
            ("BOTTOMPADDING", (0, 0), (-1, 0),  0),
            ("TOPPADDING",    (0, 1), (-1, 1),  3),
        ]))
        story.append(firma_tabla)

        story.append(Spacer(1, 0.4 * cm))

        # ── Código de verificación — misma tabla naranja que formato 6 ──
        if hash_code:
            cod_tabla = Table(
                [[f"Código de verificación: {hash_code}"]],
                colWidths=[doc.width],
            )
            cod_tabla.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#FFF3E0")),
                ("TEXTCOLOR",     (0, 0), (-1, -1), CAFE),
                ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("BOX",           (0, 0), (-1, -1), 1.2, NARANJA),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(cod_tabla)
            story.append(Spacer(1, 0.2 * cm))

        # ── Pie de página — igual que formato 6 ──
        story.append(HRFlowable(width="100%", thickness=1, color=NARANJA))
        story.append(Spacer(1, 0.1 * cm))
        story.append(Paragraph(
            f"Documento generado automáticamente por el Sistema de Gestión de "
            f"Correspondencia SRTI-INVIAS · {dia_exp} de {mes_exp} de {año_exp}",
            s_pie,
        ))

        doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
        buf.seek(0)
        return buf.getvalue()



     