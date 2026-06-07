from app.pages_admin import admin_firmantes
from app.core.sesion import obtener_sesion

admin_firmantes.render(obtener_sesion())
