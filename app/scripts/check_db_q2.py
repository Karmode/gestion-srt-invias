import sys
from pymongo import MongoClient
from app.config import configuracion

client = MongoClient(configuracion.mongodb_uri)
db = client[configuracion.mongodb_db]
col = db["correspondencia"]

anio = 2026
trimestre = 2 # T2: April, May, June

print("Running manual query matching the logic for year 2026, Q2 (T2):")
docs = col.find({"estado_actual": "respondido"})
counts = {}

for doc in docs:
    if "PQRD" not in str(doc.get("tipo", "")).upper():
        continue
    
    f_rad = doc.get("fecha_radicacion")
    f_resp = doc.get("respuesta", {}).get("fecha_salida") if isinstance(doc.get("respuesta"), dict) else None
    
    fecha_ref = f_resp or f_rad
    if not fecha_ref:
        continue
        
    ref_year = fecha_ref.year
    ref_trimestre = (fecha_ref.month - 1) // 3 + 1
    
    if ref_year == anio and ref_trimestre == trimestre:
        grupo = doc.get("grupo", "sin_grupo")
        counts[grupo] = counts.get(grupo, 0) + 1

print("Matches found by group for 2026 T2:")
print(counts)
