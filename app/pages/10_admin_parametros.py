import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.pages_admin import admin_parametros
from app.core.sesion import obtener_sesion

admin_parametros.render(obtener_sesion())
