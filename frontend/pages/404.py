# frontend/pages/404.py

import streamlit as st
from lucide_streamlit import icon


def render_404():
    """
    Render a user-friendly 404 page for invalid routes or broken links.
    """
    st.markdown(
        """
        <style>
            .error-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 3rem;
                color: #ff4b4b;
                font-family: 'Segoe UI', sans-serif;
            }
            .error-title {
                font-size: 3rem;
                font-weight: 700;
            }
            .error-subtext {
                font-size: 1.2rem;
                margin-top: 1rem;
                color: #555;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="error-container">
            <div>{icon("alert-triangle", size=48)}</div>
            <div class="error-title">404 – Page Not Found</div>
            <div class="error-subtext">
                The page you're looking for doesn't exist.<br>
                Please check the URL or go back to the homepage.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
