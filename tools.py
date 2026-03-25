import requests
import pandas as pd
import os
from dotenv import load_dotenv


def extraccion_metabase_final(DATABASE_ID : str, SQL_QUERY : str, LIMIT : int = 2000) -> pd.DataFrame:
    load_dotenv(override=True)
    
    URL = os.getenv('METABASE_URL', '').rstrip('/')
    # Según tu log, el database_id es 12
    DB_ID = DATABASE_ID
    
    # 1. Autenticación
    print("🔑 Paso 1: Autenticando...")
    session_response = requests.post(f"{URL}/api/session", 
                                     json={"username": os.getenv('USERNAME'), 
                                           "password": os.getenv('PASSWORD')})
    session_id = session_response.json().get('id')
    
    if not session_id:
        print("❌ Error de autenticación")
        return None

    # 2. La Query (limpia)
    SQL_BASE = SQL_QUERY

    # 3. Extracción
    all_chunks = []
    offset = 0
    limit = LIMIT
    headers = {"X-Metabase-Session": session_id, "Content-Type": "application/json"}

    while True:
        print(f"📡 Solicitando offset {offset}...")
        payload = {
            "database": DB_ID,
            "type": "native",
            "native": {"query": f"{SQL_BASE} LIMIT {limit} OFFSET {offset}"}
        }
        
        res = requests.post(f"{URL}/api/dataset", json=payload, headers=headers)
        data = res.json()
        
        # --- EL PUNTO CRÍTICO ---
        # Extraemos las filas y los nombres de las columnas que vienen en el JSON
        rows = data.get('data', {}).get('rows', [])
        cols = [c['name'] for c in data.get('data', {}).get('cols', [])]
        
        if not rows:
            print("🏁 No más datos.")
            break
            
        # Creamos el DataFrame del chunk usando los nombres exactos que envía Metabase
        chunk_df = pd.DataFrame(rows, columns=cols)
        all_chunks.append(chunk_df)
        
        print(f"✔️ {len(rows)} filas obtenidas y guardadas en lista.")
        
        if len(rows) < limit:
            break
        offset += limit

    # 4. Unión
    if all_chunks:
        df_final = pd.concat(all_chunks, ignore_index=True)
        print(f"✅ Proceso terminado. Total final: {len(df_final)} filas.")
        return df_final
    else:
        print("❌ La lista de chunks está vacía.")
        return None

if __name__ == "__main__":
    QUERY = r"""
    with info as (
        select
            cr.bank_reference as Referencia,
            pi.document_number_cleaned as DNI,
            crd.credit_repair_id as Cl_id,
            crd.id as debt_id,
            CAST(REGEXP_REPLACE(crd.amount::TEXT, '\((\d+),.*\)', '\1') AS NUMERIC) / 100 as monto,
            crd.last_paid_date as ultimo_pago,
            CAST(REGEXP_REPLACE(cr.monthly_commission_amount::TEXT, '\((\d+),.*\)', '\1') AS NUMERIC) / 119 as cm,
            cr.total_debt_amount as dbt,
            INITCAP(pi.full_name) AS Nombre,
            cfe.name as banco,
            CAST(REGEXP_REPLACE(cr.monthly_payment::TEXT, '\((\d+),.*\)', '\1') AS NUMERIC) / 100 as am,
            REGEXP_REPLACE(credit_number,'[^0-9]', '', 'g') as credit_number,
            crd.state,
            CAST(cr.inserted_at at time zone 'America/Bogota' as timestamp) as Fecha_firma,
            cr.tracker_id
        from
            credit_repair_debts as crd
            left join credit_repairs as cr on cr.id = crd.credit_repair_id
            left join personal_information as pi on pi.credit_repair_id = crd.credit_repair_id
            left join catalog_financial_entities AS cfe ON cfe.id = crd.financial_entity_id
        where
            crd.state in ('new','negotiation')
            and cr.Status in ('active','partial_credit')
            and cfe.name ~* 'AECSA TUYA|CARULLA|Éxito|QNT TUYA|Tuya|Tuya S.A Contactosol|VIVA-Tuya'
            and CAST(crd.amount AS TEXT) ~* 'COP'
    )
    select *,
        (monto/dbt)*am as CD,
        (am-(cm*1.19)) as AMN,
        ((monto/dbt)*am)/monto as "%am"
    from
        info
    where
        DNI is not null
    order by 15 asc
    """
    resultado = extraccion_metabase_final(12, QUERY, 2000)
    if resultado is not None:
        print(resultado.head())
        print(resultado.tail())