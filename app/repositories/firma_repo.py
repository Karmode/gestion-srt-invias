from bson import ObjectId

from app.db.mongo import obtener_coleccion


class FirmaRepositorio:
    """Acceso a la colección 'firmas' (un documento por usuario)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("firmas")

    def obtener(self, usuario_id: str):
        return self.coleccion.find_one({"usuario_id": ObjectId(usuario_id)})

    def guardar(self, usuario_id: str, doc: dict) -> None:
        self.coleccion.update_one(
            {"usuario_id": ObjectId(usuario_id)},
            {"$set": doc},
            upsert=True,
        )

    def eliminar(self, usuario_id: str) -> None:
        self.coleccion.delete_one({"usuario_id": ObjectId(usuario_id)})
