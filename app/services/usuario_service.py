import re
from datetime import datetime, timezone

import pytz

from app.core.autorizacion import ValidacionAutorizacion, validar_permiso
from app.core.seguridad import generar_hash_password
from app.config import configuracion
from app.repositories.usuario_repo import UsuarioRepositorio
from app.services.auditoria_service import AuditoriaService

_ZONA_BOGOTA = pytz.timezone("America/Bogota")


class UsuarioService:
    def __init__(self) -> None:
        self.repositorio = UsuarioRepositorio()
        self.auditoria = AuditoriaService()

    @staticmethod
    def _normalizar_numero_documento(numero: str) -> str:
        numero = numero.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", numero):
            raise ValueError(
                "El número de documento solo puede contener letras y números, sin espacios, puntos ni símbolos."
            )
        return numero

    @staticmethod
    def _contrato_finalizado(contrato) -> bool:
        if not contrato:
            return False
        fecha_fin = contrato.get("fecha_fin")
        if not fecha_fin:
            return False
        hoy = datetime.now(_ZONA_BOGOTA).date()
        if fecha_fin.tzinfo is None:
            fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
        return fecha_fin.astimezone(_ZONA_BOGOTA).date() < hoy

    @staticmethod
    def _afiliacion(datos) -> dict:
        """Normaliza una afiliación {entidad, valor}; campos vacíos → None."""
        datos = datos or {}
        entidad = (datos.get("entidad") or "").strip() or None
        valor = datos.get("valor")
        valor = int(valor) if valor not in (None, "", 0) and int(valor) > 0 else None
        return {"entidad": entidad, "valor": valor}

    @staticmethod
    def _construir_informacion_laboral(datos) -> dict:
        """Sanea el bloque de información laboral proveniente del formulario.

        Mantiene la forma estable del sub-documento; los campos sin valor quedan
        en None y los dependientes sin nombre se descartan.
        """
        datos = datos or {}
        ss = datos.get("seguridad_social") or {}
        bancaria = datos.get("bancaria") or {}
        tributaria = datos.get("tributaria") or {}

        dependientes = []
        for dep in datos.get("dependientes") or []:
            nombre = (dep.get("nombre") or "").strip()
            if not nombre:
                continue
            dependientes.append({
                "nombre": nombre,
                "tipo_documento": (dep.get("tipo_documento") or "").strip().upper() or None,
                "numero_documento": (dep.get("numero_documento") or "").strip() or None,
                "tipo": (dep.get("tipo") or "").strip() or None,
            })

        return {
            "seguridad_social": {
                "eps": UsuarioService._afiliacion(ss.get("eps")),
                "arl": UsuarioService._afiliacion(ss.get("arl")),
                "afp": UsuarioService._afiliacion(ss.get("afp")),
                "ccf": UsuarioService._afiliacion(ss.get("ccf")),
            },
            "bancaria": {
                "banco": (bancaria.get("banco") or "").strip() or None,
                "numero_cuenta": (bancaria.get("numero_cuenta") or "").strip() or None,
            },
            "tributaria": {
                "rut": (tributaria.get("rut") or "").strip() or None,
                "declarante_renta": bool(tributaria.get("declarante_renta")),
            },
            "dependientes": dependientes,
        }

    @staticmethod
    def _fecha_a_datetime(d):
        if d is None:
            return None
        if isinstance(d, datetime):
            return d
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    def obtener_usuario(self, id_usuario: str):
        return self.repositorio.buscar_por_id(id_usuario)

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

        lugar = (datos.get("lugar_expedicion_documento") or "").strip()
        if lugar:
            datos["lugar_expedicion_documento"] = lugar
        else:
            datos.pop("lugar_expedicion_documento", None)

        if "informacion_laboral" in datos:
            datos["informacion_laboral"] = self._construir_informacion_laboral(datos.get("informacion_laboral"))

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

        if "lugar_expedicion_documento" in datos:
            datos["lugar_expedicion_documento"] = (datos.get("lugar_expedicion_documento") or "").strip() or None

        if "informacion_laboral" in datos:
            datos["informacion_laboral"] = self._construir_informacion_laboral(datos.get("informacion_laboral"))

        if datos.get("password"):
            datos["password_hash"] = generar_hash_password(datos.pop("password"))
        else:
            datos.pop("password", None)

        datos.pop("contrato", None)
        datos.pop("contratos", None)

        resultado = self.repositorio.actualizar(id_usuario, datos)

        self.auditoria.registrar_accion(
            datos.get("actualizado_por", "sistema"),
            "editar",
            "usuario",
            {"usuario_editado": usuario_actual["usuario"]},
        )
        return resultado

    @staticmethod
    def _construir_contrato(numero: str, datos: dict) -> dict:
        contrato: dict = {"numero": numero}
        if datos.get("tipo"):
            contrato["tipo"] = datos["tipo"]
        objeto = (datos.get("objeto") or "").strip()
        if objeto:
            contrato["objeto"] = objeto
        valor = datos.get("valor")
        if valor is not None and valor > 0:
            contrato["valor"] = int(valor)
        rp = (datos.get("rp_compromiso_presupuestal") or "").strip()
        if rp:
            contrato["rp_compromiso_presupuestal"] = rp
        fecha_inicio = datos.get("fecha_inicio")
        if fecha_inicio:
            contrato["fecha_inicio"] = UsuarioService._fecha_a_datetime(fecha_inicio)
        fecha_fin = datos.get("fecha_fin")
        if fecha_fin:
            contrato["fecha_fin"] = UsuarioService._fecha_a_datetime(fecha_fin)
        fecha_rp = datos.get("fecha_recurso_presupuestal")
        if fecha_rp:
            contrato["fecha_recurso_presupuestal"] = UsuarioService._fecha_a_datetime(fecha_rp)
        valor_mensual = datos.get("valor_mensual")
        if valor_mensual is not None and valor_mensual > 0:
            contrato["valor_mensual"] = int(valor_mensual)
        return contrato

    def agregar_contrato(self, id_usuario: str, datos_contrato: dict):
        usuario = self.repositorio.buscar_por_id(id_usuario)
        if not usuario:
            raise ValueError("El usuario no existe.")
        numero = (datos_contrato.get("numero") or "").strip()
        if not numero:
            raise ValueError("El número de contrato es obligatorio.")
        existente = self.repositorio.buscar_por_numero_contrato(numero)
        if existente:
            raise ValueError("Ya existe un empleado registrado con ese número de contrato.")
        contratos_actuales = usuario.get("contratos") or []
        if any(c.get("numero") == numero for c in contratos_actuales):
            raise ValueError("Este usuario ya tiene registrado ese número de contrato.")
        contrato = self._construir_contrato(numero, datos_contrato)
        self.repositorio.agregar_contrato_a_usuario(id_usuario, contrato)

    def editar_contrato(self, id_usuario: str, numero_contrato: str, datos_contrato: dict):
        usuario = self.repositorio.buscar_por_id(id_usuario)
        if not usuario:
            raise ValueError("El usuario no existe.")
        contratos = usuario.get("contratos") or []
        contrato_actual = next((c for c in contratos if c.get("numero") == numero_contrato), None)
        if not contrato_actual:
            raise ValueError("Contrato no encontrado.")
        if self._contrato_finalizado(contrato_actual):
            raise ValueError("El contrato ya finalizó y no puede ser modificado.")
        nuevo_numero = (datos_contrato.get("numero") or "").strip()
        if not nuevo_numero:
            raise ValueError("El número de contrato es obligatorio.")
        if nuevo_numero != numero_contrato:
            existente = self.repositorio.buscar_por_numero_contrato(nuevo_numero)
            if existente:
                raise ValueError("Ya existe un empleado con ese número de contrato.")
            if any(c.get("numero") == nuevo_numero for c in contratos if c.get("numero") != numero_contrato):
                raise ValueError("Este usuario ya tiene registrado ese número de contrato.")
        nuevo_contrato = self._construir_contrato(nuevo_numero, datos_contrato)
        self.repositorio.editar_contrato_en_usuario(id_usuario, numero_contrato, nuevo_contrato)

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
