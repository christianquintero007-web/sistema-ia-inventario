import streamlit as st
import pandas as pd
import google.generativeai as genai

# Configuración de la página
st.set_page_config(page_title="Sistema de Inventario e Inspecciones", page_icon="📦", layout="wide")

# Inicializar bases de datos en sesión
if "inventario" not in st.session_state:
    st.session_state.inventario = pd.DataFrame(columns=["Codigo", "Tipo", "Marca_Modelo", "Fecha_Fab"])

if "inspecciones" not in st.session_state:
    st.session_state.inspecciones = pd.DataFrame(columns=["Fecha", "Codigo", "Cinta_Textil", "Costuras", "Hebillas", "Observaciones", "Resultado"])

# Título Principal
st.title("📦 Sistema de Inventario e Inspecciones")

# Menú Lateral
menu = st.sidebar.selectbox(
    "Navegación", 
    ["Dashboard", "Registrar Equipo", "Inspección Pre-operacional", "Eliminar / Gestionar Equipo", "Historial", "Asistente IA"]
)

# 1. DASHBOARD
if menu == "Dashboard":
    st.header("📊 Estado General de Equipos")
    
    col1, col2, col3 = st.columns(3)
    total_equipos = len(st.session_state.inventario)
    
    if len(st.session_state.inspecciones) > 0:
        conformes = len(st.session_state.inspecciones[st.session_state.inspecciones["Resultado"] == "CONFORME ✅"])
        no_conformes = len(st.session_state.inspecciones[st.session_state.inspecciones["Resultado"] == "NO CONFORME ❌"])
    else:
        conformes = 0
        no_conformes = 0
        
    col1.metric("Total de Equipos", total_equipos)
    col2.metric("Conformes ✅", conformes)
    col3.metric("No Conformes ❌", no_conformes)
    
    st.divider()
    st.subheader("Inventario Actual")
    if not st.session_state.inventario.empty:
        st.dataframe(st.session_state.inventario, use_container_width=True)
    else:
        st.info("No hay equipos en la base de datos. Ve a 'Registrar Equipo' para agregar el primero.")

# 2. REGISTRAR EQUIPO
elif menu == "Registrar Equipo":
    st.header("➕ Registrar Nuevo Equipo / EPP")
    
    with st.form("form_registro", clear_on_submit=True):
        codigo = st.text_input("Código / N° de Serie del Equipo")
        tipo = st.selectbox("Tipo de Equipo", ["Arnés", "Línea de Vida / Lanyard", "Casco", "Mosquetón / Conector", "Cuerda", "Otro"])
        marca = st.text_input("Marca / Modelo")
        fecha_fab = st.date_input("Fecha de Fabricación")
        
        btn_guardar = st.form_submit_button("Guardar en Inventario")
        
        if btn_guardar:
            if codigo and marca:
                # Verificar si ya existe
                if codigo in st.session_state.inventario["Codigo"].values:
                    st.error(f"El equipo con código {codigo} ya está registrado.")
                else:
                    nuevo_registro = pd.DataFrame([{
                        "Codigo": codigo,
                        "Tipo": tipo,
                        "Marca_Modelo": marca,
                        "Fecha_Fab": str(fecha_fab)
                    }])
                    st.session_state.inventario = pd.concat([st.session_state.inventario, nuevo_registro], ignore_index=True)
                    st.success(f"Equipo {codigo} registrado correctamente.")
            else:
                st.warning("Por favor completa los campos de Código y Marca / Modelo.")

# 3. INSPECCIÓN PRE-OPERACIONAL
elif menu == "Inspección Pre-operacional":
    st.header("📋 Inspección Pre-operacional de EPP")
    
    if st.session_state.inventario.empty:
        st.warning("Primero debes registrar al menos un equipo en el inventario.")
    else:
        lista_codigos = st.session_state.inventario["Codigo"].tolist()
        codigo_sel = st.selectbox("Selecciona el Equipo a Inspeccionar", lista_codigos)
        
        st.subheader("Puntos de Verificación Técnica")
        c1 = st.checkbox("Cinta textil sin desgastes, cortes o quemaduras")
        c2 = st.checkbox("Costuras de seguridad integras y sin hilos sueltos")
        c3 = st.checkbox("Hebillas y partes metálicas sin deformación ni corrosión")
        
        obs = st.text_area("Observaciones técnicas")
        
        if st.button("Guardar Inspección"):
            resultado = "CONFORME ✅" if (c1 and c2 and c3) else "NO CONFORME ❌"
            
            nueva_inspeccion = pd.DataFrame([{
                "Fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Codigo": codigo_sel,
                "Cinta_Textil": "OK" if c1 else "FALLA",
                "Costuras": "OK" if c2 else "FALLA",
                "Hebillas": "OK" if c3 else "FALLA",
                "Observaciones": obs,
                "Resultado": resultado
            }])
            st.session_state.inspecciones = pd.concat([st.session_state.inspecciones, nueva_inspeccion], ignore_index=True)
            
            if resultado == "CONFORME ✅":
                st.success(f"Inspección guardada: {resultado}")
            else:
                st.error(f"Inspección guardada: {resultado}. Se requiere retiro de servicio.")

# 4. ELIMINAR / GESTIONAR EQUIPO
elif menu == "Eliminar / Gestionar Equipo":
    st.header("🗑️ Eliminar Equipo del Inventario")
    
    if st.session_state.inventario.empty:
        st.info("No hay equipos para eliminar.")
    else:
        lista_codigos = st.session_state.inventario["Codigo"].tolist()
        codigo_a_eliminar = st.selectbox("Selecciona el Código del Equipo a Eliminar", lista_codigos)
        
        st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar el equipo **{codigo_a_eliminar}**?")
        
        if st.button("❌ Confirmar y Eliminar Equipo"):
            # Eliminar del inventario
            st.session_state.inventario = st.session_state.inventario[st.session_state.inventario["Codigo"] != codigo_a_eliminar]
            st.success(f"El equipo {codigo_a_eliminar} ha sido eliminado correctamente del inventario.")

# 5. HISTORIAL
elif menu == "Historial":
    st.header("📜 Historial de Inspecciones")
    if not st.session_state.inspecciones.empty:
        st.dataframe(st.session_state.inspecciones, use_container_width=True)
    else:
        st.info("Aún no se han realizado inspecciones.")

# 6. ASISTENTE IA
elif menu == "Asistente IA":
    st.header("🤖 Asistente Técnico de Inspección (IA)")
    
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        pregunta = st.text_input("Consulta norma, criterio de rechazo o especificación técnica:")
        
        if st.button("Consultar IA"):
            if pregunta:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(
                    f"Eres un inspector experto en Seguridad Industrial y EPP. Responde de forma clara y concisa: {pregunta}"
                )
                st.write(response.text)
            else:
                st.warning("Escribe una consulta primero.")
    except Exception as e:
        st.error("No se pudo conectar con la IA. Verifica que tu API KEY esté guardada en los Secrets de Streamlit.")
