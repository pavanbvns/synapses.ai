# frontend/components/header.py

import streamlit as st

# uses consolidated config loader for retrieving URLs
from utils.config_loader import get_config_value

# No modal trigger function needed here anymore


def render_header():
    """
    Renders the application header bar using custom HTML/CSS.
    Uses configuration values for external links.
    Help and Tech Docs links use query parameters to trigger modals in app.py.
    """
    # retrieve necessary URLs from configuration using the safe getter
    backend_docs_url = (
        get_config_value("backend_base_url", "http://127.0.0.1:8000") + "/docs"
    )
    llama_ui_url = get_config_value("llama_server_ui_url", "http://127.0.0.1:8080")

    # Links for modals now use query parameters
    # We use "?show_help=true" and "?show_tech_docs=true"
    help_link_target = "/?show_help=true"  # Target current page with query param
    tech_docs_link_target = (
        "/?show_tech_docs=true"  # Target current page with query param
    )

    # defines CSS rules for header styling (using your provided CSS)
    header_style = """
    <style>
        /* contains header bar within a full-width div */
        .header-container {
            width: 100%;
        }
        /* main header bar styling */
        .header-bar {
            background-color: #004080; /* professional blue background */
            color: white; /* white text */
            width: 100%;
            height: 70px; /* fixed header height */
            display: flex;
            align-items: center; /* vertically centers items */
            justify-content: space-between; /* spaces out title and buttons */
            padding: 0 1rem; /* horizontal padding */
            box-sizing: border-box;
            border-radius: 0px;
            margin-bottom: 10px; /* space below header */
        }
        /* header title styling - centered */
        .header-title {
            font-size: 1.75rem;
            font-weight: 600;
            margin: 0;
            flex-grow: 1; /* allows title to expand */
            text-align: center; /* centers the title text */
            position: relative;
            /* Adjust left offset based on button count/width */
            left: -80px; /* Value might need adjustment */
        }
        /* container for header buttons */
        .header-buttons {
            display: flex;
            align-items: center;
        }
        /* styling for the text links used as buttons */
        .header-buttons a {
            text-decoration: none;
            color: #004080; /* button text color */
            background-color: #FFFFFF; /* button background */
            border: 1px solid #DEE2E6;
            border-radius: 6px;
            padding: 0.4rem 0.8rem; /* button padding */
            margin-left: 0.6rem; /* space between buttons */
            font-size: 0.85rem; /* button font size */
            font-weight: 500;
            white-space: nowrap; /* prevents text wrapping */
            transition: background-color 0.2s ease, border-color 0.2s ease; /* hover effect */
        }
        /* hover effect for buttons */
        .header-buttons a:hover {
            background-color: #F8F9FA;
            border-color: #ADB5BD;
            color: #003366;
        }
        /* hides the default Streamlit header element */
        .stApp > header {
            background-color: transparent;
        }
         /* ensures reduced global padding is applied (defined in app.py) */
         div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] {
             padding-left: 0.5rem !important;
             padding-right: 0.5rem !important;
        }
    </style>
    """

    # defines the HTML structure for the header (using your provided structure)
    # IMPORTANT: href for Tech Docs and Help now include query parameters
    header_html = f"""
    <div class="header-container">
        <div class="header-bar">
            <div class="header-title">Synapses.AI</div>
            <div class="header-buttons">
                <a href="{backend_docs_url}" target="_blank" title="View Backend API Documentation">API Docs</a>
                <a href="{tech_docs_link_target}" target="_self" title="View Technical Documentation">Tech Docs</a>
                <a href="{llama_ui_url}" target="_blank" title="Access Llama Server UI">LLM UI</a>
                <a href="{help_link_target}" target="_self" title="Get User Help">Help</a>
            </div>
        </div>
    </div>
    """

    # renders the CSS styles first, then the HTML structure
    st.markdown(header_style, unsafe_allow_html=True)
    st.markdown(header_html, unsafe_allow_html=True)
