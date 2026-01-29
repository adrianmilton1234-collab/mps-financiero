import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA (DISEÑO PRO) ---
st.set_page_config(
    page_title="MI PC S.A. | MPS Engine",
    page_icon="🖨️",
    layout="wide"
)

# Estilos CSS personalizados para que se vea "Chingón"
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #1E3A8A; }
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #1E3A8A; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. BASE DE DATOS TÉCNICA (Tus Costos Reales) ---
# Aquí están "quemados" los datos para que no tengas que escribirlos cada vez
INVENTARIO = {
    "Brother MFC-L6915DW (Nueva)": {
        "costo_equipo": 850.91, "meses": 36, "residual": 50.00,
        "toner_cost": 145.48, "toner_yield": 25000,
        "drum_cost": 97.19, "drum_yield": 75000,
        "fuser_cost": 185.00, "fuser_yield": 200000,
        "servicio": 20.00
    },
    "Brother MFC-L6900DW (Anterior)": {
        "costo_equipo": 850.91, "meses": 36, "residual": 50.00,
        "toner_cost": 112.50, "toner_yield": 20000,
        "drum_cost": 86.89, "drum_yield": 50000,
        "fuser_cost": 185.00, "fuser_yield": 200000,
        "servicio": 20.00
    },
    "Brother MFC-L9630CDN (Color)": {
        "costo_equipo": 850.91, "meses": 36, "residual": 50.00,
        "toner_cost": 492.00, "toner_yield": 10000, # Promedio CMYK
        "drum_cost": 178.64, "drum_yield": 100000,
        "fuser_cost": 185.00, "fuser_yield": 200000,
        "servicio": 20.00
    }
}

# --- BARRA LATERAL (CONFIGURACIÓN GLOBAL) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2885/2885456.png", width=80)
    st.title("Configuración Financiera")
    
    st.subheader("Variables Globales")
    margen_meta = st.slider("Margen de Ganancia Meta (%)", 10, 60, 30) / 100
    costo_papel_resma = st.number_input("Costo Resma Papel ($)", value=2.80)
    incluir_papel = st.checkbox("¿Incluir Papel en el Costo?", value=True)
    
    st.divider()
    st.info("💡 Sistema desarrollado para la Dirección Financiera de MI PC S.A.")

# --- TÍTULO PRINCIPAL ---
st.title("🚀 MPS QUOTE ENGINE | Generador de Contratos")
st.markdown("Diseña el contrato ideal, calcula costos ocultos y obtén el **Precio Único Ponderado** al instante.")
st.divider()

# --- 2. EL COTIZADOR (INPUT DE DATOS) ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📍 Definición de Sedes y Equipos")
    
    # Creamos un DataFrame inicial (Ejemplo Daquilema)
    default_data = pd.DataFrame([
        {"Ubicación": "Agencia Matriz - Operativo", "Modelo": "Brother MFC-L6915DW (Nueva)", "Cantidad": 15, "Volumen Total": 118000},
        {"Ubicación": "Sucursal - Admin", "Modelo": "Brother MFC-L6900DW (Anterior)", "Cantidad": 10, "Volumen Total": 10000},
        {"Ubicación": "Gerencia - Color", "Modelo": "Brother MFC-L9630CDN (Color)", "Cantidad": 1, "Volumen Total": 2000}
    ])
    
    # Editor Interactivo (Como Excel pero en Web)
    edited_df = st.data_editor(
        default_data,
        column_config={
            "Modelo": st.column_config.SelectboxColumn(
                "Modelo de Impresora",
                options=list(INVENTARIO.keys()),
                required=True,
                width="large"
            ),
            "Cantidad": st.column_config.NumberColumn("Cant.", min_value=1, step=1),
            "Volumen Total": st.column_config.NumberColumn("Volumen Mes", min_value=0, step=100)
        },
        num_rows="dynamic",
        use_container_width=True
    )

# --- 3. MOTOR DE CÁLCULO (BACKEND FINANCIERO) ---
resultados = []
total_facturacion = 0
total_costo = 0
total_volumen = 0

for index, row in edited_df.iterrows():
    specs = INVENTARIO[row["Modelo"]]
    
    # A. Costos Fijos (Amortización + Servicio)
    amort = (specs["costo_equipo"] - specs["residual"]) / specs["meses"]
    fijo_unit = amort + specs["servicio"]
    fijo_total = fijo_unit * row["Cantidad"]
    
    # B. Costos Variables (Consumibles)
    cpp_toner = specs["toner_cost"] / specs["toner_yield"]
    cpp_drum = specs["drum_cost"] / specs["drum_yield"]
    cpp_fuser = specs["fuser_cost"] / specs["fuser_yield"]
    cpp_papel = (costo_papel_resma / 500) if incluir_papel else 0
    
    cv_unit = cpp_toner + cpp_drum + cpp_fuser + cpp_papel
    cv_total = cv_unit * row["Volumen Total"]
    
    # Totales Línea
    costo_total_linea = fijo_total + cv_total
    precio_sugerido_linea = costo_total_linea * (1 + margen_meta)
    
    # Acumuladores
    total_costo += costo_total_linea
    total_facturacion += precio_sugerido_linea
    total_volumen += row["Volumen Total"]
    
    resultados.append({
        "Ubicación": row["Ubicación"],
        "Costo Real": costo_total_linea,
        "Precio Venta": precio_sugerido_linea,
        "Utilidad": precio_sugerido_linea - costo_total_linea
    })

# --- 4. DASHBOARD DE RESULTADOS (EL PRECIO ÚNICO) ---

# Calculo del Blended Price
precio_unico_ponderado = total_facturacion / total_volumen if total_volumen > 0 else 0
utilidad_neta = total_facturacion - total_costo
margen_real = (utilidad_neta / total_facturacion * 100) if total_facturacion > 0 else 0

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.subheader("🎯 PRECIO ÚNICO (Blended)")
    st.metric(label="Precio por Hoja (All-In)", value=f"${precio_unico_ponderado:.4f}")
    st.divider()
    st.metric(label="Facturación Mensual Estimada", value=f"${total_facturacion:,.2f}")
    st.metric(label="Costo Operativo Total", value=f"${total_costo:,.2f}", delta="- Salida de Caja", delta_color="inverse")
    st.metric(label="Utilidad Neta Mensual", value=f"${utilidad_neta:,.2f}", delta=f"{margen_real:.1f}% Margen")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 5. DETALLE Y PROPUESTAS COMERCIALES ---
st.divider()
st.subheader("📋 Las 3 Estrategias de Venta (Script Comercial)")

tab1, tab2, tab3 = st.tabs(["📊 Análisis Financiero", "💡 Propuestas al Cliente", "📈 Proyección Anual"])

with tab1:
    res_df = pd.DataFrame(resultados)
    st.dataframe(res_df.style.format({
        "Costo Real": "${:,.2f}",
        "Precio Venta": "${:,.2f}",
        "Utilidad": "${:,.2f}"
    }), use_container_width=True)
    
    # Gráfico
    chart_data = pd.DataFrame({
        "Concepto": ["Facturación", "Costos", "Utilidad"],
        "Monto": [total_facturacion, total_costo, utilidad_neta]
    })
    fig = px.bar(chart_data, x="Concepto", y="Monto", color="Concepto", 
                 color_discrete_map={"Facturación": "#1E3A8A", "Costos": "#B91C1C", "Utilidad": "#047857"})
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.success(f"✅ **ESTRATEGIA RECOMENDADA:** Ofrecer tarifa plana unificada de **${precio_unico_ponderado:.4f}**")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown("### 🅰️ PLAN VARIABLE")
        st.caption("Pago por consumo real")
        precio_a = precio_unico_ponderado * 1.05 # Un poco mas caro por riesgo
        st.metric("Precio por Hoja", f"${precio_a:.4f}")
        st.write("Ideal si no quieren compromisos fijos.")
        
    with col_b:
        st.markdown("### 🅱️ PLAN HÍBRIDO")
        st.caption("Renta Base + Click barato")
        # Calculamos una renta que cubra el 40% del contrato
        renta_base = total_facturacion * 0.40
        click_base = (total_facturacion * 0.60) / total_volumen
        st.metric("Renta Fija", f"${renta_base:,.2f}")
        st.metric("+ Costo Click", f"${click_base:.4f}")
        st.write("Equilibrio entre seguridad y volumen.")

    with col_c:
        st.markdown("### ©️ TARIFA PLANA")
        st.caption("Todo incluido mensual")
        st.metric("Mensualidad Fija", f"${total_facturacion:,.2f}")
        st.write(f"Incluye hasta {total_volumen:,.0f} impresiones.")

with tab3:
    st.write("Flujo de caja proyectado si el cliente firma a 36 meses:")
    proy_data = {
        "Periodo": ["Mensual", "Anual", "Contrato (36 Meses)"],
        "Ingresos": [total_facturacion, total_facturacion*12, total_facturacion*36],
        "EBITDA (Utilidad)": [utilidad_neta, utilidad_neta*12, utilidad_neta*36]
    }
    st.dataframe(pd.DataFrame(proy_data).style.format({
        "Ingresos": "${:,.2f}", 
        "EBITDA (Utilidad)": "${:,.2f}"
    }), use_container_width=True)
