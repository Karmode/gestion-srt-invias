"""Festivos de Colombia: instancia unica compartida.

holidays.CO() puebla los festivos de forma perezosa por anio; crear una
instancia por rerun (o por fila de tabla) desperdicia trabajo. Este
singleton se usa solo para consultas de pertenencia (fecha in FESTIVOS_CO).
"""

import holidays

FESTIVOS_CO = holidays.CO()
