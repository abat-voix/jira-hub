"""
Sprint Analyzer - Streamlit приложение для анализа спринтов Jira
"""
import os
from dotenv import load_dotenv

import streamlit as st
from datetime import datetime
from jira_client import JiraClient
from pages.analysis import render_analysis_page
from pages.create_tasks import render_task_creator
from pages.transcribe import render_transcribe_page

load_dotenv()
API_TOKEN = os.getenv("JIRA_API_TOKEN")
BASE_URL = os.getenv("JIRA_BASE_URL")

st.set_page_config(
    page_title="Sprint Analyzer",
    page_icon="🏃",
    layout="wide"
)

# Стили
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .sprint-active {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }
    .sprint-future {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }
    .sprint-closed {
        background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        display: inline-block;
    }
    .metric-container {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
    }
    .status-done { background-color: #d1fae5; padding: 2px 8px; border-radius: 4px; }
    .status-progress { background-color: #fef3c7; padding: 2px 8px; border-radius: 4px; }
    .status-todo { background-color: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #10b981, #3b82f6); }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Инициализация состояния сессии"""
    if 'jira_client' not in st.session_state:
        st.session_state.jira_client = None
    if 'sprint_data' not in st.session_state:
        st.session_state.sprint_data = None
    if 'connected' not in st.session_state:
        st.session_state.connected = False
    if 'page' not in st.session_state:
        st.session_state.page = "analysis"


def render_sidebar():
    """Сайдбар: меню навигации + подключение/отключение"""

    st.sidebar.markdown("## 🏃 Sprint Analyzer")
    st.sidebar.markdown("---")

    # --- Навигация ---
    st.sidebar.markdown("### 📑 Меню")
    page = st.sidebar.radio(
        "Навигация",
        options=["🏃 Анализ спринта", "➕ Создание задач", "📝 Аудио → текст"],
        label_visibility="collapsed"
    )
    if "Анализ" in page:
        st.session_state.page = "analysis"
    elif "Создание" in page:
        st.session_state.page = "create"
    else:
        st.session_state.page = "transcribe"

    st.sidebar.markdown("---")

    # --- Подключение / Отключение ---
    if not st.session_state.connected:
        st.sidebar.markdown("### 🔗 Подключение к Jira")
        with st.sidebar.form("jira_connection"):
            submitted = st.form_submit_button("🔌 Подключиться", use_container_width=True)
            if submitted:
                if not API_TOKEN or not BASE_URL:
                    st.error("Укажите URL и токен в .env")
                    return
                with st.spinner("Подключение..."):
                    client = JiraClient(base_url=BASE_URL, api_token=API_TOKEN)
                    success, message = client.test_connection()
                    if success:
                        st.session_state.jira_client = client
                        st.session_state.connected = True
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    else:
        st.sidebar.markdown(f"✅ **Подключено** к Jira")
        if st.sidebar.button("🔌 Отключиться", use_container_width=True):
            st.session_state.jira_client = None
            st.session_state.connected = False
            st.session_state.sprint_data = None
            st.rerun()

        # Время последней загрузки
        if st.session_state.sprint_data:
            st.sidebar.markdown("---")
            st.sidebar.caption(f"🕐 Загружено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")


def main():
    init_session_state()
    render_sidebar()

    if st.session_state.page == "analysis":
        render_analysis_page()
    elif st.session_state.page == "create":
        render_task_creator()
    else:
        render_transcribe_page()


if __name__ == "__main__":
    main()
