# app.py

import streamlit as st

# --- Core Imports and Setup ---
try:
    from src.core.constants import FASTAPI_URL
    from src.core.logger import logger
    from src.data_processing import setup_database
except ImportError as e:
    st.error(f"Fatal Import Error (core): {e}"); st.stop()

# --- Authentication Imports ---
try:
    from src.auth import (
        initialize_session_state,
        verify_session_on_load,
        process_auth_params,
        load_user_accounts,
    )
except ImportError as e:
    st.error(f"Fatal Import Error (auth): {e}"); logger.critical(f"Import Error (auth): {e}", exc_info=True); st.stop()

# --- UI and Logic Imports ---
try:
    from src.components.sidebar import render_sidebar
    from src.utils.context import get_selected_account_context
    from src.pages import analytics, content_generation
except ImportError as e:
    st.error(f"Fatal Import Error (app structure): {e}"); logger.critical(f"Import Error (app structure): {e}", exc_info=True); st.stop()

def main():
    """
    Main function to run the Streamlit application.
    Handles initialization, session management, and page routing.
    """
    st.set_page_config(page_title="AIPost", layout="wide")
    logger.info("--- Streamlit App Execution Start/Reload ---")

    # --- Initialization and Session Verification ---
    try:
        initialize_session_state()
        setup_database()

        session_was_valid = verify_session_on_load()
        processed_new_login = False
        if not session_was_valid:
            processed_new_login = process_auth_params()

        accounts_loaded_or_refreshed = False
        if st.session_state.get("li_connected"):
            if load_user_accounts("LinkedIn"):
                 accounts_loaded_or_refreshed = True
                 logger.info("LinkedIn accounts loaded/refreshed.")
        
        if processed_new_login or accounts_loaded_or_refreshed:
             logger.debug("Rerunning UI after login or account refresh.")
             st.rerun()

    except Exception as init_err:
        st.error(f"Error during application initialization: {init_err}")
        logger.critical(f"Initialization Error: {init_err}", exc_info=True)
        st.stop()

    # --- Sidebar and Navigation ---
    selected_tab, selected_account_data = render_sidebar()

    # --- Main Content Area ---
    active_context = get_selected_account_context(selected_account_data)

    # --- Page Routing ---
    if selected_tab == "Analytics":
        analytics.render_page(active_context)
    elif selected_tab == "Content Generation":
        content_generation.render_page(active_context)
    
    # --- Footer ---
    st.sidebar.divider()
    st.sidebar.caption(f"AIPost v0.4.1 (Modular) | FastAPI: {FASTAPI_URL}")

if __name__ == "__main__":
    main()