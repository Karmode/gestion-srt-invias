import re
import sys
import os

# Add app directory to path
sys.path.append(os.path.abspath('.'))

from app.services.correspondencia_service import CorrespondenciaService

svc = CorrespondenciaService()

test_terms = ['2026E-VUVRAZ-049377', '049377', 'VUVRAZ', 'Ana', 'perez', '2026E', 'convenio 2863', '04937']
for term in test_terms:
    res, count = svc.listar_correspondencia(ver_todas=True, skip=0, limit=100, filtros={'busqueda': term})
    radicados = [d['numero_radicado'] for d in res]
    print(f'Term: "{term}" -> Count: {count}, Sample: {radicados[:5]}')
