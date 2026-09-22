import streamlit as st
import pandas as pd
from datetime import date

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Sistema de Inventario e Inspecciones")

# Inicialización de la base de datos temporal en sesión
if "inventario" not in st.session_state:
    st.session_state.inventario = []

# Menú lateral de navegación
menu = st.sidebar.selectbox(
    "Navegación",
    ["Dashboard", "Registrar Equipo", "Inspección Pre-operacional", "Historial"]
)

# ---------------------------------------------------------
# MÓDULO 1: DASHBOARD
# ---------------------------------------------------------
if menu == "Dashboard":
    st.subheader("📊 Estado General de Equipos")
    
    total = len(st.session_state.inventario)
    conformes = sum(1 for e in st.session_state.inventario if e.get("estado") == "Conforme")
    no_conformes = sum(1 for e in st.session_state.inventario if e.get("estado") == "No Conforme")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Equipos", total)
    col2.metric("Conformes ✅", conformes)
    col3.metric("No Conformes ❌", no_conformes)
    
    st.markdown("---")
    if st.session_state.inventario:
        df = pd.DataFrame(st.session_state.inventario)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay equipos en la base de datos. Ve a 'Registrar Equipo' para agregar el primero.")

# ---------------------------------------------------------
# MÓDULO 2: REGISTRO DE EQUIPOS
# ---------------------------------------------------------
elif menu == "Registrar Equipo":
    st.subheader("📝 Alta de Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            codigo = st.text_input("Código / N° de Serie del Equipo")
            tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Casco", "Línea de Vida / Eslinga", "Mosquetón", "Cuerda", "Otro"])
        with col_b:
            marca = st.text_input("Marca / Modelo")
            fecha_fab = st.date_input("Fecha de Fabricación", value=date.today())
            
        guardar = st.form_submit_button("Guardar en Inventario")
        
        if guardar:
            if codigo:
                st.session_state.inventario.append({
                    "codigo": codigo,
                    "tipo": tipo,
                    "marca": marca,
                    "fecha_fab": str(fecha_fab),
                    "estado": "Pendiente de Inspección",
                    "observaciones": "Sin inspeccionar"
                })
                st.success(f"Equipo {codigo} registrado correctamente.")
            else:
                st.warning("El campo Código / N° de Serie es obligatorio.")

# ---------------------------------------------------------
# MÓDULO 3: INSPECCIÓN PRE-OPERACIONAL
# ---------------------------------------------------------
elif menu == "Inspección Pre-operacional":
    st.subheader("🔍 Check-list de Inspección de Seguridad")
    
    if not st.session_state.inventario:
        st.warning("Debes registrar al menos un equipo en la sección 'Registrar Equipo' antes de realizar una inspección.")
    else:
        codigos = [eq["codigo"] for eq in st.session_state.inventario]
        equipo_sel = st.selectbox("Selecciona el equipo a inspeccionar", codigos)
        
        with st.form("form_inspeccion"):
            st.write("**Puntos de verificación técnica:**")
            c1 = st.checkbox("Estructura libre de cortes, desgaste, fisuras o deformaciones")
            c2 = st.checkbox("Costuras, hebillas, mosquetones y mecanismos de bloqueo operativos")
            c3 = st.checkbox("Etiquetas de identificación y trazabilidad legibles")
            
            obs = st.text_area("Observaciones técnicas o hallazgos")
            
            finalizar = st.form_submit_button("Guardar Inspección")
            
            if finalizar:
                resultado = "Conforme" if (c1 and c2 and c3) else "No Conforme"
                for eq in st.session_state.inventario:
                    if eq["codigo"] == equipo_sel:
                        eq["estado"] = resultado
                        eq["observaciones"] = obs
                
                if resultado == "Conforme":
                    st.success(f"Inspección finalizada. Equipo {equipo_sel}: CONFORME ✅")
                else:
                    st.error(f"Inspección finalizada. Equipo {equipo_sel}: NO CONFORME ❌")

# ---------------------------------------------------------
# MÓDULO 4: HISTORIAL Y EXPORTACIÓN
# ---------------------------------------------------------
elif menu == "Historial":
    st.subheader("📋 Registro Completo")
    if st.session_state.inventario:
        df_historial = pd.DataFrame(st.session_state.inventario)
        st.dataframe(df_historial, use_container_width=True)
    else:
        st.info("Sin registros en el historial.")
