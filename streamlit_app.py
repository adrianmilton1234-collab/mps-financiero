import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MPS CFO Suite V4.0", page_icon="💼", layout="wide")

# --- ESTILOS CSS PROFESIONALES ---
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    h1, h2, h3 { color: #0f172a; font-family: 'Helvetica Neue', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: white; padding: 10px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .stTabs [data-baseweb="tab"] { height: 50px; border-radius: 5px; border: none; font-weight: 600; color: #64748b; }
    .stTabs [aria-selected="true"] { background-color: #1e40af; color: white; }
    
    /* Tarjetas Métricas */
    .metric-container {
        background-color: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-top: 4px solid #1e40af; text-align: center;
        margin-bottom: 10px;
    }
    .metric-label { font-size: 0.875rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { font-size: 1.875rem; font-weight: 800; color: #0f172a; margin: 8px 0; }
    .metric-delta { font-size: 0.875rem; font-weight: 600; }
    .positive { color: #10b981; background-color: #ecfdf5; padding: 2px 8px; border-radius: 9999px; }
    .negative { color: #ef4444; background-color: #fef2f2; padding: 2px 8px; border-radius: 9999px; }
    
    /* Tarjetas de Oferta */
    .offer-card {
        background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px;
        transition: transform 0.2s; height: 100%; position: relative; overflow: hidden;
    }
    .offer-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); border-color: #1e40af; }
    .offer-header { background: #eff6ff; margin: -20px -20px 15px -20px; padding: 15px; font-weight: bold; color: #1e40af; text-align: center; border-bottom: 1px solid #dbeafe; }
    .badge-excess { background-color: #fee2e2; color: #991b1b; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-top: 10px; display: inline-block;}
    </style>
""", unsafe_allow_html=True)

# --- BACKEND (SQLITE) ---
def init_db():
    conn = sqlite3.connect('mps_cfo_v4.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS equipos
                 (id INTEGER PRIMARY KEY, marca TEXT, modelo TEXT, tipo TEXT, 
                  velocidad INTEGER, costo_adq REAL, residual REAL, vida_util INTEGER, mantenimiento REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS consumibles
                 (id INTEGER PRIMARY KEY, equipo_id INTEGER, tipo TEXT, costo REAL, rendimiento INTEGER,
                  FOREIGN KEY(equipo_id) REFERENCES equipos(id))''')
    conn.commit()
    return conn

conn = init_db()

# --- LÓGICA FINANCIERA AVANZADA ---
def calcular_amortizacion(monto, tasa_anual, meses, tipo, gracia=0):
    """Genera la tabla de amortización completa"""
    tabla = []
    saldo = monto
    tasa_mensual = (tasa_anual / 100) / 12
    
    # Ajuste de plazo efectivo por gracia
    plazo_pago = meses - gracia
    
    # Cuota Fija (Francesa)
    cuota_francesa = 0
    if tipo == "Francesa" and tasa_mensual > 0 and plazo_pago > 0:
        cuota_francesa = saldo * (tasa_mensual * (1 + tasa_mensual)**plazo_pago) / ((1 + tasa_mensual)**plazo_pago - 1)
    elif tipo == "Francesa" and tasa_mensual == 0 and plazo_pago > 0:
        cuota_francesa = saldo / plazo_pago

    # Amortización Fija (Alemana/Lineal)
    amort_alemana = saldo / plazo_pago if plazo_pago > 0 else 0

    for m in range(1, meses + 1):
        interes = saldo * tasa_mensual
        
        if m <= gracia:
            # Periodo de gracia: Solo paga interés (o nada si se difiere, aquí asumimos pago interés)
            pago_capital = 0
            cuota = interes # Solo paga interés
            saldo_final = saldo
        else:
            if tipo == "Francesa":
                cuota = cuota_francesa
                pago_capital = cuota - interes
            else: # Alemana / Lineal
                pago_capital = amort_alemana
                cuota = pago_capital + interes
            
            saldo_final = saldo - pago_capital
            if saldo_final < 0: saldo_final = 0 # Ajuste centavos
        
        tabla.append({
            "Mes": m,
            "Cuota Total": cuota,
            "Interés": interes,
            "Capital": pago_capital,
            "Saldo Restante": saldo_final
        })
        saldo = saldo_final

    return pd.DataFrame(tabla)

def calcular_costos_operativos(equipo_id, volumen, incluir_papel, costo_papel):
    df_cons = pd.read_sql_query(f"SELECT * FROM consumibles WHERE equipo_id = {equipo_id}", conn)
    cpp_cons = 0
    for _, row in df_cons.iterrows():
        if row['rendimiento'] > 0:
            cpp_cons += row['costo'] / row['rendimiento']
    
    if incluir_papel:
        cpp_cons += costo_papel / 500

    costo_var = cpp_cons * volumen
    
    # Fijo Operativo (Mantenimiento Técnico)
    equipo = pd.read_sql_query(f"SELECT * FROM equipos WHERE id = {equipo_id}", conn).iloc[0]
    # NOTA: En V4, la amortización del equipo NO se suma al costo operativo, 
    # porque eso se maneja en la pestaña de FINANCIAMIENTO (CAPEX).
    # Aquí solo calculamos OPEX (Mantenimiento + Consumibles)
    costo_fijo_ope = equipo['mantenimiento']

    return costo_fijo_ope, costo_var, equipo['modelo'], equipo['costo_adq']

# --- SESSION STATE ---
if 'proyecto' not in st.session_state: st.session_state['proyecto'] = []
if 'financiamiento' not in st.session_state: st.session_state['financiamiento'] = {}

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/781/781760.png", width=60)
    st.title("CFO Config")
    st.divider()
    margen_meta = st.slider("Margen Meta (%)", 10, 60, 30) / 100
    incluir_papel = st.toggle("Incluir Papel", value=True)
    if incluir_papel:
        costo_papel = st.number_input("Costo Resma ($)", value=2.80)
    else:
        costo_papel = 0
    
    st.divider()
    if st.button("🗑️ Nuevo Proyecto"):
        st.session_state['proyecto'] = []
        st.session_state['financiamiento'] = {}
        st.rerun()

# --- TÍTULO ---
st.title("💼 MPS CFO Suite V4.0")
st.markdown("Plataforma Integral de Gestión Financiera de Contratos MPS.")

# --- PESTAÑAS ---
tabs = st.tabs([
    "🛠️ 1. Inventario", 
    "🏗️ 2. Armador", 
    "💰 3. Financiamiento", 
    "📊 4. Oferta Comercial", 
    "📈 5. Proyección"
])

# ==============================================================================
# TAB 1: INVENTARIO (CRUD)
# ==============================================================================
with tabs[0]:
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        st.subheader("Alta de Equipos")
        with st.form("alta_eq"):
            marca = st.text_input("Marca", "Brother")
            modelo = st.text_input("Modelo")
            costo = st.number_input("Costo Compra ($)", 0.0)
            residual = st.number_input("Valor Residual ($)", 50.0)
            manto = st.number_input("Mantenimiento Mensual ($)", 20.0)
            if st.form_submit_button("Guardar"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                               (marca, modelo, costo, residual, 36, manto))
                conn.commit()
                st.success("Guardado")
                st.rerun()

    with c2:
        st.subheader("Gestión de Consumibles")
        equipos = pd.read_sql("SELECT * FROM equipos", conn)
        if not equipos.empty:
            eq_id = st.selectbox("Seleccionar Equipo", equipos['id'].tolist(), format_func=lambda x: equipos[equipos['id']==x]['modelo'].values[0])
            
            # Form Agregar
            with st.expander("➕ Agregar Consumible"):
                with st.form("add_cons"):
                    cc1, cc2, cc3 = st.columns(3)
                    tipo = cc1.selectbox("Tipo", ["Toner", "Drum", "Fuser", "Kit"])
                    costo_c = cc2.number_input("Costo Unit. ($)", 0.0)
                    rend = cc3.number_input("Rendimiento (Págs)", 10000)
                    if st.form_submit_button("Agregar"):
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", (eq_id, tipo, costo_c, rend))
                        conn.commit()
                        st.rerun()
            
            # Tabla Editable
            cons_df = pd.read_sql(f"SELECT tipo, costo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            st.info("📝 Puedes editar los precios directamente en la tabla:")
            edited_df = st.data_editor(cons_df, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 Guardar Cambios Inventario"):
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM consumibles WHERE equipo_id={eq_id}")
                for i, row in edited_df.iterrows():
                    if row['tipo']:
                        cursor.execute("INSERT INTO consumibles (equipo_id, tipo, costo, rendimiento) VALUES (?,?,?,?)", 
                                       (eq_id, row['tipo'], row['costo'], row['rendimiento']))
                conn.commit()
                st.success("Inventario actualizado.")
                st.rerun()

# ==============================================================================
# TAB 2: ARMADOR
# ==============================================================================
with tabs[1]:
    st.subheader("🛒 Configuración del Proyecto")
    equipos_disp = pd.read_sql("SELECT * FROM equipos", conn)
    
    if not equipos_disp.empty:
        # Input Bar
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            with c1: sede = st.text_input("Sede / Dpto")
            with c2: id_eq = st.selectbox("Modelo", equipos_disp['id'].tolist(), format_func=lambda x: equipos_disp[equipos_disp['id']==x]['modelo'].values[0], key="sel_eq_arm")
            with c3: cant = st.number_input("Cant.", 1, 100, 1)
            with c4: vol = st.number_input("Vol. Unit.", 100, 200000, 3000)
            with c5: 
                st.write("") 
                st.write("") 
                add_btn = st.button("➕ Agregar Línea", use_container_width=True)

        if add_btn and sede:
            fijo_ope, var_tot, mod_nom, cost_adq = calcular_costos_operativos(id_eq, vol, incluir_papel, costo_papel)
            
            st.session_state['proyecto'].append({
                "Sede": sede, "Modelo": mod_nom, "Cantidad": cant,
                "Vol. Total": vol * cant,
                "OPEX Fijo": fijo_ope * cant, # Mantenimiento Tecnico
                "OPEX Var": var_tot * cant,   # Toner + Papel
                "Inversión": cost_adq * cant
            })
            st.rerun()

        # Tabla Resumen
        if len(st.session_state['proyecto']) > 0:
            df_proy = pd.DataFrame(st.session_state['proyecto'])
            st.dataframe(df_proy, use_container_width=True)
            
            tot_inv = df_proy['Inversión'].sum()
            st.metric("Inversión Total Requerida (CAPEX)", f"${tot_inv:,.2f}")
            
            if st.button("Deshacer última"):
                st.session_state['proyecto'].pop()
                st.rerun()
    else:
        st.warning("Carga inventario primero.")

# ==============================================================================
# TAB 3: FINANCIAMIENTO (RESTORED & IMPROVED)
# ==============================================================================
with tabs[2]:
    st.subheader("💰 Escenarios de Adquisición")
    
    if len(st.session_state['proyecto']) == 0:
        st.info("Arma el proyecto primero para saber cuánto financiar.")
    else:
        df_proy = pd.DataFrame(st.session_state['proyecto'])
        monto_total = df_proy['Inversión'].sum()
        
        col_conf, col_chart = st.columns([1, 2])
        
        with col_conf:
            st.markdown(f"**Monto a Financiar:** :blue[${monto_total:,.2f}]")
            
            tipo_fin = st.selectbox("Fuente de Fondos", ["Propios (Contado)", "Bancario", "Crédito Mayorista"])
            
            tasa = 0.0
            plazo = 12
            gracia = 0
            metodo = "Lineal"
            
            if tipo_fin == "Bancario":
                tasa = st.number_input("Tasa Interés Anual (%)", 0.0, 100.0, 12.0)
                plazo = st.number_input("Plazo (Meses)", 1, 60, 36)
                metodo = st.selectbox("Amortización", ["Francesa", "Alemana"])
            
            elif tipo_fin == "Crédito Mayorista":
                tasa = st.number_input("Interés Mora/Financiero (%)", 0.0, 100.0, 5.0)
                plazo = st.number_input("Plazo Pago (Meses)", 1, 36, 12)
                gracia = st.number_input("Meses de Gracia", 0, 12, 0)
                metodo = "Alemana" # Usualmente mayorista es capital fijo
                st.caption("Nota: Los mayoristas suelen cobrar capital fijo.")

            # Calcular Tabla
            if tipo_fin == "Propios (Contado)":
                df_amort = pd.DataFrame() # Vacio
                cuota_promedio = 0
                interes_total = 0
                st.success("Sin costo financiero. Salida de caja inicial completa.")
            else:
                df_amort = calcular_amortizacion(monto_total, tasa, plazo, metodo, gracia)
                cuota_promedio = df_amort['Cuota Total'].mean()
                interes_total = df_amort['Interés'].sum()
            
            # Guardar en estado
            st.session_state['financiamiento'] = {
                "Tipo": tipo_fin,
                "Tabla": df_amort,
                "Inversión": monto_total if tipo_fin == "Propios (Contado)" else 0,
                "Interés Total": interes_total,
                "Plazo": plazo
            }

        with col_chart:
            if tipo_fin != "Propios (Contado)":
                st.markdown("#### 📅 Tabla de Amortización (Proyección)")
                
                # Métricas Financieras
                m1, m2, m3 = st.columns(3)
                m1.metric("Cuota Promedio", f"${cuota_promedio:,.2f}")
                m2.metric("Total Intereses", f"${interes_total:,.2f}", delta="- Costo Fin.", delta_color="inverse")
                m3.metric("Costo Total Deuda", f"${(monto_total + interes_total):,.2f}")

                # Gráfico
                fig = px.bar(df_amort, x="Mes", y=["Capital", "Interés"], title="Composición de Pagos Mensuales",
                             color_discrete_map={"Capital": "#3b82f6", "Interés": "#ef4444"})
                st.plotly_chart(fig, use_container_width=True)
                
                with st.expander("Ver Tabla Detallada"):
                    st.dataframe(df_amort, use_container_width=True)

# ==============================================================================
# TAB 4: OFERTA COMERCIAL
# ==============================================================================
with tabs[3]:
    st.subheader("📊 Estructuración de la Oferta")
    
    if len(st.session_state['proyecto']) == 0:
        st.warning("Faltan datos.")
    else:
        # Datos Proyecto
        df = pd.DataFrame(st.session_state['proyecto'])
        vol_total = df['Vol. Total'].sum()
        opex_total = df['OPEX Fijo'].sum() + df['OPEX Var'].sum() # Costo Operativo
        
        # Datos Financieros
        fin_data = st.session_state.get('financiamiento', {})
        if not fin_data:
            st.error("Configura el financiamiento en la Pestaña 3 primero.")
            st.stop()
            
        # Costo Financiero Mensual Promedio (Para prorratear en el precio)
        costo_fin_mes = 0
        if fin_data['Tipo'] == "Propios (Contado)":
            # Si es propio, debemos recuperar la inversión en X meses (ej. 36)
            costo_fin_mes = df['Inversión'].sum() / 36 # Depreciación lineal simple para precio
        else:
            # Si es banco, usamos la cuota promedio
            costo_fin_mes = fin_data['Tabla']['Cuota Total'].mean()
            
        # COSTO TOTAL REAL (Operativo + Financiero)
        costo_total_real = opex_total + costo_fin_mes
        
        # FACTURACIÓN OBJETIVO (Con Margen)
        facturacion_meta = costo_total_real / (1 - margen_meta)
        utilidad_estimada = facturacion_meta - costo_total_real
        
        # CÁLCULO DE PRECIOS
        precio_unico = facturacion_meta / vol_total if vol_total > 0 else 0
        renta_base = (df['OPEX Fijo'].sum() + costo_fin_mes) / (1 - margen_meta)
        click_var = (df['OPEX Var'].sum() / (1 - margen_meta)) / vol_total if vol_total > 0 else 0
        excedente = precio_unico * 1.15 # 15% recargo

        # --- UI TARJETAS ---
        c1, c2, c3 = st.columns(3)
        
        # Opción A
        with c1:
            st.markdown(f"""
            <div class="offer-card">
                <div class="offer-header">OPCIÓN A: PRECIO ÚNICO</div>
                <div class="metric-value">${precio_unico:.4f}</div>
                <p>Precio por hoja (All-In)</p>
                <hr>
                <small>Incluye amortización de equipos y consumibles.</small>
            </div>
            """, unsafe_allow_html=True)
            
        # Opción B
        with c2:
            st.markdown(f"""
            <div class="offer-card">
                <div class="offer-header">OPCIÓN B: HÍBRIDA</div>
                <div class="metric-value">${renta_base:,.2f}</div>
                <p>Renta Fija Mensual</p>
                <div class="metric-value" style="font-size: 1.2rem">+ ${click_var:.4f}</div>
                <p>Click Variable</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Opción C
        with c3:
            st.markdown(f"""
            <div class="offer-card">
                <div class="offer-header">OPCIÓN C: TARIFA PLANA</div>
                <div class="metric-value">${facturacion_meta:,.2f}</div>
                <p>Mensualidad Fija</p>
                <div class="badge-excess">⚠️ Excedente: ${excedente:.4f}</div>
                <br><small>Hasta {vol_total:,.0f} páginas.</small>
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        # Análisis de Break Even Financiero
        st.markdown("#### 🔎 Análisis de Cobertura Financiera")
        k1, k2, k3 = st.columns(3)
        k1.metric("Costo Operativo (OPEX)", f"${opex_total:,.2f}")
        k2.metric("Costo Financiero (CAPEX)", f"${costo_fin_mes:,.2f}", help="Cuota préstamo o amortización inversión")
        k3.metric("Utilidad Neta Real", f"${utilidad_estimada:,.2f}", delta="Disponible")

# ==============================================================================
# TAB 5: PROYECCIÓN (RESTORED)
# ==============================================================================
with tabs[4]:
    st.subheader("📈 Proyección de Flujo de Caja")
    
    if len(st.session_state['proyecto']) == 0:
        st.warning("Faltan datos.")
    else:
        fin_data = st.session_state.get('financiamiento', {})
        
        meses_proy = st.slider("Horizonte de Proyección (Meses)", 12, 60, 36)
        
        # Construcción del Flujo
        flujo_caja = []
        saldo_acum = 0
        inversion_inicial = fin_data.get('Inversión', 0) # Si es contado
        
        # Si hay tabla de amortización (banco/mayorista)
        tabla_amort = fin_data.get('Tabla', pd.DataFrame())
        
        # Salida inicial (si es contado)
        saldo_acum -= inversion_inicial
        
        for m in range(1, meses_proy + 1):
            ingreso = facturacion_meta # Asumimos venta constante (Plan C)
            egreso_opex = opex_total
            
            # Egreso Financiero (Cuota)
            egreso_fin = 0
            if not tabla_amort.empty and m <= len(tabla_amort):
                egreso_fin = tabla_amort.loc[tabla_amort['Mes'] == m, 'Cuota Total'].values[0]
            
            flujo_neto = ingreso - egreso_opex - egreso_fin
            
            # Ajuste mes 0 para gráfico (Inversión inicial)
            if m == 1: 
                flujo_neto -= inversion_inicial
            
            saldo_acum += flujo_neto
            
            flujo_caja.append({
                "Mes": m,
                "Ingresos": ingreso,
                "OPEX": egreso_opex,
                "Servicio Deuda": egreso_fin,
                "Flujo Neto": flujo_neto,
                "Acumulado": saldo_acum
            })
            
        df_flujo = pd.DataFrame(flujo_caja)
        
        # Gráficos
        gf1, gf2 = st.columns([2, 1])
        
        with gf1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_flujo['Mes'], y=df_flujo['Ingresos'], name='Ingresos', marker_color='#10b981'))
            fig.add_trace(go.Bar(x=df_flujo['Mes'], y=df_flujo['OPEX'], name='Costos Op.', marker_color='#f59e0b'))
            fig.add_trace(go.Bar(x=df_flujo['Mes'], y=df_flujo['Servicio Deuda'], name='Pago Deuda', marker_color='#ef4444'))
            fig.update_layout(barmode='group', title="Ingresos vs Egresos Mensuales")
            st.plotly_chart(fig, use_container_width=True)
            
        with gf2:
            fig2 = px.line(df_flujo, x="Mes", y="Acumulado", title="Cash Flow Acumulado (ROI)")
            fig2.add_hline(y=0, line_dash="dot", line_color="black", annotation_text="Break Even")
            st.plotly_chart(fig2, use_container_width=True)
            
        # Tabla y Exportación
        with st.expander("Ver Tabla de Datos Completa"):
            st.dataframe(df_flujo)
            
            # Exportar a CSV (Excel compatible)
            csv = df_flujo.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar a Excel",
                data=csv,
                file_name='proyeccion_mps.csv',
                mime='text/csv',
            )
            
        # KPI Finales
        k1, k2, k3 = st.columns(3)
        vpn = np.npv(0.10/12, df_flujo['Flujo Neto']) # VPN al 10% anual
        k1.metric("VPN (10%)", f"${vpn:,.2f}")
        
        payback = df_flujo[df_flujo['Acumulado'] >= 0].head(1)['Mes'].values
        val_payback = payback[0] if len(payback) > 0 else "N/A"
        k2.metric("Mes de Recuperación", val_payback)
        
        total_profit = df_flujo['Acumulado'].iloc[-1]
        k3.metric("Ganancia Total Proyecto", f"${total_profit:,.2f}")
