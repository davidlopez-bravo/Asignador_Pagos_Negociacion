import numpy as np
import pandas as pd
import os
import json
import streamlit as st
import io
from datetime import datetime, timedelta
from tools import extraccion_metabase_final

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Asignador de Pagos v3", layout="wide")
DB_FILE = "historial_gestiones_2.json"

EFECTIVO_JOB_TITLES = [
    'Encargado Negociación', 'Gestor Alianzas', 'Negociador de Alianzas',
    'Negociador de Refinanciación', 'Negociador Plus', 'Negociador Tradicional', 'Negociador de Refinanciación mid',
    'Negociador Puro ', 'Negociador Puro' 
]

AUTORIZACION_EFECTIVO_LIST = [
    "William Santiago Abril", "Angie Natalia Borda", "Mauricio David Valencia",
    "Maria Daniela Sarta", "Maria Alejandra Bejarano", "Angie Lizeth Cubides ",
    "Vivian Caterin Rodriguez", "Norbey Alejandro Duarte", "Suleimy Tatiana Malaver",
    "Hector Elian Lacera", "Dayana Isabel Ojito", "Diego Alejandro Sanchez",
    "Niyiret Julio Santos", "Jana Milena Lopez", "Alba Yohana Moreno Martin",
    "Rosa Yessenia Jimenez Lara"
]

# --- FUNCION EXPORTAR EXCEL ESTILIZADO ---
def to_excel_stylized(df):
    output = io.BytesIO()
    df_export = df.copy()
    df_export['fecha'] = df_export['fecha'].dt.date
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Historial')
        workbook  = writer.book
        worksheet = writer.sheets['Historial']

        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#1F4E78', 'font_color': 'white', 'border': 1
        })
        cell_format = workbook.add_format({'border': 1})
        bbva_true_format = workbook.add_format({'bg_color': '#DDEBF7', 'font_color': '#1F4E78'})

        for col_num, value in enumerate(df_export.columns.values):
            worksheet.write(0, col_num, value, header_format)
            column_len = max(df_export[value].astype(str).map(len).max(), len(value)) + 2
            worksheet.set_column(col_num, col_num, column_len)

        worksheet.conditional_format(1, 0, len(df_export), len(df_export.columns) - 1, 
                                     {'type': 'no_blanks', 'format': cell_format})
        
        worksheet.conditional_format(1, 0, len(df_export), len(df_export.columns) - 1,
                                     {'type': 'formula', 'criteria': '=$D2=TRUE', 'format': bbva_true_format})

    return output.getvalue()

# --- PERSISTENCIA JSON ---
def cargar_historial():
    cols = ['fecha', 'nombre', 'rol', 'bbva']
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=cols)
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            df = pd.DataFrame(json.load(f))
        if df.empty: return pd.DataFrame(columns=cols)
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['bbva'] = df['bbva'].astype(bool)
        return df[cols]
    except:
        return pd.DataFrame(columns=cols)

def guardar_en_historial(df_nuevos):
    df_actual = cargar_historial()
    df_temp = df_nuevos[['fecha', 'nombre', 'rol', 'bbva']].copy()
    df_temp['fecha'] = df_temp['fecha'].dt.strftime('%Y-%m-%d')
    
    data = []
    if not df_actual.empty:
        df_actual['fecha'] = df_actual['fecha'].dt.strftime('%Y-%m-%d')
        data = df_actual.to_dict(orient='records')
    
    data.extend(df_temp.to_dict(orient='records'))
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def procesar_hc(df):
    df.columns = df.columns.str.strip()
    df = df.rename(columns={'name': 'nombre'})
    df['nombre'] = df['nombre'].str.strip()
    df['job_title'] = df['job_title'].str.strip()
    
    df = df[~df['job_title'].isin(["Gerente Operaciones", "Practicante Estratégico", "Analista de ciencia de datos", 
                                  "Analista de ciencia de datos Jr.", "Ejecutivo Jr", "Team Leader Negociación", 
                                  "Analista de Cobranza Jr Negociación", "Analista de Datos Senior", "Analista Senior"])]
    
    # Mantenemos tus filtros de nombres específicos
    df = df[~df['nombre'].isin(['Cindy Viviana Barrera Buitrago', 'Niyiret Julio Santos', 'Angie Lorena Romero Sanchez', 'Jose Luis Sanchez Piñeros', 'Johan Hernando Morales Meneses', 'Jilary Johana Velasco Rodriguez'])]
    
    df = df[df['nombre']!=""]    
    patron_auth = "(?:" + '|'.join(AUTORIZACION_EFECTIVO_LIST) + ')'
    df["Es_Autorizado"] = df['nombre'].str.contains(patron_auth, case=False, na=False)
    
    df.loc[df['job_title'].isin(EFECTIVO_JOB_TITLES), "cat_base"] = "Efectivo"
    df.loc[df['cat_base'].isna(), "cat_base"] = "Cheques"
    return df

query_hc = """SELECT 
    email,
    employee_id,
    name,
    job_title,
    leader,
    status,
    joined_resuelve_on,
    became_inactive_on,
    cedula
FROM
    coyote_employees
WHERE 
    office = 'Colombia'
    AND area = 'Negociación'
    AND status = 'Activo'
"""

# --- MAIN ---
def main():
    st.title("🐍 Asignador de Pagos v3 🐍")

    df_hc_raw = extraccion_metabase_final(16,query_hc)
    if df_hc_raw is None: return
    df_hc = procesar_hc(df_hc_raw)
    df_hist = cargar_historial()

    with st.sidebar:
        fecha_inicio = st.date_input("Inicio de semana", datetime.now())
        st.divider()
        st.subheader("Configuración de Cupos")
        cupos_bbva = st.number_input("Cupos BBVA diarios", 1, 3, 2)
        cupos_efectivo = st.number_input("Cupos Efectivo diarios", 1, 5, 3)
        cupos_recogen = st.number_input("Cupos Recogen diarios", 1, 10, 3) 
        # NUEVO: Input para configurar los cupos de Cheques
        cupos_cheques = st.number_input("Cupos Cheques diarios", 1, 10, 2) 

    tab1, tab2, tab3 = st.tabs(["Generador", "Historial por Rango", "🔍 Búsqueda por Persona"])

    with tab1:
        if st.button("🐍 Generar Plan Semanal"):
            c_asig = df_hist['nombre'].value_counts().to_dict()
            c_bbva = df_hist[df_hist['bbva'] == True]['nombre'].value_counts().to_dict()
            c_reco = df_hist[df_hist['rol'] == 'Recogen']['nombre'].value_counts().to_dict()
            
            ult_asig_gen = df_hist.groupby('nombre')['fecha'].max().to_dict()
            ult_bbva = df_hist[df_hist['bbva'] == True].groupby('nombre')['fecha'].max().to_dict()
            # NUEVO: Rastreamos cuándo fue la última vez que hicieron rol "Recogen" (incluyendo BBVA)
            ult_reco = df_hist[df_hist['rol'] == 'Recogen'].groupby('nombre')['fecha'].max().to_dict()

            plan_semana = []
            
            for i in range(5):
                f_dia = pd.bdate_range(start=fecha_inicio, periods=5)[i]
                df_d = df_hc.copy()
                
                df_d['v_asig'] = df_d['nombre'].map(c_asig).fillna(0)
                df_d['v_bbva'] = df_d['nombre'].map(c_bbva).fillna(0)
                df_d['v_reco'] = df_d['nombre'].map(c_reco).fillna(0)
                df_d['rand'] = np.random.rand(len(df_d))
                
                df_d['gap_gen'] = (f_dia - pd.to_datetime(df_d['nombre'].map(ult_asig_gen))).dt.days.fillna(999)
                df_d['gap_bbva'] = (f_dia - pd.to_datetime(df_d['nombre'].map(ult_bbva))).dt.days.fillna(999)
                # NUEVO: Calculamos la brecha específica para Recogen
                df_d['gap_reco'] = (f_dia - pd.to_datetime(df_d['nombre'].map(ult_reco))).dt.days.fillna(999)

                # --- 1. SELECCIÓN BBVA (Pool: Solo los que NO son autorizados pero son de cat_base Efectivo) ---
                # CAMBIO: Priorizamos primero el gap_gen (para evitar días seguidos), luego BBVA, luego Recogen
                candidatos_bbva_pool = df_d[(df_d['cat_base'] == 'Efectivo') & (~df_d['Es_Autorizado'])].sort_values(
                    by=['gap_gen', 'gap_bbva', 'gap_reco', 'v_bbva', 'rand'], 
                    ascending=[False, False, False, True, True]
                )
                elegidos_bbva_nombres = candidatos_bbva_pool.head(int(cupos_bbva))['nombre'].tolist()
                
                nombres_ya_asignados = []
                final_dia_rows = []

                # --- 2. ASIGNACIÓN POR ROLES ---
                
                # A. EFECTIVO (SOLO AUTORIZADOS)
                otros_ef = df_d[df_d['Es_Autorizado']].sort_values(
                    by=['gap_gen', 'v_asig', 'rand'], ascending=[False, True, True]
                ).head(int(cupos_efectivo)).copy()
                otros_ef['rol'] = 'Efectivo'
                nombres_ya_asignados += otros_ef['nombre'].tolist()
                final_dia_rows.append(otros_ef)

                # B. RECOGEN (NO AUTORIZADOS + BBVA)
                bbva_re = df_d[df_d['nombre'].isin(elegidos_bbva_nombres)].copy()
                bbva_re['rol'] = 'Recogen'
                
                faltan_re = int(cupos_recogen) - len(bbva_re)
                # CAMBIO: Agregamos gap_reco para distribuir mejor los que recogen y no fueron a BBVA
                otros_re = df_d[(df_d['cat_base'] == 'Efectivo') & (~df_d['Es_Autorizado']) & (~df_d['nombre'].isin(elegidos_bbva_nombres))].sort_values(
                    by=['gap_gen', 'gap_reco', 'v_reco', 'rand'], 
                    ascending=[False, False, True, True]
                ).head(max(0, faltan_re)).copy()
                otros_re['rol'] = 'Recogen'
                
                grupo_re = pd.concat([bbva_re, otros_re])
                nombres_ya_asignados += grupo_re['nombre'].tolist()
                final_dia_rows.append(grupo_re)

                # C. CHEQUES
                # CAMBIO: Reemplazamos head(2) por head(int(cupos_cheques))
                s_ch = df_d[(df_d['cat_base'] == 'Cheques') & (~df_d['nombre'].isin(nombres_ya_asignados))].sort_values(
                    by=['gap_gen', 'v_asig', 'rand'], ascending=[False, True, True]
                ).head(int(cupos_cheques)).copy()
                s_ch['rol'] = 'Cheques'
                nombres_ya_asignados += s_ch['nombre'].tolist()
                final_dia_rows.append(s_ch)

                dia_df = pd.concat(final_dia_rows)
                dia_df['bbva'] = dia_df['nombre'].isin(elegidos_bbva_nombres)
                dia_df['fecha'] = f_dia
                plan_semana.append(dia_df)

                for _, r in dia_df.iterrows():
                    c_asig[r['nombre']] = c_asig.get(r['nombre'], 0) + 1
                    ult_asig_gen[r['nombre']] = f_dia
                    if r['bbva']:
                        c_bbva[r['nombre']] = c_bbva.get(r['nombre'], 0) + 1
                        ult_bbva[r['nombre']] = f_dia
                    if r['rol'] == 'Recogen':
                        c_reco[r['nombre']] = c_reco.get(r['nombre'], 0) + 1
                        ult_reco[r['nombre']] = f_dia # NUEVO: Actualizamos cuándo fue la última vez que recogieron

            st.session_state.resultado = pd.concat(plan_semana)

        if 'resultado' in st.session_state and st.session_state.resultado is not None:
            res = st.session_state.resultado
            if st.button("💾 GUARDAR"):
                guardar_en_historial(res)
                st.success("Guardado exitosamente.")
                st.session_state.resultado = None
                st.rerun()

            for i in range(5):
                f_cur = pd.bdate_range(start=fecha_inicio, periods=5)[i]
                with st.expander(f"📅 {f_cur.strftime('%Y-%m-%d')}"):
                    df_v = res[res['fecha'].dt.date == f_cur.date()]
                    st.table(df_v[['nombre', 'rol', 'bbva']].sort_values(by='rol'))

    with tab2:
        if not df_hist.empty:
            c1, c2, c3 = st.columns([1, 1, 1])
            start_f = c1.date_input("Desde", df_hist['fecha'].min())
            end_f = c2.date_input("Hasta", df_hist['fecha'].max())
            
            mask = (df_hist['fecha'].dt.date >= start_f) & (df_hist['fecha'].dt.date <= end_f)
            df_filt = df_hist[mask].sort_values(by='fecha', ascending=False)
            
            excel_data = to_excel_stylized(df_filt)
            c3.markdown("<br>", unsafe_allow_html=True)
            c3.download_button(
                label="📥 Descargar Excel Estilizado",
                data=excel_data,
                file_name=f"historial_pagos_{start_f}_{end_f}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.divider()
            resumen = df_filt.groupby('nombre').agg(
                Dias=('nombre', 'count'),
                BBVA=('bbva', 'sum'),
                Recogidas=('rol', lambda x: (x == 'Recogen').sum())
            ).sort_values(by=['BBVA', 'Dias'], ascending=False)
            st.subheader("Resumen del Periodo")
            st.table(resumen)
            st.subheader("Detalle de Registros")
            st.dataframe(df_filt, use_container_width=True)
            
    with tab3:
        st.subheader("Buscar Historial Individual")
        if not df_hist.empty:
            persona_sel = st.selectbox("Seleccione un colaborador:", sorted(df_hist['nombre'].unique()))
            if persona_sel:
                df_p = df_hist[df_hist['nombre'] == persona_sel].sort_values(by='fecha', ascending=False)
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total Asignaciones", len(df_p))
                col_b.metric("Total BBVA", df_p['bbva'].sum())
                col_c.metric("Total 'Recogen'", len(df_p[df_p['rol'] == 'Recogen']))
                st.dataframe(df_p[['fecha', 'rol', 'bbva']], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()