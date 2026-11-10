# Optimización de rendimiento — "Sup. Formatos" (`admin_firmantes.py`)

## Contexto

Reporte del usuario: ~40 segundos para cargar la página "Sup. Formatos" y ~20 segundos adicionales al filtrar/aprobar una firma (consultar y regenerar). Diagnóstico realizado sin aplicar cambios (ver conversación del 2026-09-16). Tres causas identificadas, ninguna relacionada con índices de MongoDB — las consultas lentas son *scans completos intencionales* (se necesita a todos los usuarios), así que el problema es de **trabajo repetido y no diferido**, no de falta de índice.

## Causas identificadas

### 1. PDFs generados "de una" para todos los aprobados, no bajo demanda (impacto alto)

En el panel **"Formato de control Corr-GD-SECOP"** (`admin_firmantes.py:779-794`), por cada contratista **ya aprobado** en la lista filtrada, el código llama a `obtener_pdf_certificado_cacheado(...)` para poblar el botón de descarga — y esa llamada genera el PDF con ReportLab (más una consulta a `usuarios` para firma/datos) **de inmediato**, no al hacer clic. Con N contratistas aprobados visibles, esto es N generaciones secuenciales en cada rerun de Streamlit (cada filtro, cada aprobación).

Contraste: el panel de **Actas** (`_render_panel_actas`, mismo archivo, comentario en línea ~459) sí difiere la generación hasta abrir el diálogo (`abrir_dialogo_documento`), que es el patrón correcto ya usado en el resto de la app.

Hay caché (`@st.cache_data` en `app/core/ui_certificado.py:7`), pero solo evita regenerar el *mismo* PDF ya calculado antes. La primera vez que se ve un período (o tras un reinicio del proceso, que limpia la caché en memoria de Streamlit) el costo se paga completo y en serie.

### 2. La colección `usuarios` se escanea completa 3 veces por carga (impacto medio-alto)

Sin filtro ni proyección de campos, cada una por su cuenta:

- `CertificacionService.periodos_disponibles_global()` → `certificacion_service.py:348` (`UsuarioRepositorio().listar()`, solo para extraer `contratos`)
- `CorrespondenciaService.obtener_estado_formatos()` → vía `UsuarioService.listar_usuarios()`
- `CertificacionService.obtener_empleados_para_certificar()` → `certificacion_service.py:665` (`usuario_repo.listar()` de nuevo)

Ninguna comparte resultado con las otras dentro del mismo render.

### 3. Ninguna de estas consultas está cacheada (impacto alto, agrava 1 y 2)

Ya existe un patrón de caché establecido en `app/core/cache_datos.py` (`@st.cache_data(ttl=60)`, usado en dashboard, usuarios activos, catálogos), pero no se aplicó a:

- `obtener_empleados_para_certificar`
- `periodos_disponibles_global` / `periodos_disponibles_usuario`
- `obtener_estado_formatos`

Como Streamlit re-ejecuta todo el script en cada interacción (clic, cambio de filtro), estas 3 consultas completas + el bucle de generación de PDFs se repiten en **cada clic**, no solo en la carga inicial.

## Alcance del plan de corrección

- Diferir la generación de PDF/Excel del panel de control Corr-GD-SECOP para que siga el mismo patrón de diálogo bajo demanda que ya usa el panel de Actas.
- Cachear las consultas de solo lectura mencionadas arriba con el mismo mecanismo (`st.cache_data`, TTL corto) que ya usa `app/core/cache_datos.py`.
- Invalidar esa caché nueva desde las acciones de escritura relevantes (aprobar/revocar firma, aprobar/revocar firma de actas, designar firmante), para que un cambio de estado se refleje sin esperar el TTL.
- Eliminar la duplicación de `UsuarioRepositorio().listar()` dentro de un mismo render, reutilizando un único resultado cacheado.

## Fuera de alcance

- No se toca el modelo de datos ni el esquema de `certificaciones`/`usuarios`.
- No se cambia la lógica de negocio de aprobación/revocación ni el orden de firmas de actas (`ORDEN_FIRMAS_ACTAS`).
- No se agregan índices nuevos en MongoDB (las consultas lentas son scans completos por diseño; indexar no las acelera).
- No se toca `6_certificaciones.py` (vista contratista) en esta iteración — el mismo problema de "PDF eager" no aplica ahí porque cada contratista solo ve y genera **sus propios** formatos, no una lista de decenas de personas. Si tras esta optimización se detecta lentitud allí también, se evalúa aparte.
- No se corrige en este plan la mutación in-place de la lista `contratos` dentro de `CertificacionService._contrato_para_periodo` (`pool.sort(...)` reordena el array original cuando no hay coincidencias exactas de período). No es un problema de rendimiento — es un efecto secundario de orden que vale la pena revisar en una limpieza aparte, no bloqueante para este plan.

## Cambios propuestos

### A. Generación diferida en el panel de control (`admin_firmantes.py`)

Reemplazar el bloque que arma `st.download_button` con `data=obtener_pdf_certificado_cacheado(...)` calculado de forma eager (líneas ~779-794) por el mismo patrón que ya usa `_render_panel_actas`: un botón "👁️ Ver / Descargar" que llama a `abrir_dialogo_documento(...)`, y la generación ocurre dentro de `_dialog_ver_documento` (`app/core/ui_certificado.py`), solo al abrirse.

Esto es, en la práctica, extender a este panel el mismo componente reutilizable (`abrir_dialogo_documento` / `render_dialogo_documento_si_activo`) que Actas ya usa, en vez de una ruta de código distinta y más costosa.

### B. Caché de las consultas de solo lectura

Agregar en `app/core/cache_datos.py` (siguiendo el patrón existente, `ttl=60`, `show_spinner=False`):

- `empleados_para_certificar(tipo_formato, año, mes)` → envuelve `CertificacionService().obtener_empleados_para_certificar(...)`
- `periodos_disponibles_global()` → envuelve `CertificacionService().periodos_disponibles_global()`
- `periodos_disponibles_usuario(usuario_id)` → envuelve `CertificacionService().periodos_disponibles_usuario(usuario_id)`
- `estado_formatos()` → envuelve `CorrespondenciaService().obtener_estado_formatos()`

`admin_firmantes.py` (y `6_certificaciones.py` donde aplique) pasan a llamar estas funciones de `cache_datos.py` en vez de invocar los servicios directamente, igual que ya hacen otras páginas para dashboard/opciones/usuarios activos.

Nota de diseño: como `obtener_empleados_para_certificar` internamente ya combina `obtener_estado_formatos()` + `usuario_repo.listar()` + certificaciones del período, cachear solo esa función (con TTL corto) ya resuelve la causa 2 sin necesidad de cachear cada sub-consulta por separado — se evalúa en el plan de implementación cuál nivel de granularidad conviene más.

### C. Invalidación tras escrituras

Extender `limpiar_cache_lecturas()` (o agregar una función hermana, p. ej. `limpiar_cache_certificaciones()`) para incluir `.clear()` de las nuevas entradas cacheadas, e invocarla al final de:

- `CertificacionService.registrar_firma` / `revocar_firma`
- `CertificacionService.registrar_firma_actas` / `revocar_firma_actas`
- `CertificacionService.guardar_firmante`
- Cualquier flujo de `firmar_y_generar_*` que cree/actualice una certificación (para que un contratista recién generado aparezca sin esperar el TTL de 60s en la vista del supervisor)

Alternativa más simple si el TTL de 60s resulta aceptable en la práctica: no invalidar activamente y confiar en el TTL corto + el `st.rerun()` que ya sigue a cada acción (el usuario vería su propio cambio reflejado igual, porque el caché es por argumentos y Streamlit cachea a nivel de proceso, no de sesión — a confirmar en el plan de implementación cuál de las dos opciones da mejor equilibrio entre "frescura" y "menos llamadas a limpiar caché en cada escritura").

## Riesgos / puntos a verificar en la implementación

- **Frescura de datos**: con TTL de 60s, un supervisor podría ver por hasta un minuto el estado previo a una aprobación hecha por otro firmante en paralelo. Si eso no es aceptable, priorizar la invalidación activa (punto C) sobre el TTL solo.
- **Caché compartido entre sesiones**: `st.cache_data` es a nivel de proceso (compartido entre todos los usuarios conectados), no por sesión — hay que confirmar que ningún dato sensible por-usuario termine cacheado bajo una clave que no lo diferencie (los candidatos aquí — empleados, períodos, estado de formatos — son iguales para cualquier supervisor que consulte el mismo período, así que no debería haber fuga entre usuarios, pero vale la pena revisarlo al implementar).
- **`_servicio` como parámetro no hasheado**: igual que ya hace `obtener_pdf_certificado_cacheado` (parámetro con guión bajo), las nuevas funciones cacheadas deben evitar pasar objetos no hasheables (instancias de servicio) como parte de la clave de caché.

## Testing

Sin suite automatizada (MVP, ver `CLAUDE.md`). Checklist manual para el plan de implementación:

- Medir tiempo de carga de "Sup. Formatos" antes/después, con un período que tenga varios contratistas ya aprobados (panel de control).
- Confirmar que el botón "Ver/Descargar" del panel de control abre el diálogo y genera el PDF solo al hacer clic (no antes), igual que en Actas.
- Aprobar una firma y confirmar que el supervisor ve el cambio reflejado (inmediatamente si se implementa invalidación activa, o dentro del TTL si no).
- Verificar que dos supervisores con permisos distintos, consultando el mismo período, no ven datos cruzados ni resultados cacheados incorrectos.
- Repetir el flujo completo en "Formatos de contrato" (vista contratista) para confirmar que no se rompió nada al reutilizar `abrir_dialogo_documento` / `cache_datos.py`.
