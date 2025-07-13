import streamlit as st
from src.core.logger import logger
from typing import Dict, Any

def get_selected_account_context(selected_account_data: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    Extracts and validates the context for the selected account from session state.
    Returns a dictionary with all necessary context information.
    """
    context = {
        "data": selected_account_data,
        "platform": None,
        "account_id": None,
        "account_type": None,
        "token": None,
        "name": "N/A"
    }

    if not (selected_account_data and isinstance(selected_account_data, dict)):
        return context

    context.update({
        "platform": selected_account_data.get('platform'),
        "account_id": selected_account_data.get('urn'),
        "account_type": selected_account_data.get('type'),
        "name": selected_account_data.get('name', 'N/A')
    })

    if context["platform"] == "LinkedIn":
        context["token"] = st.session_state.get("li_token_data", {}).get("access_token")

    # Log validation result for debugging
    is_valid = all([context["platform"], context["account_id"], context["account_type"], context["token"]])
    if is_valid:
        logger.info(f"Active Context Set - Platform: {context['platform']}, Selected: {context['name']} ({context['account_id']})")
    else:
        logger.warning(f"Active Context Problem - Token Missing: {not context['token']}")

    return context