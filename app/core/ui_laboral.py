"""Componentes de UI reutilizables para información laboral y firma del usuario.

Se usan tanto en la administración de usuarios (`pages_admin/admin_usuarios.py`)
como en el perfil propio (`pages/2_mi_perfil.py`). Toda la sección se renderiza
SIN `st.form`, porque los dependientes se agregan/eliminan con botones, que
Streamlit no permite dentro de un form.
"""

import streamlit as st

from app.core.catalogos import TIPOS_DOC_DEPENDIENTE
from app.services.firma_service import FirmaService, componer_sobre_fondo, validar_y_procesar
from app.services.opciones_service import OpcionesService

# (clave en doc, etiqueta visible, categoría de catálogo)
_AFILIACIONES = [
    ("eps", "EPS", "eps"),
    ("arl", "ARL", "arl"),
    ("afp", "Fondo de pensiones (AFP)", "afp"),
    ("ccf", "Caja de compensación (CCF)", "ccf"),
]
_CATEGORIAS = ["eps", "arl", "afp", "ccf", "banco", "tipo_dependiente"]

# Cómo se cubre el aporte de seguridad social (no es catálogo: opciones fijas).
# El valor interno "entidad" se conserva por compatibilidad; la etiqueta visible
# es genérica ("por otro medio") para no explicitar quién realiza el pago.
_MAPA_PAGA = {
    "": "— Seleccionar —",
    "contratista": "La pago yo",
    "entidad": "Se paga por otro medio",
}


def _paga_inicial(af: dict) -> str:
    """Determina la opción 'quién paga' inicial, infiriéndola en registros antiguos."""
    paga = af.get("paga")
    if paga in ("contratista", "entidad"):
        return paga
    if af.get("valor"):
        return "contratista"
    if af.get("radicado"):
        return "entidad"
    return ""


# ── Catálogos ─────────────────────────────────────────────────────────────────

def _mapa_opciones(op_service, categoria, etiqueta_vacio="— Seleccionar —"):
    mapa = {"": etiqueta_vacio}
    for o in op_service.obtener_opciones(categoria):
        mapa[o["clave"]] = o["etiqueta"]
    return mapa


def construir_mapas_catalogos():
    """{categoria: {clave: etiqueta}} para los selects de información laboral."""
    op = OpcionesService()
    return {cat: _mapa_opciones(op, cat) for cat in _CATEGORIAS}


# ── Helpers de estado de widgets ──────────────────────────────────────────────

def _preseed(key, value):
    """Fija el valor inicial de un widget vía session_state (solo si aún no existe)."""
    if key not in st.session_state:
        st.session_state[key] = value


def _select_keyed(label, mapa, valor_inicial, key):
    claves = list(mapa.keys())
    _preseed(key, valor_inicial if valor_inicial in claves else "")
    return st.selectbox(label, options=claves, format_func=lambda k: mapa[k], key=key)


def limpiar_estado_laboral(prefijo):
    """Elimina las claves de session_state de los widgets laborales de un prefijo."""
    for k in [k for k in st.session_state.keys() if k.startswith(prefijo + "_")]:
        del st.session_state[k]


# ── Sección de información laboral ────────────────────────────────────────────

def inputs_informacion_laboral(prefijo, il, mapas):
    """Renderiza los campos de información laboral y devuelve el dict crudo."""
    il = il or {}
    ss = il.get("seguridad_social") or {}
    bancaria = il.get("bancaria") or {}
    tributaria = il.get("tributaria") or {}
    deps = il.get("dependientes") or []

    st.markdown("##### 🏥 Seguridad social y aportes")
    st.caption("Indica si el aporte lo pagas tú (registra el valor mensual) o se paga por otro medio (registra el número de radicado).")
    resultado_ss = {}
    for cod, etiqueta, cat in _AFILIACIONES:
        af = ss.get(cod) or {}
        c1, c2, c3 = st.columns([2, 1.3, 1.3])
        with c1:
            entidad = _select_keyed(etiqueta, mapas[cat], af.get("entidad") or "", f"{prefijo}_{cod}_ent")
        with c2:
            paga = _select_keyed("¿Quién paga?", _MAPA_PAGA, _paga_inicial(af), f"{prefijo}_{cod}_paga")
        with c3:
            if paga == "entidad":
                _preseed(f"{prefijo}_{cod}_rad", af.get("radicado") or "")
                radicado = st.text_input("N° de radicado", key=f"{prefijo}_{cod}_rad", placeholder="Radicado del pago")
                valor = 0
            elif paga == "contratista":
                _preseed(f"{prefijo}_{cod}_val", int(af.get("valor") or 0))
                valor = st.number_input("Valor mensual", min_value=0, step=10000, format="%d", key=f"{prefijo}_{cod}_val")
                radicado = ""
            else:
                st.caption("Selecciona quién paga el aporte.")
                valor, radicado = 0, ""
        resultado_ss[cod] = {"entidad": entidad, "paga": paga, "valor": valor, "radicado": radicado}

    st.markdown("##### 🏦 Información bancaria")
    cb1, cb2 = st.columns(2)
    with cb1:
        banco = _select_keyed("Banco", mapas["banco"], bancaria.get("banco") or "", f"{prefijo}_banco")
    with cb2:
        _preseed(f"{prefijo}_num_cuenta", bancaria.get("numero_cuenta") or "")
        num_cuenta = st.text_input("Número de cuenta", key=f"{prefijo}_num_cuenta", placeholder="Sin puntos ni espacios")

    st.markdown("##### 🧾 Información tributaria")
    ct1, ct2 = st.columns(2)
    with ct1:
        _preseed(f"{prefijo}_rut", tributaria.get("rut") or "")
        rut = st.text_input("RUT", key=f"{prefijo}_rut")
    with ct2:
        _preseed(f"{prefijo}_declarante", bool(tributaria.get("declarante_renta")))
        declarante = st.checkbox("¿Declarante de renta?", key=f"{prefijo}_declarante")

    st.markdown("##### 👨‍👩‍👧 Dependientes económicos")
    dependientes = _inputs_dependientes(prefijo, deps, mapas)

    return {
        "seguridad_social": resultado_ss,
        "bancaria": {"banco": banco, "numero_cuenta": num_cuenta},
        "tributaria": {"rut": rut, "declarante_renta": declarante},
        "dependientes": dependientes,
    }


def _inputs_dependientes(prefijo, deps, mapas):
    """Lista dinámica de dependientes con agregar/eliminar por fila (IDs estables)."""
    ids_key = f"{prefijo}_dep_ids"
    seq_key = f"{prefijo}_dep_seq"
    tdoc_keys = list(TIPOS_DOC_DEPENDIENTE.keys())
    tipo_mapa = mapas["tipo_dependiente"]
    tipo_keys = list(tipo_mapa.keys())

    # Inicialización: un ID estable por dependiente existente, sembrando sus valores.
    if ids_key not in st.session_state:
        st.session_state[seq_key] = 0
        ids = []
        for dep in deps:
            rid = st.session_state[seq_key]
            st.session_state[seq_key] += 1
            ids.append(rid)
            tdoc = dep.get("tipo_documento") or ""
            tipo = dep.get("tipo") or ""
            st.session_state[f"{prefijo}_dep_nombre_{rid}"] = dep.get("nombre") or ""
            st.session_state[f"{prefijo}_dep_ndoc_{rid}"] = dep.get("numero_documento") or ""
            st.session_state[f"{prefijo}_dep_tdoc_{rid}"] = tdoc if tdoc in tdoc_keys else ""
            st.session_state[f"{prefijo}_dep_tipo_{rid}"] = tipo if tipo in tipo_keys else ""
        st.session_state[ids_key] = ids

    ids = st.session_state[ids_key]
    if not ids:
        st.caption("Sin dependientes. Usa “➕ Agregar dependiente” si necesitas registrar alguno.")

    dependientes = []
    for pos, rid in enumerate(list(ids)):
        cab, bdel = st.columns([6, 1])
        with cab:
            st.markdown(f"**Dependiente {pos + 1}**")
        with bdel:
            if st.button("🗑️", key=f"{prefijo}_dep_del_{rid}", help="Eliminar este dependiente"):
                st.session_state[ids_key].remove(rid)
                st.rerun()
        cd1, cd2 = st.columns(2)
        with cd1:
            nombre = st.text_input("Nombre completo", key=f"{prefijo}_dep_nombre_{rid}")
            tdoc = st.selectbox(
                "Tipo de documento", options=tdoc_keys,
                format_func=lambda k: TIPOS_DOC_DEPENDIENTE[k], key=f"{prefijo}_dep_tdoc_{rid}",
            )
        with cd2:
            ndoc = st.text_input("Número de documento", key=f"{prefijo}_dep_ndoc_{rid}")
            tipo = st.selectbox(
                "Tipo de dependiente", options=tipo_keys,
                format_func=lambda k: tipo_mapa[k], key=f"{prefijo}_dep_tipo_{rid}",
            )
        dependientes.append({
            "nombre": nombre, "tipo_documento": tdoc,
            "numero_documento": ndoc, "tipo": tipo,
        })

    if st.button("➕ Agregar dependiente", key=f"{prefijo}_dep_add"):
        nid = st.session_state[seq_key]
        st.session_state[seq_key] += 1
        st.session_state[ids_key].append(nid)
        st.rerun()

    return dependientes


def laboral_vacia(il):
    """True si el bloque de información laboral no tiene ningún dato diligenciado."""
    ss = il.get("seguridad_social") or {}
    if any((a.get("entidad") or a.get("valor") or a.get("radicado")) for a in ss.values()):
        return False
    bancaria = il.get("bancaria") or {}
    if bancaria.get("banco") or bancaria.get("numero_cuenta"):
        return False
    tributaria = il.get("tributaria") or {}
    if tributaria.get("rut") or tributaria.get("declarante_renta"):
        return False
    if any((d.get("nombre") or "").strip() for d in (il.get("dependientes") or [])):
        return False
    return True


# ── Sección de firma ──────────────────────────────────────────────────────────

def render_seccion_firma(usuario_id, actualizado_por, prefijo, al_terminar=None):
    """Subir / previsualizar / guardar / eliminar la firma del usuario.

    al_terminar: callable(mensaje) opcional, ejecutado tras guardar/eliminar y antes
    del rerun (para que la página decida feedback/navegación). Si es None, usa toast.
    """
    servicio = FirmaService()
    firma_actual = servicio.obtener_imagen(usuario_id)

    def _finalizar(mensaje):
        if al_terminar:
            al_terminar(mensaje)
        else:
            st.toast(mensaje)
        st.rerun()

    if firma_actual:
        st.image(firma_actual, caption="Firma registrada", width=240)
        if st.button("🗑️ Eliminar firma", key=f"{prefijo}_del_firma"):
            servicio.eliminar_firma(usuario_id)
            _finalizar("Firma eliminada.")
    else:
        st.caption("No hay firma registrada.")

    archivo = st.file_uploader(
        "Subir firma (PNG/JPG sobre fondo blanco o claro, máx. 5 MB)",
        type=["png", "jpg", "jpeg"], key=f"{prefijo}_up_firma",
    )
    if archivo is not None:
        try:
            png = validar_y_procesar(archivo.name, archivo.getvalue())
            st.markdown("**Vista previa** (los cuadros indican transparencia; si ves un bloque sólido tapándolos, el fondo no se eliminó bien):")
            st.image(componer_sobre_fondo(png), width=240)
            if st.button("💾 Guardar firma", key=f"{prefijo}_save_firma"):
                servicio.guardar_firma(usuario_id, archivo.name, archivo.getvalue(), usuario_actual=actualizado_por)
                _finalizar("Firma guardada correctamente.")
        except ValueError as e:
            st.error(str(e))
