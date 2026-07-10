"""Componentes de UI reutilizables para el balance general del contrato, prórroga y plan de pagos.

Se utilizan tanto en la administración de usuarios (`pages_admin/admin_usuarios.py`)
como en el perfil del contratista (`pages/2_mi_perfil.py`).
"""

import streamlit as st
from datetime import datetime, date

def render_balance_y_pagos(prefijo: str, c: dict, deshabilitado: bool = False):
    """Renderiza el Balance General, Prórroga y el Plan de Pagos interactivo de un contrato.
    
    Devuelve un diccionario con los campos listos para enviar al servicio de actualización.
    """
    c = c or {}
    
    # Inyectar CSS para seguridad adicional, botón rojo y tooltips dinámicos idénticos a los de Información Laboral
    bg_color = "#FFFFFF"
    text_color = "#333333"
    border_color = "#E0E0E0"
    strong_color = "#111111"
    
    st.markdown(
        f"""
        <style>
        /* Ocultar el ícono de enlace (anchor link) y sus contenedores */
        a.header-anchor, [data-testid="stHeaderActionElements"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        /* Hacer el botón toggle de color rojo oscuro/tenue y más compacto */
        button[key*="_btn_toggle_balance"] {{
            background-color: #d32f2f !important;
            background: #d32f2f !important;
            color: white !important;
            font-weight: bold !important;
            padding: 10px 20px !important;
            font-size: 15px !important;
            border-radius: 8px !important;
            border: none !important;
        }}
        button[key*="_btn_toggle_balance"]:hover {{
            background-color: #b71c1c !important;
            background: #b71c1c !important;
        }}
        /* Botón de calculadora con estilo naranja forzado */
        div[data-testid="stPopover"]:has(button[key*="_btn_calc_popover"]) button {{
            background-color: #FF8C00 !important;
            background: #FF8C00 !important;
            color: white !important;
            font-weight: bold !important;
            padding: 6px 12px !important;
            font-size: 13px !important;
            border-radius: 8px !important;
            border: none !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: auto !important;
            width: auto !important;
        }}
        div[data-testid="stPopover"]:has(button[key*="_btn_calc_popover"]) button:hover {{
            background-color: #E07B00 !important;
            background: #E07B00 !important;
        }}
        /* Ocultar la flecha de expandir predeterminada de Streamlit en este popover específico */
        div[data-testid="stPopover"]:has(button[key*="_btn_calc_popover"]) button svg,
        div[data-testid="stPopover"]:has(button[key*="_btn_calc_popover"]) button span[data-testid="stIcon"],
        div[data-testid="stPopover"]:has(button[key*="_btn_calc_popover"]) button span:not(:has([data-testid="stMarkdownContainer"])) {{
            display: none !important;
            visibility: hidden !important;
        }}
        /* Reducir espacio interno de la ventana popover de la calculadora */
        div[data-testid="stPopoverBody"] {{
            padding: 10px !important;
            max-width: 280px !important;
        }}
        div[data-testid="stPopoverBody"] div[data-testid="stWidgetLabel"] p {{
            font-size: 11px !important;
            margin-bottom: -5px !important;
        }}
        div[data-testid="stPopoverBody"] input {{
            height: 28px !important;
            font-size: 12px !important;
        }}
        
        /* Contenedor del Tooltip */
        .srti-tooltip-container {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            font-weight: 500;
            margin-top: 10px;
            margin-bottom: 4px;
            position: relative;
            z-index: 99;
        }}

        .srti-tooltip-container:hover,
        .srti-tooltip-container:focus-within {{
            z-index: 999999 !important;
        }}

        /* Ícono de información */
        .srti-tooltip-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            position: relative;
            cursor: pointer;
            color: #FF8C00;
            font-size: 14px;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background-color: rgba(255, 140, 0, 0.1);
            transition: background-color 0.2s, transform 0.2s;
            user-select: none;
            outline: none;
            z-index: 99999;
            margin-left: 6px;
        }}

        .srti-tooltip-icon:hover, .srti-tooltip-icon:focus {{
            background-color: rgba(255, 140, 0, 0.25);
            transform: scale(1.1);
            z-index: 999999 !important;
        }}

        /* Contenido del Tooltip */
        .srti-tooltip-content {{
            display: none;
            position: absolute;
            top: 125%;
            left: 0;
            transform: none;
            width: 320px; /* Ancho optimizado para evitar desbordes */
            max-width: 90vw;
            background-color: {bg_color} !important;
            color: {text_color} !important;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.08);
            border: 1px solid {border_color};
            z-index: 999999;
            max-height: 450px;
            overflow-y: auto;
            font-size: 13px;
            font-weight: normal;
            line-height: 1.5;
            text-align: left;
            white-space: normal;
        }}

        /* Variante para alinear a la derecha cuando el tooltip está en la última columna */
        .srti-tooltip-container.srti-tooltip-align-right .srti-tooltip-content {{
            left: auto !important;
            right: 0 !important;
        }}

        /* Flecha apuntando hacia arriba */
        .srti-tooltip-content::after {{
            content: "";
            position: absolute;
            bottom: 100%;
            left: 8px;
            transform: none;
            border-width: 6px;
            border-style: solid;
            border-color: transparent transparent {bg_color} transparent;
        }}
        
        /* Flecha para la variante de la derecha */
        .srti-tooltip-container.srti-tooltip-align-right .srti-tooltip-content::after {{
            left: auto !important;
            right: 8px !important;
        }}

        /* Mostrar tooltip al pasar el cursor o hacer focus */
        .srti-tooltip-icon:hover .srti-tooltip-content,
        .srti-tooltip-icon:focus .srti-tooltip-content,
        .srti-tooltip-icon:focus-within .srti-tooltip-content {{
            display: block;
        }}

        /* Estilos de texto en el tooltip */
        .srti-tooltip-content h4 {{
            margin-top: 0;
            margin-bottom: 12px;
            color: #FF8C00 !important;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border-bottom: 1px solid {border_color};
            padding-bottom: 8px;
        }}

        .srti-tooltip-content strong {{
            color: {strong_color} !important;
            background-color: transparent !important;
        }}

        .srti-tooltip-content p {{
            margin-top: 0;
            margin-bottom: 10px;
            color: {text_color} !important;
            background-color: transparent !important;
        }}

        .srti-tooltip-content p:last-child {{
            margin-bottom: 0;
        }}

        /* Forzar que las columnas y bloques de Streamlit permitan ver elementos flotantes sin recorte */
        div[data-testid="column"], div.element-container, div[data-testid="stVerticalBlock"], div[data-testid="stBlock"] {{
            overflow: visible !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Control del estado desplegado/oculto
    show_key = f"{prefijo}_show_balance_general"
    if show_key not in st.session_state:
        st.session_state[show_key] = False
        
    btn_label = "⬇️ Mostrar Balance general y consolidado de pagos" if not st.session_state[show_key] else "⬆️ Ocultar Balance general y consolidado de pagos"
    
    # Botón tipo toggle rojo
    if st.button(btn_label, key=f"{prefijo}_btn_toggle_balance", type="primary", use_container_width=True):
        st.session_state[show_key] = not st.session_state[show_key]
        st.rerun()

    # Si está oculto, devolvemos los valores actuales para que al guardar el formulario no se borren
    if not st.session_state[show_key]:
        return {
            "tiene_inventario": bool(c.get("tiene_inventario")),
            "desc_inventario": c.get("desc_inventario"),
            "valor_total_ejecutado_contrato": c.get("valor_total_ejecutado_contrato"),
            "saldo_presp_lib_contrato": c.get("saldo_presp_lib_contrato"),
            "valor_total_pagado": c.get("valor_total_pagado"),
            "prorrogra_contrato": c.get("prorrogra_contrato") or {"tiene_prorroga": False, "fecha_prorrogra": None, "radicado_prorrogra": None},
            "adiciones_contrato": c.get("adiciones_contrato") or {"tiene_adiciones": False, "valor_adicion": None},
            "pagos": c.get("pagos") or []
        }
        
    st.write("")
    if deshabilitado:
        st.info("⚠️ Este contrato está finalizado. La información de balance, prórroga y pagos está en modo de solo lectura.")

    # Renderizamos el título de la sección y su tooltip dinámico alineado a la derecha (sobresale a la izquierda)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px;">
            <h3 style="margin: 0; padding: 0;">⚖️ Balance general y consolidado de pagos</h3>
            <div class="srti-tooltip-container srti-tooltip-align-right">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>⚖️ Balance general y consolidado de pagos</h4>
                        <p>Este balance de pagos se realizará antes de finalizar el contrato.</p>
                        <p>Se debe ingresar cada uno de los valores presupuestales del contrato que se encontrarán dentro del repositorio de balances antes de finalizar el contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.write("")
    
    # 1. Sección: Inventario con Tooltip alineado a la izquierda (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 10px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">📦 Inventario del Contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>📦 Inventario del Contrato</h4>
                        <p>Esta opción debe marcarse únicamente si al contratista se le asignaron bienes de propiedad de la institución durante la vigencia del contrato.</p>
                        <p><strong>Ejemplo:</strong> Equipos de cómputo (computador portátil/escritorio), periféricos, herramientas de hardware u otros activos institucionales devueltos o por devolver.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    c1, c2 = st.columns([1, 3])
    with c1:
        tiene_inv = st.checkbox(
            "¿Tiene inventario?",
            value=bool(c.get("tiene_inventario")),
            key=f"{prefijo}_tiene_inv",
            disabled=deshabilitado
        )
    with c2:
        desc_inv = None
        if tiene_inv:
            desc_inv = st.text_input(
                "Descripción de inventario (90/max)",
                value=c.get("desc_inventario") or "",
                key=f"{prefijo}_desc_inv",
                placeholder="Ingresa la descripción del inventario...",
                disabled=deshabilitado,
                max_chars=90
            )
            
    # 2. Sección: Valores financieros con Tooltip alineado a la izquierda (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">💵 Balance Financiero</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>💵 Balance Financiero</h4>
                        <p>El contratista deberá registrar el balance financiero de su contrato para poder generar el documento de balance financiero al finalizar el contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Función helper inline para renderizar una etiqueta junto con su tooltip con diseño idéntico
    def render_label_con_tooltip(label: str, tooltip_titulo: str, tooltip_contenido: str, align_right: bool = False):
        align_class = " srti-tooltip-align-right" if align_right else ""
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 14px; font-weight: 500; color: #333333;">{label}</span>
                <div class="srti-tooltip-container{align_class}" style="margin: 0; display: inline-flex;">
                    <span class="srti-tooltip-icon" tabindex="0" style="margin: 0; width: 16px; height: 16px; font-size: 12px;">ⓘ
                        <div class="srti-tooltip-content" style="font-weight: normal;">
                            <h4>{tooltip_titulo}</h4>
                            <p>{tooltip_contenido}</p>
                        </div>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        render_label_con_tooltip(
            "Valor Total Ejecutado del contrato (COP)",
            "Valor total ejecutado del contrato",
            "Es el valor total que se ha ejecutado en los pagos del contrato. Puede ser diferente al valor total del contrato (mayor o menor) según adiciones o reducciones."
        )
        val_total_ejec = st.number_input(
            "label_oculto_total_ejec",
            min_value=0,
            value=int(c.get("valor_total_ejecutado_contrato") or 0),
            step=100000,
            format="%d",
            key=f"{prefijo}_val_total_ejec",
            disabled=deshabilitado,
            label_visibility="collapsed"
        )
    with col2:
        render_label_con_tooltip(
            "Saldo presupuestal a liberar (COP)",
            "Saldo presupuestal a liberar",
            "Es el saldo no ejecutado del contrato. Esta información se remitirá al contratista."
        )
        saldo_presp = st.number_input(
            "label_oculto_saldo_presp",
            min_value=0,
            value=int(c.get("saldo_presp_lib_contrato") or 0),
            step=100000,
            format="%d",
            key=f"{prefijo}_saldo_presp",
            disabled=deshabilitado,
            label_visibility="collapsed"
        )
    with col3:
        render_label_con_tooltip(
            "Valor total pagado del contrato (COP)",
            "Valor total pagado del contrato",
            "Es la sumatoria de todos los pagos realizados en el contrato.",
            align_right=True
        )
        val_tot_pagado = st.number_input(
            "label_oculto_total_pagado",
            min_value=0,
            value=int(c.get("valor_total_pagado") or 0),
            step=100000,
            format="%d",
            key=f"{prefijo}_val_tot_pagado",
            disabled=deshabilitado,
            label_visibility="collapsed"
        )

    # 3. Sección: Prórroga del contrato con Tooltip (sobresale a la derecha)
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">⏳ Prórroga del contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>⏳ Prórroga del contrato</h4>
                        <p>Es la extensión del plazo de vigencia de un contrato.</p>
                        <p>Se debe indicar si tiene una prórroga y, en caso afirmativo, describirla ingresando el radicado o memorando que la valida junto con su fecha de vencimiento.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    prorrogra_c = c.get("prorrogra_contrato") or {}
    
    tiene_pror = st.checkbox(
        "¿Tiene prórroga?",
        value=bool(prorrogra_c.get("tiene_prorroga")),
        key=f"{prefijo}_tiene_pror",
        disabled=deshabilitado
    )
    
    fecha_pror = None
    radicado_pror = None
    if tiene_pror:
        cp1, cp2 = st.columns(2)
        with cp1:
            fecha_pror_val = prorrogra_c.get("fecha_prorrogra")
            if fecha_pror_val and hasattr(fecha_pror_val, "date"):
                fecha_pror_val = fecha_pror_val.date()
            elif isinstance(fecha_pror_val, datetime):
                fecha_pror_val = fecha_pror_val.date()
            
            fecha_pror = st.date_input(
                "Fecha de la prórroga",
                value=fecha_pror_val,
                format="DD/MM/YYYY",
                key=f"{prefijo}_fecha_pror",
                disabled=deshabilitado
            )
        with cp2:
            radicado_pror = st.text_input(
                "Doc. / Des / Radicado de la prórroga",
                value=prorrogra_c.get("radicado_prorrogra") or "",
                key=f"{prefijo}_rad_pror",
                disabled=deshabilitado
            )

    # 3.5 Sección: Adiciones del contrato
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
            <strong style="font-size: 16px; margin: 0; padding: 0;">➕ Adiciones del contrato</strong>
            <div class="srti-tooltip-container" style="margin: 0;">
                <span class="srti-tooltip-icon" tabindex="0">ⓘ
                    <div class="srti-tooltip-content">
                        <h4>Adiciones</h4>
                        <p>Dinero incluido al contrato por cualquier otro medio extra al contrato que incremente la suma total del contrato.</p>
                    </div>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    adiciones_c = c.get("adiciones_contrato") or {}
    tiene_adi = st.checkbox(
        "¿Tiene adiciones?",
        value=bool(adiciones_c.get("tiene_adiciones")),
        key=f"{prefijo}_tiene_adi",
        disabled=deshabilitado
    )
    
    val_adicion = None
    if tiene_adi:
        val_adicion_val = adiciones_c.get("valor_adicion")
        val_adicion = st.number_input(
            "Valor de la adición (COP)",
            min_value=1,
            value=int(val_adicion_val) if (val_adicion_val is not None and val_adicion_val > 0) else 1,
            step=1000,
            key=f"{prefijo}_val_adicion",
            disabled=deshabilitado
        )

    # 4. Sección: Pagos con Tooltip detallado (sobresale a la derecha)
    st.markdown(
        """
<div style="display: flex; align-items: center; gap: 8px; margin-top: 15px; margin-bottom: 5px;">
<strong style="font-size: 16px; margin: 0; padding: 0;">💳 Consolidado de Pagos</strong>
<div class="srti-tooltip-container" style="margin: 0;">
<span class="srti-tooltip-icon" tabindex="0">ⓘ
<div class="srti-tooltip-content" style="width: 400px;">
<h4>💳 Consolidado de Pagos</h4>
<p>El consolidado de pagos se encuentra en el balance enviado previamente al contratista, ya sea por correo electrónico o URL, en el cual deberá copiar y pegar o diligenciar los datos correspondientes a este balance.</p>
<p><strong>Detalles de los campos:</strong></p>
<p><strong>• Número de pago:</strong> Es el número interno del pago que emite Gestión Financiera.</p>
<p><strong>• Fecha de pago:</strong> Es la fecha de realización del pago, se encuentra en la base de datos entregada.</p>
<p><strong>• Deducciones:</strong> Las deducciones son descuentos o reducciones aplicadas al contrato. Deberá colocar lo que indica el balance enviado para ese pago.</p>
<p><strong>• Valor neto:</strong> Será el valor del pago correspondiente a ese mes, este valor deberá ser exacto según la información enviada al contratista.</p>
</div>
</span>
</div>
</div>
        """,
        unsafe_allow_html=True
    )
    pagos_lista = c.get("pagos") or []
    
    pagos_ids_key = f"{prefijo}_pagos_ids"
    pagos_seq_key = f"{prefijo}_pagos_seq"
    pagos_datos_key = f"{prefijo}_pagos_datos"

    # Inicialización del estado de los pagos si no existe. Los valores viven en
    # un espejo programático (pagos_datos_key) además de las claves de widget:
    # Streamlit borra las claves de widget cuando la sección no se renderiza
    # (navegar a otra página, o un st.rerun() que interrumpe el run antes de
    # dibujar la fila); el espejo sobrevive y permite re-sembrarlas. Sin él,
    # las filas quedaban en cero y el siguiente guardado sobreescribía los
    # pagos en la BD.
    if pagos_ids_key not in st.session_state:
        st.session_state[pagos_seq_key] = 0
        pagos_ids = []
        pagos_datos = {}
        for p in pagos_lista:
            pid = st.session_state[pagos_seq_key]
            st.session_state[pagos_seq_key] += 1
            pagos_ids.append(pid)

            f_p = p.get("fecha_pago")
            if f_p and hasattr(f_p, "date"):
                f_p = f_p.date()

            pagos_datos[pid] = {
                "num": p.get("numero_pago") or "",
                "fec": f_p,
                "bruto": int(p.get("valor_bruto_pago") or 0),
                "deduc": int(p.get("deducciones_pago") or 0),
                "neto": int(p.get("valor_neto_pago") or 0),
            }
        st.session_state[pagos_ids_key] = pagos_ids
        st.session_state[pagos_datos_key] = pagos_datos

    pids = st.session_state[pagos_ids_key]
    pagos_datos = st.session_state[pagos_datos_key]

    # Re-sembrar desde el espejo toda clave de widget que Streamlit haya limpiado.
    for pid in pids:
        fila = pagos_datos.get(pid) or {"num": "", "fec": date.today(), "bruto": 0, "deduc": 0, "neto": 0}
        for campo, sufijo in (("num", "num"), ("fec", "fec"), ("bruto", "bruto"), ("deduc", "deduc"), ("neto", "neto")):
            clave = f"{prefijo}_pago_{sufijo}_{pid}"
            if clave not in st.session_state:
                st.session_state[clave] = fila[campo]
    
    # Botón para añadir pago (límite 20)
    col_btn_add, _ = st.columns([1, 3])
    with col_btn_add:
        if len(pids) < 20:
            if st.button("➕ Agregar pago", key=f"{prefijo}_btn_add_pago", use_container_width=True, disabled=deshabilitado):
                new_id = st.session_state[pagos_seq_key]
                st.session_state[pagos_seq_key] += 1
                
                # Valores por defecto para el nuevo pago (vía espejo; las
                # claves de widget se siembran arriba en el próximo render)
                pagos_datos[new_id] = {
                    "num": f"Pago No. {len(pids) + 1}",
                    "fec": date.today(),
                    "bruto": 0,
                    "deduc": 0,
                    "neto": 0,
                }
                st.session_state[pagos_ids_key].append(new_id)
                st.rerun()
        else:
            if not deshabilitado:
                st.warning("Se ha alcanzado el límite máximo de 20 pagos para este contrato.")
            
    # Renderizado de los pagos en filas individuales
    pagos_retorno = []
    for index, pid in enumerate(pids):
        st.markdown(f"**Pago #{index + 1}**")
        
        # Fila de Inputs
        r1, r2, r3 = st.columns(3)
        with r1:
            num_pago = st.text_input("Número de Pago", key=f"{prefijo}_pago_num_{pid}", disabled=deshabilitado)
        with r2:
            fecha_pago = st.date_input("Fecha de Pago", key=f"{prefijo}_pago_fec_{pid}", format="DD/MM/YYYY", disabled=deshabilitado)
        with r3:
            val_bruto = st.number_input("Valor Bruto", min_value=0, step=10000, key=f"{prefijo}_pago_bruto_{pid}", disabled=deshabilitado)
            
        r5, r6, col_del = st.columns([3, 3, 2])
        with r5:
            deduc = st.number_input("Deducciones", min_value=0, step=10000, key=f"{prefijo}_pago_deduc_{pid}", disabled=deshabilitado)
        with r6:
            val_neto = st.number_input("Valor Neto", min_value=0, step=10000, key=f"{prefijo}_pago_neto_{pid}", disabled=deshabilitado)
        with col_del:
            st.write("")  # Espaciado para alinear con el botón
            if st.button("🗑️ Eliminar pago", key=f"{prefijo}_pago_del_{pid}", type="secondary", use_container_width=True, disabled=deshabilitado):
                st.session_state[pagos_ids_key].remove(pid)
                pagos_datos.pop(pid, None)
                st.rerun()
                
        st.markdown("---")

        # Actualizar el espejo con lo tecleado en este render.
        pagos_datos[pid] = {"num": num_pago, "fec": fecha_pago, "bruto": val_bruto, "deduc": deduc, "neto": val_neto}

        # Guardaremos provisionalmente los acumulados como None o 0 por pago, pues los ingresará globalmente
        pagos_retorno.append({
            "numero_pago": num_pago,
            "fecha_pago": fecha_pago,
            "valor_bruto_pago": val_bruto,
            "valor_bruto_total": 0,
            "deducciones_pago": deduc,
            "deducciones_pago_total": 0,
            "valor_neto_pago": val_neto,
            "valor_neto_pago_total": 0,
        })
        
    # Fila de Totales Estilizada y MANUAL debajo de la barra divisoria con Tooltip
    st.markdown("<hr style='margin:15px 0; border: 1.5px solid #FF8C00;'>", unsafe_allow_html=True)
    st.markdown(
        """
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
<strong style="font-size: 16px; margin: 0; padding: 0;">📊 TOTALES GENERALES DEL CONTRATO</strong>
<div class="srti-tooltip-container" style="margin: 0;">
<span class="srti-tooltip-icon" tabindex="0">ⓘ
<div class="srti-tooltip-content" style="width: 380px;">
<h4>📊 TOTALES GENERALES DEL CONTRATO</h4>
<p>El contratista debe sumar todos los valores brutos acumulados, todas las deducciones totales acumuladas y el valor neto acumulado en los pagos e ingresar el valor.</p>
<p>El proceso no es automático, dada la variabilidad de estos valores según el contratista.</p>
</div>
</span>
</div>
</div>
        """,
        unsafe_allow_html=True
    )
    
    # Inferir o inicializar valores del primer pago o del contrato en general
    # Para cumplir con el esquema MongoDB, guardaremos los totales generales en las propiedades '..._total' de cada pago de la lista
    val_bruto_tot_inicial = int(pagos_lista[0].get("valor_bruto_total") or 0) if pagos_lista else 0
    deduc_tot_inicial = int(pagos_lista[0].get("deducciones_pago_total") or 0) if pagos_lista else 0
    neto_tot_inicial = int(pagos_lista[0].get("valor_neto_pago_total") or 0) if pagos_lista else 0
    
    t1, t2, t3 = st.columns(3)
    with t1:
        acum_bruto_total = st.number_input(
            "Valor Bruto Total (Acumulado)",
            min_value=0,
            step=100000,
            value=val_bruto_tot_inicial,
            key=f"{prefijo}_val_bruto_tot_global",
            disabled=deshabilitado
        )
    with t2:
        acum_deduc_total = st.number_input(
            "Deducciones Total (Acumulado)",
            min_value=0,
            step=100000,
            value=deduc_tot_inicial,
            key=f"{prefijo}_pago_deduc_tot_global",
            disabled=deshabilitado
        )
    with t3:
        acum_neto_total = st.number_input(
            "Valor Neto Total (Acumulado)",
            min_value=0,
            step=100000,
            value=acum_bruto_total - acum_deduc_total if acum_bruto_total > acum_deduc_total else neto_tot_inicial,
            key=f"{prefijo}_pago_neto_tot_global",
            disabled=deshabilitado
        )
    # Botón de calculadora popover debajo de los inputs de totales
    c_col1, c_col2 = st.columns([1.2, 4])
    with c_col1:
        with st.popover("🧮 Calculadora", key=f"{prefijo}_btn_calc_popover", use_container_width=True):
            st.markdown("<h4 style='margin:0; padding-bottom:10px; color:#FF8C00;'>🧮 Calculadora Rápida</h4>", unsafe_allow_html=True)
            calc_v1 = st.number_input("Valor A (COP)", min_value=0, step=10000, key=f"{prefijo}_calc_val_a")
            calc_op = st.selectbox("Operación", ["+", "-", "*", "/"], key=f"{prefijo}_calc_oper")
            calc_v2 = st.number_input("Valor B (COP)", min_value=0, step=10000, key=f"{prefijo}_calc_val_b")
            
            res_val = 0
            if calc_op == "+":
                res_val = calc_v1 + calc_v2
            elif calc_op == "-":
                res_val = calc_v1 - calc_v2
            elif calc_op == "*":
                res_val = calc_v1 * calc_v2
            elif calc_op == "/" and calc_v2 != 0:
                res_val = calc_v1 / calc_v2
                
            res_entero = int(res_val)
            
            # Autocopiador HTML renderizado usando st.components.v1.html para aislamiento correcto en sandbox de Streamlit
            import streamlit.components.v1 as components
            components.html(
                f"""
                <div style="font-family:sans-serif; background-color:#E8F5E9; border-radius:8px; padding:8px 12px; border:1px solid #C8E6C9; display:flex; align-items:center; justify-content:between;">
                    <span style="font-weight:bold; color:#2E7D32; font-size:13px; flex-grow:1;">Resultado: {res_entero}</span>
                    <button
                        onclick='navigator.clipboard.writeText("{res_entero}").then(() => {{ this.innerText = "✅"; setTimeout(() => this.innerText = "📋", 1000); }})'
                        style="border:1px solid #A5D6A7; border-radius:4px; width:26px; height:26px; background:#fff; cursor:pointer; font-size:12px; display:inline-flex; align-items:center; justify-content:center;"
                        title="Copiar resultado"
                    >📋</button>
                </div>
                """,
                height=48
            )
            st.caption("Usa esta ventana flotante para hacer tus sumas manuales de forma rápida. Haz clic en el botón de la derecha para copiar el resultado.")

    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)

    # Inyectamos los totales del contrato ingresados por el usuario en cada uno de los elementos de pagos para que la base de datos valide correctamente
    for p in pagos_retorno:
        p["valor_bruto_total"] = acum_bruto_total
        p["deducciones_pago_total"] = acum_deduc_total
        p["valor_neto_pago_total"] = acum_neto_total
        
    return {
        "tiene_inventario": tiene_inv,
        "desc_inventario": desc_inv if tiene_inv else None,
        "valor_total_ejecutado_contrato": val_total_ejec,
        "saldo_presp_lib_contrato": saldo_presp,
        "valor_total_pagado": val_tot_pagado,
        "prorrogra_contrato": {
            "tiene_prorroga": tiene_pror,
            "fecha_prorrogra": fecha_pror if tiene_pror else None,
            "radicado_prorrogra": radicado_pror if tiene_pror else None
        },
        "adiciones_contrato": {
            "tiene_adiciones": tiene_adi,
            "valor_adicion": val_adicion if tiene_adi else None
        },
        "pagos": pagos_retorno
    }

def limpiar_estado_balance_pagos(prefijo: str):
    """Limpia el estado de sesión para el balance de pagos de un prefijo dado."""
    for key in list(st.session_state.keys()):
        if key.startswith(f"{prefijo}_"):
            del st.session_state[key]
