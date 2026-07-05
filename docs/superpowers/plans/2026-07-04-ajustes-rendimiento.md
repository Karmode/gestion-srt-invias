# Plan de Ajustes de Rendimiento — Gestión SRTI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar los cuellos de botella de rendimiento detectados en la revisión del 2026-07-04: consultas sin índice, lecturas repetidas sin caché y agregaciones hechas en Python que deben ejecutarse en MongoDB.

**Architecture:** No se cambia la arquitectura en capas (pages → services → repositories → MongoDB). Se agregan índices en el bootstrap, un módulo nuevo de caché de lecturas (`app/core/cache_datos.py`) que las páginas consumen en lugar de llamar servicios directamente para datos de solo lectura, y se reescriben tres funciones de servicio para que agreguen en el servidor de Mongo.

**Tech Stack:** Streamlit ≥ 1.35, PyMongo 4.x, `st.cache_data`, pipelines de agregación de MongoDB.

## Global Constraints

- El proyecto NO tiene suite de tests automatizados. Cada tarea termina con un paso de **verificación ejecutable** (comando `python -c ...` contra la BD de desarrollo o verificación manual en la app). No inventar infraestructura de pytest en este plan.
- Toda operación de escritura en `correspondencia` debe seguir agregando entrada al array `trazabilidad` (no se toca esa lógica).
- Los servicios no acceden a Streamlit; el caché con `st.cache_data` vive SOLO en `app/core/cache_datos.py` y en páginas. Los repositorios y servicios quedan libres de imports de `streamlit`.
- Zona horaria: usar `app/core/zona_horaria.py` donde ya se usa; no cambiar semántica de fechas.
- Config siempre desde `Configuracion` (`app/config.py`), nunca `os.environ`.
- Rama de trabajo: `javier-lab`. Commits pequeños, uno por tarea.
- El botón "🔄 Actualizar" de las páginas **se conserva** (el usuario lo necesita porque F5 pierde la sesión). Con el caché nuevo, ese botón pasa a limpiar el caché antes del rerun.
- Verificar conexión a BD de desarrollo antes de empezar: las variables `MONGODB_URI` y `MONGODB_DB` del `.env` deben apuntar al entorno de desarrollo, NO a producción (los pasos de verificación ejecutan consultas reales).

---

### Task 1: Índices de MongoDB para correspondencia (PRIORIDAD 1 — máxima ganancia, mínimo riesgo)

**Files:**
- Modify: `app/services/mongo_bootstrap_service.py` (dentro de `asegurar_estructura`, después de la línea que crea `idx_correspondencia_responsable`, ~línea 80)

**Interfaces:**
- Consumes: `self.db["correspondencia"]` (ya disponible en el método).
- Produces: índices `idx_correspondencia_fecha_radicacion` e `idx_correspondencia_resp_estado_venc` que las consultas existentes usarán automáticamente. Ninguna otra tarea depende de nombres nuevos de código.

**Por qué:** El listado principal ordena SIEMPRE por `fecha_radicacion` descendente sin índice (sort en memoria en cada página que carga cualquier usuario). Todas las métricas de vencimiento filtran por `responsable_actual.usuario_id` + `estado_actual` + `fecha_vencimiento` sin índice compuesto.

- [ ] **Step 1: Agregar los dos índices en el bootstrap**

En `app/services/mongo_bootstrap_service.py`, inmediatamente después del bloque:

```python
        self.db["correspondencia"].create_index(
            "responsable_actual.usuario_id", name="idx_correspondencia_responsable"
        )
```

agregar:

```python
        self.db["correspondencia"].create_index(
            [("fecha_radicacion", -1)],
            name="idx_correspondencia_fecha_radicacion",
        )
        self.db["correspondencia"].create_index(
            [
                ("responsable_actual.usuario_id", 1),
                ("estado_actual", 1),
                ("fecha_vencimiento", 1),
            ],
            name="idx_correspondencia_resp_estado_venc",
        )
```

- [ ] **Step 2: Ejecutar el bootstrap (es idempotente)**

Run: `python -m app.scripts.init_db`
Expected: termina sin errores, imprime "Estructura y validadores asegurados." y los conteos por colección.

- [ ] **Step 3: Verificar que los índices existen**

Run:
```bash
python -c "from app.db.mongo import obtener_coleccion; import json; print(json.dumps(sorted(obtener_coleccion('correspondencia').index_information().keys()), indent=2))"
```
Expected: la lista incluye `idx_correspondencia_fecha_radicacion` e `idx_correspondencia_resp_estado_venc`.

- [ ] **Step 4: Verificar que el listado usa el índice (explain)**

Run:
```bash
python -c "from app.db.mongo import obtener_coleccion; c = obtener_coleccion('correspondencia'); plan = c.find({}).sort('fecha_radicacion', -1).limit(50).explain(); print(plan['queryPlanner']['winningPlan'])"
```
Expected: el plan ganador contiene `IXSCAN` con `idx_correspondencia_fecha_radicacion` (NO `COLLSCAN` + `SORT`).

- [ ] **Step 5: Commit**

```bash
git add app/services/mongo_bootstrap_service.py
git commit -m "perf: indices para fecha_radicacion y responsable+estado+vencimiento en correspondencia"
```

---

### Task 2: Módulo de caché de lecturas con st.cache_data (PRIORIDAD 2 — mayor impacto percibido)

**Files:**
- Create: `app/core/cache_datos.py`
- Modify: `app/pages/2_correspondencia.py` (líneas ~255-258, ~290-295, ~545-546, ~650-655, ~625)
- Modify: `app/pages/5_dashboard.py` (líneas ~29-31, ~35-41, ~53-60)
- Modify: `app/main.py` (función `pantalla_dashboard`, ~línea 1550)

**Interfaces:**
- Consumes: `UsuarioService.listar_usuarios()`, `OpcionesService.obtener_opciones(categoria)`, `CorrespondenciaService.obtener_metricas_dashboard(id_usuario)`, `ReporteService` (todos existentes, sin cambios de firma).
- Produces (para todas las páginas):
  - `usuarios_activos_para_seleccion() -> dict[str, str]` — mapa `str(id) -> nombre para mostrar`, solo usuarios activos, orden alfabético por nombre.
  - `admins_activos_para_seleccion() -> dict[str, str]` — igual, filtrado a rol `admin`.
  - `opciones_activas(categoria: str) -> list[dict]` — opciones de catálogo (dicts con `clave` y `etiqueta`).
  - `metricas_inicio(id_usuario: str | None) -> dict` — resultado de `obtener_metricas_dashboard`.
  - `datos_dashboard_admin(usuario_id: str | None) -> dict` — dict con claves `resumen`, `dist_estado`, `carga_usuarios`, `vencimientos`, `tendencia_d`, `tiempos_resp`.
  - `limpiar_cache_lecturas() -> None` — limpia todo lo anterior.

**Por qué:** Hoy `listar_usuarios()` (colección completa) se ejecuta hasta 4 veces en UN solo rerun de la página de correspondencia, y cada interacción con cualquier widget vuelve a disparar todas las consultas. Un TTL de 60s elimina >90% del tráfico repetido sin cambiar la UX.

- [ ] **Step 1: Crear `app/core/cache_datos.py`**

```python
"""Caché de lecturas frecuentes para las páginas Streamlit.

Única capa donde se permite mezclar st.cache_data con servicios.
Las páginas consumen estas funciones en lugar de llamar servicios
directamente para datos de solo lectura que cambian poco.
"""

from typing import Optional

import streamlit as st


@st.cache_data(ttl=60, show_spinner=False)
def usuarios_activos_para_seleccion() -> dict:
    """Mapa str(id) -> nombre visible, solo usuarios activos, orden alfabético."""
    from app.services.usuario_service import UsuarioService

    usuarios = UsuarioService().listar_usuarios()
    activos = [u for u in usuarios if u.get("activo", True)]
    activos.sort(key=lambda u: (u.get("nombre_completo") or u.get("usuario", "")).lower())
    return {
        str(u["_id"]): u.get("nombre_completo") or u["usuario"]
        for u in activos
    }


@st.cache_data(ttl=60, show_spinner=False)
def admins_activos_para_seleccion() -> dict:
    """Mapa str(id) -> nombre visible, solo usuarios activos con rol admin."""
    from app.services.usuario_service import UsuarioService

    usuarios = UsuarioService().listar_usuarios()
    return {
        str(u["_id"]): u.get("nombre_completo") or u["usuario"]
        for u in usuarios
        if u.get("activo", True) and "admin" in u.get("roles", [])
    }


@st.cache_data(ttl=300, show_spinner=False)
def opciones_activas(categoria: str) -> list:
    """Opciones activas de un catálogo (lista de dicts con clave/etiqueta)."""
    from app.services.opciones_service import OpcionesService

    return OpcionesService().obtener_opciones(categoria)


@st.cache_data(ttl=60, show_spinner=False)
def metricas_inicio(id_usuario: Optional[str]) -> dict:
    """Métricas del panel de inicio (pendientes/urgentes/recientes)."""
    from app.services.correspondencia_service import CorrespondenciaService

    return CorrespondenciaService().obtener_metricas_dashboard(id_usuario=id_usuario)


@st.cache_data(ttl=60, show_spinner=False)
def datos_dashboard_admin(usuario_id: Optional[str]) -> dict:
    """Todas las consultas del dashboard admin en una sola entrada de caché."""
    from app.services.reporte_service import ReporteService

    svc = ReporteService()
    return {
        "resumen": svc.resumen_operativo(usuario_id=usuario_id),
        "dist_estado": svc.distribucion_por_estado(usuario_id=usuario_id),
        "carga_usuarios": svc.carga_por_usuario(usuario_id=usuario_id),
        "vencimientos": svc.analisis_vencimiento(usuario_id=usuario_id),
        "tendencia_d": svc.tendencia_diaria(dias=30, usuario_id=usuario_id),
        "tiempos_resp": svc.analisis_tiempos_respuesta(usuario_id=usuario_id),
    }


def limpiar_cache_lecturas() -> None:
    """Limpia todo el caché de lecturas. Llamar tras escrituras y en botones Actualizar."""
    usuarios_activos_para_seleccion.clear()
    admins_activos_para_seleccion.clear()
    opciones_activas.clear()
    metricas_inicio.clear()
    datos_dashboard_admin.clear()
```

- [ ] **Step 2: Usar el caché en `app/pages/2_correspondencia.py`**

2a. Agregar el import junto a los demás imports de `app.core`:

```python
from app.core.cache_datos import (
    usuarios_activos_para_seleccion,
    admins_activos_para_seleccion,
    opciones_activas,
    limpiar_cache_lecturas,
)
```

2b. Reemplazar la carga de catálogos (líneas ~98-99):

```python
grupos_dict = {op["clave"]: op["etiqueta"] for op in opciones_activas("grupo")}
clases_dict = {op["clave"]: op["etiqueta"] for op in opciones_activas("clase_correspondencia")}
```

2c. En el popover "Asignar / Reasignar" del modal (líneas ~256-258), reemplazar:

```python
                    usuarios = usuario_service.listar_usuarios()
                    usuarios_opts = {str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}" for u in usuarios if u.get("activo", True)}
```

por:

```python
                    usuarios_opts = usuarios_activos_para_seleccion()
```

2d. En el popover de reasignación restringida del gestor (líneas ~290-295), reemplazar:

```python
                    todos_usuarios = usuario_service.listar_usuarios()
                    admins_opts = {
                        str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}"
                        for u in todos_usuarios
                        if u.get("activo", True) and "admin" in u.get("roles", [])
                    }
```

por:

```python
                    admins_opts = admins_activos_para_seleccion()
```

2e. En el formulario de creación (líneas ~545-546), reemplazar:

```python
            usuarios = usuario_service.listar_usuarios()
            usuarios_opts = {str(u["_id"]): f"{u.get('nombre_completo', u['usuario'])}" for u in usuarios if u.get("activo", True)}
```

por:

```python
            usuarios_opts = usuarios_activos_para_seleccion()
```

2f. En el filtro por responsable (líneas ~650-655), reemplazar:

```python
            usuarios_list = usuario_service.listar_usuarios()
            usuarios_f_opts = {"Todos": "Todos los responsables"}
            for u in usuarios_list:
                if u.get("activo", True):
                    usuarios_f_opts[str(u["_id"])] = f"{u.get('nombre_completo', u['usuario'])}"
```

por:

```python
            usuarios_f_opts = {"Todos": "Todos los responsables"}
            usuarios_f_opts.update(usuarios_activos_para_seleccion())
```

2g. El botón "🔄 Actualizar Datos" (línea ~625) ahora limpia el caché (se conserva porque F5 pierde la sesión):

```python
        if st.button("🔄 Actualizar Datos", width="stretch", help="Recarga la lista de correspondencia"):
            limpiar_cache_lecturas()
            st.rerun()
```

2h. Tras cada escritura exitosa dentro del modal y del formulario de creación (los bloques que ya llaman `st.rerun()` después de `service.editar_correspondencia`, `service.asignar_correspondencia`, `service.dar_respuesta`, `service.archivar`, `service.cambiar_estado` y `service.crear_correspondencia`), agregar `limpiar_cache_lecturas()` en la línea inmediatamente anterior al `st.rerun()`. Son 8 puntos en el archivo; buscar con:

```bash
grep -n "st.rerun()" app/pages/2_correspondencia.py
```

y en cada ocurrencia que siga a una llamada de escritura del servicio, insertar `limpiar_cache_lecturas()` antes.

- [ ] **Step 3: Usar el caché en `app/pages/5_dashboard.py`**

3a. Agregar import:

```python
from app.core.cache_datos import usuarios_activos_para_seleccion, datos_dashboard_admin, limpiar_cache_lecturas
```

3b. Reemplazar el bloque de filtros (líneas ~35-41):

```python
from app.repositories.usuario_repo import UsuarioRepositorio
usuarios_activos = sorted(
    [u for u in UsuarioRepositorio().listar() if u.get("activo", True)],
    key=lambda x: x.get("nombre_completo", "").lower()
)
opciones_gestores = ["Todos"] + [u["nombre_completo"] for u in usuarios_activos]
nombre_a_id = {u["nombre_completo"]: str(u["_id"]) for u in usuarios_activos}
```

por:

```python
usuarios_map = usuarios_activos_para_seleccion()  # id -> nombre, ya ordenado
opciones_gestores = ["Todos"] + list(usuarios_map.values())
nombre_a_id = {nombre: uid for uid, nombre in usuarios_map.items()}
```

3c. Reemplazar el bloque de carga de servicios (líneas ~53-60):

```python
try:
    datos = datos_dashboard_admin(usuario_id_filtro)
    resumen = datos["resumen"]
    dist_estado = datos["dist_estado"]
    carga_usuarios = datos["carga_usuarios"]
    vencimientos = datos["vencimientos"]
    tendencia_d = datos["tendencia_d"]
    tiempos_resp = datos["tiempos_resp"]
except Exception as e:
    st.error(f"Error al cargar las métricas: {e}")
    st.stop()
```

3d. El botón "🔄 Actualizar" (línea ~29) limpia caché:

```python
    if st.button("🔄 Actualizar", use_container_width=True, key="refresh_dashboard"):
        limpiar_cache_lecturas()
        st.rerun()
```

- [ ] **Step 4: Usar el caché en el inicio (`app/main.py`, `pantalla_dashboard`)**

Reemplazar (líneas ~1550-1553):

```python
    servicio_corr = CorrespondenciaService()
    id_filtro = sesion.get("id")
    metricas = servicio_corr.obtener_metricas_dashboard(id_usuario=id_filtro)
```

por:

```python
    from app.core.cache_datos import metricas_inicio
    metricas = metricas_inicio(sesion.get("id"))
```

(El import local evita tocar la cabecera de un archivo de 1.900 líneas; si prefieres, muévelo arriba con los demás.)

- [ ] **Step 5: Invalidar caché donde se editan catálogos y usuarios**

Buscar los puntos de escritura de opciones y usuarios en las páginas admin:

```bash
grep -rn "limpiar_cache_opciones\|actualizar_opciones\|upsert\|crear_usuario\|actualizar_usuario\|cambiar_estado" app/pages_admin/ app/pages/10_admin_parametros.py
```

En cada handler de guardado exitoso encontrado (admin de usuarios, admin de parámetros/opciones), agregar:

```python
from app.core.cache_datos import limpiar_cache_lecturas
limpiar_cache_lecturas()
```

antes del `st.rerun()` o mensaje de éxito correspondiente. Si ya existe una llamada a `limpiar_cache_opciones()` (del `lru_cache` viejo), dejarla y añadir la nueva al lado.

- [ ] **Step 6: Verificación manual**

Run: `streamlit run app/main.py`
Expected:
1. Login funciona; el inicio muestra las 3 métricas.
2. En Correspondencia: los dropdowns de responsable/grupo/clase cargan; crear/asignar/responder un radicado de prueba refleja el cambio inmediatamente (el caché se invalidó).
3. En Dashboard: cambiar el filtro de gestor recalcula; pulsar "🔄 Actualizar" refresca datos.
4. Con la app abierta, interactuar con un filtro dos veces seguidas: la segunda interacción se siente notablemente más rápida (datos servidos de caché).

- [ ] **Step 7: Commit**

```bash
git add app/core/cache_datos.py app/pages/2_correspondencia.py app/pages/5_dashboard.py app/main.py app/pages_admin/ app/pages/10_admin_parametros.py
git commit -m "perf: cache de lecturas con st.cache_data (usuarios, catalogos, metricas, dashboard)"
```

---

### Task 3: Proyección sin password_hash en listado de usuarios (PRIORIDAD 3 — seguridad + rendimiento, 1 línea)

**Files:**
- Modify: `app/repositories/usuario_repo.py:49-50`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `UsuarioRepositorio.listar()` devuelve los mismos documentos SIN el campo `password_hash`. `buscar_por_usuario` y `buscar_por_id` NO cambian (login y cambio de contraseña los necesitan).

**Por qué:** Hoy los hashes bcrypt de todos los usuarios viajan hasta la capa de UI para armar dropdowns. No es una fuga crítica, pero es superficie de exposición innecesaria y datos extra transferidos.

- [ ] **Step 1: Agregar la proyección**

Reemplazar:

```python
    def listar(self):
        return list(self.coleccion.find().sort("usuario", 1))
```

por:

```python
    def listar(self):
        return list(self.coleccion.find({}, {"password_hash": 0}).sort("usuario", 1))
```

- [ ] **Step 2: Verificar que ningún consumidor de `listar()` usa password_hash**

Run: `grep -rn "password_hash" app/pages/ app/pages_admin/ app/services/usuario_service.py`
Expected: ninguna coincidencia que lea `password_hash` de un elemento devuelto por `listar()` (las coincidencias válidas son en auth/cambio de contraseña, que usan `buscar_por_usuario`/`buscar_por_id`).

- [ ] **Step 3: Verificación funcional**

Run: `streamlit run app/main.py` → abrir Administración → Usuarios.
Expected: la tabla de usuarios carga y se puede editar un usuario sin errores.

- [ ] **Step 4: Commit**

```bash
git add app/repositories/usuario_repo.py
git commit -m "sec/perf: excluir password_hash del listado de usuarios"
```

---

### Task 4: `obtener_estado_formatos` sin cargar la colección completa (PRIORIDAD 4 — bomba de escalabilidad)

**Files:**
- Modify: `app/services/correspondencia_service.py:340-415`

**Interfaces:**
- Consumes: `self.repo.coleccion` (PyMongo Collection, ya expuesta por el repo).
- Produces: misma firma y mismo shape de retorno que hoy — `obtener_estado_formatos() -> List[Dict]` con claves `usuario_id`, `responsable`, `estado_pendiente`, `cantidad_pendientes`, `cantidad_vencidas`, `cantidad_vencer_fin_mes`. `certificacion_service.py:279` no necesita cambios.

**Por qué:** Hoy hace `repo.listar(query, limit=100000)` — trae TODOS los documentos activos completos (incluido el array `trazabilidad`) para agrupar en Python, y recalcula los "últimos 3 días hábiles del mes" dentro del bucle por usuario (es invariante).

- [ ] **Step 1: Reescribir el método**

Reemplazar el cuerpo completo de `obtener_estado_formatos` por:

```python
    def obtener_estado_formatos(self) -> List[Dict]:
        """Obtiene el estado de correspondencia pendiente de todos los responsables activos."""
        from app.services.usuario_service import UsuarioService
        from app.core.zona_horaria import utc_a_bogota, ZONA_BOGOTA

        usuario_service = UsuarioService()

        # 1. Usuarios activos
        usuarios = usuario_service.listar_usuarios()
        usuarios_activos = [u for u in usuarios if u.get("activo", True)]

        # 2. Solo los campos necesarios de las correspondencias activas
        #    (proyección en servidor: NO viaja trazabilidad ni el documento completo)
        pipeline = [
            {"$match": {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}},
            {"$project": {
                "_id": 0,
                "responsable_id": "$responsable_actual.usuario_id",
                "fecha_vencimiento": 1,
            }},
        ]
        docs = list(self.repo.coleccion.aggregate(pipeline))

        # 3. Fechas de referencia (UNA sola vez, fuera del bucle por usuario)
        hoy_colombia = datetime.now(ZONA_BOGOTA)
        ultimo_dia_mes = (hoy_colombia.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        ultimos_dias_habiles = set()
        dia_actual = ultimo_dia_mes.date()
        while len(ultimos_dias_habiles) < 3:
            if dia_actual.weekday() < 5 and dia_actual not in self.festivos_co:
                ultimos_dias_habiles.add(dia_actual)
            dia_actual -= timedelta(days=1)

        # 4. Un solo paso sobre los docs proyectados: acumular por responsable
        from collections import defaultdict
        acumulado = defaultdict(lambda: {"pendientes": 0, "vencidas": 0, "fin_mes": 0})
        for doc in docs:
            resp_id = doc.get("responsable_id")
            if not resp_id:
                continue
            stats = acumulado[str(resp_id)]
            stats["pendientes"] += 1
            fecha_venc = doc.get("fecha_vencimiento")
            if fecha_venc:
                fecha_venc_bogota = utc_a_bogota(fecha_venc)
                if fecha_venc_bogota.date() < hoy_colombia.date():
                    stats["vencidas"] += 1
                if fecha_venc_bogota.date() in ultimos_dias_habiles:
                    stats["fin_mes"] += 1

        # 5. Armar resultado por usuario activo
        resultados = []
        for u in usuarios_activos:
            id_usuario = str(u["_id"])
            nombre_completo = u.get("nombre_completo") or u.get("usuario")
            stats = acumulado.get(id_usuario, {"pendientes": 0, "vencidas": 0, "fin_mes": 0})

            if stats["pendientes"] == 0:
                estado_pendiente = "gris"
            elif stats["vencidas"] > 0:
                estado_pendiente = "rojo"
            else:
                estado_pendiente = "verde"

            resultados.append({
                "usuario_id": id_usuario,
                "responsable": nombre_completo,
                "estado_pendiente": estado_pendiente,
                "cantidad_pendientes": stats["pendientes"],
                "cantidad_vencidas": stats["vencidas"],
                "cantidad_vencer_fin_mes": stats["fin_mes"],
            })

        resultados.sort(key=lambda x: x["responsable"].lower())
        return resultados
```

- [ ] **Step 2: Verificar equivalencia contra la BD de desarrollo**

Run:
```bash
python -c "from app.services.correspondencia_service import CorrespondenciaService; import json; r = CorrespondenciaService().obtener_estado_formatos(); print(json.dumps(r[:3], indent=2, ensure_ascii=False)); print('total responsables:', len(r))"
```
Expected: lista con el mismo shape de antes (`usuario_id`, `responsable`, `estado_pendiente`, `cantidad_pendientes`, `cantidad_vencidas`, `cantidad_vencer_fin_mes`), sin errores. Si tienes los números de la versión anterior a mano, deben coincidir exactamente.

- [ ] **Step 3: Verificación funcional en la app**

Abrir la página que consume esto (Seguimiento - Formatos, `pages/7_admin_certif.py`) y confirmar que el semáforo por responsable se ve igual que antes.

- [ ] **Step 4: Commit**

```bash
git add app/services/correspondencia_service.py
git commit -m "perf: obtener_estado_formatos con proyeccion en servidor en vez de cargar coleccion completa"
```

---

### Task 5: `existe_radicado` con match exacto indexado (PRIORIDAD 5)

**Files:**
- Modify: `app/repositories/correspondencia_repo.py:13-17`

**Interfaces:**
- Consumes: índice `idx_correspondencia_radicado` (ya existe).
- Produces: `buscar_por_radicado(numero_radicado)` con la misma firma; ahora normaliza y hace match exacto.

**Por qué:** El chequeo de duplicados corre en cada rerun del formulario de creación con un regex case-insensitive que no usa el índice. Los radicados ya se guardan normalizados a mayúsculas y sin espacios (`correspondencia_service.py:107`), así que un match exacto sobre el valor normalizado es equivalente y sí usa el índice.

- [ ] **Step 1: Comprobar que no hay radicados legados en minúsculas**

Run:
```bash
python -c "from app.db.mongo import obtener_coleccion; c = obtener_coleccion('correspondencia'); print('con minusculas:', c.count_documents({'numero_radicado': {'$regex': '[a-z]'}}))"
```
Expected: `con minusculas: 0`. **Si es > 0**, ejecutar primero esta migración puntual y volver a comprobar:

```bash
python -c "
from app.db.mongo import obtener_coleccion
c = obtener_coleccion('correspondencia')
for doc in c.find({'numero_radicado': {'\$regex': '[a-z]'}}, {'numero_radicado': 1}):
    c.update_one({'_id': doc['_id']}, {'\$set': {'numero_radicado': doc['numero_radicado'].replace(' ', '').upper()}})
print('migrados')
"
```

- [ ] **Step 2: Reemplazar el regex por match exacto**

En `app/repositories/correspondencia_repo.py`, reemplazar:

```python
    def buscar_por_radicado(self, numero_radicado: str):
        import re
        return self.coleccion.find_one({
            "numero_radicado": {"$regex": f"^{re.escape(numero_radicado)}$", "$options": "i"}
        })
```

por:

```python
    def buscar_por_radicado(self, numero_radicado: str):
        normalizado = (numero_radicado or "").replace(" ", "").upper()
        return self.coleccion.find_one({"numero_radicado": normalizado})
```

- [ ] **Step 3: Verificar**

Run:
```bash
python -c "
from app.repositories.correspondencia_repo import CorrespondenciaRepositorio
repo = CorrespondenciaRepositorio()
doc = repo.coleccion.find_one({}, {'numero_radicado': 1})
if doc:
    rad = doc['numero_radicado']
    assert repo.buscar_por_radicado(rad) is not None, 'exacto fallo'
    assert repo.buscar_por_radicado(rad.lower()) is not None, 'lowercase fallo'
    assert repo.buscar_por_radicado(' ' + rad + ' ') is not None, 'espacios fallo'
    print('OK:', rad)
else:
    print('coleccion vacia, verificar manualmente creando un radicado')
"
```
Expected: `OK: <radicado>`.

- [ ] **Step 4: Commit**

```bash
git add app/repositories/correspondencia_repo.py
git commit -m "perf: buscar_por_radicado con match exacto normalizado (usa indice)"
```

---

### Task 6: Singleton de festivos de Colombia (PRIORIDAD 6)

**Files:**
- Create: `app/core/festivos.py`
- Modify: `app/services/correspondencia_service.py:13`
- Modify: `app/services/pdf_report_service.py:26`
- Modify: `app/pages/2_correspondencia.py:799` y `:813`

**Interfaces:**
- Produces: `app.core.festivos.FESTIVOS_CO` — instancia única de `holidays.CO()` compartida por todo el proceso (el objeto soporta `fecha in FESTIVOS_CO` y es de solo lectura en nuestro uso, por lo que compartirlo es seguro).

**Por qué:** Hoy se crea un objeto `holidays.CO()` nuevo por cada instanciación de servicio (es decir, por cada rerun) y, peor, DENTRO del bucle por fila de la tabla de correspondencia (dos veces).

- [ ] **Step 1: Crear `app/core/festivos.py`**

```python
"""Festivos de Colombia: instancia unica compartida.

holidays.CO() puebla los festivos de forma perezosa por anio; crear una
instancia por rerun (o por fila de tabla) desperdicia trabajo. Este
singleton se usa solo para consultas de pertenencia (fecha in FESTIVOS_CO).
"""

import holidays

FESTIVOS_CO = holidays.CO()
```

- [ ] **Step 2: Usarlo en `correspondencia_service.py`**

Reemplazar en `__init__`:

```python
        self.festivos_co = holidays.CO()
```

por:

```python
        self.festivos_co = FESTIVOS_CO
```

agregando el import `from app.core.festivos import FESTIVOS_CO` y eliminando `import holidays` de la cabecera.

- [ ] **Step 3: Usarlo en `pdf_report_service.py`**

Reemplazar `self.co_holidays = holidays.CO()` por `self.co_holidays = FESTIVOS_CO` con el mismo import; eliminar `import holidays` si queda sin uso.

- [ ] **Step 4: Usarlo en `2_correspondencia.py`**

Agregar `from app.core.festivos import FESTIVOS_CO` a los imports y reemplazar las DOS ocurrencias de:

```python
                        co_holidays = holidays.CO()
```

por:

```python
                        co_holidays = FESTIVOS_CO
```

Eliminar `import holidays` de la cabecera del archivo (queda sin uso).

- [ ] **Step 5: Verificar**

Run:
```bash
python -c "from app.core.festivos import FESTIVOS_CO; import datetime; print(datetime.date(2026, 7, 20) in FESTIVOS_CO)"
```
Expected: `True` (20 de julio, fiesta nacional).

Run: `grep -rn "holidays.CO()" app/`
Expected: única coincidencia en `app/core/festivos.py`.

- [ ] **Step 6: Verificación funcional**

Abrir Correspondencia en la app: la columna "Tiempo" de la tabla muestra los mismos días hábiles de atraso/restantes que antes.

- [ ] **Step 7: Commit**

```bash
git add app/core/festivos.py app/services/correspondencia_service.py app/services/pdf_report_service.py app/pages/2_correspondencia.py
git commit -m "perf: singleton de festivos CO en vez de instanciar holidays.CO() por rerun/fila"
```

---

### Task 7: Reportes pesados como agregaciones en Mongo (PRIORIDAD 7)

**Files:**
- Modify: `app/services/reporte_service.py:82-171` (`analisis_vencimiento` y `analisis_tiempos_respuesta`)

**Interfaces:**
- Consumes: `self.repo.coleccion.aggregate` (mismo patrón que ya usan `distribucion_por_estado` y `tendencia_diaria` en este archivo).
- Produces: mismas firmas y mismos DataFrames de salida:
  - `analisis_vencimiento(usuario_id) -> DataFrame[categoria, cantidad]` con las 3 categorías siempre presentes.
  - `analisis_tiempos_respuesta(usuario_id) -> DataFrame[Tipo, Días Promedio]`.

**Por qué:** Hoy cargan hasta 10.000 y 5.000 documentos completos (incluida `trazabilidad`) para clasificar/promediar en Python. Nota de semántica: la versión actual usa `(f_venc - hoy).days` (trunca hacia cero); la agregación compara datetimes directamente. La diferencia máxima es de horas en el borde de cada categoría — aceptable para un gráfico de semáforo.

- [ ] **Step 1: Reescribir `analisis_vencimiento`**

```python
    def analisis_vencimiento(self, usuario_id: str = None) -> pd.DataFrame:
        """Clasifica los trámites activos por su proximidad al vencimiento (agregado en servidor)."""
        from bson import ObjectId
        hoy = datetime.now(timezone.utc)
        limite_urgente = hoy + timedelta(days=5)

        match_stage = {"estado_actual": {"$in": ["pendiente", "en_tramite", "en_revision"]}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        pipeline = [
            {"$match": match_stage},
            {"$match": {"fecha_vencimiento": {"$ne": None}}},
            {"$group": {
                "_id": None,
                "Vencidos": {"$sum": {"$cond": [{"$lt": ["$fecha_vencimiento", hoy]}, 1, 0]}},
                "Urgentes (0-5d)": {"$sum": {"$cond": [
                    {"$and": [
                        {"$gte": ["$fecha_vencimiento", hoy]},
                        {"$lte": ["$fecha_vencimiento", limite_urgente]},
                    ]}, 1, 0]}},
                "A Tiempo (>5d)": {"$sum": {"$cond": [{"$gt": ["$fecha_vencimiento", limite_urgente]}, 1, 0]}},
            }},
        ]
        resultado = list(self.repo.coleccion.aggregate(pipeline))
        categorias = {"Vencidos": 0, "Urgentes (0-5d)": 0, "A Tiempo (>5d)": 0}
        if resultado:
            fila = resultado[0]
            for k in categorias:
                categorias[k] = fila.get(k, 0)
        return pd.DataFrame([{"categoria": k, "cantidad": v} for k, v in categorias.items()])
```

- [ ] **Step 2: Reescribir `analisis_tiempos_respuesta`**

```python
    def analisis_tiempos_respuesta(self, usuario_id: str = None) -> pd.DataFrame:
        """Tiempo promedio de respuesta/cierre por tipo (agregado en servidor)."""
        from bson import ObjectId
        match_stage = {"estado_actual": {"$in": ["respondido", "archivado", "traslado_competencia"]}}
        if usuario_id:
            match_stage["responsable_actual.usuario_id"] = ObjectId(usuario_id)

        # Fecha de cierre: respuesta.fecha_salida si el estado es "respondido"
        # (con fallback al último evento de trazabilidad), si no, el último
        # evento de trazabilidad — misma prioridad que la versión en Python.
        ultimo_evento = {"$arrayElemAt": ["$trazabilidad.fecha", -1]}
        pipeline = [
            {"$match": match_stage},
            {"$project": {
                "tipo": {"$ifNull": ["$tipo", "otro"]},
                "fecha_radicacion": 1,
                "f_cierre": {"$cond": [
                    {"$eq": ["$estado_actual", "respondido"]},
                    {"$ifNull": ["$respuesta.fecha_salida", ultimo_evento]},
                    ultimo_evento,
                ]},
            }},
            {"$match": {"fecha_radicacion": {"$ne": None}, "f_cierre": {"$ne": None}}},
            {"$group": {
                "_id": "$tipo",
                "dias_promedio": {"$avg": {"$divide": [
                    {"$subtract": ["$f_cierre", "$fecha_radicacion"]},
                    1000 * 60 * 60 * 24,
                ]}},
            }},
            {"$sort": {"_id": 1}},
        ]
        datos = list(self.repo.coleccion.aggregate(pipeline))
        if not datos:
            return pd.DataFrame(columns=["Tipo", "Días Promedio"])

        resumen = pd.DataFrame(
            [{"Tipo": d["_id"], "Días Promedio": round(d["dias_promedio"], 1)} for d in datos]
        )
        return resumen
```

- [ ] **Step 3: Verificar contra la BD de desarrollo**

Run:
```bash
python -c "
from app.services.reporte_service import ReporteService
svc = ReporteService()
print(svc.analisis_vencimiento())
print(svc.analisis_tiempos_respuesta())
"
```
Expected: dos DataFrames con las mismas columnas de antes (`categoria/cantidad` y `Tipo/Días Promedio`) y valores plausibles (comparar a ojo con el dashboard actual antes de hacer el cambio si quieres una referencia exacta).

- [ ] **Step 4: Verificación funcional**

Abrir el Dashboard admin: el semáforo de vencimientos y el gráfico de tiempos de respuesta se renderizan con datos equivalentes. Nota: si hiciste la Task 2, pulsa "🔄 Actualizar" para invalidar el caché antes de comparar.

- [ ] **Step 5: Commit**

```bash
git add app/services/reporte_service.py
git commit -m "perf: analisis_vencimiento y tiempos_respuesta como agregaciones en Mongo"
```

---

### Task 8: Excluir `trazabilidad` del listado y cargarla solo al abrir el modal (PRIORIDAD 8)

**Files:**
- Modify: `app/repositories/correspondencia_repo.py:19-21`
- Modify: `app/services/correspondencia_service.py:25-81` (`listar_correspondencia`)
- Modify: `app/pages/2_correspondencia.py:943-950` (selección de fila)

**Interfaces:**
- Consumes: `CorrespondenciaService.buscar_por_id` (existente, devuelve el documento completo).
- Produces: `CorrespondenciaRepositorio.listar(query, skip, limit, projection=None)` — nuevo parámetro opcional. `listar_correspondencia` devuelve documentos SIN `trazabilidad`. El modal recibe siempre el documento completo vía `buscar_por_id`.

**Por qué:** El array `trazabilidad` crece sin límite y la tabla no lo usa; hoy viaja completo en cada página de 50 filas y en cada rerun. Bonus: el modal pasa a leer el documento fresco de la BD, así que si otro usuario lo modificó, se ve el estado actual.

- [ ] **Step 1: Parámetro de proyección en el repo**

Reemplazar:

```python
    def listar(self, query: dict = None, skip: int = 0, limit: int = 10):
        q = query or {}
        return list(self.coleccion.find(q).sort("fecha_radicacion", -1).skip(max(0, skip)).limit(limit))
```

por:

```python
    def listar(self, query: dict = None, skip: int = 0, limit: int = 10, projection: dict = None):
        q = query or {}
        return list(
            self.coleccion.find(q, projection)
            .sort("fecha_radicacion", -1)
            .skip(max(0, skip))
            .limit(limit)
        )
```

- [ ] **Step 2: Proyección en el servicio de listado**

En `listar_correspondencia` (línea ~81), reemplazar:

```python
        return self.repo.listar(query, skip, limit), self.repo.contar(query)
```

por:

```python
        return (
            self.repo.listar(query, skip, limit, projection={"trazabilidad": 0}),
            self.repo.contar(query),
        )
```

- [ ] **Step 3: El modal carga el documento completo por id**

En `2_correspondencia.py`, reemplazar el bloque de selección (líneas ~943-950):

```python
        if event.selection.rows:
            idx = event.selection.rows[0]
            id_sel = df.iloc[idx]["_id"]
            if st.session_state.get("last_opened_id") != id_sel:
                st.session_state["last_opened_id"] = id_sel
                corr_sel = next((c for c in datos_corr if str(c["_id"]) == id_sel), None)
                if corr_sel:
                    modal_gestion_correspondencia(corr_sel)
```

por:

```python
        if event.selection.rows:
            idx = event.selection.rows[0]
            id_sel = df.iloc[idx]["_id"]
            if st.session_state.get("last_opened_id") != id_sel:
                st.session_state["last_opened_id"] = id_sel
                corr_sel = service.buscar_por_id(id_sel)
                if corr_sel:
                    modal_gestion_correspondencia(corr_sel)
```

- [ ] **Step 4: Confirmar que nadie más depende de `trazabilidad` en el listado**

Run: `grep -rn "listar_correspondencia" app/`
Expected: los consumidores encontrados (páginas y servicios) no leen `trazabilidad` de los elementos devueltos. Si alguno lo hace (revisar `certificacion_service.py` y reportes), cambiarlo a `buscar_por_id` o quitarle la proyección a ese llamado puntual.

- [ ] **Step 5: Verificación funcional**

En la app: abrir Correspondencia, seleccionar una fila → el modal muestra el historial de trazabilidad completo; la tabla sigue mostrando las mismas columnas.

- [ ] **Step 6: Commit**

```bash
git add app/repositories/correspondencia_repo.py app/services/correspondencia_service.py app/pages/2_correspondencia.py
git commit -m "perf: listado sin trazabilidad; el modal carga el documento completo por id"
```

---

### Task 9: Logo e imágenes en base64 con caché (PRIORIDAD 9 — rápida)

**Files:**
- Create: `app/core/recursos.py`
- Modify: `app/main.py:1360-1370` (`pantalla_politica_datos`) y `app/main.py:1860-1870` (sidebar)
- Modify: `app/pages/6_certificaciones.py:302-306` (`_img_b64`)
- Modify: `app/pages/8_adres_secop_klic2.py:145-147`

**Interfaces:**
- Produces: `app.core.recursos.imagen_b64(ruta: str) -> str` — devuelve el contenido base64 del archivo o `""` si no existe. Cacheado para siempre en el proceso (los assets no cambian en runtime).

**Por qué:** El logo del sidebar se relee del disco y se re-codifica a base64 en CADA rerun de CADA página.

- [ ] **Step 1: Crear `app/core/recursos.py`**

```python
"""Assets estaticos codificados en base64, cacheados por proceso."""

import base64
import os

import streamlit as st


@st.cache_data(show_spinner=False)
def imagen_b64(ruta: str) -> str:
    """Contenido base64 de una imagen local, o cadena vacia si no existe."""
    if not os.path.exists(ruta):
        return ""
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
```

- [ ] **Step 2: Usarlo en el sidebar de `main.py`**

Reemplazar (líneas ~1860-1870):

```python
        logo_path = os.path.join("app", "assets", "INVIAS_login_logo.png")
        if os.path.exists(logo_path):
            import base64
            with open(logo_path, "rb") as img_file:
                logo_b64 = base64.b64encode(img_file.read()).decode()
            st.markdown(
```

por:

```python
        from app.core.recursos import imagen_b64
        logo_b64 = imagen_b64(os.path.join("app", "assets", "INVIAS_login_logo.png"))
        if logo_b64:
            st.markdown(
```

(el `st.markdown` interior no cambia).

- [ ] **Step 3: Usarlo en `pantalla_politica_datos` (main.py ~1360)**

Reemplazar:

```python
    logo_path = os.path.join("app", "assets", "INVIAS_login_logo.png")
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_b64 = base64.b64encode(image_file.read()).decode("utf-8")
```

por:

```python
    from app.core.recursos import imagen_b64
    logo_b64 = imagen_b64(os.path.join("app", "assets", "INVIAS_login_logo.png"))
```

y eliminar el `import base64` local de la función si queda sin uso.

- [ ] **Step 4: Usarlo en `6_certificaciones.py` y `8_adres_secop_klic2.py`**

En ambos archivos, reemplazar la función local `_img_b64` (o el bloque equivalente de lectura+encode) por:

```python
from app.core.recursos import imagen_b64
```

y llamar `imagen_b64(path)` donde antes se llamaba `_img_b64(path)` / el bloque local. Eliminar los `import base64` que queden sin uso.

- [ ] **Step 5: Verificar**

Run: `grep -rn "b64encode" app/`
Expected: única coincidencia en `app/core/recursos.py`.

Verificación funcional: el logo se ve en sidebar, pantalla de política y las tarjetas de certificaciones/ADRES.

- [ ] **Step 6: Commit**

```bash
git add app/core/recursos.py app/main.py app/pages/6_certificaciones.py app/pages/8_adres_secop_klic2.py
git commit -m "perf: imagenes base64 cacheadas en app/core/recursos.py"
```

---

### Task 10: Buscador con índice de texto (PRIORIDAD 10 — evaluar antes de aplicar)

**Files:**
- Modify: `app/services/mongo_bootstrap_service.py` (agregar índice de texto junto a los de la Task 1)
- Modify: `app/services/correspondencia_service.py:68-78` (filtro de búsqueda)

**Interfaces:**
- Consumes: índice de texto nuevo `idx_correspondencia_texto`.
- Produces: `listar_correspondencia` sin cambio de firma; la búsqueda usa `$text` con fallback al regex actual.

**Por qué:** El buscador actual (`$or` con 4 regex case-insensitive no anclados) escanea la colección completa DOS veces por tecleo (find + count). `$text` usa índice.

**⚠️ Cambio de comportamiento a validar con el usuario:** `$text` busca por tokens (palabras separadas por espacios/guiones), no por subcadena arbitraria. Buscar `051829` en `2026E-VUVRAZ-051829` funciona (el guion tokeniza), pero buscar `5182` (fragmento interno) solo lo encuentra el fallback regex. El diseño abajo intenta `$text` primero y cae al regex si no hay resultados, así la UX no pierde capacidad — solo cambia qué tan rápido responde cada caso.

- [ ] **Step 1: Agregar el índice de texto en el bootstrap**

En `mongo_bootstrap_service.py`, junto a los índices de la Task 1:

```python
        self.db["correspondencia"].create_index(
            [
                ("numero_radicado", "text"),
                ("peticionario", "text"),
                ("asunto", "text"),
                ("respuesta.numero_oficio", "text"),
            ],
            name="idx_correspondencia_texto",
            default_language="spanish",
        )
```

Run: `python -m app.scripts.init_db` → sin errores. (Mongo permite UN solo índice de texto por colección; si en el futuro se necesita otro campo, se agrega a este mismo índice.)

- [ ] **Step 2: Búsqueda con $text y fallback regex en el servicio**

En `listar_correspondencia`, reemplazar el bloque:

```python
            if "busqueda" in filtros and filtros["busqueda"]:
                busqueda_escapada = re.escape(filtros["busqueda"])
                patron = {"$regex": busqueda_escapada, "$options": "i"}
                # El buscador hace coincidencia parcial (insensible a mayúsculas) sobre:
                # número de radicado, número de oficio de la respuesta, peticionario y asunto.
                query["$or"] = [
                    {"numero_radicado": patron},
                    {"respuesta.numero_oficio": patron},
                    {"peticionario": patron},
                    {"asunto": patron},
                ]


        return self.repo.listar(query, skip, limit), self.repo.contar(query)
```

por:

```python
            if "busqueda" in filtros and filtros["busqueda"]:
                texto = filtros["busqueda"].strip()

                # 1) Intento rápido con índice de texto (busca por tokens)
                query_text = dict(query)
                query_text["$text"] = {"$search": texto}
                total_text = self.repo.contar(query_text)
                if total_text > 0:
                    return (
                        self.repo.listar(query_text, skip, limit, projection={"trazabilidad": 0}),
                        total_text,
                    )

                # 2) Fallback: coincidencia parcial por subcadena (scan, pero
                #    solo cuando el índice de texto no encontró nada)
                patron = {"$regex": re.escape(texto), "$options": "i"}
                query["$or"] = [
                    {"numero_radicado": patron},
                    {"respuesta.numero_oficio": patron},
                    {"peticionario": patron},
                    {"asunto": patron},
                ]

        return (
            self.repo.listar(query, skip, limit, projection={"trazabilidad": 0}),
            self.repo.contar(query),
        )
```

(Nota: si aún no hiciste la Task 8, omite el argumento `projection={"trazabilidad": 0}` en ambos retornos.)

- [ ] **Step 3: Verificar**

Run:
```bash
python -c "
from app.services.correspondencia_service import CorrespondenciaService
svc = CorrespondenciaService()
docs, total = svc.listar_correspondencia(ver_todas=True, limit=5, filtros={'busqueda': 'VUVRAZ'})
print('por token:', total)
docs, total = svc.listar_correspondencia(ver_todas=True, limit=5, filtros={'busqueda': 'zzz-no-existe-zzz'})
print('sin resultados:', total)
"
```
Expected: primer conteo > 0 (si hay radicados VUVRAZ en la BD), segundo = 0, sin excepciones.

- [ ] **Step 4: Verificación funcional**

En la app, probar el buscador con: un radicado completo, un fragmento de número (ej. los últimos 6 dígitos), un nombre de peticionario y una palabra del asunto. Todos deben devolver resultados coherentes.

- [ ] **Step 5: Commit**

```bash
git add app/services/mongo_bootstrap_service.py app/services/correspondencia_service.py
git commit -m "perf: buscador con indice de texto y fallback a regex"
```

---

## Backlog (no incluido en este plan — decidir después)

Estos puntos salieron de la revisión pero son proyectos aparte; no bloquean lo anterior:

1. **Persistencia de sesión ante F5.** Hoy la sesión vive en `st.session_state` y se pierde al refrescar el navegador (por eso existen los botones "🔄 Actualizar"). La colección `sesiones` ya registra sesiones con `id_sesion`; la mejora es emitir una cookie firmada (con `SECRET_KEY`) que contenga el `id_sesion` y restaurar la sesión al arrancar si la cookie es válida y la sesión sigue abierta. Requiere un componente de cookies (Streamlit no permite escribir cookies de forma nativa; evaluar `streamlit-cookies-controller` o similar) y decisiones de seguridad (expiración, revocación al cerrar sesión). Hacerlo como spec propio.
2. **Consolidación del CSS.** ~1.100 líneas inyectadas por rerun, dependientes de selectores internos de Streamlit (`data-testid`, `st-key-*`) que pueden romperse al actualizar la versión. Migrar colores/fuente base a `.streamlit/config.toml` y unificar el resto en un solo archivo leído con `st.cache_data`. Es refactor de mantenibilidad más que de rendimiento.
3. **Retirar el `lru_cache` de `opciones_repo.py`** una vez que todas las páginas consuman `cache_datos.opciones_activas` (Task 2). El `lru_cache` a nivel de proceso nunca expira y puede servir catálogos obsoletos entre workers.
4. **Suite de pruebas.** Cuando se adopte pytest (CLAUDE.md ya define la convención), las funciones reescritas como agregaciones (Tasks 4 y 7) son las primeras candidatas a tests de regresión con una instancia local de Mongo.
