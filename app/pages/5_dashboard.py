import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.core.ui_titulos import mostrar_titulo_decorado

from app.core.autorizacion import validar_permiso, ValidacionAutorizacion
from app.core.sesion import obtener_sesion
from app.core.cache_datos import usuarios_activos_para_seleccion, datos_dashboard_admin, limpiar_cache_lecturas
from app.core.graficos import (
    aplicar_tema, colores_categoricos, color_estado, color_secuencial, hex_a, ESTADO_SEMAFORO,
)

sesion = obtener_sesion()

if not sesion:
    st.warning("Debes iniciar sesión.")
    st.stop()

try:
    validar_permiso(sesion.get("permisos", []), "dashboard.ver")
except ValidacionAutorizacion:
    st.error("No tienes permisos para ver este módulo.")
    st.stop()

oscuro = st.session_state.get("dark_mode", False)

# --- Encabezado ---
col_title, col_btn = st.columns([5, 1])
with col_title:
    mostrar_titulo_decorado("📊 Dashboard de Gestión")
    st.markdown("Métricas clave y gráficos de rendimiento operativo para el control de correspondencia.")
with col_btn:
    st.write("")  # Espaciador para alineación vertical
    st.write("")
    if st.button("🔄 Actualizar", use_container_width=True, key="refresh_dashboard"):
        limpiar_cache_lecturas()
        st.rerun()

st.divider()

# --- Filtros superiores ---
usuarios_map = usuarios_activos_para_seleccion()  # id -> nombre, ya ordenado
opciones_gestores = ["Todos"] + list(usuarios_map.values())
nombre_a_id = {nombre: uid for uid, nombre in usuarios_map.items()}

TIPOS_DASHBOARD = {"Todos": None, "PQRD": "pqrds", "MEMORANDO": "memorandos", "OFICIO": "oficios"}
OPCIONES_ESTADO_DASHBOARD = [
    "Todos", "pendiente", "en_tramite", "en_revision", "respondido", "archivado", "traslado_competencia"
]

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    gestor_seleccionado = st.selectbox(
        "Por usuario gestor",
        options=opciones_gestores,
        index=0,
        key="dashboard_filtro_gestor"
    )

with col_f2:
    tipo_seleccionado = st.selectbox(
        "Por tipo",
        options=list(TIPOS_DASHBOARD.keys()),
        index=0,
        key="dashboard_filtro_tipo"
    )

with col_f3:
    estado_seleccionado = st.selectbox(
        "Por estado",
        options=OPCIONES_ESTADO_DASHBOARD,
        index=0,
        format_func=lambda x: x.replace("_", " ").title(),
        key="dashboard_filtro_estado"
    )

usuario_id_filtro = nombre_a_id.get(gestor_seleccionado) if gestor_seleccionado != "Todos" else None
tipo_id_filtro = TIPOS_DASHBOARD.get(tipo_seleccionado)
estado_id_filtro = None if estado_seleccionado == "Todos" else estado_seleccionado

# --- Carga de datos ---
try:
    datos = datos_dashboard_admin(usuario_id_filtro, tipo_id_filtro, estado_id_filtro)
    resumen = datos["resumen"]
    dist_estado = datos["dist_estado"]
    carga_usuarios = datos["carga_usuarios"]
    vencimientos = datos["vencimientos"]
    tendencia_d = datos["tendencia_d"]
    tiempos_resp = datos["tiempos_resp"]
    conteo_tipo = datos["conteo_tipo"]
    tendencia_m = datos["tendencia_m"]
    por_dia_semana = datos["por_dia_semana"]
    vencidos_resp = datos["vencidos_resp"]
except Exception as e:
    st.error(f"Error al cargar las métricas: {e}")
    st.stop()

# --- 1. Resumen Ejecutivo (KPIs) ---
st.markdown("### 📈 Indicadores Clave de Rendimiento (KPIs)")
m1, m2, m3, m4 = st.columns(4)

vencidos = resumen.get("vencidos_criticos", 0)
ALTURA_KPI = 128
with m1.container(border=True, height=ALTURA_KPI):
    st.metric("Trámites Activos", resumen.get("tramites_activos", 0))
with m2.container(border=True, height=ALTURA_KPI):
    st.metric(
        "Vencidos Críticos",
        vencidos,
        delta=f"{vencidos} hoy" if vencidos > 0 else None,
        delta_color="inverse"
    )
with m3.container(border=True, height=ALTURA_KPI):
    st.metric("Finalizados", resumen.get("tramites_finalizados", 0))
with m4.container(border=True, height=ALTURA_KPI):
    st.metric("% Cumplimiento", f"{resumen.get('porcentaje_cumplimiento', 0)}%")

st.write("")

tab_resumen, tab_vencimientos, tab_tendencias, tab_equipo = st.tabs([
    "🧭 Resumen", "🚨 Vencimientos y Riesgo", "📅 Tendencias", "👥 Equipo",
])

# =====================================================================
# TAB 1 — RESUMEN
# =====================================================================
with tab_resumen:
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.markdown("**📌 Distribución por Estado**")
        if dist_estado is not None and not dist_estado.empty:
            colores = [color_estado(e, oscuro) for e in dist_estado["estado"]]
            fig = go.Figure(go.Pie(
                labels=dist_estado["estado"], values=dist_estado["cantidad"],
                hole=0.55, marker=dict(colors=colores, line=dict(color=("#1a1a19" if oscuro else "#fcfcfb"), width=2)),
                textinfo="label+percent", textposition="outside",
                hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            ))
            total = int(dist_estado["cantidad"].sum())
            fig.add_annotation(text=f"<b>{total}</b><br>radicados", x=0.5, y=0.5, showarrow=False, font=dict(size=15))
            fig.update_layout(showlegend=False)
            aplicar_tema(fig, oscuro, altura=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Sin datos de estados para mostrar.")

    with c2:
        st.markdown("**🗂️ Radicados por Tipo**")
        df_tipo = pd.DataFrame({
            "tipo": ["PQRD", "Memorandos", "Oficios"],
            "cantidad": [conteo_tipo.get("pqrds", 0), conteo_tipo.get("memorandos", 0), conteo_tipo.get("oficios", 0)],
        })
        if df_tipo["cantidad"].sum() > 0:
            fig = go.Figure(go.Pie(
                labels=df_tipo["tipo"], values=df_tipo["cantidad"],
                hole=0.55, marker=dict(colors=colores_categoricos(oscuro)[:3], line=dict(color=("#1a1a19" if oscuro else "#fcfcfb"), width=2)),
                textinfo="label+percent", textposition="outside",
                hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
            ))
            fig.add_annotation(text=f"<b>{int(df_tipo['cantidad'].sum())}</b><br>total", x=0.5, y=0.5, showarrow=False, font=dict(size=15))
            fig.update_layout(showlegend=False)
            aplicar_tema(fig, oscuro, altura=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Sin radicados para mostrar.")

    with c3:
        st.markdown("**✅ % Cumplimiento**")
        valor = resumen.get("porcentaje_cumplimiento", 0)
        color_barra = ESTADO_SEMAFORO["critical"] if valor < 50 else (ESTADO_SEMAFORO["warning"] if valor < 80 else ESTADO_SEMAFORO["good"])
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=valor,
            number={"suffix": "%", "font": {"size": 32}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": ("#c3c2b7" if oscuro else "#898781")},
                "bar": {"color": color_barra},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0, 50], "color": "rgba(208,59,59,0.12)"},
                    {"range": [50, 80], "color": "rgba(250,178,25,0.14)"},
                    {"range": [80, 100], "color": "rgba(12,163,12,0.12)"},
                ],
            },
        ))
        aplicar_tema(fig, oscuro, altura=320)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with st.expander("📋 Ver datos del resumen"):
        st.dataframe(dist_estado, hide_index=True, width="stretch")
        st.dataframe(df_tipo, hide_index=True, width="stretch")

# =====================================================================
# TAB 2 — VENCIMIENTOS Y RIESGO
# =====================================================================
with tab_vencimientos:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**🚦 Semáforo de Vencimientos (Activos)**")
        if vencimientos is not None and not vencimientos.empty and vencimientos["cantidad"].sum() > 0:
            orden = ["Vencidos", "Urgentes (0-5d)", "A Tiempo (>5d)"]
            colores_estado = {"Vencidos": ESTADO_SEMAFORO["critical"], "Urgentes (0-5d)": ESTADO_SEMAFORO["warning"], "A Tiempo (>5d)": ESTADO_SEMAFORO["good"]}
            df_v = vencimientos.set_index("categoria").reindex(orden).reset_index()
            fig = go.Figure(go.Bar(
                x=df_v["categoria"], y=df_v["cantidad"],
                marker_color=[colores_estado[c] for c in df_v["categoria"]],
                text=df_v["cantidad"], textposition="outside",
                hovertemplate="%{x}: %{y}<extra></extra>",
            ))
            fig.update_yaxes(title="Cantidad de radicados")
            aplicar_tema(fig, oscuro, altura=340)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Sin trámites activos en el sistema.")

    with c2:
        st.markdown("**🎯 Responsables con Más Vencidos**")
        if vencidos_resp is not None and not vencidos_resp.empty:
            df_vr = vencidos_resp.sort_values("cantidad", ascending=True)
            fig = go.Figure(go.Bar(
                x=df_vr["cantidad"], y=df_vr["usuario"], orientation="h",
                marker_color=ESTADO_SEMAFORO["critical"],
                text=df_vr["cantidad"], textposition="outside",
                hovertemplate="%{y}: %{x} vencidos<extra></extra>",
            ))
            fig.update_xaxes(title="Radicados vencidos")
            aplicar_tema(fig, oscuro, altura=340)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.success("Sin responsables con radicados vencidos. ✅")

    st.info("💡 Un radicado se considera **vencido** cuando su fecha de vencimiento ya pasó y sigue activo (pendiente, en trámite o en revisión).")

    with st.expander("📋 Ver datos de vencimientos"):
        st.dataframe(vencimientos, hide_index=True, width="stretch")
        st.dataframe(vencidos_resp, hide_index=True, width="stretch")

# =====================================================================
# TAB 3 — TENDENCIAS
# =====================================================================
with tab_tendencias:
    st.markdown("**📅 Tendencia de Radicación Diaria (últimos 30 días)**")
    if tendencia_d is not None and not tendencia_d.empty:
        df_t = tendencia_d.copy()
        df_t["fecha"] = pd.to_datetime(df_t["fecha"])
        df_t["media_movil_7d"] = df_t["radicados"].rolling(window=7, min_periods=1).mean().round(1)
        cat = colores_categoricos(oscuro)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_t["fecha"], y=df_t["radicados"], name="Radicados/día", mode="lines",
            line=dict(color=cat[0], width=2), fill="tozeroy",
            fillcolor=hex_a(cat[0], 0.18),
            hovertemplate="%{x|%d %b %Y}: %{y} radicados<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df_t["fecha"], y=df_t["media_movil_7d"], name="Media móvil 7d", mode="lines",
            line=dict(color=cat[1], width=2, dash="dash"),
            hovertemplate="%{x|%d %b %Y}: %{y} prom. 7d<extra></extra>",
        ))
        fig.update_yaxes(title="Radicados")
        aplicar_tema(fig, oscuro, altura=340)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.info("Sin registros en los últimos 30 días.")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**📊 Radicados vs. Finalizados (últimos 6 meses)**")
        if tendencia_m is not None and not tendencia_m.empty and (tendencia_m["Radicados"].sum() + tendencia_m["Finalizados"].sum()) > 0:
            cat = colores_categoricos(oscuro)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=tendencia_m["mes"], y=tendencia_m["Radicados"], name="Radicados", marker_color=cat[0]))
            fig.add_trace(go.Bar(x=tendencia_m["mes"], y=tendencia_m["Finalizados"], name="Finalizados", marker_color=cat[1]))
            fig.update_layout(barmode="group")
            aplicar_tema(fig, oscuro, altura=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Historial insuficiente en los últimos 6 meses.")

    with c2:
        st.markdown("**🗓️ Radicación por Día de la Semana**")
        if por_dia_semana is not None and not por_dia_semana.empty and por_dia_semana["cantidad"].sum() > 0:
            fig = go.Figure(go.Bar(
                x=por_dia_semana["dia"], y=por_dia_semana["cantidad"],
                marker_color=color_secuencial(oscuro),
                text=por_dia_semana["cantidad"], textposition="outside",
                hovertemplate="%{x}: %{y} radicados<extra></extra>",
            ))
            aplicar_tema(fig, oscuro, altura=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Historial insuficiente para calcular el patrón semanal.")

    with st.expander("📋 Ver datos de tendencias"):
        st.dataframe(tendencia_d, hide_index=True, width="stretch")
        st.dataframe(tendencia_m, hide_index=True, width="stretch")
        st.dataframe(por_dia_semana, hide_index=True, width="stretch")

# =====================================================================
# TAB 4 — EQUIPO
# =====================================================================
with tab_equipo:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**👥 Carga por Responsable (activos)**")
        if carga_usuarios is not None and not carga_usuarios.empty:
            df_c = carga_usuarios.sort_values("cantidad", ascending=True)
            fig = go.Figure(go.Bar(
                x=df_c["cantidad"], y=df_c["usuario"], orientation="h",
                marker_color=color_secuencial(oscuro),
                text=df_c["cantidad"], textposition="outside",
                hovertemplate="%{y}: %{x} radicados activos<extra></extra>",
            ))
            fig.update_xaxes(title="Radicados activos")
            aplicar_tema(fig, oscuro, altura=max(320, 32 * len(df_c)))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("No hay trámites activos asignados actualmente.")

    with c2:
        st.markdown("**⏱️ Tiempo de Respuesta Promedio (Días)**")
        if tiempos_resp is not None and not tiempos_resp.empty:
            cat = colores_categoricos(oscuro)
            fig = go.Figure(go.Bar(
                x=tiempos_resp["Tipo"], y=tiempos_resp["Días Promedio"],
                marker_color=cat[:len(tiempos_resp)],
                text=tiempos_resp["Días Promedio"], textposition="outside",
                hovertemplate="%{x}: %{y} días<extra></extra>",
            ))
            fig.update_yaxes(title="Días promedio")
            aplicar_tema(fig, oscuro, altura=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Historial insuficiente para calcular promedios de tiempo.")

    st.caption("El tiempo de respuesta se calcula desde la fecha de radicación hasta la fecha de la última acción de cierre (respuesta o archivo).")

    with st.expander("📋 Ver datos de equipo"):
        st.dataframe(carga_usuarios, hide_index=True, width="stretch")
        st.dataframe(tiempos_resp, hide_index=True, width="stretch")
