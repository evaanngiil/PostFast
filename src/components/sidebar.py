import streamlit as st
from typing import Tuple, Dict, Any

try:
    from src.auth import display_auth_status, display_account_selector
except ImportError as e:
    st.error(f"Fatal Import Error (auth): {e}")
    st.stop()

def render_sidebar() -> Tuple[str, Dict[str, Any] | None]:
    """
    Renders the sidebar content and returns the selected tab and account data.
    
    Returns:
        A tuple containing:
            - selected_tab (str): The name of the selected navigation tab.
            - selected_account_data (dict | None): The dictionary of the selected account.
    """
    with st.sidebar:
        st.title("🚀 AIPost")
        display_auth_status(sidebar=True)
        st.divider()

        selected_account_data = display_account_selector(sidebar=True)
        st.divider()
        
        selected_tab = st.radio(
            "Navigation", 
            ["Analytics", "Content Generation"], 
            key="main_nav"
        )
        
        return selected_tab, selected_account_data