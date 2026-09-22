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

# Inicialización de conexión con Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Funciones auxiliares para leer datos de Google Sheets de forma segura
def cargar_inventario():
    try:
        df = conn.read(worksheet="Inventario", ttl="5s")
        if df.empty or "codigo" not in df.columns:
            return pd.DataFrame(columns=["codigo", "tipo", "marca", "fecha_fab", "estado", "observaciones"])
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=["codigo", "tipo", "marca", "fecha_fab", "estado", "observaciones"])

def cargar_inspecciones():
    try:
        df = conn.read(worksheet="Inspecciones", ttl="5s")
        if df.empty or "Fecha" not in df.columns:
            return pd.DataFrame(columns=["Fecha", "Codigo", "Resultado", "Observaciones"])
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=["Fecha", "Codigo", "Resultado", "Observaciones"])

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# --- NAVEGACIÓN SUPERIOR TIPO TABLA / PESTAÑAS (HIPERVÍNCULOS) ---
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
    df_inv = cargar_inventario()
    
    col1, col2, col3 = st.columns(3)
    total_equipos = len(df_inv)
    conformes = len(df_inv[df_inv["estado"] == "Conforme"]) if total_equipos > 0 else 0
    no_conformes = len(df_inv[df_inv["estado"] == "No Conforme"]) if total_equipos > 0 else 0
        
    col1.metric("Total de Equipos", total_equipos)
    col2.metric("Conformes ✅", conformes)
    col3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual (Sincronizado en la Nube)")
    if total_equipos > 0:
        st.dataframe(df_inv, use_container_width=True)
    else:
        st.info("No hay equipos registrados en la base de datos de Google Sheets. Ve a 'Registrar Equipo' para agregar el primero.")

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
                df_inv = cargar_inventario()
                if codigo in df_inv["codigo"].astype(str).values:
                    st.error(f"El equipo con código {codigo} ya está registrado en la base de datos.")
                else:
                    nuevo_registro = pd.DataFrame([{
                        "codigo": str(codigo),
                        "tipo": tipo,
                        "marca": marca,
                        "fecha_fab": str(fecha_fab),
                        "estado": "Pendiente de Inspección",
                        "observaciones": "Sin inspeccionar"
                    }])
                    
                    df_actualizado = pd.concat([df_inv, nuevo_registro], ignore_index=True)
                    conn.update(worksheet="Inventario", data=df_actualizado)
                    st.success(f"Equipo {codigo} guardado exitosamente en Google Sheets.")
                    st.rerun()
            else:
                st.warning("Por favor completa los campos de Código y Marca / Modelo.")

# 3. INSPECCIÓN PRE-OPERACIONAL
with tab_inspeccion:
    st.header("📋 Inspección Pre-operacional de EPP")
    df_inv = cargar_inventario()
    
    if df_inv.empty:
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
            
            # Actualizar el estado en la pestaña Inventario
            df_inv.loc[df_inv["codigo"].astype(str) == str(codigo_sel), "estado"] = resultado
            df_inv.loc[df_inv["codigo"].astype(str) == str(codigo_sel), "observaciones"] = obs
            conn.update(worksheet="Inventario", data=df_inv)
            
            # Guardar en la pestaña Inspecciones
            df_insp = cargar_inspecciones()
            nueva_insp = pd.DataFrame([{
                "Fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Codigo": str(codigo_sel),
                "Resultado": resultado,
                "Observaciones": obs
            }])
            
            df_insp_actualizado = pd.concat([df_insp, nueva_insp], ignore_index=True)
            conn.update(worksheet="Inspecciones", data=df_insp_actualizado)
            
            if resultado == "Conforme":
                st.success(f"Inspección guardada: CONFORME ✅")
            else:
                st.error(f"Inspección guardada: NO CONFORME ❌. Se requiere retiro de servicio.")
            st.rerun()

# 4. ELIMINAR / GESTIONAR EQUIPO
with tab_gestionar:
    st.header("🗑️ Eliminar Equipo del Inventario")
    df_inv = cargar_inventario()
    
    if df_inv.empty:
        st.info("No hay equipos para eliminar.")
    else:
        lista_codigos = df_inv["codigo"].astype(str).tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código del Equipo a Eliminar", lista_codigos)
        
        st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar el equipo **{codigo_a_eliminar}**?")
        
        if st.button("❌ Confirmar y Eliminar Equipo"):
            df_filtrado = df_inv[df_inv["codigo"].astype(str) != str(codigo_a_eliminar)]
            conn.update(worksheet="Inventario", data=df_filtrado)
            st.success(f"El equipo {codigo_a_eliminar} ha sido eliminado de Google Sheets.")
            st.rerun()

# 5. HISTORIAL
with tab_historial:
    st.header("📜 Historial de Inspecciones")
    df_insp = cargar_inspecciones()
    if not df_insp.empty:
        st.dataframe(df_insp, use_container_width=True)
    else:
        st.info("Aún no se han realizado inspecciones.")

# 6. ASISTENTE IA
with tab_ia:
    st.header("🤖 Asistente Técnico de Inspección (IA)")
    
    pregunta = st.text_input("Consulta norma, criterio de rechazo o especificación técnica:")
    btn_consultar = st.button("Consultar IA")
    
    if btn_consultar:
        if pregunta:
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ No se encontró la etiqueta 'GEMINI_API_KEY' en Secrets de Streamlit.")
                else:
                    api_key = st.secrets["GEMINI_API_KEY"].strip()
                    genai.configure(api_key=api_key)
                    
                    modelos_disponibles = []
                    try:
                        for m in genai.list_models():
                            if 'generateContent' in m.supported_generation_methods:
                                modelos_disponibles.append(m.name)
                    except Exception:
                        pass
                    
                    if not modelos_disponibles:
                        modelos_disponibles = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
                    
                    exito = False
                    ultimo_error = ""
                    for nombre in modelos_disponibles:
                        try:
                            model = genai.GenerativeModel(nombre)
                            response = model.generate_content(
                                f"Eres un inspector experto en Seguridad Industrial y EPP. Responde de forma clara y concisa: {pregunta}"
                            )
                            st.write(response.text)
                            exito = True
                            break
                        except Exception as err:
                            ultimo_error = str(err)
                            continue
                    
                    if not exito:
                        st.error(f"❌ Detalle del error: {ultimo_error}")
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")
        else:
            st.warning("Escribe una consulta primero.")