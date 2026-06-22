import re
import unicodedata

from app.core.catalogos import PERMISOS_BASE, ROLES_BASE
from app.db.mongo import obtener_coleccion


def _slug(texto: str) -> str:
    """Convierte una etiqueta en una clave slug estable (sin tildes ni símbolos)."""
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    return base


def _opciones_desde_etiquetas(etiquetas: list) -> list:
    """Construye opciones {clave, etiqueta, activo} a partir de una lista de etiquetas."""
    return [{"clave": _slug(e), "etiqueta": e, "activo": True} for e in etiquetas]


# ── Catálogos de entidades de seguridad social, bancos y dependientes ──────────
_EPS = [
    "ALIANSALUD EPS", "ANAS WAYUU EPSI", "ASMET SALUD EPS", "AIC EPSI", "CAJACOPI EPS",
    "CAPITAL SALUD EPS", "CAPRESOCA EPS", "COOSALUD EPS", "COMPENSAR EPS", "COMFAORIENTE EPS",
    "COMFACHOCÓ EPS", "COMFENALCO VALLE EPS", "DUSAKAWI EPSI", "EMSSANAR EPS",
    "EPS FAMILIAR DE COLOMBIA", "EPS SANITAS", "EPS SURA", "FAMISANAR EPS",
    "FONDO DE PASIVO SOCIAL DE FERROCARRILES NACIONALES", "MALLAMAS EPSI", "MUTUAL SER EPS",
    "NUEVA EPS", "SALUD MÍA EPS", "SALUD TOTAL EPS", "SAVIA SALUD EPS",
    "SERVICIO OCCIDENTAL DE SALUD (SOS)", "EMPRESAS PÚBLICAS DE MEDELLÍN (EPM Salud)",
]
_ARL = [
    "ARL SURA", "ARL POSITIVA", "ARL AXA COLPATRIA", "ARL COLMENA", "ARL BOLÍVAR",
    "ARL LA EQUIDAD", "ARL AURORA", "ARL COLSANITAS", "ARL MAPFRE", "ARL SEGUROS ALFA",
]
_AFP = ["COLPENSIONES", "PORVENIR", "PROTECCIÓN", "COLFONDOS", "SKANDIA"]
_CCF = [
    "CAFAM", "COLSUBSIDIO", "COMPENSAR", "COMFAMA", "COMFANDI", "COMFENALCO VALLE DELAGENTE",
    "COMFENALCO ANTIOQUIA", "COMFAMILIAR ATLÁNTICO", "COMFACAUCA", "COMFACOR",
    "COMFAMILIAR NARIÑO", "COMFENALCO QUINDÍO", "COMFACASANARE", "COMFAORIENTE", "COMFAGUAJIRA",
    "CAJACOPI", "COMFATOLIMA", "COMFASUCRE", "COMFAMILIAR CARTAGENA Y BOLÍVAR", "COMFACUNDI",
    "COMFACA", "COMFAMILIAR PUTUMAYO", "COMFIAR", "COMFACHOCÓ", "CAFABA", "COMCAJA", "CAJASAI",
    "CAFAMAZ", "CAFASUR", "COMFAMILIAR CAMACOL", "COMBARRANQUILLA", "COMFABOY",
    "COMFENALCO CARTAGENA", "COMFENALCO TOLIMA", "COMFENALCO SANTANDER", "CONFA", "COFREM",
    "CAJAMAG", "CAJASAN", "COMFACESAR", "COMFANORTE", "COMFAMILIAR HUILA", "COMFAMILIAR RISARALDA",
]
_BANCOS = [
    "BANCOLOMBIA", "BANCO DE BOGOTÁ", "BANCO DE OCCIDENTE", "BANCO POPULAR", "BANCO AV VILLAS",
    "DAVIVIENDA", "BANCO CAJA SOCIAL", "BBVA COLOMBIA", "BANCO AGRARIO DE COLOMBIA",
    "BANCO GNB SUDAMERIS", "BANCO FALABELLA", "BANCO PICHINCHA", "BANCO ITAÚ", "BANCOOMEVA",
    "BANCO SERFINANZA", "BANCO MUNDO MUJER", "BANCO W", "BANCO FINANDINA",
    "BANCO SANTANDER COLOMBIA", "CITIBANK COLOMBIA", "JP MORGAN COLOMBIA", "BNP PARIBAS COLOMBIA",
    "MIBANCO", "LULO BANK", "NU COLOMBIA", "BAN100", "BANCO UNIÓN",
]
# Categorías de dependiente económico (placeholder; ajustar etiquetas a las categorías reales).
_TIPO_DEPENDIENTE = ["TIPO A", "TIPO B", "TIPO C", "TIPO D", "TIPO E"]


OPCIONES_BASE = [
    {
        "categoria": "tipo",
        "opciones": [
            {"clave": "memorandos", "etiqueta": "Memorandos", "activo": True},
            {"clave": "oficios", "etiqueta": "Oficios", "activo": True},
            {"clave": "pqrds", "etiqueta": "PQRDS", "activo": True},
        ],
    },
    {
        "categoria": "grupo",
        "opciones": [
            {"clave": "permisos", "etiqueta": "Permisos", "activo": True},
            {"clave": "despacho", "etiqueta": "Despacho", "activo": True},
            {"clave": "innovacion", "etiqueta": "Innovación", "activo": True},
            {"clave": "normativa", "etiqueta": "Normativa", "activo": True},
        ],
    },
    {
        "categoria": "clase_correspondencia",
        "opciones": [
            {"clave": "solicitudes_info", "etiqueta": "Solicitudes de información", "activo": True},
            {"clave": "respuestas", "etiqueta": "Respuestas", "activo": True},
            {"clave": "observaciones", "etiqueta": "Observaciones / Revisiones", "activo": True},
            {"clave": "permisos", "etiqueta": "Permisos", "activo": True},
            {"clave": "contratos", "etiqueta": "Contratos", "activo": True},
            {"clave": "informes", "etiqueta": "Informes", "activo": True},
            {"clave": "radicado_general", "etiqueta": "Radicado General", "activo": True},
            {"clave": "conceptos", "etiqueta": "Conceptos", "activo": True},
            {"clave": "aprobaciones", "etiqueta": "Aprobaciones", "activo": True},
            {"clave": "devoluciones_dinero", "etiqueta": "Devoluciones de dinero", "activo": True},
            {"clave": "doc_administrativo", "etiqueta": "Documento administrativo", "activo": True},
            {"clave": "derechos_peticion", "etiqueta": "Derechos de petición", "activo": True},
            {"clave": "doc_informativo", "etiqueta": "Documento informativo", "activo": True},
            {"clave": "traslado_competencia", "etiqueta": "Traslado por competencia", "activo": True},
            {"clave": "subsanaciones", "etiqueta": "Subsanaciones", "activo": True},
            {"clave": "disciplinarios", "etiqueta": "Disciplinarios", "activo": True},
            {"clave": "informativo", "etiqueta": "Informativo", "activo": True},
        ],
    },
    {
        "categoria": "estados",
        "opciones": [
            {"clave": "recibido", "etiqueta": "Recibido", "activo": True},
            {"clave": "en_tramite", "etiqueta": "En Trámite", "activo": True},
            {"clave": "en_revision", "etiqueta": "En Revisión", "activo": True},
            {"clave": "respondido", "etiqueta": "Respondido", "activo": True},
            {"clave": "archivado", "etiqueta": "Archivado", "activo": True},
            {"clave": "traslado_competencia", "etiqueta": "Traslado por Competencia", "activo": True},
        ],
    },
    {"categoria": "eps", "opciones": _opciones_desde_etiquetas(_EPS)},
    {"categoria": "arl", "opciones": _opciones_desde_etiquetas(_ARL)},
    {"categoria": "afp", "opciones": _opciones_desde_etiquetas(_AFP)},
    {"categoria": "ccf", "opciones": _opciones_desde_etiquetas(_CCF)},
    {"categoria": "banco", "opciones": _opciones_desde_etiquetas(_BANCOS)},
    {"categoria": "tipo_dependiente", "opciones": _opciones_desde_etiquetas(_TIPO_DEPENDIENTE)},
]


class CatalogoService:
    def __init__(self) -> None:
        self.coleccion_permisos = obtener_coleccion("permisos")
        self.coleccion_roles = obtener_coleccion("roles")
        self.coleccion_opciones = obtener_coleccion("opciones_configuracion")

    def asegurar_catalogos_base(self) -> None:
        for permiso in PERMISOS_BASE:
            self.coleccion_permisos.update_one(
                {"clave": permiso["clave"]},
                {"$setOnInsert": permiso},
                upsert=True,
            )

        for rol in ROLES_BASE:
            self.coleccion_roles.update_one(
                {"nombre": rol["nombre"]},
                {"$set": rol},
                upsert=True,
            )

        for opcion in OPCIONES_BASE:
            self.coleccion_opciones.update_one(
                {"categoria": opcion["categoria"]},
                {"$set": opcion},
                upsert=True,
            )

        # Configuración inicial de firmantes designados para certificaciones
        self.coleccion_opciones.update_one(
            {"categoria": "firmantes_certificacion"},
            {
                "$setOnInsert": {
                    "categoria": "firmantes_certificacion",
                    "firmantes": {"corr": None, "gd": None, "secop": None},
                }
            },
            upsert=True,
        )
