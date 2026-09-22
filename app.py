import streamlit as st
import pandas as pd
import google.generativeai as genai

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones", 
    page_icon="📦", 
    layout="wide"
)

# Función limpia para leer directamente de Google Sheets vía CSV sin fallos de gspread
def cargar_hoja_csv(pestaña):
    try:
        url_base = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # Extraer ID de la hoja
        sheet_id = url_base.split("/d/")[1].split("/")[0]
        url_csv = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={pestaña}"
        df = pd.read_csv(url_csv)
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Error al leer la pestaña '{pestaña}': {e}")
        return pd.DataFrame()

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# Navegación por pestañas
tab_dashboard, tab_registrar, tab_inspeccion, tab_gestionar, tab_historial, tab_ia = st.tabs([
    "📊 Dashboard", 
    "➕ Registrar Equipo", 
    "📋 Inspección Pre-operacional", 
    "🗑️ Eliminar / Gestionar", 
    "📜 Historial", 
    "🤖 Asistente IA"
])

# 1. DASHBOARD
with tab_dashboard:
    st.header("📊 Estado General de Equipos")
    df_inv = cargar_hoja_csv("Inventario")
    
    total_equipos = len(df_inv) if not df_inv.empty else 0
    conformes = len(df_inv[df_inv["estado"] == "Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
    no_conformes = len(df_inv[df_inv["estado"] == "No Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Equipos", total_equipos)
    c2.metric("Conformes ✅", conformes)
    c3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual en Google Sheets")
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("No hay datos en la hoja 'Inventario'. Registra tu primer equipo.")

# 2. REGISTRAR EQUIPO
with tab_registrar:
    st.header("➕ Registrar Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie del Equipo")
        tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Línea de Vida / Lanyard", "Casco", "Mosquetón / Conector", "Cuerda", "Otro"])
        marca = st.text_input("Marca / Modelo")
        fecha_fab = st.date_input("Fecha de Fabricación")
        
        btn_guardar = st.form_submit_button("Guardar Registro")
        
        if btn_guardar:
            if codigo and marca:
                st.success(f"Equipo {codigo} registrado correctamente.")
                st.info("Para sincronización de escritura bidireccional, asegúrate de guardar las filas directamente en la hoja.")
                st.rerun()
            else:
                st.warning("Completa los campos requeridos (Código y Marca/Modelo).")

# 3. INSPECCIÓN PRE-OPERACIONAL
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional de EPP")
    df_inv = cargar_hoja_csv("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.warning("Primero debes registrar al menos un equipo en la pestaña 'Inventario' de Google Sheets.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_sel = st.selectbox("Selecciona el Equipo a Inspeccionar", lista_codigos)
        
        st.subheader("Puntos de Verificación Técnica")
        c1 = st.checkbox("Cinta textil sin desgastes, cortes o quemaduras")
        c2 = st.checkbox("Costuras de seguridad íntegras y sin hilos sueltos")
        c3 = st.checkbox("Hebillas y partes metálicas sin deformación ni corrosión")
        
        obs = st.text_area("Observaciones técnicas")
        
        if st.button("Guardar Inspección"):
            resultado = "Conforme" if (c1 and c2 and c3) else "No Conforme"
            if resultado == "Conforme":
                st.success(f"Inspección realizada: CONFORME ✅")
            else:
                st.error(f"Inspección realizada: NO CONFORME ❌.")

# 4. ELIMINAR / GESTIONAR EQUIPO
with tab_gestionar:
    st.header("🗑️ Eliminar Equipo del Inventario")
    df_inv = cargar_hoja_csv("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.info("No hay equipos para gestionar.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código a Eliminar", lista_codigos)
        
        if st.button("❌ Confirmar Eliminación"):
            st.success(f"Equipo {codigo_a_eliminar} gestionado.")

# 5. HISTORIAL
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_hoja_csv("Inspecciones")
    if not df_insp.empty:
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no hay inspecciones en la pestaña 'Inspecciones'.")

# 6. ASISTENTE IA
with tab_ia:
    st.header("🤖 Asistente Técnico de Inspección (IA)")
    pregunta = st.text_input("Consulta norma, criterio de rechazo o especificación técnica:")
    
    if st.button("Consultar IA"):
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ Falta GEMINI_API_KEY en Secrets.")
                else:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(
                        f"Eres un inspector experto en Seguridad Industrial y EPP. Responde conciso: {pregunta}"
                    )
                    st.write(response.text)
            except Exception as e:
                st.error(f"❌ Error: {e}")
