import os
import io
from datetime import datetime, timezone, timedelta
import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Spacer,
    Paragraph,
    KeepTogether,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

from app.repositories.correspondencia_repo import CorrespondenciaRepositorio
from app.core.festivos import FESTIVOS_CO

class PDFReportService:
    def __init__(self):
        self.repo = CorrespondenciaRepositorio()
        self.co_holidays = FESTIVOS_CO
        self.ruta_logo = os.path.join("app", "assets", "INVIAS.png")

    def _calcular_dias_habiles(self, fecha_inicio: datetime, fecha_fin: datetime) -> int:
        if not fecha_inicio or not fecha_fin:
            return 0
        if fecha_inicio.tzinfo:
            fecha_inicio = fecha_inicio.replace(tzinfo=None)
        if fecha_fin.tzinfo:
            fecha_fin = fecha_fin.replace(tzinfo=None)
            
        fecha_inicio_date = fecha_inicio.date()
        fecha_fin_date = fecha_fin.date()
        
        if fecha_inicio_date > fecha_fin_date:
            return 0
            
        dias = 0
        actual = fecha_inicio_date + timedelta(days=1)
        while actual < fecha_fin_date:
            if actual.weekday() < 5 and actual not in self.co_holidays:
                dias += 1
            actual += timedelta(days=1)
        return dias

    def _fondo_pdf(self, canvas, doc):
        canvas.setFillColor(HexColor("#FFF4E6"))
        canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)

    def _agregar_logo(self, elementos):
        if os.path.exists(self.ruta_logo):
            logo = Image(self.ruta_logo)
            logo.drawHeight = 60
            logo.drawWidth = 160
            logo.hAlign = "CENTER"
            elementos.append(logo)
            elementos.append(Spacer(1, 15))

    def _obtener_datos_activos(self) -> list:
        return self.repo.listar({"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}, limit=10000)

    def _construir_tabla_resumen(self, df_reporte, col_usuario, col_valor_nombre="Atrasados"):
        if df_reporte.empty:
            return None
        
        resumen = df_reporte[col_usuario].value_counts().reset_index()
        resumen.columns = ["Usuario Responsable", col_valor_nombre]
        
        total_valores = resumen[col_valor_nombre].sum()
        resumen.loc[len(resumen)] = ["Total", total_valores]
        
        data_resumen = [resumen.columns.tolist()] + resumen.astype(str).values.tolist()
        tabla = Table(data_resumen, repeatRows=1)
        
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.orange),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))
        return tabla

    def generar_pdf_pqrd(self) -> io.BytesIO:
        buffer = io.BytesIO()
        colombia_tz = timezone(timedelta(hours=-5))
        hoy = datetime.now(colombia_tz)
        fecha_hoy = hoy.strftime("%Y-%m-%d")
        
        hoy_utc = hoy.astimezone(timezone.utc)
        
        # Filtro optimizado a nivel de base de datos (MongoDB)
        query = {
            "estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]},
            "tipo": {"$regex": "pqrd", "$options": "i"},
            "responsable_actual.nombre": {"$ne": "Gladys Gutierrez Buitrago", "$exists": True}
        }
        
        datos = self.repo.listar(query, limit=10000)
        filas = []
        
        for doc in datos:
            responsable = doc.get("responsable_actual", {}).get("nombre", "Sin Asignar")
            
            if doc.get("respuesta", {}).get("numero_oficio"):
                continue
                
            f_radicacion = doc.get("fecha_radicacion")
            if not f_radicacion:
                continue
            
            if isinstance(f_radicacion, datetime):
                if f_radicacion.tzinfo is None:
                    f_radicacion = f_radicacion.replace(tzinfo=timezone.utc)
                f_radicacion_utc = f_radicacion.astimezone(timezone.utc)
            
            dias_correspondencia = self._calcular_dias_habiles(f_radicacion_utc, hoy_utc)
            if dias_correspondencia >= 10:
                filas.append({
                    "NO. RADICADO": doc.get("numero_radicado", "S/N"),
                    "Usuario Responsable": responsable,
                    "Días sin respuesta": dias_correspondencia
                })
                
        df_reporte = pd.DataFrame(filas)
        if not df_reporte.empty:
            df_reporte = df_reporte.sort_values(by="Días sin respuesta", ascending=False)
            
        styles = getSampleStyleSheet()
        elementos = []
        
        self._agregar_logo(elementos)
        
        titulo = Paragraph(f"<b>Reporte VUVR PQRD ({fecha_hoy})</b>", styles["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 25))
        
        elementos.append(Paragraph("<b>1. Resumen</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        tabla_resumen = self._construir_tabla_resumen(df_reporte, "Usuario Responsable")
        if tabla_resumen:
            elementos.append(tabla_resumen)
        else:
            elementos.append(Paragraph("No hay radicados PQRD atrasados.", styles["Normal"]))
        elementos.append(Spacer(1, 30))
        
        elementos.append(Paragraph("<b>2. Reporte Detallado</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        
        if df_reporte.empty:
            elementos.append(Paragraph("No hay datos para el reporte detallado.", styles["Normal"]))
        else:
            data_reporte = [df_reporte.columns.tolist()] + df_reporte.astype(str).values.tolist()
            tabla_reporte = Table(data_reporte, repeatRows=1)
            
            estilos = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
            ]
            
            col_index = 2
            for i, fila in enumerate(data_reporte[1:], start=1):
                estilos.append(("BACKGROUND", (col_index, i), (col_index, i), HexColor("#FFCCCC")))
                    
            tabla_reporte.setStyle(TableStyle(estilos))
            elementos.append(tabla_reporte)
            
        pdf = SimpleDocTemplate(buffer, pagesize=letter)
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer

    def generar_pdf_conglomerado(self) -> io.BytesIO:
        from reportlab.platypus import PageBreak
        buffer = io.BytesIO()
        colombia_tz = timezone(timedelta(hours=-5))
        hoy = datetime.now(colombia_tz)
        fecha_hoy = hoy.strftime("%Y-%m-%d")
        
        hoy_utc = hoy.astimezone(timezone.utc)
        
        # Filtro optimizado a nivel de base de datos (MongoDB)
        query = {
            "estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]},
            "responsable_actual.nombre": {"$ne": "Gladys Gutierrez Buitrago", "$exists": True}
        }
        
        datos = self.repo.listar(query, limit=10000)
        filas = []
        
        for doc in datos:
            responsable = doc.get("responsable_actual", {}).get("nombre", "Sin Asignar")
            
            if doc.get("respuesta", {}).get("numero_oficio"):
                continue
                
            f_radicacion = doc.get("fecha_radicacion")
            if not f_radicacion:
                continue
            
            if isinstance(f_radicacion, datetime):
                if f_radicacion.tzinfo is None:
                    f_radicacion = f_radicacion.replace(tzinfo=timezone.utc)
                f_radicacion_utc = f_radicacion.astimezone(timezone.utc)
            
            dias_correspondencia = self._calcular_dias_habiles(f_radicacion_utc, hoy_utc)
            if dias_correspondencia >= 10:
                filas.append({
                    "No. Radicado": doc.get("numero_radicado", "S/N"),
                    "Usuario Responsable": responsable,
                    "Días sin respuesta": dias_correspondencia
                })
                
        df_reporte = pd.DataFrame(filas)
        
        styles = getSampleStyleSheet()
        elementos = []
        
        self._agregar_logo(elementos)
        
        titulo = Paragraph(f"<b>Reporte Matriz de asignación a la correspondencia ({fecha_hoy}) SRTI</b>", styles["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 25))
        
        elementos.append(Paragraph("<b>1. Resumen</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        tabla_resumen = self._construir_tabla_resumen(df_reporte, "Usuario Responsable")
        if tabla_resumen:
            elementos.append(tabla_resumen)
        else:
            elementos.append(Paragraph("No hay radicados activos atrasados.", styles["Normal"]))
        elementos.append(Spacer(1, 30))
        
        elementos.append(PageBreak())
        elementos.append(Paragraph("<b>2. Reporte Detallado</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        
        if df_reporte.empty:
            elementos.append(Paragraph("No hay datos para el reporte detallado.", styles["Normal"]))
        else:
            usuarios = df_reporte["Usuario Responsable"].unique()
            for usuario in sorted(usuarios):
                df_usuario = df_reporte[df_reporte["Usuario Responsable"] == usuario]
                df_usuario = df_usuario.sort_values(by="Días sin respuesta", ascending=False)
                
                subtitulo = Paragraph(f"<b>Nombre: {usuario}</b>", styles["Heading3"])
                
                data = [df_usuario.columns.tolist()] + df_usuario.astype(str).values.tolist()
                tabla = Table(data)
                
                estilos = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ]
                
                for i, fila in enumerate(data[1:], start=1):
                    estilos.append(("BACKGROUND", (2, i), (2, i), HexColor("#FFCCCC")))
                
                tabla.setStyle(TableStyle(estilos))
                
                bloque = KeepTogether([
                    subtitulo,
                    Spacer(1, 10),
                    tabla,
                    Spacer(1, 30)
                ])
                elementos.append(bloque)
                
        pdf = SimpleDocTemplate(buffer, pagesize=letter)
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer

    def generar_pdf_total_sin_tramite(self) -> io.BytesIO:
        from reportlab.platypus import PageBreak
        buffer = io.BytesIO()
        colombia_tz = timezone(timedelta(hours=-5))
        hoy = datetime.now(colombia_tz)
        fecha_hoy = hoy.strftime("%Y-%m-%d")
        
        hoy_utc = hoy.astimezone(timezone.utc)
        
        query = {
            "estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]},
            "responsable_actual.nombre": {"$ne": "Gladys Gutierrez Buitrago", "$exists": True}
        }
        
        datos = self.repo.listar(query, limit=10000)
        filas = []
        
        for doc in datos:
            responsable = doc.get("responsable_actual", {}).get("nombre", "Sin Asignar")
            
            if doc.get("respuesta", {}).get("numero_oficio"):
                continue
                
            f_radicacion = doc.get("fecha_radicacion")
            if not f_radicacion:
                continue
            
            if isinstance(f_radicacion, datetime):
                if f_radicacion.tzinfo is None:
                    f_radicacion = f_radicacion.replace(tzinfo=timezone.utc)
                f_radicacion_utc = f_radicacion.astimezone(timezone.utc)
            
            dias_correspondencia = self._calcular_dias_habiles(f_radicacion_utc, hoy_utc)
            # No se filtra >= 10, muestra todos los pendientes
            filas.append({
                "No. Radicado": doc.get("numero_radicado", "S/N"),
                "Usuario Responsable": responsable,
                "Días sin respuesta": dias_correspondencia
            })
                
        df_reporte = pd.DataFrame(filas)
        
        styles = getSampleStyleSheet()
        elementos = []
        
        self._agregar_logo(elementos)
        
        titulo = Paragraph(f"<b>Reporte Total sin trámite ({fecha_hoy}) SRTI</b>", styles["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 25))
        
        elementos.append(Paragraph("<b>1. Resumen</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        tabla_resumen = self._construir_tabla_resumen(df_reporte, "Usuario Responsable", "Pendientes")
        if tabla_resumen:
            elementos.append(tabla_resumen)
        else:
            elementos.append(Paragraph("No hay radicados activos.", styles["Normal"]))
        elementos.append(Spacer(1, 30))
        
        elementos.append(PageBreak())
        elementos.append(Paragraph("<b>2. Reporte Detallado</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))
        
        if df_reporte.empty:
            elementos.append(Paragraph("No hay datos para el reporte detallado.", styles["Normal"]))
        else:
            usuarios = df_reporte["Usuario Responsable"].unique()
            for usuario in sorted(usuarios):
                df_usuario = df_reporte[df_reporte["Usuario Responsable"] == usuario]
                df_usuario = df_usuario.sort_values(by="Días sin respuesta", ascending=False)
                
                subtitulo = Paragraph(f"<b>Nombre: {usuario}</b>", styles["Heading3"])
                
                data = [df_usuario.columns.tolist()] + df_usuario.astype(str).values.tolist()
                tabla = Table(data)
                
                estilos = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ]
                
                for i, fila in enumerate(data[1:], start=1):
                    try:
                        dias = int(float(fila[2]))
                        if dias >= 10:
                            estilos.append(("BACKGROUND", (2, i), (2, i), HexColor("#FFCCCC")))
                        else:
                            estilos.append(("BACKGROUND", (2, i), (2, i), colors.yellow))
                    except ValueError:
                        pass
                
                tabla.setStyle(TableStyle(estilos))
                
                bloque = KeepTogether([
                    subtitulo,
                    Spacer(1, 10),
                    tabla,
                    Spacer(1, 30)
                ])
                elementos.append(bloque)
                
        pdf = SimpleDocTemplate(buffer, pagesize=letter)
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer

    def generar_pdf_cargue_cuentas(self, anio: int) -> io.BytesIO:
        from reportlab.platypus import PageBreak
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from app.repositories.usuario_repo import UsuarioRepositorio
        from app.repositories.certificacion_repo import CertificacionRepositorio
        from app.services.certificacion_service import CertificacionService

        buffer = io.BytesIO()
        usr_repo = UsuarioRepositorio()
        cert_repo = CertificacionRepositorio()

        # Meses en español
        MESES_ES = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]

        # 1. Obtener todos los usuarios registrados activos con contratos activos
        usuarios = usr_repo.listar()
        usuarios_activos = []
        for u in usuarios:
            if not u.get("activo", True):
                continue
            contrato = CertificacionService._contrato_vigente(u.get("contratos") or [])
            if contrato and contrato.get("numero"):
                usuarios_activos.append((u, contrato))

        # 2. Consultar certificaciones de ese año (filtrando por formato de correspondencia)
        certs_cursor = cert_repo.coleccion.find({
            "año": anio,
            "tipo_formato": {"$in": [None, "gestion_correspondencia"]}
        })
        certs_dict = {}
        for c in certs_cursor:
            uid = str(c.get("usuario_id", ""))
            mes = c.get("mes")
            certs_dict[(uid, mes)] = c

        # Configurar estilos de ReportLab
        styles = getSampleStyleSheet()
        
        style_normal = ParagraphStyle(
            "CargueNormal",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9
        )
        
        style_header = ParagraphStyle(
            "CargueHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=9,
            textColor=colors.white,
            alignment=TA_CENTER
        )

        elementos = []

        # Meses del año abreviados
        meses_abrv = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

        # Helper para agregar cabecera de página
        def agregar_cabecera_reporte(titulo_texto):
            self._agregar_logo_compacto(elementos)
            titulo = Paragraph(f"<b>{titulo_texto}</b>", styles["Title"])
            titulo.style.fontSize = 12
            titulo.style.leading = 14
            elementos.append(titulo)
            elementos.append(Spacer(1, 10))

        # Helper para agregar logo compacto
        if not hasattr(self, "_agregar_logo_compacto"):
            def _agregar_logo_compacto(self, elementos):
                if os.path.exists(self.ruta_logo):
                    logo = Image(self.ruta_logo)
                    logo.drawHeight = 35
                    logo.drawWidth = 93 # proporcional
                    logo.hAlign = "CENTER"
                    elementos.append(logo)
                    elementos.append(Spacer(1, 5))
            self._agregar_logo_compacto = _agregar_logo_compacto.__get__(self, PDFReportService)

        # -------------------------------------------------------------
        # REPORTE: Estado Cargue de cuenta SECOP II
        # -------------------------------------------------------------
        agregar_cabecera_reporte(f"Reporte de estado Cargue de cuenta SECOP II ({anio})")

        # Columnas: Responsable (200pt), Contrato (100pt), 12 meses (12*35=420pt)
        col_widths = [200, 100] + [35]*12
        
        header = [
            Paragraph("RESPONSABLE", style_header),
            Paragraph("CONTRATO", style_header)
        ] + [Paragraph(m, style_header) for m in meses_abrv]
        
        data = [header]
        estilos = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
        ]

        for u, contr in usuarios_activos:
            uid_str = str(u["_id"])
            nombre_u = u.get("nombre_completo", "")
            num_contr = contr.get("numero", "")
            
            fila = [
                Paragraph(nombre_u, style_normal),
                Paragraph(num_contr, style_normal)
            ]
            
            row_idx = len(data)
            
            # 12 meses
            for m_idx, m in enumerate(range(1, 13)):
                fila.append("") # Celda vacía que será pintada
                col_idx = 2 + m_idx
                
                c = certs_dict.get((uid_str, m))
                if c and c.get("firmas", {}).get("secop"):
                    # Tiene firma secop
                    obs = c.get("observacion") or c.get("observaciones")
                    if obs and obs.strip():
                        # Firma + Observación en la base de datos para ese mes
                        estilos.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), HexColor("#F7DC6F"))) # Amarillo más intenso
                    else:
                        # Solo firma
                        estilos.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), HexColor("#58D68D"))) # Verde más intenso
                else:
                    # No tiene firma
                    estilos.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), HexColor("#E2E3E5"))) # Gris claro
            
            data.append(fila)

        tabla = Table(data, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle(estilos))
        elementos.append(tabla)

        # -------------------------------------------------------------
        # HOJA APARTE: Observaciones del mes de firma
        # -------------------------------------------------------------
        _, mes_actual = CertificacionService().periodo_certificable()
        nombre_mes = MESES_ES[mes_actual - 1]

        observaciones_activas = []
        for u, contr in usuarios_activos:
            uid_str = str(u["_id"])
            c = certs_dict.get((uid_str, mes_actual))
            if c:
                obs = c.get("observacion") or c.get("observaciones")
                if obs and obs.strip():
                    observaciones_activas.append((u.get("nombre_completo", ""), obs.strip()))

        if observaciones_activas:
            elementos.append(PageBreak())
            agregar_cabecera_reporte(f"Observaciones {nombre_mes.upper()} ({anio})")

            # Columnas: Responsable (200pt), Ultima Observación (520pt)
            col_widths_obs = [200, 520]
            header_obs = [
                Paragraph("RESPONSABLE", style_header),
                Paragraph("ULTIMA OBSERVACIÓN", style_header)
            ]
            data_obs = [header_obs]
            estilos_obs = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.orange),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]

            for responsable, obs_texto in observaciones_activas:
                fila_obs = [
                    Paragraph(responsable, style_normal),
                    Paragraph(obs_texto, style_normal)
                ]
                data_obs.append(fila_obs)

            tabla_obs = Table(data_obs, colWidths=col_widths_obs, repeatRows=1)
            tabla_obs.setStyle(TableStyle(estilos_obs))
            elementos.append(tabla_obs)

        # Generar PDF
        pdf = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=30,
            rightMargin=30,
            topMargin=20,
            bottomMargin=25
        )
        pdf.build(elementos, onFirstPage=self._fondo_pdf, onLaterPages=self._fondo_pdf)
        
        buffer.seek(0)
        return buffer

