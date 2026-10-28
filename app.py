"""
app.py — Streamlit entry point.

Defines the six pages and the navigation sidebar.
Contains no application logic.
"""
import streamlit as st

st.set_page_config(
    page_title="Auto-Insight Report Generator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("ui/pages/upload.py",   title="Upload",   icon="📤", default=True),
    st.Page("ui/pages/profile.py",  title="Profile",  icon="📋"),
    st.Page("ui/pages/explore.py",  title="Explore",  icon="📈"),
    st.Page("ui/pages/forecast.py", title="Forecast", icon="🔮"),
    st.Page("ui/pages/report.py",   title="Report",   icon="📄"),
    st.Page("ui/pages/saved.py",    title="Saved",    icon="🗄️"),
]

nav = st.navigation(pages)
nav.run()

