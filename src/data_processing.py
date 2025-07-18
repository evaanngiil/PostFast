import psycopg
from psycopg.rows import dict_row # Para obtener resultados como diccionarios
import pandas as pd
import streamlit as st
import requests
from datetime import datetime, date
import time

from src.core.constants import DATABASE_URL
from src.social_apis import get_instagram_insights, get_linkedin_page_insights # For simple backoff
from src.core.logger import logger 

def get_db_connection(read_only: bool = False): # Mantener read_only por si se usa en el futuro
    """
    Obtiene una conexión a la base de datos PostgreSQL.
    Devuelve la conexión o None si falla.
    """
    # psycopg no tiene un modo 'read_only' directo en connect().
    # Se maneja con permisos de usuario o transacciones read-only si es necesario.
    # Por ahora, ignoraremos el flag read_only y siempre conectaremos normal.
    mode = "Read-Write (Default)" # Indicar modo
    try:
        # Conectar usando la URL de constants.py
        # row_factory=dict_row hace que fetchone/fetchall devuelvan diccionarios
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        logger.debug(f"PostgreSQL connection opened to DB defined in DATABASE_URL ({mode}).")
        return conn
    except psycopg.Error as e: # Capturar errores específicos de psycopg
        logger.error(f"Failed to connect to PostgreSQL DB: {e}", exc_info=True)
        return None

def setup_database():
    """Crea tablas necesarias si no existen en PostgreSQL."""
    conn = None
    cur = None # Necesitamos un cursor en psycopg
    try:
        conn = get_db_connection()
        if not conn:
             logger.error("Cannot setup database, failed to get connection.")
             return

        cur = conn.cursor() # Crear cursor para ejecutar comandos

        # Crear tabla user_sessions (Adaptada para PostgreSQL)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_cookie_id VARCHAR PRIMARY KEY,
                provider VARCHAR NOT NULL,
                user_provider_id VARCHAR NOT NULL,
                access_token VARCHAR NOT NULL,
                refresh_token VARCHAR,
                token_type VARCHAR,
                expires_at TIMESTAMPTZ,
                user_info JSONB,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_user_provider UNIQUE (user_provider_id, provider)
            );
        """)
        # Crear índices (PostgreSQL los crea automáticamente para PRIMARY KEY)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_provider ON user_sessions (user_provider_id, provider);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_access_token ON user_sessions (access_token);")


        # Crear tabla daily_account_metrics (Adaptada para PostgreSQL)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_account_metrics (
                metric_date DATE NOT NULL,
                platform VARCHAR NOT NULL,
                account_id VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                metric_value BIGINT,
                extracted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (metric_date, platform, account_id, metric_name) -- Clave primaria compuesta
            );
        """)
        # Crear índice para búsquedas eficientes por cuenta y fecha
        cur.execute("CREATE INDEX IF NOT EXISTS idx_metrics_account_date ON daily_account_metrics (platform, account_id, metric_date DESC);")

        conn.commit() # ¡Importante! Confirmar los cambios (CREATE TABLE)
        logger.info("PostgreSQL database tables configured.")

    except psycopg.Error as e:
         logger.exception(f"Error during PostgreSQL database setup: {e}")
         if conn:
             conn.rollback() # Deshacer cambios si hubo error
    finally:
        if cur: 
            cur.close()
        if conn: 
            conn.close()


# --- Extraction Functions  ---
def fetch_with_retry(api_call_func, max_retries=3, delay=5):
    """Wrapper to retry API calls in case of transient errors."""
    for attempt in range(max_retries):
        try:
            return api_call_func()
        except requests.exceptions.RequestException as e:
            print(f"API call error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt + 1 == max_retries:
                raise # Raise exception if retries are exhausted
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)

# --- Load and Transform Functions (ELT) ---
def transform_and_load_instagram(data, ig_user_id, conn):
    """Transforma datos de IG Insights y los carga en DuckDB."""
    if not data or 'data' not in data: return 0
    rows_added = 0
    records = []
    for metric_data in data['data']:
        metric_name = metric_data['name']
        for value_entry in metric_data.get('values', []):
            try:
                metric_date = datetime.strptime(value_entry['end_time'][:10], '%Y-%m-%d').date()
                metric_value = value_entry.get('value')
                # Handle follower_count potentially being lifetime only
                if metric_name == 'follower_count' and metric_data.get('period') == 'lifetime':
                     # Si es lifetime, lo asignamos a la última fecha del rango como 'snapshot'
                     # OJO: Esto no es crecimiento diario, es el total a esa fecha.
                     # El análisis de crecimiento real requeriría almacenar snapshots diarios.
                     metric_date = datetime.strptime(value_entry['end_time'][:10], '%Y-%m-%d').date() # Usa la fecha dada
                     if metric_value is not None:
                        records.append({
                            "metric_date": metric_date, "platform": "Instagram", "account_id": ig_user_id,
                            "metric_name": "follower_total", # Renombrar para claridad
                             "metric_value": int(metric_value)
                         })

                elif metric_value is not None: # Para métricas diarias normales
                    records.append({
                        "metric_date": metric_date, "platform": "Instagram", "account_id": ig_user_id,
                        "metric_name": metric_name, "metric_value": int(metric_value)
                    })
            except (KeyError, ValueError, TypeError) as e:
                print(f"Skipping invalid IG record for {metric_name}: {value_entry} - Error: {e}")
                continue

    if records:
        df = pd.DataFrame(records)
        conn.execute("""
            INSERT OR IGNORE INTO daily_account_metrics (metric_date, platform, account_id, metric_name, metric_value)
            SELECT metric_date, platform, account_id, metric_name, metric_value FROM df;
        """)
        rows_added = len(records)
    return rows_added


def transform_and_load_linkedin(data, org_urn, conn):
    """Transforma datos de LI Analytics y los carga en DuckDB."""
    if not data: 
        return 0

    rows_added = 0
    records = []
    log_prefix = "[LINKEDIN TRANSFORM]"
    
    # 1. Procesar Seguidores
    logger.debug(f"{log_prefix} Processing LinkedIn data for {org_urn}")
    if data.get('followers') and 'elements' in data['followers']:
        logger.debug(f"{log_prefix} Processing LinkedIn followers")
        for element in data['followers']['elements']:
            try:
                # Process total followers across all categories
                total_organic = 0
                total_paid = 0
                
                # Sum up followers from each category
                for category in ['followerCountsByFunction', 'followerCountsByStaffCountRange', 
                               'followerCountsBySeniority', 'followerCountsByIndustry']:
                    if category in element:
                        for item in element[category]:
                            if 'followerCounts' in item:
                                total_organic += item['followerCounts'].get('organicFollowerCount', 0)
                                total_paid += item['followerCounts'].get('paidFollowerCount', 0)
                
                # Calculate average since we're counting the same followers in different categories
                num_categories = sum(1 for cat in ['followerCountsByFunction', 'followerCountsByStaffCountRange', 
                                                 'followerCountsBySeniority', 'followerCountsByIndustry'] 
                                   if cat in element)
                if num_categories > 0:
                    total_organic = total_organic // num_categories
                    total_paid = total_paid // num_categories
                
                total_followers = total_organic + total_paid
                
                if total_followers > 0:
                    metric_date = date.today()  # Use current date for follower stats
                    records.append({
                        "metric_date": metric_date,
                        "platform": "LinkedIn",
                        "account_id": org_urn,
                        "metric_name": "follower_total",
                        "metric_value": int(total_followers)
                    })
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error processing LinkedIn follower data: {e}")
                continue

    # 2. Procesar Vistas de Página
    if data.get('views') and 'elements' in data['views']:
        for element in data['views']['elements']:
            try:
                if 'totalPageStatistics' in element and 'views' in element['totalPageStatistics']:
                    views_data = element['totalPageStatistics']['views']
                    
                    # Extract key metrics
                    metrics_to_extract = {
                        'allPageViews': 'page_views_total',
                        'allDesktopPageViews': 'page_views_desktop',
                        'allMobilePageViews': 'page_views_mobile',
                        'aboutPageViews': 'page_views_about',
                        'overviewPageViews': 'page_views_overview'
                    }
                    
                    metric_date = date.today()  # Use current date since no date provided
                    
                    for source_metric, target_name in metrics_to_extract.items():
                        value = views_data.get(source_metric, {}).get('pageViews', 0)
                        if value is not None:
                            records.append({
                                "metric_date": metric_date,
                                "platform": "LinkedIn",
                                "account_id": org_urn,
                                "metric_name": target_name,
                                "metric_value": int(value)
                            })
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error processing LinkedIn page views: {e}")
                continue

    # 3. Insert records
    rows_inserted = 0
    if records:
         cur = None
         try:
             cur = conn.cursor()
             # Es más eficiente que borrar e insertar o chequear existencia
             sql_upsert = """
                 INSERT INTO daily_account_metrics
                     (metric_date, platform, account_id, metric_name, metric_value, extracted_at)
                 VALUES
                     (%(metric_date)s, %(platform)s, %(account_id)s, %(metric_name)s, %(metric_value)s, CURRENT_TIMESTAMP)
                 ON CONFLICT (metric_date, platform, account_id, metric_name) DO UPDATE SET
                     metric_value = EXCLUDED.metric_value,
                     extracted_at = CURRENT_TIMESTAMP;
             """
             # executemany funciona bien con listas de diccionarios en psycopg3
             cur.executemany(sql_upsert, records)
             rows_inserted = cur.rowcount # Número de filas afectadas
             conn.commit() # Commit después de la transacción
             logger.info(f"Upserted {rows_inserted} LinkedIn metrics for {org_urn}")
         except psycopg.Error as e:
             logger.exception(f"Error upserting LinkedIn metrics for {org_urn}")
             if conn: 
                conn.rollback() # Deshacer en caso de error
             rows_inserted = 0 # Indicar fallo
         finally:
              if cur: cur.close()
    else:
         logger.info(f"No new LinkedIn metrics data parsed/formatted to insert for {org_urn}")

    return rows_inserted


def run_etl_pipeline(platform, account_id, access_token, start_date, end_date):
    """Ejecuta el pipeline ELT completo para una plataforma y cuenta."""
    conn = get_db_connection()
    rows_processed = 0
    try:
        if platform == "LinkedIn":
            # LinkedIn necesita timestamps en ms
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            # We assume that `account_id` is the organization URN
            org_urn = account_id # NOTE: Assumption for the demo!
            raw_data = get_linkedin_page_insights(org_urn, access_token, start_ts, end_ts)
            if raw_data:
                 rows_processed = transform_and_load_linkedin(raw_data, org_urn, conn)
    except Exception as e:
         st.error(f"Error in ELT pipeline for {platform} ({account_id}): {e}")
    finally:
        conn.close()
    return rows_processed

# --- Query Functions for Dashboards ---
def get_metrics_timeseries(platform: str, account_id: str, metrics: list, start_date: date, end_date: date) -> pd.DataFrame:
    """Obtiene datos de series de tiempo (USA CONEXIÓN READ-ONLY)."""
    logger.debug(f"Fetching timeseries for {platform}, {account_id}, metrics: {metrics}, range: {start_date} to {end_date}")
    conn = None
    df = pd.DataFrame()
    if not metrics: 
        return df

    try:
        conn = get_db_connection(read_only=True)
        if not conn: 
            raise Exception("DB connection failed")

       # Crear placeholders %s para psycopg
        metrics_placeholders = ','.join(['%s'] * len(metrics))
        # Query SQL estándar, funcionará en PostgreSQL
        query = f"""
            SELECT metric_date, metric_name, metric_value
            FROM daily_account_metrics
            WHERE platform = %s AND account_id = %s
              AND metric_name IN ({metrics_placeholders})
              AND metric_date BETWEEN %s AND %s
            ORDER BY metric_date, metric_name;
        """
        params = [platform, account_id] + metrics + [start_date, end_date]

        # Ejecutar y obtener resultados en un DataFrame de Pandas
        # psycopg3 no tiene fetchdf directo, podemos usar fetchall y convertir
        cur = conn.cursor()
        cur.execute(query, params)
        results = cur.fetchall() # Obtiene lista de diccionarios (por row_factory)
        cur.close()

        if results:
            print(f"[TIMESERIES] Fetched {results} from PostgreSQL for timeseries.")
            df_raw = pd.DataFrame(results)
            # Pivotear como antes
            df = df_raw.pivot(index='metric_date', columns='metric_name', values='metric_value')
            logger.debug(f"[TIMESERIES] DF: {df}.")
            # Tratar NaNs. Convertir a 0
            df.fillna(0, inplace=True)
            logger.info(f"Successfully fetched {len(df_raw)} rows for timeseries from PostgreSQL.")
        else:
            logger.info("No timeseries data found in PostgreSQL for the specified criteria.")

    except psycopg.Error as e:
        logger.exception(f"PostgreSQL Error fetching timeseries data: {e}")
        df = pd.DataFrame()
    except Exception as e:
        logger.exception(f"General Error fetching timeseries data: {e}")
        df = pd.DataFrame()
    finally:
        if conn: conn.close()
    return df


def get_latest_kpis(platform: str, account_id: str, kpi_metrics: tuple) -> dict:
    """Obtiene el valor más reciente para KPIs (USA CONEXIÓN READ-ONLY)."""
    logger.debug(f"Fetching latest KPIs for {platform}, {account_id}, metrics: {kpi_metrics}")
    conn = None
    kpis = {}
    if not kpi_metrics: 
        return kpis

    # Map generic metric names to their stored counterparts
    metric_mapping = {
        'follower_total': 'follower_total',
        'page_views': 'page_views_total'  # Map to the actual stored metric name
    }

    # Transform requested metrics to their stored names
    stored_metrics = [metric_mapping.get(m, m) for m in kpi_metrics]
    
    try:
        conn = get_db_connection(read_only=True)
        if not conn: 
            raise Exception("DB connection failed")

        metrics_placeholders = ','.join(['%s'] * len(stored_metrics))
        # Query con ROW_NUMBER() es estándar SQL y funciona en PostgreSQL
        query = f"""
            WITH RankedMetrics AS (
                SELECT metric_name, metric_value, metric_date,
                    ROW_NUMBER() OVER(PARTITION BY metric_name ORDER BY metric_date DESC) as rn
                FROM daily_account_metrics
                WHERE platform = %s AND account_id = %s
                  AND metric_name IN ({metrics_placeholders})
            )
            SELECT metric_name, metric_value
            FROM RankedMetrics
            WHERE rn = 1;
        """
        params = [platform, account_id] + stored_metrics

        cur = conn.cursor()
        cur.execute(query, params)
        results = cur.fetchall() # Lista de diccionarios
        cur.close()

        # Map the results back to the requested metric names
        reverse_mapping = {v: k for k, v in metric_mapping.items()}
        kpis = {reverse_mapping.get(row['metric_name'], row['metric_name']): row['metric_value'] 
                for row in results}
        logger.info(f"Fetched latest KPIs from PostgreSQL: {kpis}")

    except psycopg.Error as e:
        logger.exception(f"PostgreSQL Error fetching latest KPIs: {e}")
        kpis = {}
    except Exception as e:
        logger.exception(f"General Error fetching latest KPIs: {e}")
        kpis = {}
    finally:
        if conn: conn.close()
    return kpis

