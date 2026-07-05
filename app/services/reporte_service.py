from datetime import datetime, timedelta, timezone
import pandas as pd
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio


class ReporteService:
    """Servicio de reportes enfocado en la gestión operativa de correspondencia."""

    def __init__(self) -> None:
        self.repo = CorrespondenciaRepositorio()

    def resumen_operativo(self, usuario_id: str = None) -> dict:
        """Obtiene métricas clave de alto nivel."""
        from bson import ObjectId
        query = {}
        if usuario_id:
            query["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        total = self.repo.contar(query)
        
        activos_query = {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}
        activos_query.update(query)
        activos = self.repo.contar(activos_query)
        
        finalizados_query = {"estado_actual": {"$in": ["respondido", "archivado", "traslado_competencia"]}}
        finalizados_query.update(query)
        finalizados = self.repo.contar(finalizados_query)
        
        hoy = datetime.now(timezone.utc)
        vencidos_query = {
            "estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]},
            "fecha_vencimiento": {"$lt": hoy}
        }
        vencidos_query.update(query)
        vencidos = self.repo.contar(vencidos_query)

        return {
            "total_historico": total,
            "tramites_activos": activos,
            "tramites_finalizados": finalizados,
            "vencidos_criticos": vencidos,
            "porcentaje_cumplimiento": round((finalizados / total * 100), 1) if total > 0 else 0
        }

    def distribucion_por_estado(self, usuario_id: str = None) -> pd.DataFrame:
        """Datos para gráfico de torta de estados."""
        from bson import ObjectId
        match_stage = {}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        pipeline.extend([
            {"$group": {"_id": "$estado_actual", "cantidad": {"$sum": 1}}},
            {"$project": {"estado": "$_id", "cantidad": 1, "_id": 0}}
        ])
        datos = list(self.repo.coleccion.aggregate(pipeline))
        if not datos:
            return pd.DataFrame(columns=["estado", "cantidad"])
        df = pd.DataFrame(datos)
        df["estado"] = df["estado"].apply(lambda x: x.replace("_", " ").title())
        return df

    def carga_por_usuario(self, usuario_id: str = None) -> pd.DataFrame:
        """Datos para gráfico de barras de carga de trabajo por usuario (solo activos)."""
        from bson import ObjectId
        match_stage = {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$responsable_actual.nombre", "cantidad": {"$sum": 1}}},
            {"$project": {"usuario": {"$ifNull": ["$_id", "Sin Asignar"]}, "cantidad": 1, "_id": 0}},
            {"$sort": {"cantidad": -1}}
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        return pd.DataFrame(datos) if datos else pd.DataFrame(columns=["usuario", "cantidad"])

    def analisis_vencimiento(self, usuario_id: str = None) -> pd.DataFrame:
        """Clasifica los trámites activos por su proximidad al vencimiento (agregado en servidor)."""
        from bson import ObjectId
        hoy = datetime.now(timezone.utc)
        limite_urgente = hoy + timedelta(days=5)

        match_stage = {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        pipeline = [
            {"$match": match_stage},
            {"$match": {"fecha_vencimiento": {"$ne": None}}},
            {"$group": {
                "_id": None,
                "Vencidos": {"$sum": {"$cond": [{"$lt": ["$fecha_vencimiento", hoy]}, 1, 0]}},
                "Urgentes (0-5d)": {"$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$fecha_vencimiento", hoy]},
                        {"$lte": ["$fecha_vencimiento", limite_urgente]},
                    ]}, 1, 0]}},
                "A Tiempo (>5d)": {"$sum": {"$cond": [{"$gt": ["$fecha_vencimiento", limite_urgente]}, 1, 0]}},
            }},
        ]
        resultado = list(self.repo.coleccion.aggregate(pipeline))
        categorias = {"Vencidos": 0, "Urgentes (0-5d)": 0, "A Tiempo (>5d)": 0}
        if resultado:
            fila = resultado[0]
            for k in categorias:
                categorias[k] = fila.get(k, 0)
        return pd.DataFrame([{"categoria": k, "cantidad": v} for k, v in categorias.items()])

    def tendencia_diaria(self, dias: int = 30, usuario_id: str = None) -> pd.DataFrame:
        """Tendencia de radicación diaria en los últimos N días."""
        from bson import ObjectId
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=dias)
        match_stage = {"fecha_radicacion": {"$gte": fecha_desde}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        pipeline = [
            {"$match": match_stage},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_radicacion"}},
                "cantidad": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        resultado = [{"fecha": d["_id"], "radicados": d["cantidad"]} for d in datos]
        return pd.DataFrame(resultado) if resultado else pd.DataFrame(columns=["fecha", "radicados"])

    def analisis_tiempos_respuesta(self, usuario_id: str = None) -> pd.DataFrame:
        """Tiempo promedio de respuesta/cierre por tipo (agregado en servidor)."""
        from bson import ObjectId
        match_stage = {"estado_actual": {"$in": ["respondido", "archivado", "traslado_competencia"]}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        # Fecha de cierre: respuesta.fecha_salida si el estado es "respondido"
        # (con fallback al último evento de trazabilidad), si no, el último
        # evento de trazabilidad — misma prioridad que la versión en Python.
        ultimo_evento = {"$arrayElemAt": ["$trazabilidad.fecha", -1]}
        pipeline = [
            {"$match": match_stage},
            {"$project": {
                "tipo": {"$ifNull": ["$tipo", "otro"]},
                "fecha_radicacion": 1,
                "f_cierre": {"$cond": [
                    {"$eq": ["$estado_actual", "respondido"]},
                    {"$ifNull": ["$respuesta.fecha_salida", ultimo_evento]},
                    ultimo_evento,
                ]},
            }},
            {"$match": {"fecha_radicacion": {"$ne": None}, "f_cierre": {"$ne": None}}},
            {"$group": {
                "_id": "$tipo",
                "dias_promedio": {"$avg": {"$divide": [
                    {"$subtract": ["$f_cierre", "$fecha_radicacion"]},
                    1000 * 60 * 60 * 24,
                ]}},
            }},
            {"$sort": {"_id": 1}},
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        if not datos:
            return pd.DataFrame(columns=["Tipo", "Días Promedio"])

        resumen = pd.DataFrame(
            [{"Tipo": d["_id"], "Días Promedio": round(d["dias_promedio"], 1)} for d in datos]
        )
        return resumen
