from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import obtener_coleccion

TIPOS_FIRMA = ("corr", "gd", "secop")


class CertificacionRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("certificaciones")

    def buscar_por_usuario_periodo(self, usuario_id: str, año: int, mes: int):
        return self.coleccion.find_one({
            "usuario_id": ObjectId(usuario_id),
            "año": año,
            "mes": mes,
        })

    def listar_por_usuario(self, usuario_id: str):
        return list(
            self.coleccion.find({"usuario_id": ObjectId(usuario_id)})
            .sort([("año", -1), ("mes", -1)])
        )

    def listar_por_periodo(self, año: int, mes: int):
        return list(self.coleccion.find({"año": año, "mes": mes}))

    def buscar_por_hash(self, hash_code: str):
        return self.coleccion.find_one({"hash_verificacion": hash_code})

    def crear(self, datos: dict):
        return self.coleccion.insert_one(datos).inserted_id

    def actualizar(self, id_cert: str, campos: dict):
        return self.coleccion.update_one(
            {"_id": ObjectId(id_cert)},
            {"$set": campos},
        )

    def registrar_firma(
        self,
        usuario_id: str,
        nombre_usuario: str,
        año: int,
        mes: int,
        tipo: str,
        firmante_id: str,
        firmante_nombre: str,
    ) -> bool:
        ahora = datetime.now(timezone.utc)
        self.coleccion.update_one(
            {"usuario_id": ObjectId(usuario_id), "año": año, "mes": mes},
            {
                "$set": {
                    f"firmas.{tipo}": {
                        "firmante_id": ObjectId(firmante_id),
                        "firmante_nombre": firmante_nombre,
                        "fecha": ahora,
                    }
                },
                "$setOnInsert": {
                    "nombre_usuario": nombre_usuario,
                    "estado": "pendiente",
                    "creado_en": ahora,
                },
            },
            upsert=True,
        )
        return True

    def revocar_firma(self, usuario_id: str, año: int, mes: int, tipo: str) -> bool:
        self.coleccion.update_one(
            {"usuario_id": ObjectId(usuario_id), "año": año, "mes": mes},
            {"$unset": {f"firmas.{tipo}": ""}},
        )
        return True
