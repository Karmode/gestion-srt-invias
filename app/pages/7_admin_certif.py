from app.pages_admin import admin_certificaciones
from app.core.sesion import obtener_sesion

admin_certificaciones.render(obtener_sesion())
