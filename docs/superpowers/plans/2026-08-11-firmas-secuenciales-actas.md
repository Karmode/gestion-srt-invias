# Firmas secuenciales para Actas (Financiera / Abogado / Jefe) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar aprobación secuencial de 3 roles nuevos (Financiera → Abogado → Jefe, o solo Jefe) antes de que "Acta de compromiso", "Balance General CPS" y "Acta de recibo y entrega CPS" queden aprobados y descargables, siguiendo el patrón ya usado para el formato de Correspondencia/GD/SECOP II.

**Architecture:** Se reutiliza el patrón existente de firmantes designados (`opciones_configuracion` + `permisos_extra` + subdocumento `firmas` en `certificaciones`), generalizando los métodos ya existentes en `CertificacionService` y agregando un segundo conjunto de métodos de firma con orden estricto y revocación en cascada. El contratista sigue generando el borrador; los 3 documentos ahora nacen `pendiente` y solo pasan a `aprobado` cuando se completa la secuencia de firmas.

**Tech Stack:** Streamlit, PyMongo, patrones ya presentes en `app/services/certificacion_service.py` y `app/pages_admin/admin_firmantes.py`.

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-08-11-firmas-secuenciales-actas-design.md` — léelo antes de empezar, cada tarea implementa una sección de ese documento.
- **Sin suite de pruebas automatizada** (ver CLAUDE.md — proyecto en etapa MVP). Este plan NO introduce pytest/mongomock. Cada tarea se verifica manualmente ejecutando `streamlit run app/main.py` contra la base de datos configurada en `.env` y siguiendo el recorrido de UI descrito en el paso de verificación de la tarea. No inventes infraestructura de tests nueva.
- Sigue los patrones de capas del proyecto: páginas → services → repositories → MongoDB. No poner lógica de negocio en las páginas Streamlit.
- Usa `app/core/zona_horaria.py` para fechas cuando corresponda; el código ya existente en este módulo usa `datetime.now(timezone.utc)` para timestamps de firma — mantén esa convención (coincide con el patrón de `corr/gd/secop`).
- Los permisos de firma (`certificacion.firmar_*`) **nunca** van en el rol `admin` — se asignan solo vía `permisos_extra` cuando el admin designa al firmante. Este proyecto ya tiene esa regla codificada en `_PERMISOS_SOLO_FIRMANTES` (`app/core/catalogos.py`) — los 3 permisos nuevos deben agregarse también a ese set.
- Commits frecuentes: uno por tarea, con mensaje en español describiendo el cambio (sigue el estilo de los commits recientes del repo: `git log --oneline -10`).

---

### Task 1: Permisos nuevos y esquema de datos

**Files:**
- Modify: `app/core/catalogos.py:38-64`
- Modify: `app/core/esquemas.py:311-350`

**Interfaces:**
- Produces: permisos `certificacion.firmar_financiera`, `certificacion.firmar_abogado`, `certificacion.firmar_jefe` (usados por todas las tareas siguientes). Esquema `ESQUEMA_CERTIFICACIONES.firmas` con claves `financiera`/`abogado`/`jefe` y campo nuevo `eventos` a nivel de documento (usados por Task 4 en adelante).

- [ ] **Step 1: Agregar los 3 permisos nuevos a `PERMISOS_BASE`**

En `app/core/catalogos.py`, dentro de la lista `PERMISOS_BASE` (líneas 38-58), agrega estas 3 líneas justo después de `certificacion.firmar_secop` y antes de `certificacion.gestionar_firmantes`:

```python
    {"clave": "certificacion.firmar_financiera", "descripcion": "Firmar aprobación Financiera (actas)", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_abogado", "descripcion": "Firmar aprobación Jurídica (actas)", "modulo": "certificaciones"},
    {"clave": "certificacion.firmar_jefe", "descripcion": "Firmar aprobación del Jefe (actas)", "modulo": "certificaciones"},
```

- [ ] **Step 2: Excluirlos del rol admin**

En el mismo archivo, `_PERMISOS_SOLO_FIRMANTES` (líneas 60-64) debe quedar así:

```python
_PERMISOS_SOLO_FIRMANTES = {
    "certificacion.firmar_corr",
    "certificacion.firmar_gd",
    "certificacion.firmar_secop",
    "certificacion.firmar_financiera",
    "certificacion.firmar_abogado",
    "certificacion.firmar_jefe",
}
```

(`ROLES_BASE["admin"]["permisos"]` ya se calcula excluyendo este set, no requiere cambios.)

- [ ] **Step 3: Ampliar el esquema `ESQUEMA_CERTIFICACIONES`**

En `app/core/esquemas.py`, dentro de `ESQUEMA_CERTIFICACIONES["properties"]["firmas"]["properties"]` (líneas 314-345), agrega 3 propiedades nuevas después de `"secop"` y antes del cierre `},`:

```python
                "financiera": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "abogado": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
                "jefe": {
                    "bsonType": "object",
                    "required": ["firmante_id", "firmante_nombre", "fecha"],
                    "properties": {
                        "firmante_id":     {"bsonType": "objectId"},
                        "firmante_nombre": {"bsonType": "string"},
                        "fecha":           {"bsonType": "date"},
                        "comentario":      {"bsonType": ["string", "null"]},
                    },
                },
```

También actualiza la `"description"` de `"firmas"` (línea 313) a:

```python
            "description": "Aprobaciones de firmantes designados: corr/gd/secop (correspondencia) o financiera/abogado/jefe (actas)",
```

Y agrega un campo nuevo `"eventos"` en `ESQUEMA_CERTIFICACIONES["properties"]`, justo antes de `"hash_verificacion"` (línea 347):

```python
        "eventos": {
            "bsonType": ["array", "null"],
            "description": "Bitácora de eventos del documento (ej. revocaciones en cascada de firmas de actas)",
            "items": {
                "bsonType": "object",
                "properties": {
                    "tipo":         {"bsonType": "string"},
                    "rol_revocado": {"bsonType": "string"},
                    "causada_por":  {"bsonType": "string"},
                    "fecha":        {"bsonType": "date"},
                },
            },
        },
```

- [ ] **Step 4: Verificación manual**

Ejecuta:

```bash
python -m app.scripts.init_db
```

Debe imprimir `Validador de 'certificaciones' actualizado.` sin errores (el script hace `collMod` sobre la colección existente, así que aplica el esquema nuevo sin perder datos — ver `app/services/mongo_bootstrap_service.py:149-155`). Abre `mongosh` (o Compass) contra la base configurada en `.env` y confirma que la colección `permisos` tiene ahora `certificacion.firmar_financiera`, `certificacion.firmar_abogado` y `certificacion.firmar_jefe`:

```
db.permisos.find({clave: {$regex: "^certificacion.firmar_"}}, {clave: 1})
```

Debe listar 6 claves (las 3 antiguas + las 3 nuevas).

- [ ] **Step 5: Commit**

```bash
git add app/core/catalogos.py app/core/esquemas.py
git commit -m "feat(certificaciones): agrega permisos y esquema para firmas de actas (financiera/abogado/jefe)"
```

---

### Task 2: Repositorio — métodos de firma para actas

**Files:**
- Modify: `app/repositories/certificacion_repo.py`

**Interfaces:**
- Consumes: nada nuevo (usa `self.coleccion`, `ObjectId`, `datetime`, ya importados en el archivo).
- Produces: `registrar_firma_actas(usuario_id, año, mes, tipo_formato, rol, firmante_id, firmante_nombre, comentario=None) -> None`, `revocar_firmas_actas(usuario_id, año, mes, tipo_formato, roles: list) -> None`, `agregar_evento_actas(usuario_id, año, mes, tipo_formato, evento: dict) -> None`. Usados por Task 4.

- [ ] **Step 1: Agregar los 3 métodos nuevos**

En `app/repositories/certificacion_repo.py`, agrega estos métodos al final de la clase `CertificacionRepositorio` (después de `revocar_firma`, línea 104):

```python
    def registrar_firma_actas(
        self,
        usuario_id: str,
        año: int,
        mes: int,
        tipo_formato: str,
        rol: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> None:
        """Guarda la firma de un rol (financiera/abogado/jefe) sobre el documento
        exacto (usuario_id, año, mes, tipo_formato) que ya debe existir."""
        ahora = datetime.now(timezone.utc)
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {
                "$set": {
                    f"firmas.{rol}": {
                        "firmante_id": ObjectId(firmante_id),
                        "firmante_nombre": firmante_nombre,
                        "fecha": ahora,
                        "comentario": comentario.strip() if comentario and comentario.strip() else None,
                    }
                }
            },
        )

    def revocar_firmas_actas(
        self, usuario_id: str, año: int, mes: int, tipo_formato: str, roles: list
    ) -> None:
        """Borra las firmas de los roles indicados (el revocado + los posteriores en cascada)."""
        if not roles:
            return
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {"$unset": {f"firmas.{r}": "" for r in roles}},
        )

    def agregar_evento_actas(
        self, usuario_id: str, año: int, mes: int, tipo_formato: str, evento: dict
    ) -> None:
        """Agrega una entrada a la bitácora `eventos` del documento (ej. revocación en cascada)."""
        self.coleccion.update_one(
            {
                "usuario_id": ObjectId(usuario_id),
                "año": año,
                "mes": mes,
                "tipo_formato": tipo_formato,
            },
            {"$push": {"eventos": evento}},
        )
```

- [ ] **Step 2: Verificación manual**

No hay UI todavía conectada a estos métodos (eso llega en Task 4-6). Verifica solo que el archivo importa correctamente:

```bash
python -c "from app.repositories.certificacion_repo import CertificacionRepositorio; print('OK')"
```

Debe imprimir `OK` sin errores de sintaxis ni de import.

- [ ] **Step 3: Commit**

```bash
git add app/repositories/certificacion_repo.py
git commit -m "feat(certificaciones): metodos de repositorio para firmas secuenciales de actas"
```

---

### Task 3: Servicio — constantes, generalizar config de firmantes y creación en estado "pendiente"

**Files:**
- Modify: `app/services/certificacion_service.py:26-31` (constantes), `:393-437` (`obtener_firmantes_config`/`guardar_firmante`), `:227-334` (los 3 métodos `firmar_y_generar_*` de actas)

**Interfaces:**
- Consumes: `CertificacionRepositorio` (ya inyectado como `self.repo`), `ConfiguracionRepositorio` (import local ya presente en el archivo).
- Produces: constantes de módulo `TIPOS_FIRMA_CORR`, `TIPOS_FIRMA_ACTAS`, `ORDEN_FIRMAS_ACTAS` (usadas por Task 4, 5, 6, 7). `obtener_firmantes_config(categoria=..., tipos=...)` y `guardar_firmante(tipo, usuario_id, nombre, categoria=...)` con nuevo parámetro `categoria` (default = comportamiento actual, no rompe llamadas existentes).

- [ ] **Step 1: Agregar constantes de módulo**

En `app/services/certificacion_service.py`, justo después de `DIA_INICIO_PERIODO = 29` (línea 31), agrega:

```python

# ── Firmas secuenciales de Actas (Financiera → Abogado → Jefe) ────────────────
TIPOS_FIRMA_CORR = ("corr", "gd", "secop")
TIPOS_FIRMA_ACTAS = ("financiera", "abogado", "jefe")

ORDEN_FIRMAS_ACTAS = {
    "acta_compromiso": ("jefe",),
    "acta_recibo_entrega_cps": ("financiera", "abogado", "jefe"),        # Balance General CPS
    "acta_recibo_entrega_cps_real": ("financiera", "abogado", "jefe"),   # Acta recibo y entrega CPS
}
```

- [ ] **Step 2: Generalizar `obtener_firmantes_config` y `guardar_firmante`**

Reemplaza el método `obtener_firmantes_config` (líneas 393-398):

```python
    def obtener_firmantes_config(
        self, categoria: str = "firmantes_certificacion", tipos: tuple = TIPOS_FIRMA_CORR
    ) -> Dict:
        """Devuelve los firmantes designados de la categoría dada (por defecto, corr/gd/secop)."""
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        doc = ConfiguracionRepositorio().obtener(categoria)
        vacio = {t: None for t in tipos}
        return doc.get("firmantes", vacio) if doc else vacio
```

Reemplaza la firma de `guardar_firmante` (línea 400) para aceptar `categoria`, y el cuerpo para usarla en `obtener_firmantes_config` y en el `upsert` final (líneas 400-437):

```python
    def guardar_firmante(
        self,
        tipo: str,
        usuario_id: Optional[str],
        nombre: Optional[str],
        categoria: str = "firmantes_certificacion",
    ) -> bool:
        """Admin designa quién es el firmante de un tipo dado, dentro de la categoría indicada.
        Sincroniza el permiso certificacion.firmar_<tipo> en permisos_extra del usuario.
        """
        from app.repositories.opciones_repo import ConfiguracionRepositorio
        from app.repositories.usuario_repo import UsuarioRepositorio

        perm = f"certificacion.firmar_{tipo}"
        config = self.obtener_firmantes_config(categoria)
        repo_conf = ConfiguracionRepositorio()
        repo_usr = UsuarioRepositorio()

        old = config.get(tipo) or {}
        old_uid = str(old.get("usuario_id", "")) if old and old.get("usuario_id") else None

        # Remover permiso del firmante anterior si cambia
        if old_uid and old_uid != usuario_id:
            old_user = repo_usr.buscar_por_id(old_uid)
            if old_user:
                permisos_limpios = [p for p in old_user.get("permisos_extra", []) if p != perm]
                repo_usr.actualizar(old_uid, {"permisos_extra": permisos_limpios})

        # Asignar permiso al nuevo firmante
        if usuario_id:
            new_user = repo_usr.buscar_por_id(usuario_id)
            if new_user:
                permisos_new = list(set(new_user.get("permisos_extra", []) + [perm]))
                repo_usr.actualizar(usuario_id, {"permisos_extra": permisos_new})

        valor = {"usuario_id": usuario_id, "nombre": nombre} if usuario_id else None
        repo_conf.upsert(
            categoria,
            {
                "categoria": categoria,
                f"firmantes.{tipo}": valor,
            },
        )
        return True
```

(El comportamiento para `corr`/`gd`/`secop` no cambia: ambos parámetros nuevos tienen default igual al valor que se usaba antes.)

- [ ] **Step 3: Crear el documento de actas en estado "pendiente" en vez de "aprobado"**

Reemplaza `firmar_y_generar_acta_compromiso` (líneas 227-258):

```python
    def firmar_y_generar_acta_compromiso(self, usuario_id: str, nombre_usuario: str) -> bool:
        año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_compromiso")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando el Jefe firma (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_compromiso",
            "hash_verificacion": None,
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True
```

Reemplaza `firmar_y_generar_acta_recibo_entrega` (líneas 260-296, Balance General CPS):

```python
    def firmar_y_generar_acta_recibo_entrega(self, usuario_id: str, nombre_usuario: str) -> bool:
        from app.services.usuario_service import UsuarioService
        req_bg = UsuarioService().validar_datos_balance_general_cps(usuario_id)
        if not req_bg["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Balance General CPS: {', '.join(req_bg['faltantes'])}")

        año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_recibo_entrega_cps")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando Financiera → Abogado → Jefe firman (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_recibo_entrega_cps",
            "hash_verificacion": None,
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True
```

Reemplaza `firmar_y_generar_acta_recibo_entrega_cps_real` (líneas 298-334, Acta de recibo y entrega CPS):

```python
    def firmar_y_generar_acta_recibo_entrega_cps_real(self, usuario_id: str, nombre_usuario: str) -> bool:
        from app.services.usuario_service import UsuarioService
        req_acta = UsuarioService().validar_datos_acta_recibo_entrega_cps(usuario_id)
        if not req_acta["valido"]:
            raise ValueError(f"Faltan requisitos para generar el Acta de Recibo y Entrega CPS: {', '.join(req_acta['faltantes'])}")

        año, mes = self.periodo_certificable()
        cert_existente = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, "acta_recibo_entrega_cps_real")
        if cert_existente:
            return True

        ahora_utc = datetime.now(timezone.utc)
        campos = {
            "usuario_id": ObjectId(usuario_id),
            "nombre_usuario": nombre_usuario,
            "año": año,
            "mes": mes,
            "estado": "pendiente",  # Se aprueba cuando Financiera → Abogado → Jefe firman (ver registrar_firma_actas)
            "fecha_corte": ahora_utc,
            "snapshot_al_dia": True,
            "tipo_formato": "acta_recibo_entrega_cps_real",
            "hash_verificacion": None,
            "creado_en": ahora_utc,
        }
        self.repo.crear(campos)
        return True
```

- [ ] **Step 4: Verificación manual**

```bash
python -c "from app.services.certificacion_service import CertificacionService, ORDEN_FIRMAS_ACTAS, TIPOS_FIRMA_ACTAS; print(ORDEN_FIRMAS_ACTAS); print(TIPOS_FIRMA_ACTAS)"
```

Debe imprimir el diccionario y la tupla sin errores.

Levanta la app (`streamlit run app/main.py`), entra como un contratista de prueba a **Formatos de contrato → Últimos formatos de contrato → 1- Form. Acta compromiso**, y haz clic en "✍️ Firmar y Generar Formato". Debe desaparecer el formulario (ya existe un documento), pero **todavía no debe verse el botón de descarga** — como aún no actualizamos esa vista (eso es la Task 5), verás el mensaje de éxito viejo por ahora; solo confirma en `mongosh` que el documento quedó así:

```
db.certificaciones.find({tipo_formato: "acta_compromiso"}, {estado:1, hash_verificacion:1, firmas:1}).sort({creado_en:-1}).limit(1)
```

Debe mostrar `estado: "pendiente"`, `hash_verificacion: null`, sin campo `firmas` (o `firmas` ausente).

- [ ] **Step 5: Commit**

```bash
git add app/services/certificacion_service.py
git commit -m "feat(certificaciones): actas nacen pendientes y config de firmantes admite categoria generica"
```

---

### Task 4: Servicio — registrar y revocar firmas de actas (orden estricto + cascada)

**Files:**
- Modify: `app/services/certificacion_service.py` (agregar métodos nuevos a la clase `CertificacionService`, después de `revocar_firma`, alrededor de la línea 493)

**Interfaces:**
- Consumes: `ORDEN_FIRMAS_ACTAS`, `self.repo.registrar_firma_actas/revocar_firmas_actas/agregar_evento_actas` (Task 2), `self.repo.buscar_por_usuario_periodo`, `self._generar_hash` (ya existen).
- Produces: `registrar_firma_actas(usuario_id, tipo_formato, rol, firmante_id, firmante_nombre, comentario=None) -> bool`, `revocar_firma_actas(usuario_id, tipo_formato, rol) -> bool`. Usados por Task 6 (UI de firmantes).

- [ ] **Step 1: Agregar los 2 métodos**

Agrega estos métodos a la clase `CertificacionService`, justo después de `revocar_firma` (línea 493):

```python
    def registrar_firma_actas(
        self,
        usuario_id: str,
        tipo_formato: str,
        rol: str,
        firmante_id: str,
        firmante_nombre: str,
        comentario: str | None = None,
    ) -> bool:
        """Registra la aprobación de un rol (financiera/abogado/jefe) sobre un formato
        de actas. Exige que el rol anterior en ORDEN_FIRMAS_ACTAS ya haya firmado. Si con
        esta firma se completa el orden requerido, aprueba el documento y genera (o
        preserva) su hash de verificación."""
        orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato)
        if not orden or rol not in orden:
            raise ValueError(f"El rol '{rol}' no aplica para el formato '{tipo_formato}'.")

        año, mes = self.periodo_certificable()
        cert = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)
        if not cert:
            raise ValueError("No existe un formato generado para este período.")

        idx = orden.index(rol)
        if idx > 0:
            rol_anterior = orden[idx - 1]
            if not (cert.get("firmas") or {}).get(rol_anterior):
                raise ValueError(
                    f"Aún falta la firma de '{rol_anterior}' antes de poder firmar como '{rol}'."
                )

        self.repo.registrar_firma_actas(
            usuario_id, año, mes, tipo_formato, rol, firmante_id, firmante_nombre, comentario
        )

        cert_actualizado = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)
        firmas = cert_actualizado.get("firmas") or {}
        if all(firmas.get(r) for r in orden):
            ahora_utc = datetime.now(timezone.utc)
            hash_code = cert_actualizado.get("hash_verificacion") or self._generar_hash(
                usuario_id, año, mes, firmante_id, ahora_utc.isoformat()
            )
            self.repo.actualizar(str(cert_actualizado["_id"]), {
                "estado": "aprobado",
                "hash_verificacion": hash_code,
            })
        return True

    def revocar_firma_actas(self, usuario_id: str, tipo_formato: str, rol: str) -> bool:
        """Revoca la firma de un rol y, en cascada, las de los roles posteriores en el
        orden (que dependían de esta). Registra un evento por cada firma revocada en
        cascada para que el firmante afectado sepa por qué desapareció, y vuelve el
        documento a 'pendiente' si estaba aprobado."""
        orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato)
        if not orden or rol not in orden:
            raise ValueError(f"El rol '{rol}' no aplica para el formato '{tipo_formato}'.")

        año, mes = self.periodo_certificable()
        cert = self.repo.buscar_por_usuario_periodo(usuario_id, año, mes, tipo_formato)
        if not cert:
            return False

        idx = orden.index(rol)
        firmas = cert.get("firmas") or {}
        posteriores_firmados = [r for r in orden[idx + 1:] if firmas.get(r)]
        roles_a_borrar = [rol] + posteriores_firmados

        self.repo.revocar_firmas_actas(usuario_id, año, mes, tipo_formato, roles_a_borrar)

        ahora_utc = datetime.now(timezone.utc)
        for r in posteriores_firmados:
            self.repo.agregar_evento_actas(usuario_id, año, mes, tipo_formato, {
                "tipo": "revocacion_cascada",
                "rol_revocado": r,
                "causada_por": rol,
                "fecha": ahora_utc,
            })

        if cert.get("estado") == "aprobado":
            self.repo.actualizar(str(cert["_id"]), {"estado": "pendiente"})

        return True
```

- [ ] **Step 2: Verificación manual**

Con la app corriendo, usa una consola Python en el entorno del proyecto (con `.env` cargado) para simular el flujo sin UI todavía (la UI llega en Task 6):

```bash
python -c "
from app.services.certificacion_service import CertificacionService
s = CertificacionService()
uid = '<pega aqui un ObjectId de usuario de prueba, como string>'
# 1) intentar firmar 'abogado' antes que 'financiera' debe fallar
try:
    s.registrar_firma_actas(uid, 'acta_recibo_entrega_cps', 'abogado', uid, 'Prueba')
    print('ERROR: no debio permitir firmar fuera de orden')
except ValueError as e:
    print('OK, rechazado como se esperaba:', e)
"
```

Debe imprimir la rama "OK, rechazado como se esperaba". (Usa el `usuario_id` de un contratista que ya haya generado el Balance General CPS en la Task 3; si no tienes uno a mano, genera uno primero desde la UI.)

- [ ] **Step 3: Commit**

```bash
git add app/services/certificacion_service.py
git commit -m "feat(certificaciones): registrar_firma_actas y revocar_firma_actas con orden estricto y cascada"
```

---

### Task 5: Vista del contratista — mostrar avance de firmas (página 6)

**Files:**
- Modify: `app/pages/6_certificaciones.py`

**Interfaces:**
- Consumes: `ORDEN_FIRMAS_ACTAS` (Task 3), `cert_actual["firmas"]`, `cert_actual["eventos"]`.
- Produces: helper `_mostrar_avance_actas(tipo_formato, cert_actual)` usado dentro de las 3 opciones.

- [ ] **Step 1: Importar `ORDEN_FIRMAS_ACTAS` y agregar el helper de avance**

Cambia el import existente (línea 20):

```python
from app.services.certificacion_service import CertificacionService, MESES_ES
```

por:

```python
from app.services.certificacion_service import CertificacionService, MESES_ES, ORDEN_FIRMAS_ACTAS
```

Agrega, justo después de la definición de `_PREFIJO_ARCHIVO_DEFAULT` (línea 41) y antes de `_nombre_archivo_pdf`:

```python
_LABEL_ROL_ACTAS = {
    "financiera": "Financiera",
    "abogado": "Jurídico",
    "jefe": "Jefe inmediato",
}


def _mostrar_avance_actas(tipo_formato: str, cert_actual: dict) -> None:
    """Stepper de avance de firmas para los formatos de actas (financiera/abogado/jefe)."""
    firmas = (cert_actual or {}).get("firmas", {}) or {}
    orden = ORDEN_FIRMAS_ACTAS.get(tipo_formato, ())
    pasos = [
        f"✅ {_LABEL_ROL_ACTAS[rol]}" if firmas.get(rol) else f"⏳ {_LABEL_ROL_ACTAS[rol]}"
        for rol in orden
    ]
    st.markdown(" &nbsp;→&nbsp; ".join(pasos))

    eventos = (cert_actual or {}).get("eventos") or []
    if eventos:
        ultimo = eventos[-1]
        rol_afectado = ultimo.get("rol_revocado")
        if rol_afectado and not firmas.get(rol_afectado):
            causante = _LABEL_ROL_ACTAS.get(ultimo.get("causada_por"), ultimo.get("causada_por"))
            st.caption(
                f"⚠️ La firma de **{_LABEL_ROL_ACTAS.get(rol_afectado, rol_afectado)}** fue removida "
                f"porque **{causante}** revocó la suya."
            )
```

- [ ] **Step 2: Usar el helper en la opción 5 (Acta de compromiso)**

En `_render_opcion_5_acta_compromiso`, reemplaza el bloque `if cert_actual:` (que empieza con `st.success(...)`) por:

```python
    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Acta de compromiso** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Acta de compromiso** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_compromiso", cert_actual)
```

(El `else:` que sigue, con el formulario y el botón "✍️ Firmar y Generar Formato", **no cambia** — solo el `if`/nuevo `elif` de arriba reemplaza al `if cert_actual:` original.)

- [ ] **Step 3: Mismo patrón en la opción 8 (Balance General CPS)**

En `_render_opcion_8_acta_recibo_entrega`, reemplaza el bloque `if cert_actual:` (el que arma el `st.success` de "Balance General CPS") por el mismo patrón, con estas 2 diferencias: el texto menciona "Balance General CPS" (ya está en el `st.success` existente, mantenlo igual) y el `elif` llama a `_mostrar_avance_actas("acta_recibo_entrega_cps", cert_actual)`:

```python
    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Balance General CPS** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Balance General CPS** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_recibo_entrega_cps", cert_actual)
```

- [ ] **Step 4: Mismo patrón en la opción 9 (Acta de recibo y entrega CPS)**

En `_render_opcion_9_acta_recibo_entrega_real`, reemplaza el bloque `if cert_actual:` (el que arma el `st.success` de "Acta de recibo y entrega CPS") por:

```python
    if cert_actual and cert_actual.get("estado") == "aprobado":
        st.success(
            f"Tu formato de **Acta de recibo y entrega CPS** para **{nombre_mes_cert} {año_cert}** "
            f"ha sido generado y firmado digitalmente."
        )

        try:
            pdf_bytes = servicio.generar_pdf(cert_actual)
        except Exception as e:
            st.error(f"No se pudo generar el PDF del formato: {e}")
            pdf_bytes = None

        if pdf_bytes:
            nombre_archivo = _nombre_archivo_pdf(cert_actual, nombre_mes_cert, año_cert)
            c_dl, c_prev = st.columns(2)
            with c_dl:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=nombre_archivo,
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with c_prev:
                if st.button("👁️ Ver formato", use_container_width=True):
                    st.session_state["_preview_cert_user"] = {
                        "cert": cert_actual,
                        "mes_nombre": nombre_mes_cert,
                        "año": año_cert,
                    }
                    st.rerun()
    elif cert_actual:
        st.info(
            f"Tu formato de **Acta de recibo y entrega CPS** para **{nombre_mes_cert} {año_cert}** "
            "fue generado y está en espera de aprobación."
        )
        _mostrar_avance_actas("acta_recibo_entrega_cps_real", cert_actual)
```

(El `else:` que sigue, con la validación de requisitos específicos y el formulario, **no cambia**.)

- [ ] **Step 5: Verificación manual**

Levanta la app, entra como el mismo contratista de prueba de la Task 3 (que ya tiene el Acta de compromiso en `pendiente`) a **Formatos de contrato → Últimos formatos de contrato → 1- Form. Acta compromiso**. Debes ver un `st.info` de "en espera de aprobación" y el stepper `⏳ Jefe inmediato` — **no** debe verse ningún botón de descarga. Repite generando el Balance General CPS y el Acta de recibo y entrega CPS (botones 2 y 3 del mismo contenedor) y confirma que cada uno muestra su propio stepper (`⏳ Financiera → ⏳ Jurídico → ⏳ Jefe inmediato`).

- [ ] **Step 6: Commit**

```bash
git add app/pages/6_certificaciones.py
git commit -m "feat(certificaciones): mostrar avance de firmas de actas al contratista mientras esta pendiente"
```

---

### Task 6: Vista de firmantes — activar y reordenar botones en "Sup. Formatos"

**Files:**
- Modify: `app/pages_admin/admin_firmantes.py`

**Interfaces:**
- Consumes: `ORDEN_FIRMAS_ACTAS` (Task 3), `servicio.registrar_firma_actas`/`servicio.revocar_firma_actas` (Task 4), `servicio.obtener_empleados_para_certificar(tipo_formato=...)` (ya existe, sin cambios — devuelve `{"usuario_id","nombre","certificacion","firmas",...}` por colaborador).
- Produces: nada consumido por otras tareas — es la última pieza de UI de acción.

- [ ] **Step 1: Importar `ORDEN_FIRMAS_ACTAS`**

Cambia el import existente (línea 14):

```python
from app.services.certificacion_service import CertificacionService, MESES_ES
```

por:

```python
from app.services.certificacion_service import CertificacionService, MESES_ES, ORDEN_FIRMAS_ACTAS
```

- [ ] **Step 2: Agregar metadatos y helpers de actas**

Agrega, después de `MAPA_TIPOS_CONTRATO` (línea 30) y antes de la sección `# ── Helpers de badges ──`:

```python
_LABEL_FORMATO_ACTAS = {
    "acta_compromiso": "Acta de compromiso",
    "acta_recibo_entrega_cps": "Balance General CPS",
    "acta_recibo_entrega_cps_real": "Acta de recibo y entrega CPS",
}

_META_FIRMA_ACTAS = {
    "financiera": ("F. Financiera", "Financiera",    "certificacion.firmar_financiera"),
    "abogado":    ("F. Jurídica",   "Jurídico",       "certificacion.firmar_abogado"),
    "jefe":       ("F. Jefe",       "Jefe inmediato", "certificacion.firmar_jefe"),
}
```

- [ ] **Step 3: Agregar el badge y el diálogo de confirmación de actas**

Agrega, después de `_badge_corr` (línea 64) y antes de la sección `# ── Diálogo de confirmación de firma (aplica a los 3 tipos) ──`:

```python
def _badge_firma_actas(rol: str, firma: dict | None) -> str:
    label = _META_FIRMA_ACTAS[rol][0]
    if firma:
        bg, fg, bd = "#1b4721", "#75db8b", "#2d7a3e"
        icono = "✅"
    else:
        bg, fg, bd = "#2c2c2c", "#aaaaaa", "#444"
        icono = "⏳"
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {bd};'
        f'border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">'
        f"{icono} {label}</span>"
    )


def _cerrar_dialogo_confirmar_firma_actas() -> None:
    st.session_state.pop("_confirmar_firma_actas", None)


@st.dialog("Confirmar aprobación", width="small", on_dismiss=_cerrar_dialogo_confirmar_firma_actas)
def _dialog_confirmar_firma_actas(servicio: CertificacionService, sesion: dict) -> None:
    pend = st.session_state.get("_confirmar_firma_actas")
    if not pend:
        return

    uid = pend["uid"]
    nombre = pend["nombre"]
    tipo_formato = pend["tipo_formato"]
    rol = pend["rol"]
    _, label_largo, _ = _META_FIRMA_ACTAS[rol]

    st.markdown(f"**Firma:** {label_largo}")
    st.markdown(f"**Formato:** {_LABEL_FORMATO_ACTAS[tipo_formato]}")
    st.markdown(f"**Contratista:** {nombre}")
    st.divider()

    comentario = st.text_area(
        "Comentario (opcional)",
        placeholder="Ej: se aprueba con observaciones...",
        key=f"txt_comentario_actas_{uid}_{tipo_formato}_{rol}",
    )

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirmar aprobación", type="primary", use_container_width=True, key="btn_confirmar_actas"):
            firmante_nombre = sesion.get("nombre_completo") or sesion["usuario"]
            try:
                servicio.registrar_firma_actas(uid, tipo_formato, rol, sesion["id"], firmante_nombre, comentario)
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state.pop("_confirmar_firma_actas", None)
                st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True, key="btn_cancelar_actas"):
            st.session_state.pop("_confirmar_firma_actas", None)
            st.rerun()
```

- [ ] **Step 4: Agregar el panel de firmantes de actas**

Agrega, justo antes de `# ── Render principal ──` (línea 135):

```python
def _render_panel_actas(servicio: CertificacionService, sesion: dict, tipo_formato: str) -> None:
    permisos = sesion.get("permisos", [])
    roles_sesion = sesion.get("roles", [])
    es_admin = any(r in {"admin", "administrador"} for r in roles_sesion)

    orden = ORDEN_FIRMAS_ACTAS[tipo_formato]
    mis_roles = [r for r in orden if _META_FIRMA_ACTAS[r][2] in permisos]

    if not es_admin and not mis_roles:
        st.warning("No tienes permiso de firma para este formato.")
        return

    st.subheader(_LABEL_FORMATO_ACTAS[tipo_formato])

    if len(mis_roles) > 1:
        opciones_rol = {r: _META_FIRMA_ACTAS[r][1] for r in mis_roles}
        rol_activo = st.radio(
            "Estás actuando como firmante de:",
            options=list(opciones_rol.keys()),
            format_func=lambda r: f"✍️ {opciones_rol[r]}",
            horizontal=True,
            key=f"sel_rol_actas_{tipo_formato}",
        )
    elif mis_roles:
        rol_activo = mis_roles[0]
    else:
        rol_activo = None

    if es_admin and rol_activo is None:
        st.info("🛡️ **Administrador** — Vista de solo lectura.")
    elif rol_activo:
        _, label_largo, _ = _META_FIRMA_ACTAS[rol_activo]
        st.info(f"✍️ **Actuando como:** Firma {label_largo}")

    st.divider()

    with st.spinner("Consultando colaboradores…"):
        empleados = servicio.obtener_empleados_para_certificar(tipo_formato=tipo_formato)
    empleados = [e for e in empleados if e.get("certificacion")]

    if not empleados:
        st.info("Ningún colaborador ha generado este formato todavía.")
        return

    for emp in empleados:
        uid = emp["usuario_id"]
        nombre = emp["nombre"]
        cert = emp.get("certificacion") or {}
        firmas = emp.get("firmas", {})
        eventos = cert.get("eventos") or []

        with st.container(border=True):
            c_nom, c_badges, c_accion = st.columns([3, 5, 2])

            with c_nom:
                st.markdown(f"**{nombre}**")
                st.caption("✅ Formato aprobado" if cert.get("estado") == "aprobado" else "⏳ Pendiente de firmas")

            with c_badges:
                badges = "&nbsp;".join(_badge_firma_actas(r, firmas.get(r)) for r in orden)
                st.markdown(badges, unsafe_allow_html=True)

                eventos_rol_activo = [
                    ev for ev in eventos
                    if ev.get("tipo") == "revocacion_cascada" and ev.get("rol_revocado") == rol_activo
                ]
                if rol_activo and eventos_rol_activo and not firmas.get(rol_activo):
                    ultimo = eventos_rol_activo[-1]
                    st.caption(f"⚠️ Tu aprobación fue removida porque **{ultimo.get('causada_por')}** revocó la suya.")

            with c_accion:
                if not rol_activo:
                    continue
                idx = orden.index(rol_activo)
                rol_anterior = orden[idx - 1] if idx > 0 else None
                puede_firmar = rol_anterior is None or bool(firmas.get(rol_anterior))
                ya_firmado = bool(firmas.get(rol_activo))

                if ya_firmado:
                    if st.button("↩ Revocar", key=f"revocar_actas_{tipo_formato}_{uid}", use_container_width=True):
                        servicio.revocar_firma_actas(uid, tipo_formato, rol_activo)
                        st.rerun()
                elif not puede_firmar:
                    st.button(
                        "✅ Aprobar",
                        key=f"aprobar_actas_{tipo_formato}_{uid}",
                        use_container_width=True,
                        disabled=True,
                        help=f"Esperando firma de {_META_FIRMA_ACTAS[rol_anterior][1]}",
                    )
                else:
                    if st.button(
                        "✅ Aprobar",
                        key=f"aprobar_actas_{tipo_formato}_{uid}",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state["_confirmar_firma_actas"] = {
                            "uid": uid,
                            "nombre": nombre,
                            "tipo_formato": tipo_formato,
                            "rol": rol_activo,
                        }
                        st.rerun()
```

- [ ] **Step 5: Reemplazar los botones deshabilitados y conectar el panel**

En `render()`, reemplaza el bloque de inicialización de estado (línea 191-192):

```python
    if "ver_formato_control" not in st.session_state:
        st.session_state["ver_formato_control"] = False
```

por:

```python
    if "ver_formato_control" not in st.session_state:
        st.session_state["ver_formato_control"] = False
    if "tab_actas_activo" not in st.session_state:
        st.session_state["tab_actas_activo"] = None
```

Reemplaza el bloque de 4 botones (líneas 196-206):

```python
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("1-Formato de control Corr-GP-SECOP", type="primary", use_container_width=True, key="btn_formato_control"):
            st.session_state["ver_formato_control"] = not st.session_state["ver_formato_control"]
            st.rerun()
    with col2:
        st.button("2- Formato de acta de recibo y entrega CPS", disabled=True, use_container_width=True, key="btn_acta_recibo")
    with col3:
        st.button("3- Balance General CPS", disabled=True, use_container_width=True, key="btn_balance_general")
    with col4:
        st.button("4- Gestion Actas compromiso", disabled=True, use_container_width=True, key="btn_gestion_actas_compromiso")
```

por:

```python
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("1-Formato de control Corr-GD-SECOP", type="primary", use_container_width=True, key="btn_formato_control"):
            st.session_state["ver_formato_control"] = not st.session_state["ver_formato_control"]
            st.session_state["tab_actas_activo"] = None
            st.rerun()
    with col2:
        if st.button("2- Acta de compromiso", use_container_width=True, key="btn_acta_compromiso_sup"):
            activo = st.session_state["tab_actas_activo"] == "acta_compromiso"
            st.session_state["tab_actas_activo"] = None if activo else "acta_compromiso"
            st.session_state["ver_formato_control"] = False
            st.rerun()
    with col3:
        if st.button("3- Balance General CPS", use_container_width=True, key="btn_balance_general_sup"):
            activo = st.session_state["tab_actas_activo"] == "acta_recibo_entrega_cps"
            st.session_state["tab_actas_activo"] = None if activo else "acta_recibo_entrega_cps"
            st.session_state["ver_formato_control"] = False
            st.rerun()
    with col4:
        if st.button("4- Acta de recibo y entrega CPS", use_container_width=True, key="btn_acta_recibo_sup"):
            activo = st.session_state["tab_actas_activo"] == "acta_recibo_entrega_cps_real"
            st.session_state["tab_actas_activo"] = None if activo else "acta_recibo_entrega_cps_real"
            st.session_state["ver_formato_control"] = False
            st.rerun()
```

Finalmente, al final de `render()` (justo antes de la línea `if st.session_state.get("_confirmar_firma"):`, línea 436), agrega:

```python
    tab_actas = st.session_state.get("tab_actas_activo")
    if tab_actas:
        _render_panel_actas(servicio, sesion, tab_actas)

    if st.session_state.get("_confirmar_firma_actas"):
        _dialog_confirmar_firma_actas(servicio, sesion)

```

(deja intacta la línea `if st.session_state.get("_confirmar_firma"):` que ya existe justo después, para el diálogo de corr/gd/secop).

- [ ] **Step 6: Verificación manual**

Necesitas 3 usuarios de prueba con permisos `certificacion.firmar_financiera`, `certificacion.firmar_abogado` y `certificacion.firmar_jefe` respectivamente (los asignarás en Task 7 desde el panel de admin — si Task 7 aún no está hecha, asígnalos manualmente por ahora insertando el permiso en `permisos_extra` desde `mongosh`, o adelanta Task 7 primero).

Con el contratista de prueba que generó los 3 formatos en Task 5:
1. Inicia sesión como el firmante de **Financiera** → ve a **Sup. Formatos → 3- Balance General CPS**. Debe verse el badge `⏳ F. Financiera` con el botón "✅ Aprobar" habilitado. Apruébalo con un comentario.
2. Sin cerrar sesión, cambia a un usuario que sea firmante de **Abogado** → mismo botón "3- Balance General CPS". Debe verse `✅ F. Financiera ⏳ F. Jurídica ⏳ F. Jefe`, con "✅ Aprobar" habilitado para Abogado. Aprueba.
3. Repite con el firmante de **Jefe** → al aprobar, el badge debe quedar `✅ F. Financiera ✅ F. Jurídica ✅ F. Jefe` y la fila debe cambiar a "✅ Formato aprobado".
4. Vuelve a entrar como el contratista de prueba y confirma en **Formatos de contrato → 2- Balance General CPS** que ahora aparece el botón de descarga en vez del stepper.
5. Prueba la revocación en cascada: como Abogado, haz clic en "↩ Revocar" sobre ese mismo contratista (ahora con las 3 firmas puestas). Debe volver a `pendiente`, y el badge de Jefe debe quedar `⏳` de nuevo. Entra como el firmante de Jefe y confirma que ve el aviso "⚠️ Tu aprobación fue removida porque abogado revocó la suya."

- [ ] **Step 7: Commit**

```bash
git add app/pages_admin/admin_firmantes.py
git commit -m "feat(certificaciones): activa la firma secuencial de actas en Sup. Formatos"
```

---

### Task 7: Configuración de firmantes de actas + supervisión en "Seguimiento - Formatos"

**Files:**
- Modify: `app/pages_admin/admin_certificaciones.py`

**Interfaces:**
- Consumes: `TIPOS_FIRMA_ACTAS`, `ORDEN_FIRMAS_ACTAS` (Task 3), `servicio.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)` / `servicio.guardar_firmante(tipo, uid, nombre, categoria="firmantes_formatos_actas")` (Task 3), `servicio.obtener_empleados_para_certificar(tipo_formato=...)` (ya existe).
- Produces: nada consumido por otras tareas.

- [ ] **Step 1: Importar las constantes de actas**

Cambia el import existente (línea 14):

```python
from app.services.certificacion_service import CertificacionService, MESES_ES
```

por:

```python
from app.services.certificacion_service import CertificacionService, MESES_ES, TIPOS_FIRMA_ACTAS, ORDEN_FIRMAS_ACTAS
```

- [ ] **Step 2: Agregar metadatos y el expander de configuración de firmantes de actas**

Agrega, después de `_META_FIRMA` (línea 22) y antes de `# ── Configuración de firmantes (solo admin con gestionar_firmantes) ──`:

```python
_META_FIRMA_ACTAS = {
    "financiera": ("F. Financiera", "Financiera"),
    "abogado":    ("F. Jurídica",   "Jurídico"),
    "jefe":       ("F. Jefe",       "Jefe inmediato"),
}

_PREFIJO_ARCHIVO_ACTAS = {
    "acta_compromiso": "Acta_Compromiso",
    "acta_recibo_entrega_cps": "Balance_General_CPS",
    "acta_recibo_entrega_cps_real": "Acta_Recibo_Entrega_CPS",
}

_TITULO_ACTAS = {
    "acta_compromiso": "Acta de compromiso",
    "acta_recibo_entrega_cps": "Balance General CPS",
    "acta_recibo_entrega_cps_real": "Acta de recibo y entrega CPS",
}
```

Agrega, después de `_seccion_config_firmantes` (línea 73, antes de `# ── Badges ──`):

```python

def _seccion_config_firmantes_actas(servicio: CertificacionService, sesion: dict) -> None:
    if "certificacion.gestionar_firmantes" not in sesion.get("permisos", []):
        return

    from app.repositories.usuario_repo import UsuarioRepositorio

    with st.expander("⚙️ Configurar firmantes de Actas (Financiera / Abogado / Jefe)", expanded=False):
        st.caption(
            "Designa qué usuario ejerce cada rol de aprobación para Acta de compromiso, "
            "Balance General CPS y Acta de recibo y entrega CPS. "
            "Al guardar se asigna automáticamente el permiso correspondiente."
        )

        config = servicio.obtener_firmantes_config("firmantes_formatos_actas", TIPOS_FIRMA_ACTAS)
        usuarios_activos = [u for u in UsuarioRepositorio().listar() if u.get("activo", True)]
        id_a_nombre = {str(u["_id"]): u["nombre_completo"] for u in usuarios_activos}
        opciones_lista = ["(ninguno)"] + sorted(id_a_nombre.values())
        nombre_a_id = {v: k for k, v in id_a_nombre.items()}

        for tipo in TIPOS_FIRMA_ACTAS:
            label_largo = _META_FIRMA_ACTAS[tipo][1]
            actual = config.get(tipo) or {}
            actual_nombre = actual.get("nombre") if actual else None
            idx_actual = 0
            if actual_nombre and actual_nombre in opciones_lista:
                idx_actual = opciones_lista.index(actual_nombre)

            c1, c2 = st.columns([5, 1])
            with c1:
                seleccionado = st.selectbox(
                    f"Firmante · {label_largo}",
                    options=opciones_lista,
                    index=idx_actual,
                    key=f"sel_firmante_actas_{tipo}",
                )
            with c2:
                st.write("")
                if st.button("Guardar", key=f"btn_firmante_actas_{tipo}", use_container_width=True):
                    if seleccionado == "(ninguno)":
                        servicio.guardar_firmante(tipo, None, None, categoria="firmantes_formatos_actas")
                        st.success(f"Firmante de {label_largo} eliminado.")
                    else:
                        uid = nombre_a_id.get(seleccionado)
                        if uid:
                            servicio.guardar_firmante(tipo, uid, seleccionado, categoria="firmantes_formatos_actas")
                            st.success(f"Firmante de {label_largo}: **{seleccionado}**")
                    st.rerun()
```

- [ ] **Step 3: Reemplazar el bloque de supervisión de Actas (botones 2/3/4)**

Reemplaza la inicialización de estado (líneas 194-197):

```python
    if "ver_formato_control_seg" not in st.session_state:
        st.session_state["ver_formato_control_seg"] = False
    if "ver_actas_compromiso_seg" not in st.session_state:
        st.session_state["ver_actas_compromiso_seg"] = False
```

por:

```python
    if "ver_formato_control_seg" not in st.session_state:
        st.session_state["ver_formato_control_seg"] = False
    if "tipo_acta_seg_activo" not in st.session_state:
        st.session_state["tipo_acta_seg_activo"] = None
```

Reemplaza el bloque de 4 botones (líneas 201-215):

```python
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("1- Supervisión Formato de control Corr-GD-SECOP", type="primary" if st.session_state["ver_formato_control_seg"] else "secondary", use_container_width=True, key="btn_formato_control_seg"):
            st.session_state["ver_formato_control_seg"] = not st.session_state["ver_formato_control_seg"]
            st.session_state["ver_actas_compromiso_seg"] = False
            st.rerun()
    with col2:
        st.button("2- Supervisión Formato de acta de recibo y entrega CPS", disabled=True, use_container_width=True, key="btn_acta_recibo_seg")
    with col3:
        st.button("3- Supervisión Balance General CPS", disabled=True, use_container_width=True, key="btn_balance_general_seg")
    with col4:
        if st.button("4- Gestion Actas compromiso", type="primary" if st.session_state["ver_actas_compromiso_seg"] else "secondary", use_container_width=True, key="btn_actas_compromiso_seg"):
            st.session_state["ver_actas_compromiso_seg"] = not st.session_state["ver_actas_compromiso_seg"]
            st.session_state["ver_formato_control_seg"] = False
            st.rerun()
```

por:

```python
    _BOTONES_ACTAS_SEG = [
        ("acta_compromiso", "2- Acta de compromiso"),
        ("acta_recibo_entrega_cps", "3- Balance General CPS"),
        ("acta_recibo_entrega_cps_real", "4- Acta de recibo y entrega CPS"),
    ]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("1- Supervisión Formato de control Corr-GD-SECOP", type="primary" if st.session_state["ver_formato_control_seg"] else "secondary", use_container_width=True, key="btn_formato_control_seg"):
            st.session_state["ver_formato_control_seg"] = not st.session_state["ver_formato_control_seg"]
            st.session_state["tipo_acta_seg_activo"] = None
            st.rerun()
    for col, (tipo, etiqueta) in zip((col2, col3, col4), _BOTONES_ACTAS_SEG):
        with col:
            activo = st.session_state["tipo_acta_seg_activo"] == tipo
            if st.button(etiqueta, type="primary" if activo else "secondary", use_container_width=True, key=f"btn_seg_{tipo}"):
                st.session_state["tipo_acta_seg_activo"] = None if activo else tipo
                st.session_state["ver_formato_control_seg"] = False
                st.rerun()
```

Reemplaza el bloque `if st.session_state.get("ver_actas_compromiso_seg"):` completo (líneas 219-333, desde `if st.session_state.get("ver_actas_compromiso_seg"):` hasta el `st.rerun()` final de ese bloque, justo antes de `    if st.session_state.get("_preview_cert"):`) por una versión genérica parametrizada por `tipo_formato`:

```python
    tipo_acta_activo = st.session_state.get("tipo_acta_seg_activo")
    if tipo_acta_activo:
        _seccion_config_firmantes_actas(servicio, sesion)
        st.divider()

        orden = ORDEN_FIRMAS_ACTAS[tipo_acta_activo]
        titulo = _TITULO_ACTAS[tipo_acta_activo]

        with st.spinner(f"Consultando estado de {titulo.lower()}…"):
            empleados = servicio.obtener_empleados_para_certificar(tipo_formato=tipo_acta_activo)
        empleados = [e for e in empleados if e.get("certificacion")]

        if not empleados:
            st.info("Ningún colaborador ha generado este formato todavía.")
        else:
            total = len(empleados)
            aprobados = sum(1 for e in empleados if (e.get("certificacion") or {}).get("estado") == "aprobado")
            pendientes = total - aprobados

            m1, m2, m3 = st.columns(3)
            m1.metric("Total colaboradores", total)
            m2.metric(f"{titulo} aprobadas", aprobados)
            m3.metric("Pendientes", pendientes)

            st.divider()

            fc1, fc2 = st.columns(2)
            with fc1:
                contratistas_unicos = sorted(list(set(e["nombre"] for e in empleados)))
                buscar = st.selectbox(
                    "Filtro por Gestor",
                    options=["Todos"] + contratistas_unicos,
                    index=0,
                    key=f"filtro_gestor_{tipo_acta_activo}",
                )
            with fc2:
                filtro_aprobados = st.selectbox(
                    "Filtro por Estado",
                    options=["Todos", "Aprobadas", "Pendientes"],
                    index=0,
                    key=f"filtro_estado_{tipo_acta_activo}",
                )

            lista = empleados
            if buscar != "Todos":
                lista = [e for e in lista if e["nombre"] == buscar]
            if filtro_aprobados == "Aprobadas":
                lista = [e for e in lista if (e.get("certificacion") or {}).get("estado") == "aprobado"]
            elif filtro_aprobados == "Pendientes":
                lista = [e for e in lista if (e.get("certificacion") or {}).get("estado") != "aprobado"]

            lista = sorted(lista, key=lambda e: e["nombre"].lower())
            st.caption(f"Mostrando {len(lista)} de {total} colaboradores")

            if not lista:
                st.info("Ningún colaborador coincide con los filtros aplicados.")
            else:
                for emp in lista:
                    uid = emp["usuario_id"]
                    nombre = emp["nombre"]
                    cert = emp.get("certificacion") or {}
                    estado_cert = cert.get("estado")
                    firmas = emp.get("firmas", {})

                    with st.container(border=True):
                        c_nom, c_badges, c_btn = st.columns([3, 5, 2])

                        with c_nom:
                            st.markdown(f"**{nombre}**")
                            st.caption("Aprobado" if estado_cert == "aprobado" else "Pendiente de firmas")

                        with c_badges:
                            badge_estado = (
                                '<span style="background-color: #2E7D32; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">APROBADO</span>'
                                if estado_cert == "aprobado"
                                else '<span style="background-color: #E65100; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">PENDIENTE</span>'
                            )
                            badges_firmas = "&nbsp;".join(
                                (
                                    f'<span style="background:#1b4721;color:#75db8b;border:1px solid #2d7a3e;border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">✅ {_META_FIRMA_ACTAS[r][0]}</span>'
                                    if firmas.get(r)
                                    else f'<span style="background:#2c2c2c;color:#aaaaaa;border:1px solid #444;border-radius:4px;padding:1px 8px;font-size:.76em;font-weight:700;">⏳ {_META_FIRMA_ACTAS[r][0]}</span>'
                                )
                                for r in orden
                            )
                            st.markdown(f"{badge_estado} &nbsp;&nbsp; {badges_firmas}", unsafe_allow_html=True)

                        with c_btn:
                            if estado_cert == "aprobado":
                                pdf_bytes = obtener_pdf_certificado_cacheado(
                                    servicio, str(cert["_id"]), cert.get("hash_verificacion", ""), cert
                                )
                                prefijo = _PREFIJO_ARCHIVO_ACTAS[tipo_acta_activo]
                                st.download_button(
                                    "⬇️ Descargar",
                                    data=pdf_bytes,
                                    file_name=f"{prefijo}_{nombre.replace(' ', '_')}_{nombre_mes}_{año}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_{tipo_acta_activo}_{uid}",
                                    type="primary",
                                    use_container_width=True,
                                )
```

- [ ] **Step 4: Verificación manual**

Levanta la app, entra con un usuario que tenga `certificacion.aprobar` (rol `supervisor` o `admin`) a **Sup. Formatos y Seguimiento → Seguimiento - Formatos**, y confirma:
1. Los botones 2, 3 y 4 ya no están deshabilitados y muestran, en orden, "Acta de compromiso", "Balance General CPS", "Acta de recibo y entrega CPS".
2. Al hacer clic en cualquiera de ellos aparece el expander "⚙️ Configurar firmantes de Actas" — asigna ahí los 3 usuarios de prueba a Financiera/Abogado/Jefe (si no lo hiciste ya en la Task 6).
3. La lista de colaboradores muestra los badges `APROBADO`/`PENDIENTE` junto con los badges de cada rol de firma, y el botón de descarga solo aparece cuando el estado es `aprobado`.

- [ ] **Step 5: Commit**

```bash
git add app/pages_admin/admin_certificaciones.py
git commit -m "feat(certificaciones): configuracion de firmantes de actas y supervision en Seguimiento - Formatos"
```

---

### Task 8: Actualizar documentación de permisos y páginas

**Files:**
- Modify: `docs/permisos_y_paginas.md`

**Interfaces:** ninguna — es documentación.

- [ ] **Step 1: Agregar los permisos nuevos a la tabla de permisos**

Después de la fila de `certificacion.gestionar_firmantes` (línea 29), agrega:

```markdown
| `certificacion.firmar_financiera` | Firmar aprobación Financiera de actas (firmante designado) | Certificaciones |
| `certificacion.firmar_abogado` | Firmar aprobación Jurídica de actas (firmante designado) | Certificaciones |
| `certificacion.firmar_jefe` | Firmar aprobación del Jefe de actas (firmante designado) | Certificaciones |
```

Actualiza la nota de la línea 31 para mencionar también los roles nuevos:

```markdown
> **Nota importante sobre los permisos de firma:** `firmar_corr`, `firmar_gd`, `firmar_secop`, `firmar_financiera`, `firmar_abogado` y `firmar_jefe` **no se asignan por rol**, se otorgan individualmente como `permisos_extra` al usuario cuando el administrador lo designa como firmante (Correspondencia/GD/SECOP desde "Aprobar Certificaciones"; Financiera/Abogado/Jefe desde "Seguimiento - Formatos" o "Sup. Formatos"). Esto permite que un administrador también pueda ser firmante sin que todos los admins tengan ese permiso.
```

Y la fila del rol `admin` (línea 39):

```markdown
| `admin` | Administrador del sistema | Todos excepto `firmar_corr`, `firmar_gd`, `firmar_secop`, `firmar_financiera`, `firmar_abogado`, `firmar_jefe` |
```

- [ ] **Step 2: Documentar el flujo de firmas de actas**

Agrega una sección nueva después de la sección existente de firmas de Correspondencia/GD/SECOP (después de la línea 124, antes de la tabla final de "quién puede hacer qué"):

```markdown
### Firmas secuenciales de Actas (Financiera / Abogado / Jefe)

Aplican a 3 formatos generados por el propio contratista desde "Formatos de contrato" (botón "✍️ Firmar y Generar Formato"): **Acta de compromiso**, **Balance General CPS** y **Acta de recibo y entrega CPS**. A diferencia del formato de Correspondencia/GD/SECOP, estos NO quedan aprobados de inmediato: nacen en estado `pendiente` y requieren aprobación de los roles designados, **en orden estricto**:

- **Acta de compromiso:** solo **Jefe**.
- **Balance General CPS** y **Acta de recibo y entrega CPS:** **Financiera → Abogado → Jefe**, en ese orden — un rol solo puede firmar si el anterior ya lo hizo.

Si un firmante revoca su aprobación después de que alguien firmó detrás de él, las firmas posteriores se revocan también en cascada y el documento vuelve a `pendiente`; el firmante afectado ve un aviso explicando por qué.

| Tipo de firma (actas) | `permisos_extra` que se otorga |
|---|---|
| Financiera | `certificacion.firmar_financiera` |
| Abogado | `certificacion.firmar_abogado` |
| Jefe | `certificacion.firmar_jefe` |

Se configuran desde el expander "⚙️ Configurar firmantes de Actas" en **Seguimiento - Formatos** (`pages/7_admin_certif.py`), y se aprueban desde los botones 2/3/4 de **Sup. Formatos** (`pages/9_firmantes_certif.py`).
```

- [ ] **Step 3: Verificación manual**

Lee el archivo completo (`docs/permisos_y_paginas.md`) de arriba a abajo y confirma que no quedaron referencias contradictorias (ej. que la tabla de roles y la nota de permisos de firma coincidan en la lista de 6 permisos de firma).

- [ ] **Step 4: Commit**

```bash
git add docs/permisos_y_paginas.md
git commit -m "docs: documenta permisos y flujo de firmas secuenciales de actas"
```
