import datetime

from app.repositories.instructivo_repo import InstructivoRepositorio


def _ahora_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class InstructivoService:
    def __init__(self) -> None:
        self.repo = InstructivoRepositorio()

    def listar_activos(self) -> list:
        return self.repo.listar_activos()

    def listar_todos(self) -> list:
        return self.repo.listar_todos()

    def crear(
        self,
        titulo: str,
        url: str,
        tipo: str,
        descripcion: str | None = None,
        icono: str | None = None,
        embed_height: int | None = None,
        creado_por: str | None = None,
    ) -> str:
        ahora = _ahora_utc()
        orden = self.repo.max_orden() + 1
        datos = {
            "titulo": titulo.strip(),
            "descripcion": descripcion.strip() if descripcion else None,
            "url": url.strip(),
            "tipo": tipo,
            "icono": icono.strip() if icono else None,
            "activo": True,
            "orden": orden,
            "embed_height": embed_height,
            "fecha_creacion": ahora,
            "fecha_actualizacion": ahora,
            "creado_por": creado_por,
            "actualizado_por": creado_por,
        }
        return self.repo.crear(datos)

    def actualizar(
        self,
        id_instructivo: str,
        campos: dict,
        actualizado_por: str | None = None,
    ) -> None:
        campos["fecha_actualizacion"] = _ahora_utc()
        if actualizado_por:
            campos["actualizado_por"] = actualizado_por
        self.repo.actualizar(id_instructivo, campos)

    def toggle_activo(self, id_instructivo: str, activo: bool, actualizado_por: str | None = None) -> None:
        self.actualizar(id_instructivo, {"activo": activo}, actualizado_por)

    def hay_instructivos(self) -> bool:
        return self.repo.contar() > 0
