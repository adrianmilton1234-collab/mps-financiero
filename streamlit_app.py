import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MPS CFO Suite V4.1", page_icon="💼", layout="wide")

# --- ESTILOS CSS (DISEÑO PREMIUM) ---
st.markdown("""
    <style>
    /* Estilo General */
    .main { background-color: #f1f5f9; }
    h1, h2, h3 { color: #0f172a; font-family: 'Segoe UI', sans-serif; }
    
    /* Tabs Bonitos */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; background-color: white; padding: 10px 10px 0px 10px; 
        border-radius: 12px 12px 0px 0px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
    }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; border-radius: 8px 8px 0px 0px; border: none; 
        font-weight: 600; color: #64748b; background-color: transparent;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #1e40af; color: white; 
    }
    
    /* Tarjetas de Métricas (KPIs) */
    .metric-container {
        background-color: white; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-top: 5px solid #1e40af; text-align: center;
        transition: transform 0.2s;
    }
    .metric-container:hover { transform: translateY(-2px); }
    
    /* Tarjetas de Oferta Comercial */
    .offer-card {
        background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px;
        text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        height: 100%; display: flex; flex-direction: column; justify-content: space-between;
    }
    .offer-title { 
        color: #1e40af; font-weight: 800; font-size: 1.1rem; 
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;
    }
    .offer-price { 
        font-size: 2.5rem; font-weight: 800; color: #0f172a; margin: 10px 0; 
    }
    .offer-detail { color: #64748b; font-size: 0.9rem; margin-bottom: 15px; }
    
    /* Badge de Excedente */
    .badge-excess { 
        background-color: #fee2e2; color: #991b1b; font-size: 0.8rem; 
        padding: 6px 12px; border-radius: 20px; font-weight: bold; 
        display: inline-block; border: 1px solid #fecaca;
    }
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

# --- LÓGICA FINANCIERA ---

# Función Manual de VPN (Para evitar errores de versiones de numpy)
def calcular_vpn_manual(tasa, flujos):
    return sum(flujo / (1 + tasa) ** i for i, flujo in enumerate(flujos))

def calcular_amortizacion(monto, tasa_anual, meses, tipo, gracia=0):
    tabla = []
    saldo = monto
    tasa_mensual = (tasa_anual / 100) / 12
    plazo_pago = meses - gracia
    
    # Cálculos base
    cuota_francesa = 0
    if tipo == "Francesa" and tasa_mensual > 0 and plazo_pago > 0:
        cuota_francesa = saldo * (tasa_mensual * (1 + tasa_mensual)**plazo_pago) / ((1 + tasa_mensual)**plazo_pago - 1)
    elif tipo == "Francesa" and tasa_mensual == 0 and plazo_pago > 0:
        cuota_francesa = saldo / plazo_pago
    
    amort_alemana = saldo / plazo_pago if plazo_pago > 0 else 0

    for m in range(1, meses + 1):
        interes = saldo * tasa_mensual
        
        if m <= gracia:
            pago_capital = 0
            cuota = interes
            saldo_final = saldo
        else:
            if tipo == "Francesa":
                cuota = cuota_francesa
                pago_capital = cuota - interes
            else: # Alemana
                pago_capital = amort_alemana
                cuota = pago_capital + interes
            saldo_final = saldo - pago_capital
            if saldo_final < 0: saldo_final = 0
        
        tabla.append({
            "Mes": m, "Cuota Total": cuota, "Interés": interes, "Capital": pago_capital, "Saldo": saldo_final
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
    equipo = pd.read_sql_query(f"SELECT * FROM equipos WHERE id = {equipo_id}", conn).iloc[0]
    return equipo['mantenimiento'], costo_var, equipo['modelo'], equipo['costo_adq']

# --- SESSION STATE ---
if 'proyecto' not in st.session_state: st.session_state['proyecto'] = []
if 'financiamiento' not in st.session_state: st.session_state['financiamiento'] = {}

# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2666/2666505.png", width=70)
    st.header("Configuración CFO")
    margen_meta = st.slider("Margen Meta (%)", 10, 60, 30) / 100
    st.divider()
    incluir_papel = st.toggle("Incluir Papel", value=True)
    costo_papel = st.number_input("Costo Resma ($)", value=2.80) if incluir_papel else 0
    st.divider()
    if st.button("🗑️ Nuevo Proyecto", type="primary"):
        st.session_state['proyecto'] = []
        st.session_state['financiamiento'] = {}
        st.rerun()

# --- TÍTULO PRINCIPAL ---
st.title("💼 MPS CFO Suite V4.1")
st.markdown("Plataforma Integral de Gestión Financiera & Proyección de Contratos.")

# --- NAVEGACIÓN ---
tabs = st.tabs(["🛠️ 1. Inventario", "🏗️ 2. Armador", "💰 3. Financiamiento", "📊 4. Oferta Comercial", "📈 5. Proyección"])

# ==============================================================================
# TAB 1: INVENTARIO (CRUD)
# ==============================================================================
with tabs[0]:
    c1, c2 = st.columns([1, 2], gap="medium")
    with c1:
        st.subheader("Alta de Equipos")
        with st.form("alta_eq"):
            marca = st.text_input("Marca", "Brother")
            modelo = st.text_input("Modelo")
            costo = st.number_input("Costo Compra ($)", 0.0)
            residual = st.number_input("Valor Residual ($)", 50.0)
            manto = st.number_input("Mantenimiento Mensual ($)", 20.0)
            if st.form_submit_button("Guardar Equipo"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equipos (marca, modelo, costo_adq, residual, vida_util, mantenimiento) VALUES (?,?,?,?,?,?)",
                               (marca, modelo, costo, residual, 36, manto))
                conn.commit()
                st.success(f"{modelo} Guardado")
                st.rerun()

    with c2:
        st.subheader("Gestión de Consumibles")
        equipos = pd.read_sql("SELECT * FROM equipos", conn)
        if not equipos.empty:
            eq_id = st.selectbox("Seleccionar Equipo", equipos['id'].tolist(), format_func=lambda x: equipos[equipos['id']==x]['modelo'].values[0])
            
            with st.expander("➕ Agregar Consumible Nuevo"):
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
            
            cons_df = pd.read_sql(f"SELECT tipo, costo, rendimiento FROM consumibles WHERE equipo_id={eq_id}", conn)
            st.info("📝 Edita los precios directamente en la tabla:")
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
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 1])
            with c1: sede = st.text_input("Sede / Dpto")
            with c2: id_eq = st.selectbox("Modelo", equipos_disp['id'].tolist(), format_func=lambda x: equipos_disp[equipos_disp['id']==x]['modelo'].values[0], key="sel_eq_arm")
            with c3: cant = st.number_input("Cant.", 1, 100, 1)
            with c4: vol = st.number_input("Vol. Unit.", 100, 200000, 3000)
            with c5: 
                st.write("") 
                st.write("") 
                add_btn = st.button("➕ Agregar", use_container_width=True)

        if add_btn and sede:
            fijo_ope, var_tot, mod_nom, cost_adq = calcular_costos_operativos(id_eq, vol, incluir_papel, costo_papel)
            st.session_state['proyecto'].append({
                "Sede": sede, "Modelo": mod_nom, "Cantidad": cant,
                "Vol. Total": vol * cant,
                "OPEX Fijo": fijo_ope * cant, 
                "OPEX Var": var_tot * cant,   
                "Inversión": cost_adq * cant
            })
            st.rerun()

        if len(st.session_state['proyecto']) > 0:
            df_proy = pd.DataFrame(st.session_state['proyecto'])
            st.dataframe(df_proy, use_container_width=True)
            
            tot_inv = df_proy['Inversión'].sum()
            st.markdown(f"#### Inversión Total Requerida (CAPEX): :blue[${tot_inv:,.2f}]")
            
            if st.button("Deshacer última línea"):
                st.session_state['proyecto'].pop()
                st.rerun()
    else:
        st.warning("Carga inventario en Pestaña 1.")

# ==============================================================================
# TAB 3: FINANCIAMIENTO
# ==============================================================================
with tabs[2]:
    st.subheader("💰 Estrategia de Financiamiento")
    
    if len(st.session_state['proyecto']) == 0:
        st.info("Arma el proyecto primero.")
    else:
        df_proy = pd.DataFrame(st.session_state['proyecto'])
        monto_total = df_proy['Inversión'].sum()
        
        col_conf, col_chart = st.columns([1, 2])
        
        with col_conf:
            st.metric("Monto a Financiar", f"${monto_total:,.2f}")
            tipo_fin = st.selectbox("Fuente de Fondos", ["Propios (Contado)", "Bancario", "Crédito Mayorista"])
            
            tasa = 0.0; plazo = 12; gracia = 0; metodo = "Lineal"
            
            if tipo_fin == "Bancario":
                tasa = st.number_input("Tasa Interés Anual (%)", 0.0, 100.0, 12.0)
                plazo = st.number_input("Plazo (Meses)", 1, 60, 36)
                metodo = st.selectbox("Amortización", ["Francesa", "Alemana"])
            elif tipo_fin == "Crédito Mayorista":
                tasa = st.number_input("Interés Anual (%)", 0.0, 100.0, 5.0)
                plazo = st.number_input("Plazo Pago (Meses)", 1, 36, 12)
                gracia = st.number_input("Meses de Gracia", 0, 12, 0)
                metodo = "Alemana"

            # Calcular
            if tipo_fin == "Propios (Contado)":
                df_amort = pd.DataFrame()
                cuota_promedio = 0
                interes_total = 0
            else:
                df_amort = calcular_amortizacion(monto_total, tasa, plazo, metodo, gracia)
                cuota_promedio = df_amort['Cuota Total'].mean()
                interes_total = df_amort['Interés'].sum()
            
            st.session_state['financiamiento'] = {
                "Tipo": tipo_fin, "Tabla": df_amort, "Inversión": monto_total if tipo_fin == "Propios (Contado)" else 0,
                "Interés Total": interes_total, "Plazo": plazo
            }

        with col_chart:
            if tipo_fin != "Propios (Contado)":
                m1, m2 = st.columns(2)
                m1.metric("Cuota Promedio", f"${cuota_promedio:,.2f}")
                m2.metric("Costo Financiero Total", f"${interes_total:,.2f}", delta="- Intereses", delta_color="inverse")
                
                fig = px.bar(df_amort, x="Mes", y=["Capital", "Interés"], title="Flujo de Pagos", 
                             color_discrete_map={"Capital": "#3b82f6", "Interés": "#ef4444"})
                st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# TAB 4: OFERTA COMERCIAL
# ==============================================================================
with tabs[3]:
    st.subheader("📊 Estructura de Precios")
    
    if len(st.session_state['proyecto']) == 0:
        st.warning("Faltan datos.")
    else:
        df = pd.DataFrame(st.session_state['proyecto'])
        vol_total = df['Vol. Total'].sum()
        opex_total = df['OPEX Fijo'].sum() + df['OPEX Var'].sum()
        
        fin_data = st.session_state.get('financiamiento', {})
        if not fin_data:
            st.error("Configura Pestaña 3.")
            st.stop()
            
        # Costo Fin Mensual
        costo_fin_mes = 0
        if fin_data['Tipo'] == "Propios (Contado)":
            costo_fin_mes = df['Inversión'].sum() / 36 
        else:
            costo_fin_mes = fin_data['Tabla']['Cuota Total'].mean()
            
        costo_total_real = opex_total + costo_fin_mes
        facturacion_meta = costo_total_real / (1 - margen_meta)
        
        # Precios
        precio_unico = facturacion_meta / vol_total if vol_total > 0 else 0
        renta_base = (df['OPEX Fijo'].sum() + costo_fin_mes) / (1 - margen_meta)
        click_var = (df['OPEX Var'].sum() / (1 - margen_meta)) / vol_total if vol_total > 0 else 0
        excedente = precio_unico * 1.15

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<div class="offer-card"><div class="offer-title">OPCIÓN A<br>PRECIO ÚNICO</div>
            <div class="offer-price">${precio_unico:.4f}</div><div class="offer-detail">Costo por hoja All-In</div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="offer-card"><div class="offer-title">OPCIÓN B<br>HÍBRIDA</div>
            <div class="offer-price">${renta_base:,.2f}</div><div class="offer-detail">Renta + Click: <b>${click_var:.4f}</b></div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="offer-card"><div class="offer-title">OPCIÓN C<br>TARIFA PLANA</div>
            <div class="offer-price">${facturacion_meta:,.2f}</div><div class="badge-excess">⚠️ Excedente: ${excedente:.4f}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# TAB 5: PROYECCIÓN
# ==============================================================================
with tabs[4]:
    st.subheader("📈 Análisis de Rentabilidad")
    if len(st.session_state['proyecto']) > 0:
        meses_proy = st.slider("Horizonte (Meses)", 12, 60, 36)
        
        flujo_caja = []
        saldo_acum = 0
        inversion_inicial = fin_data.get('Inversión', 0)
        tabla_amort = fin_data.get('Tabla', pd.DataFrame())
        
        saldo_acum -= inversion_inicial # Salida inicial si es contado
        
        for m in range(1, meses_proy + 1):
            ingreso = facturacion_meta
            egreso_opex = opex_total
            egreso_fin = 0
            if not tabla_amort.empty and m <= len(tabla_amort):
                egreso_fin = tabla_amort.loc[tabla_amort['Mes'] == m, 'Cuota Total'].values[0]
            
            flujo_neto = ingreso - egreso_opex - egreso_fin
            if m == 1: flujo_neto -= inversion_inicial
            
            saldo_acum += flujo_neto
            flujo_caja.append({"Mes": m, "Ingresos": ingreso, "Egresos": egreso_opex+egreso_fin, "Neto": flujo_neto, "Acumulado": saldo_acum})
            
        df_flujo = pd.DataFrame(flujo_caja)
        
        # Gráficos
        g1, g2 = st.columns([2,1])
        with g1:
            fig = px.bar(df_flujo, x="Mes", y=["Ingresos", "Egresos"], barmode='group', title="Cash Flow Mensual", 
                         color_discrete_map={"Ingresos": "#10b981", "Egresos": "#ef4444"})
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            fig2 = px.line(df_flujo, x="Mes", y="Acumulado", title="ROI Acumulado")
            fig2.add_hline(y=0, line_dash="dot", line_color="black")
            st.plotly_chart(fig2, use_container_width=True)
            
        # KPI Finales
        col_end1, col_end2, col_end3 = st.columns(3)
        vpn = calcular_vpn_manual(0.10/12, df_flujo['Neto'])
        col_end1.metric("VPN (10%)", f"${vpn:,.2f}")
        
        recup = df_flujo[df_flujo['Acumulado'] >= 0]
        payback = recup.iloc[0]['Mes'] if not recup.empty else "N/A"
        col_end2.metric("Mes Recuperación", payback)
        
        csv = df_flujo.to_csv(index=False).encode('utf-8')
        col_end3.download_button("📥 Descargar Reporte Excel", data=csv, file_name="proyeccion_mps.csv", mime="text/csv")
