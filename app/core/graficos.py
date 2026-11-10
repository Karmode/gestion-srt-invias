"""Theming y paleta compartida para gráficos Plotly del dashboard.

Paleta categórica validada (contraste + daltonismo) — ver skill de dataviz.
No reordenar los slots: el orden es lo que garantiza la separación CVD.
"""

# Slots categóricos en orden fijo (no ciclar, no reordenar).
PALETA_CATEGORICA = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}

# Colores de estado reservados (semáforo) — nunca reutilizados como serie.
ESTADO_SEMAFORO = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}

# Mapa fijo estado_actual (etiqueta title-case) -> slot categórico.
COLOR_POR_ESTADO = {
    "Pendiente": 1,       # orange
    "En Tramite": 0,      # blue
    "En Revision": 2,     # aqua
    "Respondido": 5,      # green
    "Archivado": 6,       # violet
    "Traslado Competencia": 3,  # yellow
}

SUPERFICIE = {"light": "#fcfcfb", "dark": "#1a1a19"}
TINTA_PRIMARIA = {"light": "#0b0b0b", "dark": "#ffffff"}
TINTA_SECUNDARIA = {"light": "#52514e", "dark": "#c3c2b7"}
TINTA_MUTED = {"light": "#898781", "dark": "#898781"}
GRIDLINE = {"light": "#e1e0d9", "dark": "#2c2c2a"}

FUENTE = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def modo(oscuro: bool) -> str:
    return "dark" if oscuro else "light"


def colores_categoricos(oscuro: bool) -> list:
    return PALETA_CATEGORICA[modo(oscuro)]


def color_estado(etiqueta: str, oscuro: bool) -> str:
    slot = COLOR_POR_ESTADO.get(etiqueta, 7)
    return PALETA_CATEGORICA[modo(oscuro)][slot]


def color_secuencial(oscuro: bool) -> str:
    """Hue único para magnitud de una sola serie (barras, no gradiente)."""
    return PALETA_CATEGORICA[modo(oscuro)][0]


def hex_a(color_hex: str, alpha: float) -> str:
    """Convierte '#rrggbb' a 'rgba(r,g,b,alpha)' para rellenos semitransparentes."""
    color_hex = color_hex.lstrip("#")
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def aplicar_tema(fig, oscuro: bool, altura: int = 320):
    """Aplica layout consistente (superficie, tipografía, grid) a cualquier figura Plotly."""
    m = modo(oscuro)
    fig.update_layout(
        height=altura,
        paper_bgcolor=SUPERFICIE[m],
        plot_bgcolor=SUPERFICIE[m],
        font=dict(family=FUENTE, color=TINTA_PRIMARIA[m], size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TINTA_SECUNDARIA[m])),
        hoverlabel=dict(bgcolor=SUPERFICIE[m], font=dict(family=FUENTE, color=TINTA_PRIMARIA[m])),
        colorway=colores_categoricos(oscuro),
    )
    fig.update_xaxes(
        gridcolor=GRIDLINE[m], zerolinecolor=GRIDLINE[m],
        tickfont=dict(color=TINTA_MUTED[m]), title_font=dict(color=TINTA_SECUNDARIA[m]),
    )
    fig.update_yaxes(
        gridcolor=GRIDLINE[m], zerolinecolor=GRIDLINE[m],
        tickfont=dict(color=TINTA_MUTED[m]), title_font=dict(color=TINTA_SECUNDARIA[m]),
    )
    return fig
