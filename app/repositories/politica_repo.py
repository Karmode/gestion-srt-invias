from bson import ObjectId

from app.db.mongo import obtener_coleccion


class PoliticaRepositorio:
    def __init__(self) -> None:
        self.politicas = obtener_coleccion("politicas_datos")
        self.aceptaciones = obtener_coleccion("aceptaciones_politica")

    # ── Políticas ────────────────────────────────────────────────────────────

    def obtener_politica_activa(self) -> dict | None:
        return self.politicas.find_one({"activa": True})

    def crear_politica(self, datos: dict) -> str:
        resultado = self.politicas.insert_one(datos)
        return str(resultado.inserted_id)

    def desactivar_todas(self) -> None:
        self.politicas.update_many({}, {"$set": {"activa": False}})

    def listar_versiones(self) -> list[dict]:
        return list(self.politicas.find().sort("numero_version", -1))

    # ── Aceptaciones ─────────────────────────────────────────────────────────

    def verificar_aceptacion(self, usuario_id: str, politica_id: str) -> bool:
        doc = self.aceptaciones.find_one({
            "usuario_id": ObjectId(usuario_id),
            "politica_id": ObjectId(politica_id),
        })
        return doc is not None

    def registrar_aceptacion(self, datos: dict) -> str:
        resultado = self.aceptaciones.insert_one(datos)
        return str(resultado.inserted_id)

    def historial_usuario(self, usuario_id: str) -> list[dict]:
        return list(
            self.aceptaciones.find({"usuario_id": ObjectId(usuario_id)}).sort("fecha_aceptacion", -1)
        )

    def listar_aceptaciones_por_politica(self, politica_id: str) -> list[dict]:
        return list(
            self.aceptaciones.find({"politica_id": ObjectId(politica_id)}).sort("fecha_aceptacion", 1)
        )
