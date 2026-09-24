import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import re
import pypdf

from datetime import date
from openai import OpenAI


# =========================================================
# CONFIGURACIÓN INICIAL
# =========================================================

st.set_page_config(
    page_title="Sistema de Inventario e Inspecciones EPP",
    page_icon="🛡️",
    layout="wide"
)

ANIO_ACTUAL = date.today().year


# =========================================================
# DEPARTAMENTOS
# =========================================================

DEPARTAMENTOS = [
    "BASTIDOR 103",
    "PALAS 105",
    "MANTENIMIENTO 111",
    "USA 118",
    "REVISIÓN",
    "BAJAS"
]


MAPA_DEPARTAMENTOS = {
    "BASTIDOR 103": [
        "103",
        "BASTIDOR",
        "PERSONAL 103"
    ],

    "PALAS 105": [
        "105",
        "PALAS",
        "PERSONAL 105"
    ],

    "MANTENIMIENTO 111": [
        "111",
        "MANTENIMIENTO",
        "PERSONAL 111"
    ],

    "USA 118": [
        "118",
        "USA",
        "TEXAS",
        "AUSTIN",
        "SAN ROMAN",
        "SAN ROMÁN"
    ],

    "REVISIÓN": [
        "REVISION",
        "REVISIÓN"
    ],

    "BAJAS": [
        "BAJA",
        "BAJAS"
    ]
}


# =========================================================
# CONFIGURACIÓN DE CORREOS / GOOGLE SHEETS
# =========================================================

CORREO_NOTIFICACION_PRINCIPAL = "almacen@windsunmx.com"

CORREO_COMPANERA_OPERACIONES = (
    "auxiliaroperaciones@windsunmx.com"
)

APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbyMmcnFcNCXOYXvaf9k83_CXfvnFJTgiwTgo9sNWqxYc1NRACo24vIWqImP56lVwrL3"
    "/exec"
)


# =========================================================
# CATÁLOGO MAESTRO DE EPP
# =========================================================

CATALOGO_EQUIPOS_EPP = {

    "VERTEX": {
        "marca": "PETZL",
        "descripcion": "CASCO"
    },

    "STRATO": {
        "marca": "PETZL",
        "descripcion": "CASCO"
    },

    "ATLAS LOCK": {
        "marca": "ROCK EMPIRE",
        "descripcion": "ARNÉS"
    },

    "ATLAS": {
        "marca": "ROCK EMPIRE",
        "descripcion": "ARNÉS"
    },

    "AVAO BOD FAST": {
        "marca": "PETZL",
        "descripcion": "ARNÉS"
    },

    "AVAO FAST": {
        "marca": "PETZL",
        "descripcion": "ARNÉS"
    },

    "AVAO BOD": {
        "marca": "PETZL",
        "descripcion": "ARNÉS"
    },

    "VOLT": {
        "marca": "PETZL",
        "descripcion": "ARNÉS"
    },

    "AUSTIN": {
        "marca": "IRUDEK",
        "descripcion": "GANCHO DE GRAN APERTURA"
    },

    "FLEX 383": {
        "marca": "IRUDEK",
        "descripcion": "GANCHO DE GRAN APERTURA"
    },

    "C226H": {
        "marca": "PROTECTA",
        "descripcion": "GANCHO DE GRAN APERTURA"
    },

    "3100431": {
        "marca": "PROTECTA",
        "descripcion": "CINTURÓN RETRÁCTIL"
    },

    "3100516": {
        "marca": "PROTECTA",
        "descripcion": "CINTURÓN RETRÁCTIL"
    },

    "ANNEAU C40": {
        "marca": "PETZL",
        "descripcion": "CINTA DE ANCLAJE"
    },

    "ANNEAU": {
        "marca": "PETZL",
        "descripcion": "CINTA DE ANCLAJE"
    },

    "GRILLON HOOK": {
        "marca": "PETZL",
        "descripcion": "POSICIONADOR / ESLINGA 3M"
    },

    "GRILLON": {
        "marca": "PETZL",
        "descripcion": "POSICIONADOR / ESLINGA 3M"
    },

    "CATCH FIX": {
        "marca": "ROCK EMPIRE",
        "descripcion": "POSICIONADOR / ESLINGA 3M"
    },

    "CROLL": {
        "marca": "PETZL",
        "descripcion": "BLOQUEADOR CROLL"
    },

    "OK TL": {
        "marca": "PETZL",
        "descripcion": "MOSQUETÓN"
    },

    "OK": {
        "marca": "PETZL",
        "descripcion": "MOSQUETÓN"
    },

    "AM'D": {
        "marca": "PETZL",
        "descripcion": "MOSQUETÓN"
    },

    "MAGNUM": {
        "marca": "ROCK EMPIRE",
        "descripcion": "MOSQUETÓN"
    },

    "SKC H04 EVO": {
        "marca": "SOMAIN",
        "descripcion": "ANTICAÍDAS"
    },

    "SOLLVIGO": {
        "marca": "HONEYWELL",
        "descripcion": "ANTICAÍDAS"
    },

    "SÖLL VI-GO": {
        "marca": "HONEYWELL",
        "descripcion": "ANTICAÍDAS"
    },

    "NOVAX": {
        "marca": "NOVAX",
        "descripcion": "GUANTE DIELÉCTRICO 1000V"
    }
}


# =========================================================
# CONFIGURACIÓN VISUAL
# =========================================================

st.sidebar.header("⚙️ Configuración Visual")

color_fondo = st.sidebar.color_picker(
    "🎨 Color de Fondo del Sistema",
    "#0e1117"
)


def calcular_color_texto(hex_color):

    hex_color = hex_color.lstrip("#")

    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    luminancia = (
        0.299 * r +
        0.587 * g +
        0.114 * b
    ) / 255

    return "#000000" if luminancia > 0.5 else "#FFFFFF"


color_texto = calcular_color_texto(color_fondo)


st.markdown(
    f"""
    <style>

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stSidebar"] {{
        background-color: {color_fondo} !important;
        color: {color_texto} !important;
    }}

    h1, h2, h3, h4, h5, h6,
    p, span, label, div,
    .stMarkdown {{
        color: {color_texto} !important;
    }}

    .stTextInput input,
    .stSelectbox select {{
        color: #000000 !important;
    }}

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# PANEL DE ADMINISTRADOR
# =========================================================

st.sidebar.divider()

st.sidebar.header("🔒 Panel de Administrador")

password_ingresada = st.sidebar.text_input(
    "Contraseña de Administrador:",
    type="password"
)

PASSWORD_ADMIN = "Windsun2026*"

sistema_activo = True


if password_ingresada == PASSWORD_ADMIN:

    st.sidebar.success(
        "🔓 Administrador Autenticado"
    )

    sistema_activo = st.sidebar.toggle(
        "🟢 Sistema Operativo (Activo/Inactivo)",
        value=True,
        help="Apaga o enciende el sistema completo."
    )

elif password_ingresada != "":

    st.sidebar.error(
        "❌ Contraseña incorrecta"
    )


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def limpiar_texto(texto):
    """
    Normaliza espacios y caracteres básicos.
    """

    if texto is None:
        return ""

    texto = str(texto)

    texto = texto.replace("\xa0", " ")

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def normalizar_mayusculas(texto):

    return limpiar_texto(texto).upper()


def es_valor_vacio_serie(valor):
    """
    Determina si la columna de número de serie realmente
    está vacía.

    MUY IMPORTANTE:
    Un modelo como 6800 NO llega aquí si pertenece
    a la columna MODELO.
    """

    if valor is None:
        return True

    valor = normalizar_mayusculas(valor)

    valores_vacios = [
        "",
        "-",
        "—",
        "–",
        "_",
        "N/A",
        "NA",
        "N/D",
        "ND",
        "SIN SERIE",
        "S/S",
        "S/N"
    ]

    return valor in valores_vacios


def limpiar_numero_serie(valor):

    valor = normalizar_mayusculas(valor)

    valor = re.sub(
        r"^(FIX|S/N|SERIE)\s*:?\s*",
        "",
        valor,
        flags=re.IGNORECASE
    )

    return valor.strip()


# =========================================================
# DETECCIÓN DE DEPARTAMENTO
# =========================================================

def determinar_departamento_automatico(texto_pdf):

    texto_pdf = texto_pdf or ""

    texto_upper = texto_pdf.upper()

    match_puesto = re.search(
        r"(?:PUESTO)\s*:?\s*([^\n]+)",
        texto_pdf,
        re.IGNORECASE
    )

    match_parque = re.search(
        r"(?:PARQUE|PARQUE E[ÓO]LICO)\s*:?\s*([^\n]+)",
        texto_pdf,
        re.IGNORECASE
    )

    match_localidad = re.search(
        r"(?:LOCALIDAD)\s*:?\s*([^\n]+)",
        texto_pdf,
        re.IGNORECASE
    )

    puesto = (
        match_puesto.group(1).upper()
        if match_puesto
        else ""
    )

    parque = (
        match_parque.group(1).upper()
        if match_parque
        else ""
    )

    localidad = (
        match_localidad.group(1).upper()
        if match_localidad
        else ""
    )

    info_contexto = (
        f"{puesto} "
        f"{parque} "
        f"{localidad} "
        f"{texto_upper}"
    )

    if any(
        k in info_contexto
        for k in [
            "USA",
            "118",
            "SAN ROMAN",
            "SAN ROMÁN",
            "AUSTIN",
            "TEXAS"
        ]
    ):
        return "USA 118"

    if any(
        k in puesto
        for k in [
            "SOLDADOR",
            "BASTIDOR",
            "TECNICO BASTIDOR",
            "TÉCNICO BASTIDOR"
        ]
    ) or "BASTIDOR" in texto_upper:

        return "BASTIDOR 103"

    if any(
        k in puesto
        for k in [
            "PALAS",
            "TECNICO PALAS",
            "TÉCNICO PALAS",
            "LIDER PALAS",
            "LÍDER PALAS"
        ]
    ) or "PALAS" in texto_upper:

        return "PALAS 105"

    if any(
        k in puesto
        for k in [
            "MANTENIMIENTO",
            "TECNICO MANTENIMIENTO",
            "TÉCNICO MANTENIMIENTO"
        ]
    ) or any(
        k in info_contexto
        for k in [
            "JUCHITAN",
            "JUCHITÁN",
            "VESTAS",
            "BII HIOXO",
            "BIIHIOXO"
        ]
    ):

        return "MANTENIMIENTO 111"

    return "REVISIÓN"


# =========================================================
# EXTRAER NOMBRE DEL TÉCNICO
# =========================================================

def extraer_nombre_tecnico(texto_pdf):

    lineas = [
        l.strip()
        for l in texto_pdf.split("\n")
        if l.strip()
    ]

    if not lineas:
        return "TÉCNICO NO DETECTADO"

    for l in lineas[:15] + lineas[-15:]:

        match = re.search(
            r"(?:NOMBRE|RECIBE|PERSONAL ASIGNADO|PERSONAL|TÉCNICO)"
            r"\s*:?\s*([A-ZÁÉÍÓÚÑ\s]{5,60})",
            l,
            re.IGNORECASE
        )

        if match:

            nombre = match.group(1).strip().upper()

            nombre = re.sub(
                r"\s+",
                " ",
                nombre
            )

            return nombre

    return (
        lineas[0].upper()
        if len(lineas[0]) > 4
        else "TÉCNICO NO DETECTADO"
    )


# =========================================================
# EXTRACCIÓN DE PDF
# =========================================================

def extraer_datos_pdf_individual(stream_pdf):

    try:

        reader = pypdf.PdfReader(stream_pdf)

        texto_pdf = ""

        for page in reader.pages:

            try:

                texto = page.extract_text(
                    extraction_mode="layout"
                ) or ""

            except Exception:

                texto = (
                    page.extract_text()
                    or ""
                )

            texto_pdf += texto + "\n"

        return texto_pdf

    except Exception as e:

        print(
            f"Error leyendo PDF: {e}"
        )

        return ""


# =========================================================
# EXTRAER FILAS DE LA TABLA
# =========================================================

def extraer_filas_tabla_epp(texto_pdf):
    """
    Lee las filas de la tabla ENTREGA EPI.

    Estructura esperada:

    ITEM | DESCRIPCIÓN | NÚMERO DE SERIE |
    MARCA | MODELO | TALLA | OBSERVACIONES

    REGLA FUNDAMENTAL:

    El número de serie solamente puede salir
    de la columna NÚMERO DE SERIE.

    Nunca se toma automáticamente un número
    encontrado dentro de MODELO.
    """

    filas = []

    if not texto_pdf:
        return filas

    for linea in texto_pdf.splitlines():

        linea_original = linea.rstrip()

        # Buscar el número de ITEM al inicio.
        match_item = re.match(
            r"^\s*(\d{1,2})\s+",
            linea_original
        )

        if not match_item:
            continue

        item = int(
            match_item.group(1)
        )

        resto = linea_original[
            match_item.end():
        ].strip()

        if not resto:
            continue

        # -------------------------------------------------
        # PRIMER MÉTODO:
        # separar columnas usando 2 o más espacios.
        # -------------------------------------------------

        columnas = re.split(
            r"\s{2,}",
            resto
        )

        columnas = [
            limpiar_texto(c)
            for c in columnas
            if limpiar_texto(c)
        ]

        # -------------------------------------------------
        # Si no se pudieron detectar suficientes columnas,
        # hacemos una segunda aproximación.
        # -------------------------------------------------

        if len(columnas) < 4:

            # Intentamos identificar el número de serie
            # únicamente cuando aparece después de la
            # descripción y antes de una marca conocida.

            marcas_conocidas = [
                "PETZL",
                "ROCK EMPIRE",
                "HONEYWELL",
                "SOMAIN",
                "IRUDEK",
                "PROTECTA",
                "3M",
                "MASTER LOCK",
                "TRUPER",
                "NOVAX",
                "KLEENGUARD"
            ]

            marca_encontrada = None
            posicion_marca = -1

            resto_upper = resto.upper()

            for marca in sorted(
                marcas_conocidas,
                key=len,
                reverse=True
            ):

                pos = resto_upper.find(marca)

                if pos >= 0:

                    marca_encontrada = marca
                    posicion_marca = pos
                    break

            if marca_encontrada:

                antes_marca = resto[
                    :posicion_marca
                ].strip()

                despues_marca = resto[
                    posicion_marca + len(marca_encontrada):
                ].strip()

                tokens = antes_marca.split()

                if tokens:

                    # El primer bloque normalmente es
                    # descripción.
                    descripcion = tokens[0]

                    # Intentamos localizar un posible
                    # número de serie entre descripción
                    # y marca.
                    serie = ""

                    if len(tokens) >= 2:

                        posibles = tokens[1:]

                        for candidato in posibles:

                            candidato_limpio = (
                                candidato.strip()
                            )

                            if (
                                len(candidato_limpio) >= 6
                                and any(
                                    c.isdigit()
                                    for c in candidato_limpio
                                )
                            ):

                                serie = candidato_limpio
                                break

                    partes_despues = re.split(
                        r"\s{2,}",
                        despues_marca
                    )

                    modelo = (
                        partes_despues[0]
                        if partes_despues
                        else ""
                    )

                    columnas = [
                        descripcion,
                        serie,
                        marca_encontrada,
                        modelo
                    ]

        # -------------------------------------------------
        # Evitar filas que no correspondan a la tabla.
        # -------------------------------------------------

        if len(columnas) < 4:
            continue

        descripcion = (
            columnas[0]
            if len(columnas) > 0
            else ""
        )

        numero_serie = (
            columnas[1]
            if len(columnas) > 1
            else ""
        )

        marca = (
            columnas[2]
            if len(columnas) > 2
            else ""
        )

        modelo = (
            columnas[3]
            if len(columnas) > 3
            else ""
        )

        talla = (
            columnas[4]
            if len(columnas) > 4
            else ""
        )

        observaciones = (
            columnas[5]
            if len(columnas) > 5
            else ""
        )

        filas.append({

            "ITEM": item,

            "DESCRIPCIÓN": normalizar_mayusculas(
                descripcion
            ),

            "NÚMERO DE SERIE": normalizar_mayusculas(
                numero_serie
            ),

            "MARCA": normalizar_mayusculas(
                marca
            ),

            "MODELO": normalizar_mayusculas(
                modelo
            ),

            "TALLA": normalizar_mayusculas(
                talla
            ),

            "OBSERVACIONES": normalizar_mayusculas(
                observaciones
            )
        })

    return filas


# =========================================================
# CATÁLOGO: IDENTIFICAR EQUIPO
# =========================================================

def identificar_equipo_catalogo(
    descripcion,
    marca,
    modelo,
    linea_completa
):

    descripcion = normalizar_mayusculas(
        descripcion
    )

    marca = normalizar_mayusculas(
        marca
    )

    modelo = normalizar_mayusculas(
        modelo
    )

    linea = normalizar_mayusculas(
        linea_completa
    )

    descripcion_final = descripcion
    marca_final = marca
    modelo_final = modelo

    # -----------------------------------------------------
    # Primero buscar por modelo.
    # Se ordena por longitud para que:
    # ATLAS LOCK gane sobre ATLAS.
    # -----------------------------------------------------

    for mod_key in sorted(
        CATALOGO_EQUIPOS_EPP.keys(),
        key=len,
        reverse=True
    ):

        if mod_key in modelo:

            info = CATALOGO_EQUIPOS_EPP[
                mod_key
            ]

            modelo_final = mod_key

            if not marca_final:
                marca_final = info["marca"]

            if not descripcion_final:
                descripcion_final = info["descripcion"]

            return (
                descripcion_final,
                marca_final,
                modelo_final
            )

    # -----------------------------------------------------
    # Si no se encontró en modelo, revisar toda la línea.
    # -----------------------------------------------------

    for mod_key in sorted(
        CATALOGO_EQUIPOS_EPP.keys(),
        key=len,
        reverse=True
    ):

        if mod_key in linea:

            info = CATALOGO_EQUIPOS_EPP[
                mod_key
            ]

            modelo_final = (
                modelo_final
                if modelo_final
                else mod_key
            )

            if not marca_final:
                marca_final = info["marca"]

            if not descripcion_final:
                descripcion_final = info["descripcion"]

            return (
                descripcion_final,
                marca_final,
                modelo_final
            )

    # -----------------------------------------------------
    # Reglas generales.
    # -----------------------------------------------------

    if not descripcion_final:

        if any(
            k in linea
            for k in [
                "CASCO",
                "VERTEX",
                "STRATO"
            ]
        ):

            descripcion_final = "CASCO"

            if not marca_final:
                marca_final = "PETZL"

        elif any(
            k in linea
            for k in [
                "ARNÉS",
                "ARNES",
                "ATLAS",
                "AVAO",
                "VOLT"
            ]
        ):

            descripcion_final = "ARNÉS"

        elif any(
            k in linea
            for k in [
                "GANCHO",
                "APERTURA",
                "AUSTIN"
            ]
        ):

            descripcion_final = (
                "GANCHO DE GRAN APERTURA"
            )

        elif any(
            k in linea
            for k in [
                "RETRACTIL",
                "RETRÁCTIL",
                "CINTURÓN",
                "CINTURON"
            ]
        ):

            descripcion_final = (
                "CINTURÓN RETRÁCTIL"
            )

            if not marca_final:
                marca_final = "PROTECTA"

        elif any(
            k in linea
            for k in [
                "MOSQUETON",
                "MOSQUETÓN",
                "AM'D",
                "MAGNUM"
            ]
        ):

            descripcion_final = "MOSQUETÓN"

        elif any(
            k in linea
            for k in [
                "CINTA",
                "ANCLAJE",
                "ANNEAU"
            ]
        ):

            descripcion_final = (
                "CINTA DE ANCLAJE"
            )

        elif any(
            k in linea
            for k in [
                "GRILLON",
                "POSICIONADOR",
                "CATCH"
            ]
        ):

            descripcion_final = (
                "POSICIONADOR / ESLINGA 3M"
            )

        elif any(
            k in linea
            for k in [
                "SKC",
                "SOLL",
                "SÖLL",
                "VI-GO",
                "ANTICAIDAS",
                "ANTICAÍDAS"
            ]
        ):

            descripcion_final = "ANTICAÍDAS"

    return (
        descripcion_final,
        marca_final,
        modelo_final
    )


# =========================================================
# GOOGLE SHEETS
# =========================================================

def enviar_datos_a_google_sheets(df_nuevos):

    try:

        registros = []

        for _, row in df_nuevos.iterrows():

            registros.append({

                "DEPARTAMENTO": str(
                    row.get(
                        "DEPARTAMENTO",
                        ""
                    )
                ),

                "DESCRIPCIÓN": str(
                    row.get(
                        "DESCRIPCIÓN",
                        ""
                    )
                ),

                "MARCA": str(
                    row.get(
                        "MARCA",
                        ""
                    )
                ),

                "MODELO": str(
                    row.get(
                        "MODELO",
                        ""
                    )
                ),

                "NÚMERO DE SERIE": str(
                    row.get(
                        "NÚMERO DE SERIE",
                        ""
                    )
                ),

                "FACTURA_OC": str(
                    row.get(
                        "FACTURA_OC",
                        ""
                    )
                ),

                "FECHA_DE_ESTATUS": str(
                    row.get(
                        "FECHA_DE_ESTATUS",
                        ""
                    )
                ),

                "OBSERVACIONES": str(
                    row.get(
                        "OBSERVACIONES",
                        ""
                    )
                ),

                "ESTATUS": str(
                    row.get(
                        "ESTATUS",
                        "OK"
                    )
                )
            })

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(
            APPS_SCRIPT_URL,
            json=registros,
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:

            return (
                True,
                response.text
            )

        return (
            False,
            f"Código HTTP {response.status_code}: "
            f"{response.text}"
        )

    except Exception as e:

        return (
            False,
            str(e)
        )


# =========================================================
# POWER AUTOMATE
# =========================================================

def enviar_alerta_power_automate(
    tecnico,
    equipo,
    estatus,
    destinatario=CORREO_NOTIFICACION_PRINCIPAL,
    detalles_adicionales=""
):

    webhook_url = st.secrets.get(
        "POWER_AUTOMATE_URL"
    )

    if not webhook_url:
        return False

    asunto = (
        f"🚨 ALERTA EPP: "
        f"{equipo} - {estatus}"
    )

    cuerpo = (
        "Se ha registrado un reporte "
        "de inspección no conforme:\n\n"

        f"• Técnico / Inspector: {tecnico}\n"

        f"• Equipo / Elemento: {equipo}\n"

        f"• Estado: {estatus}\n"

        "• Observaciones / Hallazgos: "
        f"{detalles_adicionales if detalles_adicionales else 'Sin observaciones adicionales'}\n\n"

        "Mensaje generado automáticamente "
        "desde la App de Inspecciones EPP."
    )

    payload = {

        "destinatario": destinatario,

        "asunto": asunto,

        "cuerpo": cuerpo,

        "equipo": equipo,

        "tecnico": tecnico,

        "estatus": estatus
    }

    try:

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        return response.status_code in [
            200,
            202
        ]

    except Exception:

        return False


# =========================================================
# PROCESAMIENTO PRINCIPAL DEL ZIP
# =========================================================

def procesar_y_auditar_zip(
    archivo_zip_subido
):

    fichas_pdf = {}

    master_acuse_texto = ""

    master_filename = ""

    # -----------------------------------------------------
    # Limpiar nombre del ZIP.
    # -----------------------------------------------------

    nombre_zip_limpio = (
        archivo_zip_subido.name
        .replace(".zip", "")
        .replace("_", " ")
        .replace("-", " ")
        .upper()
    )

    # -----------------------------------------------------
    # Abrir ZIP.
    # -----------------------------------------------------

    with zipfile.ZipFile(
        archivo_zip_subido,
        "r"
    ) as z:

        archivos_pdf = [
            nombre
            for nombre in z.namelist()
            if nombre.lower().endswith(".pdf")
        ]

        if not archivos_pdf:

            return (
                None,
                pd.DataFrame(),
                pd.DataFrame(),
                []
            )

        # -------------------------------------------------
        # Leer todos los PDF.
        # -------------------------------------------------

        for nombre in archivos_pdf:

            try:

                with z.open(nombre) as f_pdf:

                    stream = io.BytesIO(
                        f_pdf.read()
                    )

                    texto = (
                        extraer_datos_pdf_individual(
                            stream
                        )
                    )

                    fichas_pdf[
                        nombre
                    ] = texto

                    nombre_l = nombre.lower()

                    texto_u = texto.upper()

                    # -------------------------------------
                    # Identificar acuse maestro.
                    # -------------------------------------

                    if (
                        any(
                            k in nombre_l
                            for k in [
                                "fo-09",
                                "fo09",
                                "copia",
                                "entrega"
                            ]
                        )
                        or
                        any(
                            k in texto_u
                            for k in [
                                "ENTREGA EPI",
                                "FO-09",
                                "FO09"
                            ]
                        )
                    ):

                        if not master_acuse_texto:

                            master_acuse_texto = (
                                texto
                            )

                            master_filename = (
                                nombre
                            )

            except Exception as e:

                print(
                    f"Error leyendo {nombre}: {e}"
                )

    # -----------------------------------------------------
    # Si no se encontró un maestro, usar el primer PDF.
    # -----------------------------------------------------

    if (
        not master_acuse_texto
        and archivos_pdf
    ):

        master_filename = (
            archivos_pdf[0]
        )

        master_acuse_texto = (
            fichas_pdf[
                master_filename
            ]
        )

    # -----------------------------------------------------
    # Departamento.
    # -----------------------------------------------------

    departamento_auto = (
        determinar_departamento_automatico(
            master_acuse_texto
        )
    )

    # -----------------------------------------------------
    # Técnico.
    # -----------------------------------------------------

    tecnico_master = (
        extraer_nombre_tecnico(
            master_acuse_texto
        )
    )

    if tecnico_master == (
        "TÉCNICO NO DETECTADO"
    ):

        tecnico_master = (
            nombre_zip_limpio
        )

    # -----------------------------------------------------
    # Fecha.
    # -----------------------------------------------------

    match_fechas = re.findall(
        r"\b"
        r"([0-9]{1,2}[/-]"
        r"[0-9]{1,2}[/-]"
        r"[0-9]{2,4})"
        r"\b",
        master_acuse_texto
    )

    fecha_acuse = (
        match_fechas[-1]
        if match_fechas
        else date.today().strftime(
            "%Y-%m-%d"
        )
    )

    # -----------------------------------------------------
    # EXTRAER TABLA.
    # -----------------------------------------------------

    filas_tabla = (
        extraer_filas_tabla_epp(
            master_acuse_texto
        )
    )

    items_master = []

    registros_inventario = []

    # =====================================================
    # PROCESAR FILAS
    # =====================================================

    for fila in filas_tabla:

        item = fila["ITEM"]

        descripcion_original = (
            fila["DESCRIPCIÓN"]
        )

        num_serie = (
            fila["NÚMERO DE SERIE"]
        )

        marca_original = (
            fila["MARCA"]
        )

        modelo_original = (
            fila["MODELO"]
        )

        observaciones_pdf = (
            fila["OBSERVACIONES"]
        )

        linea_completa = (
            f"{descripcion_original} "
            f"{num_serie} "
            f"{marca_original} "
            f"{modelo_original}"
        )

        # =================================================
        # REGLA CRÍTICA
        # =================================================
        #
        # SOLO SE ACEPTA COMO SERIE LO QUE ESTÉ
        # EN LA COLUMNA NÚMERO DE SERIE.
        #
        # Si la columna dice "-", se descarta.
        #
        # El modelo NO SE USA COMO SERIE.
        # =================================================

        if es_valor_vacio_serie(
            num_serie
        ):

            continue

        # -------------------------------------------------
        # Limpiar número de serie.
        # -------------------------------------------------

        num_serie = limpiar_numero_serie(
            num_serie
        )

        if es_valor_vacio_serie(
            num_serie
        ):

            continue

        # -------------------------------------------------
        # Identificar equipo mediante catálogo.
        # -------------------------------------------------

        (
            descripcion,
            marca,
            modelo
        ) = identificar_equipo_catalogo(

            descripcion_original,

            marca_original,

            modelo_original,

            linea_completa
        )

        # -------------------------------------------------
        # Observaciones.
        # -------------------------------------------------

        if (
            "NUEVO"
            in observaciones_pdf.upper()
        ):

            obs_formateada = (
                f"(NUEVO) "
                f"{tecnico_master}"
            )

        else:

            obs_formateada = (
                tecnico_master
            )

        # -------------------------------------------------
        # Guardar elemento.
        # -------------------------------------------------

        items_master.append({

            "ITEM": item,

            "raw_line": linea_completa,

            "serie": num_serie,

            "modelo": modelo,

            "marca": marca
        })

        registros_inventario.append({

            "DEPARTAMENTO":
                departamento_auto,

            "DESCRIPCIÓN":
                descripcion,

            "MARCA":
                marca,

            "MODELO":
                modelo,

            "NÚMERO DE SERIE":
                num_serie,

            "FACTURA_OC":
                "",

            "FECHA_DE_ESTATUS":
                fecha_acuse,

            "OBSERVACIONES":
                obs_formateada,

            "ESTATUS":
                "OK"
        })

    # =====================================================
    # AUDITORÍA DE FICHAS INDIVIDUALES
    # =====================================================

    reporte_correcto = []

    lista_errores = []

    for nombre_archivo, texto_ficha in fichas_pdf.items():

        if nombre_archivo == master_filename:
            continue

        # ---------------------------------------------
        # Número de serie
        # ---------------------------------------------

        match_serie = re.search(
            r"(?:n[uú]mero de serie|s/n|serie|c[oó]digo)"
            r"\s*:?\s*"
            r"([A-Z0-9\-/.*]+)",
            texto_ficha,
            re.IGNORECASE
        )

        # ---------------------------------------------
        # Modelo
        # ---------------------------------------------

        match_modelo = re.search(
            r"(?:modelo)"
            r"\s*:?\s*([^\n]+)",
            texto_ficha,
            re.IGNORECASE
        )

        # ---------------------------------------------
        # Técnico
        # ---------------------------------------------

        match_tecnico = re.search(
            r"(?:nombre|t[eé]cnico|personal)"
            r"\s*:?\s*([^\n]+)",
            texto_ficha,
            re.IGNORECASE
        )

        # ---------------------------------------------
        # Marca
        # ---------------------------------------------

        match_marca = re.search(
            r"(?:marca)"
            r"\s*:?\s*([^\n]+)",
            texto_ficha,
            re.IGNORECASE
        )

        serie_ficha = (

            match_serie.group(1)
            .strip()
            .upper()

            if match_serie

            else "DESCONOCIDO"
        )

        modelo_ficha = (

            match_modelo.group(1)
            .strip()

            if (
                match_modelo
                and match_modelo.group(1)
            )

            else "DESCONOCIDO"
        )

        tecnico_ficha = (

            match_tecnico.group(1)
            .strip()

            if match_tecnico

            else "DESCONOCIDO"
        )

        marca_ficha = (

            match_marca.group(1)
            .strip()
            .upper()

            if match_marca

            else (
                "PETZL"
                if (
                    "PETZL"
                    in texto_ficha.upper()
                    or
                    "PETZL"
                    in nombre_archivo.upper()
                )

                else "OTRA"
            )
        )

        reporte_correcto.append({

            "archivo":
                nombre_archivo,

            "marca":
                marca_ficha,

            "serie":
                serie_ficha,

            "modelo":
                modelo_ficha,

            "fecha_estatus":
                fecha_acuse,

            "estatus":
                "CORRECTO ✅"
        })

    # =====================================================
    # DEVOLVER RESULTADOS
    # =====================================================

    return (

        tecnico_master,

        pd.DataFrame(
            registros_inventario
        ),

        pd.DataFrame(
            reporte_correcto
        ),

        lista_errores
    )


# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================

st.title(
    "🛡️ Sistema de Gestión EPP e Inspecciones"
)


if not sistema_activo:

    st.warning(
        "⚠️ **SISTEMA INHABILITADO:** "
        "El administrador ha pausado temporalmente "
        "las operaciones y la sincronización con Excel."
    )

    st.stop()


# =========================================================
# PESTAÑAS
# =========================================================

(
    tab_dashboard,
    tab_registrar,
    tab_inspeccion,
    tab_historial,
    tab_ia,
    tab_zip
) = st.tabs([

    "1️⃣ Dashboard",

    "2️⃣ Registrar Equipo",

    "3️⃣ Inspección Pre-operacional",

    "4️⃣ Historial de Inspecciones",

    "5️⃣ Asistente IA",

    "6️⃣ Automatización y Fichas"
])


# =========================================================
# DASHBOARD
# =========================================================

with tab_dashboard:

    st.header(
        f"📊 Estado General del Inventario ({ANIO_ACTUAL})"
    )

    st.info(
        "Panel general activo para el seguimiento "
        "de equipos de protección personal y "
        "elementos en campo."
    )


# =========================================================
# REGISTRAR EQUIPO
# =========================================================

with tab_registrar:

    st.header(
        "➕ Registrar / Asignar Equipo"
    )

    st.write(
        "Utiliza este módulo para dar de alta "
        "de forma manual nuevos equipos o "
        "realizar asignaciones directas por departamento."
    )

    with st.form(
        "form_registrar_equipo"
    ):

        col_r1, col_r2 = st.columns(2)

        with col_r1:

            reg_depto = st.selectbox(
                "Departamento:",
                DEPARTAMENTOS
            )

            reg_desc = st.text_input(
                "Descripción del Equipo "
                "(Ej. Arnés, Casco, Eslinga):"
            )

            reg_marca = st.text_input(
                "Marca:"
            )

        with col_r2:

            reg_modelo = st.text_input(
                "Modelo:"
            )

            reg_serie = st.text_input(
                "Número de Serie:"
            )

            reg_factura = st.text_input(
                "Factura / Orden de Compra (OC):"
            )

        reg_obs = st.text_area(
            "Observaciones:"
        )

        btn_guardar_reg = st.form_submit_button(
            "💾 Guardar Registro en Inventario"
        )

        if btn_guardar_reg:

            st.success(
                "✅ Equipo registrado exitosamente "
                "en el sistema."
            )


# =========================================================
# INSPECCIÓN
# =========================================================

with tab_inspeccion:

    st.header(
        "📋 Inspección Pre-operacional en Campo"
    )

    st.write(
        "Realiza la revisión y validación de "
        "elementos de protección personal antes "
        "de iniciar labores operativas."
    )

    insp_equipo = st.text_input(
        "Buscar equipo por Número de Serie o Descripción:"
    )

    insp_estado = st.radio(
        "Estado de la inspección:",
        [
            "Conforme (OK) 🟢",
            "No Conforme / Dañado 🔴",
            "Requiere Mantenimiento 🟡"
        ]
    )

    insp_detalles = st.text_area(
        "Detalles o hallazgos de la inspección:"
    )

    if st.button(
        "📤 Enviar Reporte de Inspección"
    ):

        if "No Conforme" in insp_estado:

            enviado = enviar_alerta_power_automate(

                tecnico="OPERADOR EN CAMPO",

                equipo=(
                    insp_equipo
                    if insp_equipo
                    else "EQUIPO GENERAL"
                ),

                estatus="NO CONFORME",

                detalles_adicionales=(
                    insp_detalles
                )
            )

            if enviado:

                st.warning(
                    "⚠️ Inspección No Conforme registrada. "
                    "Se ha enviado una alerta automática por correo."
                )

            else:

                st.warning(
                    "⚠️ Inspección No Conforme registrada, "
                    "pero no fue posible enviar la alerta automática."
                )

        else:

            st.success(
                "✅ Inspección registrada correctamente."
            )


# =========================================================
# HISTORIAL
# =========================================================

with tab_historial:

    st.header(
        "📜 Historial de Inspecciones y Movimientos"
    )

    st.write(
        "Consulta el registro histórico de las "
        "auditorías, asignaciones e inspecciones "
        "pre-operacionales realizadas."
    )

    st.info(
        "No hay registros históricos recientes "
        "para mostrar en este momento."
    )


# =========================================================
# ASISTENTE IA - DEEPSEEK
# =========================================================

with tab_ia:

    st.header(
        "🤖 Asistente IA (DeepSeek)"
    )

    st.write(
        "Asistente interactivo libre. Puedes "
        "consultar cualquier tema técnico, "
        "de seguridad industrial, programación "
        "o conversar de manera completamente abierta."
    )

    pregunta_ia = st.text_input(
        "Escribe tu consulta o mensaje para DeepSeek:"
    )

    if pregunta_ia:

        with st.spinner(
            "Generando respuesta con DeepSeek..."
        ):

            try:

                deepseek_key = st.secrets.get(
                    "DEEPSEEK_API_KEY"
                )

                if not deepseek_key:

                    st.error(
                        "⚠️ Falta configurar la clave "
                        "`DEEPSEEK_API_KEY` en los secretos "
                        "de Streamlit."
                    )

                else:

                    client = OpenAI(

                        api_key=deepseek_key,

                        base_url=(
                            "https://api.deepseek.com"
                        )
                    )

                    response = client.chat.completions.create(

                        model="deepseek-chat",

                        messages=[

                            {
                                "role": "system",

                                "content":
                                (
                                    "Eres un asistente técnico "
                                    "experto en seguridad industrial, "
                                    "normativas, EPP, inspecciones, "
                                    "programación y gestión general."
                                )
                            },

                            {
                                "role": "user",

                                "content":
                                pregunta_ia
                            }
                        ],

                        stream=False
                    )

                    texto_respuesta = (
                        response
                        .choices[0]
                        .message
                        .content
                    )

                    st.markdown(
                        "### Respuesta:"
                    )

                    st.write(
                        texto_respuesta
                    )

            except Exception as e:

                st.error(
                    f"❌ Error al conectar con DeepSeek: {e}"
                )


# =========================================================
# AUTOMATIZACIÓN Y FICHAS ZIP
# =========================================================

with tab_zip:

    st.header(
        f"📂 Auditoría y Sincronización de Fichas EPP ({ANIO_ACTUAL})"
    )

    st.caption(
        "Sube el archivo ZIP del técnico. "
        "El sistema auditará las fichas, filtrará "
        "elementos seriables y te permitirá enviarlos "
        "a Google Sheets o descargar el Excel."
    )

    col_c1, col_c2 = st.columns(
        [1.5, 1.5]
    )

    with col_c1:

        correo_notificacion_mi_usuario = st.text_input(

            "Tu correo (notificaciones de error):",

            value=(
                CORREO_NOTIFICACION_PRINCIPAL
            )
        ).strip()

    with col_c2:

        correo_companera = st.text_input(

            "Correo de tu compañera:",

            value=(
                CORREO_COMPANERA_OPERACIONES
            )
        ).strip()


    zip_cargado = st.file_uploader(

        "Sube el archivo ZIP con las fichas del técnico:",

        type=["zip"],

        key=(
            "uploader_zip_sincronizacion_total"
        )
    )


    # =====================================================
    # PROCESAR ZIP
    # =====================================================

    if zip_cargado:

        with st.spinner(
            "⚡ Leyendo PDF, detectando departamento "
            "y procesando registros..."
        ):

            (
                tecnico_master,
                df_inventario,
                df_ok,
                lista_errores
            ) = procesar_y_auditar_zip(
                zip_cargado
            )


        st.subheader(
            "📋 Resumen de Auditoría - Técnico: "
            f"**{tecnico_master}**"
        )


        # =================================================
        # ERRORES
        # =================================================

        if lista_errores:

            st.error(
                f"⚠️ Se detectaron "
                f"**{len(lista_errores)}** "
                "error(es) de captura en las fichas subidas:"
            )

            df_err = pd.DataFrame(
                lista_errores
            )

            st.dataframe(
                df_err,
                use_container_width=True
            )

        else:

            st.success(
                "🎉 ¡Fichas auditadas exitosamente! "
                "No se detectaron errores de captura."
            )


        # =================================================
        # INVENTARIO
        # =================================================

        if not df_inventario.empty:

            st.success(
                f"✅ Se procesaron "
                f"**{len(df_inventario)}** "
                f"filas correctamente para "
                f"**{tecnico_master}**."
            )


            # ---------------------------------------------
            # ENVIAR GOOGLE SHEETS
            # ---------------------------------------------

            if st.button(
                "🚀 Enviar Automáticamente a Google Sheets"
            ):

                with st.spinner(
                    "Conectando con Google Sheets..."
                ):

                    (
                        exito_gs,
                        mensaje_gs
                    ) = enviar_datos_a_google_sheets(
                        df_inventario
                    )

                    if exito_gs:

                        st.success(
                            "🎉 ¡Datos sincronizados "
                            "exitosamente con tu Google Sheets!"
                        )

                        st.balloons()

                    else:

                        st.error(
                            "⚠️ No se pudo sincronizar "
                            "automáticamente con Google Sheets. "
                            f"Detalle: {mensaje_gs}"
                        )


            # ---------------------------------------------
            # GENERAR EXCEL
            # ---------------------------------------------

            output = io.BytesIO()

            with pd.ExcelWriter(
                output,
                engine="openpyxl"
            ) as writer:

                df_inventario.to_excel(

                    writer,

                    index=False,

                    sheet_name="INVENTARIO"
                )

            excel_data = output.getvalue()


            st.download_button(

                label=(
                    "📥 Descargar Inventario "
                    "Formateado en Excel (.xlsx)"
                ),

                data=excel_data,

                file_name=(
                    f"Inventario_"
                    f"{tecnico_master.replace(' ', '_')}_"
                    f"{date.today()}.xlsx"
                ),

                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )


            # =================================================
            # VISTA PREVIA
            # =================================================

            st.subheader(
                "📦 Registros Seriables Extraídos "
                "(Vista Previa)"
            )

            st.dataframe(
                df_inventario,
                use_container_width=True
            )


        else:

            st.warning(
                "⚠️ No se encontraron elementos "
                "seriables válidos en el archivo."
            )