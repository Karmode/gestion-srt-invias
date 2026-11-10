import streamlit as st

def mostrar_titulo_decorado(titulo: str):
    """
    Renderiza un título decorado con el diseño institucional naranja de INVIAS.
    """
    st.markdown(f"""
        <div style="background-color: #E87A00; color: white; padding: 12px 20px; border-radius: 8px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px;">
            <div style="display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border: 2px solid white; border-radius: 50%;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2L2 12l10 10 10-10L12 2z"></path>
                    <path d="M12 2v20"></path>
                    <path d="M2 12h20"></path>
                </svg>
            </div>
            <div>
                <div style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px;">INVIAS • SRTI</div>
                <div style="font-size: 22px; font-weight: 700; line-height: 1;">{titulo}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
