import re

from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
from app.core.seguridad import generar_hash_password
from app.config import configuracion
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService


class UsuarioService:
    def __init__(self) -> None:
        self.repositorio = UsuarioRepositorio()
        self.auditoria = AuditoriaService()

    @staticmethod
    def _normalizar_numero_documento(numero: str) -> str:
        """Valida y devuelve el número en mayúsculas; lanza ValueError si tiene caracteres inválidos."""
        numero = numero.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", numero):
            raise ValueError(
                "El número de documento solo puede contener letras y números, sin espacios, puntos ni símbolos."
            )
        return numero

    def listar_usuarios(self):
        return self.repositorio.listar()

    def crear_usuario(self, datos: dict, validar_permisos: bool = True, permisos_usuario: list = None):
        usuario_existente = self.repositorio.buscar_por_usuario(datos["usuario"])
        if usuario_existente:
            raise ValueError("Ya existe un usuario con ese nombre de acceso")

        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.crear")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        datos = datos.copy()

        numero_doc = datos.get("numero_documento", "").strip()
        if numero_doc:
            datos["numero_documento"] = self._normalizar_numero_documento(numero_doc)
            existente = self.repositorio.buscar_por_numero_documento(datos["numero_documento"])
            if existente:
                raise ValueError("Ya existe un usuario con ese número de documento")
        else:
            datos.pop("numero_documento", None)

        if datos.get("tipo_documento"):
            datos["tipo_documento"] = datos["tipo_documento"].strip().upper()
        else:
            datos.pop("tipo_documento", None)

        datos["password_hash"] = generar_hash_password(datos.pop("password"))
        datos.setdefault("activo", True)
        datos.setdefault("roles", [])
        datos.setdefault("permisos_extra", [])
        id_nuevo = self.repositorio.crear(datos)
        
        self.auditoria.registrar_accion(
            datos.get("creado_por", "sistema"),
            "crear",
            "usuario",
            {"usuario_creado": datos["usuario"]},
        )
        return id_nuevo

    def actualizar_usuario(self, id_usuario: str, datos: dict, validar_permisos: bool = True, permisos_usuario: list = None):
        datos = datos.copy()
        usuario_actual = self.repositorio.buscar_por_id(id_usuario)
        if not usuario_actual:
            raise ValueError("El usuario no existe")

        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.editar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))

        nuevo_usuario = datos.get("usuario")
        if nuevo_usuario:
            usuario_existente = self.repositorio.buscar_por_usuario(nuevo_usuario)
            if usuario_existente and str(usuario_existente["_id"]) != id_usuario:
                raise ValueError("Ya existe un usuario con ese nombre de acceso")

        numero_doc = datos.get("numero_documento", "").strip()
        if numero_doc:
            datos["numero_documento"] = self._normalizar_numero_documento(numero_doc)
            existente = self.repositorio.buscar_por_numero_documento(datos["numero_documento"])
            if existente and str(existente["_id"]) != id_usuario:
                raise ValueError("Ya existe un usuario con ese número de documento")
        else:
            datos.pop("numero_documento", None)

        if datos.get("tipo_documento"):
            datos["tipo_documento"] = datos["tipo_documento"].strip().upper()
        else:
            datos.pop("tipo_documento", None)

        if datos.get("password"):
            datos["password_hash"] = generar_hash_password(datos.pop("password"))
        else:
            datos.pop("password", None)
        
        resultado = self.repositorio.actualizar(id_usuario, datos)
        self.auditoria.registrar_accion(
            datos.get("actualizado_por", "sistema"),
            "editar",
            "usuario",
            {"usuario_editado": usuario_actual["usuario"]},
        )
        return resultado

    def activar_usuario(self, id_usuario: str, validar_permisos: bool = True, permisos_usuario: list = None, usuario_actual: str = None):
        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))
        
        usuario = self.repositorio.buscar_por_id(id_usuario)
        resultado = self.repositorio.cambiar_estado(id_usuario, True)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "activar", "usuario", {"usuario_activado": usuario.get("usuario")})
        return resultado

    def desactivar_usuario(self, id_usuario: str, validar_permisos: bool = True, permisos_usuario: list = None, usuario_actual: str = None):
        if validar_permisos and permisos_usuario:
            try:
                validar_permiso(permisos_usuario, "usuario.desactivar")
            except ValidacionAutorizacion as e:
                raise ValueError(str(e))
        
        usuario = self.repositorio.buscar_por_id(id_usuario)
        resultado = self.repositorio.cambiar_estado(id_usuario, False)
        self.auditoria.registrar_accion(usuario_actual or "sistema", "desactivar", "usuario", {"usuario_desactivado": usuario.get("usuario")})
        return resultado

    def asegurar_usuario_admin_inicial(self):
        if self.repositorio.buscar_por_usuario("admin"):
            return None

        if not configuracion.admin_inicial_password:
            return None

        datos = {
            "usuario": "admin",
            "nombre_completo": "Administrador del sistema",
            "email": "admin@local",
            "password": configuracion.admin_inicial_password,
            "activo": True,
            "roles": ["admin"],
            "permisos_extra": [],
            "creado_por": "sistema",
        }
        return self.crear_usuario(datos, validar_permisos=False)
