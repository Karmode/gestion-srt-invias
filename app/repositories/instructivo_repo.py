from bson import ObjectId

from app.db.mongo import obtener_coleccion


class InstructivoRepositorio:
    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("instructivos")

    def listar_activos(self) -> list:
        return list(self.coleccion.find({"activo": True}).sort("orden", 1))

    def listar_todos(self) -> list:
        return list(self.coleccion.find().sort("orden", 1))

    def obtener_por_id(self, id_instructivo: str) -> dict | None:
        return self.coleccion.find_one({"_id": ObjectId(id_instructivo)})

    def max_orden(self) -> int:
        resultado = self.coleccion.find_one({}, sort=[("orden", -1)])
        return resultado.get("orden", 0) if resultado else 0

    def crear(self, datos: dict) -> str:
        resultado = self.coleccion.insert_one(datos)
        return str(resultado.inserted_id)

    def actualizar(self, id_instructivo: str, campos: dict) -> None:
        self.coleccion.update_one(
            {"_id": ObjectId(id_instructivo)},
            {"$set": campos},
        )

    def contar(self) -> int:
        return self.coleccion.count_documents({})
