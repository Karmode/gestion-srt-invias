TIPOS_CONTRATO = {
    "": "— Sin especificar —",
    "termino_indefinido": "Término indefinido",
    "termino_fijo": "Término fijo",
    "obra_labor": "Obra o labor",
    "prestacion_servicios": "Prestación de servicios",
    "aprendizaje": "Aprendizaje",
}

# Tipos de documento admitidos para un dependiente económico
TIPOS_DOC_DEPENDIENTE = {
    "": "— Sin especificar —",
    "CC": "CC — Cédula de Ciudadanía",
    "TI": "TI — Tarjeta de Identidad",
    "CE": "CE — Cédula de Extranjería",
}

PERMISOS_BASE = [
    {"clave": "usuario.ver", "descripcion": "Ver usuarios", "modulo": "usuarios"},
    {"clave": "usuario.crear", "descripcion": "Crear usuarios", "modulo": "usuarios"},
    {"clave": "usuario.editar", "descripcion": "Editar usuarios", "modulo": "usuarios"},
    {"clave": "usuario.desactivar", "descripcion": "Desactivar usuarios", "modulo": "usuarios"},
    {"clave": "rol.ver", "descripcion": "Ver roles", "modulo": "roles"},
    {"clave": "rol.crear", "descripcion": "Crear roles", "modulo": "roles"},
    {"clave": "rol.editar", "descripcion": "Editar roles", "modulo": "roles"},
    {"clave": "rol.desactivar", "descripcion": "Desactivar roles", "modulo": "roles"},
    {"clave": "dashboard.ver", "descripcion": "Ver dashboard", "modulo": "dashboard"},
    {"clave": "reporte.ver", "descripcion": "Ver reportes", "modulo": "reportes"},
    {"clave": "correspondencia.ver", "descripcion": "Ver correspondencia", "modulo": "correspondencia"},
    {"clave": "correspondencia.crear", "descripcion": "Crear correspondencia", "modulo": "correspondencia"},
    {"clave": "correspondencia.editar", "descripcion": "Editar correspondencia", "modulo": "correspondencia"},
    {"clave": "certificacion.ver", "descripcion": "Ver certificaciones propias", "modulo": "certificaciones"},
    {"clave": "certificacion.aprobar", "descripcion": "Aprobar certificaciones de colaboradores", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_corr", "descripcion": "Firmar aprobación de Correspondencia", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_gd", "descripcion": "Firmar aprobación de Gestión Documental", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_secop", "descripcion": "Firmar aprobación de SECOP II", "modulo": "certificaciones"},
    {"clave": "certificacion.gestionar_firmantes", "descripcion": "Configurar firmantes designados de certificaciones", "modulo": "certificaciones"},
]

_PERMISOS_SOLO_FIRMANTES = {
    "certificacion.firmar_corr",
    "certificacion.firmar_gd",
    "certificacion.firmar_secop",
}

ROLES_BASE = [
    {
        "nombre": "admin",
        "descripcion": "Administrador del sistema",
        "permisos": [p["clave"] for p in PERMISOS_BASE if p["clave"] not in _PERMISOS_SOLO_FIRMANTES],
        "activo": True,
    },
    {
        "nombre": "firmante_certificacion",
        "descripcion": "Firmante designado para aprobación de certificaciones",
        "permisos": ["certificacion.ver"],
        "activo": True,
    },
    {
        "nombre": "direccion",
        "descripcion": "Dirección con acceso a reportes",
        "permisos": ["reporte.ver", "dashboard.ver"],
        "activo": True,
    },
    {
        "nombre": "asignacion",
        "descripcion": "Rol de asignación de correspondencia",
        "permisos": ["correspondencia.ver", "correspondencia.crear", "correspondencia.editar"],
        "activo": True,
    },
    {
        "nombre": "coordinador",
        "descripcion": "Coordinador de área",
        "permisos": ["correspondencia.ver", "dashboard.ver", "reporte.ver"],
        "activo": True,
    },
    {
        "nombre": "lider",
        "descripcion": "Líder de equipo",
        "permisos": ["correspondencia.ver"],
        "activo": True,
    },
    {
        "nombre": "gestor",
        "descripcion": "Gestor de correspondencia",
        "permisos": ["correspondencia.ver"],
        "activo": True,
    },
    {
        "nombre": "supervisor",
        "descripcion": "Supervisor de certificaciones mensuales",
        "permisos": [
            "certificacion.ver",
            "certificacion.aprobar",
            "correspondencia.ver",
            "dashboard.ver",
        ],
        "activo": True,
    },
]
