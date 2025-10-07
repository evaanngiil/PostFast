import streamlit as st
from typing import List, Optional

def render_stepper(current_step: int, steps: List[str]):
    """Muestra un stepper visual horizontal para indicar el progreso del usuario."""
    stepper = ""
    for i, step in enumerate(steps):
        if i < current_step:
            stepper += f"<span style='color: #4CAF50; font-weight: bold;'>&#10003; {step}</span>"
        elif i == current_step:
            stepper += f"<span style='color: #2196F3; font-weight: bold;'>&#9679; {step}</span>"
        else:
            stepper += f"<span style='color: #BDBDBD;'>&#9675; {step}</span>"
        if i < len(steps) - 1:
            stepper += " <span style='color: #BDBDBD;'>→</span> "
    st.markdown(f"<div style='margin-bottom: 1em;'>{stepper}</div>", unsafe_allow_html=True)

def render_instruction(title: str, description: str, icon: Optional[str] = None):
    """Muestra una instrucción destacada con icono y descripción."""
    with st.container():
        st.markdown(f"<h4>{icon or ''} {title}</h4>", unsafe_allow_html=True)
        st.markdown(f"<div style='color: #666;'>{description}</div>", unsafe_allow_html=True)

def render_feedback_box(message: str, type_: str = "info"):
    """Muestra un mensaje de feedback destacado (info, success, warning, error)."""
    if type_ == "info":
        st.info(message)
    elif type_ == "success":
        st.success(message)
    elif type_ == "warning":
        st.warning(message)
    elif type_ == "error":
        st.error(message)
    else:
        st.write(message) 