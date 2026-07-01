"""Servicio de parámetros del sistema editables por el administrador.

A diferencia de la configuración de infraestructura/secretos (que vive en `.env`
y se lee desde `Configuracion`), estos son parámetros de negocio que afectan el
comportamiento del sistema y pueden ajustarse en runtime desde el panel de admin.

Se almacenan en la colección `opciones_configuracion`, bajo la categoría
`parametros_sistema`, vía `ConfiguracionRepositorio`.

Cada parámetro se define de forma declarativa en PARAMETROS: agregar uno nuevo es
una sola entrada (clave, etiqueta, tipo, rango, default, descripción e impacto).
El código siempre conserva un default seguro: si el valor falta o es inválido en
la BD, se cae al `default` y nunca se rompe.
"""

from typing import Any, Dict

from app.repositories.opciones_repo import ConfiguracionRepositorio
from app.services.auditoria_service import AuditoriaService

# ── Registro declarativo de parámetros editables ──────────────────────────────
# Para agregar un parámetro nuevo, añade una entrada aquí. El panel de admin lo
# renderiza automáticamente con su validación e impacto.
PARAMETROS: Dict[str, dict] = {
    "dia_inicio_periodo_certificacion": {
        "etiqueta": "Día de inicio del período de certificación",
        "tipo": "int",
        "min": 1,
        "max": 31,
        "default": 29,
        "unidad": "Día del mes",
        "descripcion": (
            "Desde este día del mes, el sistema habilita la certificación del "
            "mes en curso (ventana normal). Antes de ese día se certifica el mes "
            "anterior (ventana para ponerse al día). Recomendado: 25–31."
        ),
        "impacto": (
            "Cambia qué mes queda habilitado para certificar hoy y la fecha en "
            "que se abre la ventana normal de firmas. Afecta a todos los "
            "contratistas y firmantes de inmediato."
        ),
    },
    "nombre_financiera_retefuente": {
        "etiqueta": "Responsable de la Subdirección Financiera - Retención en la Fuente",
        "tipo": "str",
        "default": "sin nombre_financiera_retefuente",
        "unidad": "Nombre completo",
        "descripcion": (
            "Nombre del responsable del Grupo Cuentas Por Pagar de la Subdirección "
            "Financiera encargado de recibir el formato de retención en la fuente."
        ),
        "impacto": (
            "Actualiza el destinatario (John Jairo Aguilar Ardilla u otro) de forma inmediata "
            "para todas las futuras descargas del formato de retención en la fuente."
        ),
    },
}

CATEGORIA = "parametros_sistema"


class ParametrosService:
    def __init__(self) -> None:
        self.repo = ConfiguracionRepositorio()
        self.auditoria = AuditoriaService()

    def _validar(self, clave: str, valor: Any) -> Any:
        """Valida y normaliza un valor según el tipo y rango del parámetro.
        Lanza ValueError si es inválido."""
        meta = PARAMETROS[clave]
        if meta["tipo"] == "int":
            try:
                valor = int(valor)
            except (TypeError, ValueError):
                raise ValueError(f"{meta['etiqueta']} debe ser un número entero.")
            if not (meta["min"] <= valor <= meta["max"]):
                raise ValueError(
                    f"{meta['etiqueta']} debe estar entre {meta['min']} y {meta['max']}."
                )
            return valor
        if meta["tipo"] == "str":
            if not valor or not str(valor).strip():
                return meta["default"]
            return str(valor).strip()
        return valor

    def obtener(self, clave: str) -> Any:
        """Devuelve el valor actual del parámetro (override de BD o default).
        Si el valor almacenado es inválido, cae al default de forma segura."""
        meta = PARAMETROS.get(clave)
        if not meta:
            raise ValueError(f"Parámetro desconocido: {clave}")
        doc = self.repo.obtener(CATEGORIA)
        valores = (doc.get("valores") or {}) if doc else {}
        if clave in valores:
            try:
                return self._validar(clave, valores[clave])
            except ValueError:
                return meta["default"]
        return meta["default"]

    def obtener_todos(self) -> Dict[str, Any]:
        """Devuelve {clave: valor_actual} para todos los parámetros registrados."""
        return {clave: self.obtener(clave) for clave in PARAMETROS}

    def actualizar(self, clave: str, valor: Any, usuario: str = "sistema") -> Any:
        """Valida y persiste el nuevo valor; registra el cambio en auditoría.
        Devuelve el valor normalizado. Lanza ValueError si es inválido."""
        meta = PARAMETROS.get(clave)
        if not meta:
            raise ValueError(f"Parámetro desconocido: {clave}")
        valor = self._validar(clave, valor)
        anterior = self.obtener(clave)
        self.repo.upsert(CATEGORIA, {f"valores.{clave}": valor})
        self.auditoria.registrar_accion(
            usuario,
            "editar",
            "parametro_sistema",
            {"parametro": clave, "valor_anterior": anterior, "valor_nuevo": valor},
        )
        return valor
