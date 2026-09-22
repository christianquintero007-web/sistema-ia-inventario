import streamlit as st
import pandas as pd
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# Configuración de la página (Ancho completo)
st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones", 
    page_icon="📦", 
    layout="wide"
)

# Conexión nativa con Google Sheets usando Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos(pestaña):
    try:
        df = conn.read(worksheet=pestaña, ttl="5s")
        return df.dropna(how="all") if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# Navegación Superior por Pestañas
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
    df_inv = cargar_datos("Inventario")
    
    total_equipos = len(df_inv)
    conformes = len(df_inv[df_inv["estado"] == "Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
    no_conformes = len(df_inv[df_inv["estado"] == "No Conforme"]) if total_equipos > 0 and "estado" in df_inv.columns else 0
        
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Equipos", total_equipos)
    c2.metric("Conformes ✅", conformes)
    c3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual (Google Sheets)")
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("No hay equipos registrados en la pestaña 'Inventario' de Google Sheets.")

# 2. REGISTRAR EQUIPO
with tab_registrar:
    st.header("➕ Registrar Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie del Equipo")
        tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Línea de Vida / Lanyard", "Casco", "Mosquetón / Conector", "Cuerda", "Otro"])
        marca = st.text_input("Marca / Modelo")
        fecha_fab = st.date_input("Fecha de Fabricación")
        
        btn_guardar = st.form_submit_button("Guardar en Google Sheets")
        
        if btn_guardar:
            if codigo and marca:
                df_inv = cargar_datos("Inventario")
                
                if not df_inv.empty and "codigo" in df_inv.columns and str(codigo) in df_inv["codigo"].astype(str).values:
                    st.error(f"El equipo con código {codigo} ya está registrado.")
                else:
                    nuevo = pd.DataFrame([{
                        "codigo": str(codigo),
                        "tipo": tipo,
                        "marca": marca,
                        "fecha_fab": str(fecha_fab),
                        "estado": "Pendiente de Inspección",
                        "observaciones": "Sin inspeccionar"
                    }])
                    
                    df_actualizado = pd.concat([df_inv, nuevo], ignore_index=True)
                    conn.update(worksheet="Inventario", data=df_actualizado)
                    st.success(f"Equipo {codigo} registrado con éxito en Google Sheets.")
                    st.rerun()
            else:
                st.warning("Completa los campos requeridos (Código y Marca/Modelo).")

# 3. INSPECCIÓN PRE-OPERACIONAL
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional de EPP")
    df_inv = cargar_datos("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.warning("Primero debes registrar al menos un equipo en el inventario.")
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
            
            # Actualizar estado en Inventario
            df_inv.loc[df_inv["codigo"].astype(str) == str(codigo_sel), "estado"] = resultado
            df_inv.loc[df_inv["codigo"].astype(str) == str(codigo_sel), "observaciones"] = obs
            conn.update(worksheet="Inventario", data=df_inv)
            
            # Registrar en Inspecciones
            df_insp = cargar_datos("Inspecciones")
            nueva_insp = pd.DataFrame([{
                "Fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Codigo": str(codigo_sel),
                "Resultado": resultado,
                "Observaciones": obs
            }])
            
            df_insp_actualizado = pd.concat([df_insp, nueva_insp], ignore_index=True)
            conn.update(worksheet="Inspecciones", data=df_insp_actualizado)
            
            if resultado == "Conforme":
                st.success("Inspección guardada: CONFORME ✅")
            else:
                st.error("Inspección guardada: NO CONFORME ❌.")
            st.rerun()

# 4. ELIMINAR / GESTIONAR EQUIPO
with tab_gestionar:
    st.header("🗑️ Eliminar Equipo del Inventario")
    df_inv = cargar_datos("Inventario")
    
    if df_inv.empty or "codigo" not in df_inv.columns:
        st.info("No hay equipos para eliminar.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código a Eliminar", lista_codigos)
        
        if st.button("❌ Confirmar y Eliminar Equipo"):
            df_filtrado = df_inv[df_inv["codigo"].astype(str) != str(codigo_a_eliminar)]
            conn.update(worksheet="Inventario", data=df_filtrado)
            st.success(f"Equipo {codigo_a_eliminar} eliminado de Google Sheets.")
            st.rerun()

# 5. HISTORIAL
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_datos("Inspecciones")
    if not df_insp.empty:
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no hay inspecciones registradas.")

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
