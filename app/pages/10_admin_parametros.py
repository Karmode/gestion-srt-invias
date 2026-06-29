from app.pages_admin import admin_parametros
from app.core.sesion import obtener_sesion

admin_parametros.render(obtener_sesion())
