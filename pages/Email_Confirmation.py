import streamlit as st
from src.components.ui_helpers import set_page_config

# --- Configuración Inicial ---
set_page_config("AIPost - Email Confirmado")

# --- ESTILOS MODERNOS Y MINIMALISTAS ---
modern_styles = """
    <style>
        /* Ocultar elementos de Streamlit */
        #MainMenu, header, footer { visibility: hidden; }
        .block-container { padding-top: 5vh !important; padding-bottom: 5vh !important; } /* Añadir algo de padding vertical */

        /* Variables de Color (ajusta si es necesario) */
        :root {
            --brand-teal: #00A99D;
            --text-primary: #262730; /* Un gris oscuro casi negro */
            --text-secondary: #5f6368; /* Gris medio */
            --background-light: #FFFFFF;
            --background-page: #f8f9fa; /* Un gris muy claro para el fondo */
            --border-light: #e0e0e0; /* Borde sutil */
        }

        /* Estilo del fondo de la página */
        body {
            background-color: var(--background-page);
        }
        .stApp {
            background: var(--background-page);
        }

        /* Contenedor principal para centrar la tarjeta */
        [data-testid="stVerticalBlock"] .st-emotion-cache-1jicfl2 { /* Selector específico para el contenedor interno */
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 90vh; /* Ajustado para considerar el padding */
        }

        /* Tarjeta de confirmación */
        .confirmation-card {
            background-color: var(--background-light);
            padding: 3rem;
            border-radius: 12px; /* Bordes más suaves */
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); /* Sombra más sutil */
            max-width: 480px;
            width: 90%;
            text-align: center;
            border: 1px solid var(--border-light); /* Borde ligero */
            animation: fadeIn 0.6s ease-out;
        }

        /* Icono (usando Font Awesome) */
        .icon {
            font-size: 3.5rem; /* Ligeramente más pequeño */
            color: var(--brand-teal);
            margin-bottom: 1.5rem;
        }

        /* Títulos y Texto */
        h1 {
            color: var(--text-primary);
            font-weight: 600; /* Semi-bold */
            font-size: 1.75rem; /* Tamaño ajustado */
            margin-bottom: 0.75rem;
        }
        p {
            color: var(--background-light);
            line-height: 1.6;
            margin-bottom: 2rem;
            font-size: 1rem;
        }
        
        p.message {
            color: var(--text-secondary);
        }

        /* Botón de Streamlit */
        .stButton > button {
            background-color: var(--brand-teal);
            color: white;
            border: none;
            border-radius: 8px; /* Bordes redondeados consistentes */
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            transition: background-color 0.2s ease, transform 0.1s ease;
            width: 100%; /* Ocupar todo el ancho */
        }
        .stButton > button:hover {
            background-color: #00877a; /* Teal más oscuro */
            transform: translateY(-2px); /* Ligero efecto al pasar el ratón */
            color: white; /* Asegurar color de texto */
        }
        .stButton > button:active {
            transform: translateY(0px); /* Resetear en clic */
        }

        /* Animación */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Ajustes para Móvil */
        @media (max-width: 640px) {
            .block-container { padding: 2vh 5vw !important; }
            [data-testid="stVerticalBlock"] .st-emotion-cache-1jicfl2 {
                 align-items: flex-start; /* Alinear arriba */
                 min-height: auto;
             }
            .confirmation-card {
                padding: 2rem;
                box-shadow: none;
                border: none;
                border-radius: 0;
                width: 100%;
            }
            h1 { font-size: 1.5rem; }
            p { font-size: 0.95rem; }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
"""

st.markdown(modern_styles, unsafe_allow_html=True)

# Icono
st.markdown('<div class="icon"><i class="fas fa-check-circle"></i></div>', unsafe_allow_html=True) # Icono alternativo

# Título y Mensaje
st.markdown("<h1>¡Verificación Completa!</h1>", unsafe_allow_html=True) # Usar h1 para el título
st.markdown("<p class='message'>Tu dirección de correo ha sido confirmada. Ya puedes acceder a todas las funciones de AIPost.</p>", unsafe_allow_html=True) # Usar p para el párrafo

# Botón para volver al login (app.py)
if st.button("Ir a Inicio de Sesión", key="go_to_login_btn", type="secondary"):
    st.switch_page("app.py")

