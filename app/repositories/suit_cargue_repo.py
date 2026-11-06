from app.db.mongo import obtener_coleccion


class SuitCargueRepositorio:
    """Acceso a 'suit_cargues' (un documento por trámite, año y mes)."""

    def __init__(self) -> None:
        self.coleccion = obtener_coleccion("suit_cargues")

    def obtener(self, tramite: str, anio: int, mes: int):
        return self.coleccion.find_one({"tramite": tramite, "anio": anio, "mes": mes})

    def listar_por_tramite_anio(self, tramite: str, anio: int) -> list[dict]:
        return list(
            self.coleccion.find({"tramite": tramite, "anio": anio}, {"trazabilidad": 0}).sort("mes", 1)
        )

    def listar_por_anio(self, anio: int) -> list[dict]:
        """Todos los cargues del año (sin trazabilidad) para el seguimiento."""
        return list(self.coleccion.find({"anio": anio}, {"trazabilidad": 0}))

    def guardar(self, tramite: str, anio: int, mes: int, trimestre: int, valores: dict,
                usuario: str, ahora, accion: str) -> None:
        """Crea o actualiza el mes y agrega la entrada de trazabilidad en una sola operación."""
        self.coleccion.update_one(
            {"tramite": tramite, "anio": anio, "mes": mes},
            {
                "$set": {
                    "trimestre": trimestre,
                    "valores": valores,
                    "actualizado_por": usuario,
                    "actualizado_en": ahora,
                },
                "$setOnInsert": {"creado_por": usuario, "creado_en": ahora},
                "$push": {
                    "trazabilidad": {"fecha": ahora, "accion": accion, "usuario": usuario, "valores": valores}
                },
            },
            upsert=True,
        )
