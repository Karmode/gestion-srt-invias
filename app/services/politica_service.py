from bson import ObjectId

from app.core.zona_horaria import ZONA_BOGOTA
from app.repositories.politica_repo import PoliticaRepositorio

import datetime


class PoliticaService:
    def __init__(self) -> None:
        self.repo = PoliticaRepositorio()

    def obtener_politica_vigente(self) -> dict | None:
        """Devuelve el documento de la política activa, o None si no hay ninguna."""
        return self.repo.obtener_politica_activa()

    def usuario_necesita_aceptar(self, usuario_id: str) -> tuple[bool, dict | None]:
        """Determina si el usuario debe ver el modal de política.

        Returns:
            (True, politica_doc) si debe aceptar.
            (False, None) si ya aceptó la vigente o no existe política activa.
        """
        politica = self.repo.obtener_politica_activa()
        if politica is None:
            return False, None

        ya_acepto = self.repo.verificar_aceptacion(usuario_id, str(politica["_id"]))
        if ya_acepto:
            return False, None

        return True, politica

    def registrar_aceptacion(
        self,
        *,
        usuario_id: str,
        politica: dict,
        ip: str | None,
        user_agent: str | None,
        sesion_id: str | None,
        nombre_completo: str | None,
        email: str | None,
    ) -> str:
        """Persiste la evidencia de aceptación y devuelve el id del registro."""
        ahora = datetime.datetime.now(datetime.timezone.utc)
        datos = {
            "usuario_id": ObjectId(usuario_id),
            "politica_id": politica["_id"],
            "numero_version": politica["numero_version"],
            "fecha_aceptacion": ahora,
            "ip_address": ip or "no_disponible",
            "user_agent": user_agent or "no_disponible",
            "nombre_completo": nombre_completo,
            "email": email,
            "sesion_id": sesion_id,
            "metodo": "checkbox_web",
        }
        return self.repo.registrar_aceptacion(datos)

    # ── Admin ──────────────────────────────────────────────────────────────

    def crear_nueva_version(
        self,
        titulo: str,
        contenido: str,
        creada_por: str,
        fecha_vigencia: datetime.datetime | None = None,
    ) -> str:
        """Crea una nueva versión de política y la activa (desactiva las anteriores)."""
        versiones = self.repo.listar_versiones()
        siguiente_version = (versiones[0]["numero_version"] + 1) if versiones else 1

        ahora = datetime.datetime.now(datetime.timezone.utc)
        if fecha_vigencia is None:
            fecha_vigencia = ahora

        self.repo.desactivar_todas()
        datos = {
            "numero_version": siguiente_version,
            "titulo": titulo,
            "contenido": contenido,
            "activa": True,
            "fecha_vigencia": fecha_vigencia,
            "fecha_creacion": ahora,
            "creada_por": creada_por,
        }
        return self.repo.crear_politica(datos)

    def listar_versiones(self) -> list[dict]:
        return self.repo.listar_versiones()

    def historial_usuario(self, usuario_id: str) -> list[dict]:
        return self.repo.historial_usuario(usuario_id)
