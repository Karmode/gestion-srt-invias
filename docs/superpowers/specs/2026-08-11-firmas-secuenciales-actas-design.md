# Firmas secuenciales para Acta de compromiso, Balance General CPS y Acta de recibo y entrega CPS

## Contexto

Hoy los formatos "Acta de compromiso", "Balance General CPS" (`tipo_formato="acta_recibo_entrega_cps"`) y "Acta de recibo y entrega CPS" (`tipo_formato="acta_recibo_entrega_cps_real"`) se auto-firman: el contratista hace clic en "✍️ Firmar y Generar Formato" (`app/pages/6_certificaciones.py`, opciones 5/8/9) y el documento queda `estado="aprobado"` de inmediato, sin revisión de nadie más.

Se requiere agregar una capa de aprobación secuencial por parte de tres roles nuevos — **Financiera**, **Abogado** y **Jefe** — antes de que el formato quede aprobado y descargable, siguiendo el mismo patrón ya usado para el formato de Correspondencia/Gestión Documental/SECOP II (roles `corr`/`gd`/`secop`, ver `app/services/certificacion_service.py` y `app/pages_admin/admin_firmantes.py`).

La página "Sup. Formatos" (`app/pages_admin/admin_firmantes.py`) ya tiene 3 botones deshabilitados como stub para estos formatos (líneas ~201-206), en un orden que no coincide con el deseado — confirma que el lugar estaba previsto pero falta implementar y reordenar.

## Alcance

- Formato **Acta de compromiso** (`tipo_formato="acta_compromiso"`): requiere solo la firma de **Jefe**.
- Formato **Balance General CPS** (`tipo_formato="acta_recibo_entrega_cps"`) y **Acta de recibo y entrega CPS** (`tipo_formato="acta_recibo_entrega_cps_real"`): requieren, en este orden estricto, **Financiera → Abogado → Jefe**. Un rol solo puede firmar si el anterior en el orden ya firmó.
- El Jefe termina firmando 3 formatos por contratista y período: el Acta de compromiso (solo) y como último firmante de los otros dos.

Fuente única de verdad del orden:

```python
ORDEN_FIRMAS_ACTAS = {
    "acta_compromiso": ["jefe"],
    "acta_recibo_entrega_cps": ["financiera", "abogado", "jefe"],       # Balance General CPS
    "acta_recibo_entrega_cps_real": ["financiera", "abogado", "jefe"], # Acta recibo y entrega CPS
}
```

## Fuera de alcance

- No se re-valida ni se exige la nueva secuencia a los documentos que ya quedaron `aprobado` bajo el flujo antiguo (auto-firma) antes del despliegue de este cambio — quedan como están, sin migración retroactiva.
- No se permiten múltiples personas por rol ni asignación distinta por contratista: Financiera/Abogado/Jefe son, igual que corr/gd/secop, un único usuario global por rol para toda la organización.

## Modelo de datos

### Permisos nuevos (`app/core/catalogos.py`)

```
certificacion.firmar_financiera  — Firmar aprobación Financiera (actas)
certificacion.firmar_abogado     — Firmar aprobación Jurídica (actas)
certificacion.firmar_jefe        — Firmar aprobación del Jefe (actas)
```

Se reutiliza el permiso existente `certificacion.gestionar_firmantes` para que el admin designe estos 3 roles — es la misma acción administrativa que ya existe para corr/gd/secop, no amerita un permiso nuevo.

### Asignación de firmantes

Un único usuario global por rol, igual que corr/gd/secop. Se guarda en `opciones_configuracion` bajo una categoría nueva, `firmantes_formatos_actas`, con la forma `{"financiera": {"usuario_id", "nombre"} | None, "abogado": ..., "jefe": ...}` — separada de `firmantes_certificacion` para no mezclar los dos esquemas de firma.

`CertificacionService.obtener_firmantes_config()` y `.guardar_firmante()` se generalizan para aceptar la categoría de configuración y el conjunto de tipos válidos como parámetros (con los valores actuales como default, para no romper las llamadas existentes de corr/gd/secop), evitando duplicar la lógica de sincronizar `permisos_extra`.

### Documento de certificación (`app/core/esquemas.py`, `ESQUEMA_CERTIFICACIONES`)

- `firmas` gana las claves `financiera`, `abogado`, `jefe`, con la misma forma que `corr`/`gd`/`secop` (`firmante_id`, `firmante_nombre`, `fecha`, `comentario` opcional).
- Se agrega un array opcional `eventos` a nivel de documento, para registrar revocaciones en cascada: `{"tipo": "revocacion_cascada", "rol_revocado": str, "causada_por": str, "fecha": date}`.
- `estado` ya soporta `"pendiente"` — no requiere cambios de enum.

### Cambio en la creación del documento

`firmar_y_generar_acta_compromiso`, `firmar_y_generar_acta_recibo_entrega` (Balance General CPS) y `firmar_y_generar_acta_recibo_entrega_cps_real` en `CertificacionService`: el documento se crea con `estado="pendiente"` y `firmas={}` en lugar de `estado="aprobado"` inmediato. El resto de la lógica (validaciones de datos, preservación de `hash_verificacion`) no cambia.

## Flujo de firmas

### `registrar_firma_actas(tipo_formato, usuario_id, rol, firmante_id, firmante_nombre, comentario=None) -> bool`

1. Valida que `rol` esté en `ORDEN_FIRMAS_ACTAS[tipo_formato]`.
2. Valida que el rol anterior en el orden (si existe) ya tenga `firmas.<rol_anterior>` en el documento del período. Si no, lanza `ValueError` (la UI nunca debería llegar aquí porque el botón está deshabilitado, pero el service es la garantía real).
3. Guarda `firmas.<rol>` con `firmante_id`, `firmante_nombre`, `fecha`, `comentario`.
4. Si con esta firma se completa todo `ORDEN_FIRMAS_ACTAS[tipo_formato]` → `estado="aprobado"` + genera/preserva `hash_verificacion` (mismo mecanismo que `_generar_hash`, reutilizando el hash si ya existía de un ciclo previo aprobado-revocado-reaprobado).

### `revocar_firma_actas(tipo_formato, usuario_id, rol) -> bool`

1. Borra `firmas.<rol>`.
2. Para cada rol posterior a `rol` en `ORDEN_FIRMAS_ACTAS[tipo_formato]` que tenga firma registrada: la borra también y agrega a `eventos` una entrada `{"tipo": "revocacion_cascada", "rol_revocado": <rol posterior>, "causada_por": rol, "fecha": ahora}`.
3. Si el documento estaba `aprobado`, vuelve a `pendiente`.

La UI del firmante cuya aprobación fue revocada en cascada usa `eventos` para mostrar un aviso explícito ("⚠️ Tu aprobación fue removida porque Abogado revocó la suya") la próxima vez que ve a ese contratista en su lista, en vez de que la firma desaparezca sin explicación.

## UI — vista del contratista (`app/pages/6_certificaciones.py`)

En las opciones 5 (Acta de compromiso), 8 (Balance General CPS) y 9 (Acta de recibo y entrega CPS): mientras el documento esté en `pendiente`, se muestra un stepper de badges con el avance en el orden correspondiente (reutilizando el estilo visual de `_mostrar_avance`/badges ya usado para el formato de Correspondencia), por ejemplo para Balance General CPS: `✅ Financiera → ⏳ Abogado → ⏳ Jefe`. Para Acta de compromiso el stepper tiene un solo paso (Jefe). El botón de descarga solo aparece cuando `estado == "aprobado"`.

## UI — vista de los firmantes (`app/pages_admin/admin_firmantes.py`, "Sup. Formatos")

- Se activan los 3 botones ya existentes (hoy deshabilitados), reordenados: botón 1 = Corr-GD-SECOP (sin cambios), botón 2 = Acta de compromiso, botón 3 = Balance General CPS, botón 4 = Acta de recibo y entrega CPS.
- Cada vista reutiliza el patrón existente: lista de contratistas con badges de estado, filtros, métricas (total / pendientes de mi aprobación / aprobados) y diálogo de confirmación al aprobar (mismo componente `_dialog_confirmar_firma`, parametrizado por tipo).
- El botón "✅ Aprobar" se deshabilita (con `help=`) si el rol anterior en el orden aún no ha firmado, ej. `help="Esperando firma de Financiera"`.
- El admin sin rol de firma sigue viendo todo en solo lectura, como hoy.
- Si el firmante actual tiene una entrada nueva en `eventos` para un contratista dado, se muestra un `st.info` puntual sobre esa fila.

## UI — configuración de firmantes (`app/pages_admin/admin_certificaciones.py`)

Se agrega un segundo expander "⚙️ Configurar firmantes de Actas (Financiera / Abogado / Jefe)", junto al existente "⚙️ Configurar firmantes designados", con el mismo patrón de selectbox + botón "Guardar" por rol, apuntando a la categoría de configuración `firmantes_formatos_actas`.

## Compatibilidad con datos existentes

Los certificados de estos 3 formatos que ya quedaron `aprobado` bajo el flujo antiguo (auto-firma) antes de este cambio se dejan como están — no se les exige retroactivamente pasar por la secuencia de firmas ni se modifican sus documentos. La nueva validación solo aplica a documentos nuevos creados después del despliegue.

## Testing

El proyecto está en etapa MVP sin suite automatizada (ver CLAUDE.md). Verificación manual sugerida en el plan de implementación:
- Contratista genera cada uno de los 3 formatos → queda en `pendiente` con el stepper correcto.
- Firmante intenta aprobar fuera de orden → botón deshabilitado / service rechaza.
- Secuencia completa → documento pasa a `aprobado`, hash se genera, descarga se habilita.
- Revocación intermedia con firmas posteriores ya registradas → cascada correcta + `eventos` visibles para el firmante afectado.
- Admin asigna/reasigna firmantes de Actas → permisos `permisos_extra` sincronizados igual que con corr/gd/secop.
