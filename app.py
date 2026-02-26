"""
Sprint Analyzer - Streamlit приложение для анализа спринтов Jira
"""
import os
import json
from dotenv import load_dotenv

import streamlit as st
import pandas as pd
from datetime import datetime
from jira_client import JiraClient, JiraTaskCreator, SprintData

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
        options=["🏃 Анализ спринта", "➕ Создание задач"],
        label_visibility="collapsed"
    )
    st.session_state.page = "analysis" if "Анализ" in page else "create"

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


# ─────────────────────────────────────────────
# Выбор спринта — теперь внутри страницы анализа
# ─────────────────────────────────────────────
def render_sprint_selector():
    """Блок выбора спринта (отображается на странице анализа)"""
    client: JiraClient = st.session_state.jira_client

    st.markdown("### 🏃 Выбор спринта")

    input_mode = st.radio(
        "Способ выбора",
        options=["📋 Из списка", "✏️ Ввести название"],
        horizontal=True,
        label_visibility="collapsed"
    )

    sprint_name_to_load = None

    if input_mode == "✏️ Ввести название":
        col_input, col_btn = st.columns([3, 1])
        with col_input:
            manual_sprint = st.text_input(
                "Название спринта",
                placeholder="Например: 2026.2",
                help="Введите точное название спринта",
                label_visibility="collapsed"
            )
        with col_btn:
            if st.button("📊 Загрузить", use_container_width=True, key="load_manual"):
                if manual_sprint.strip():
                    sprint_name_to_load = manual_sprint.strip()
                else:
                    st.warning("Введите название спринта")

    else:
        with st.spinner("Загрузка спринтов..."):
            sprints = client.get_all_sprints()

        if not sprints:
            st.warning("Спринты не найдены")
            return

        active_sprints = [s for s in sprints if s.state == 'active']
        future_sprints = [s for s in sprints if s.state == 'future']
        closed_sprints = [s for s in sprints if s.state == 'closed']

        sprint_options = []
        sprint_map = {}

        for s in active_sprints:
            label = f"🟢 {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        for s in future_sprints:
            label = f"🔵 {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        for s in sorted(closed_sprints, key=lambda x: x.name, reverse=True)[:20]:
            label = f"⚪ {s.name}"
            sprint_options.append(label)
            sprint_map[label] = s

        col_select, col_btn = st.columns([3, 1])
        with col_select:
            selected = st.selectbox(
                "Спринт",
                options=sprint_options,
                help="🟢 Активный | 🔵 Будущий | ⚪ Завершённый",
                label_visibility="collapsed"
            )
        with col_btn:
            if st.button("📊 Загрузить", use_container_width=True, key="load_list"):
                if selected:
                    sprint_name_to_load = sprint_map[selected].name

    # Загрузка данных
    if sprint_name_to_load:
        with st.spinner(f"Загрузка задач спринта «{sprint_name_to_load}»..."):
            sprint_data = client.get_sprint_issues(sprint_name_to_load)
            if sprint_data:
                st.session_state.sprint_data = sprint_data
                st.rerun()
            else:
                st.error("Не удалось загрузить данные. Проверьте название спринта.")


# ─────────────────────────────────────────────
# Отображение данных спринта (без изменений)
# ─────────────────────────────────────────────

def render_sprint_header(sprint_data: SprintData):
    info = sprint_data.sprint_info
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"## 🏃 {info.name if info else 'Спринт'}")
        if info:
            st.caption(f"📋 Доска: {info.board_name or 'Неизвестно'}")
    with col2:
        if info:
            state_class = {
                'active': 'sprint-active', 'future': 'sprint-future', 'closed': 'sprint-closed'
            }.get(info.state, 'sprint-closed')
            state_label = {
                'active': '🟢 Активный', 'future': '🔵 Будущий', 'closed': '⚪ Завершён'
            }.get(info.state, info.state)
            st.markdown(f'<span class="{state_class}">{state_label}</span>', unsafe_allow_html=True)
    if info and (info.start_date or info.end_date):
        start = info.start_date[:10] if info.start_date else "?"
        end = info.end_date[:10] if info.end_date else "?"
        st.caption(f"📅 {start} → {end}")


def render_metrics(sprint_data: SprintData):
    issues = sprint_data.issues
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    total_tasks = len(issues)
    unassigned = sum(1 for i in issues if i.assignee == 'Не назначен')

    done_statuses = ['Выполнено', 'Done', 'Closed', 'Resolved']
    in_progress_statuses = ['В работе', 'In Progress', 'Тестирование', 'Testing', 'Создан MR', 'Review']

    done_count = sum(1 for i in issues if any(s in i.status for s in done_statuses))
    in_progress_count = sum(1 for i in issues if any(s in i.status for s in in_progress_statuses))

    done_hours = sum(i.estimated_hours or 0 for i in issues if any(s in i.status for s in done_statuses))
    progress_pct = (done_hours / sprint_data.total_estimated * 100) if sprint_data.total_estimated > 0 else 0

    col1.metric("📋 Всего задач", total_tasks)
    col2.metric("✅ Выполнено", done_count)
    col3.metric("🔄 В работе", in_progress_count)
    col4.metric("⏱️ Оценка", f"{sprint_data.total_estimated:.0f} ч")
    col5.metric("📝 Залогировано", f"{sprint_data.total_spent:.1f} ч")
    col6.metric("⚠️ Без исполнителя", unassigned, delta_color="inverse")

    st.progress(min(progress_pct / 100, 1.0))
    st.caption(f"Прогресс по выполненным задачам: {progress_pct:.0f}% ({done_hours:.0f} из {sprint_data.total_estimated:.0f} ч)")


def render_status_breakdown(sprint_data: SprintData):
    st.markdown("### 📊 По статусам")
    by_status = {}
    for issue in sprint_data.issues:
        status = issue.status
        if status not in by_status:
            by_status[status] = {'count': 0, 'estimated': 0, 'spent': 0, 'issues': []}
        by_status[status]['count'] += 1
        by_status[status]['estimated'] += issue.estimated_hours or 0
        by_status[status]['spent'] += issue.spent_hours or 0
        by_status[status]['issues'].append(issue)

    status_order = ['Выполнено', 'Done', 'Финальное тестирование', 'Создан MR',
                    'Тестирование', 'Testing', 'Review', 'В работе', 'In Progress',
                    'Создан', 'Open', 'Необходимо сделать', 'To Do']
    status_icons = {
        'Выполнено': '✅', 'Done': '✅', 'Closed': '✅',
        'Финальное тестирование': '🔵', 'Создан MR': '🟣', 'Review': '🟣',
        'Тестирование': '🟡', 'Testing': '🟡',
        'В работе': '🟠', 'In Progress': '🟠',
        'Создан': '🔷', 'Open': '🔷',
        'Необходимо сделать': '⚪', 'To Do': '⚪'
    }

    sorted_statuses = [s for s in status_order if s in by_status]
    for s in by_status:
        if s not in sorted_statuses:
            sorted_statuses.append(s)

    for status in sorted_statuses:
        data = by_status[status]
        icon = status_icons.get(status, '📌')
        with st.expander(
            f"{icon} **{status}** — {data['count']} задач ({data['estimated']:.0f} ч)",
            expanded=(status in ['В работе', 'In Progress', 'Тестирование', 'Testing'])
        ):
            for issue in data['issues']:
                c1, c2, c3 = st.columns([1, 4, 2])
                with c1:
                    st.markdown(f"[`{issue.key}`]({issue.url})")
                with c2:
                    summary = issue.summary[:70] + ('...' if len(issue.summary) > 70 else '')
                    t = {'Bug': '🐛', 'Story': '📖', 'Task': '✔️', 'Epic': '🎯'}.get(issue.issue_type, '📋')
                    st.markdown(f"{t} {summary}")
                with c3:
                    hours_info = f"⏱️ {issue.estimated_hours:.0f}ч" if issue.estimated_hours else "⏱️ —"
                    if issue.spent_hours:
                        over = issue.spent_hours > (issue.estimated_hours or 0)
                        hours_info += f" / {'🔴' if over else ''}{issue.spent_hours:.1f}ч"
                    assignee = issue.assignee
                    if assignee == 'Не назначен':
                        st.markdown(f"{hours_info}<br>🚫 *Не назначен*", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{hours_info}<br>👤 {assignee}", unsafe_allow_html=True)


def render_assignee_stats(sprint_data: SprintData):
    st.markdown("### 👥 По исполнителям")
    by_assignee = {}
    for issue in sprint_data.issues:
        a = issue.assignee
        if a not in by_assignee:
            by_assignee[a] = {'count': 0, 'estimated': 0, 'spent': 0, 'statuses': {}}
        by_assignee[a]['count'] += 1
        by_assignee[a]['estimated'] += issue.estimated_hours or 0
        by_assignee[a]['spent'] += issue.spent_hours or 0
        s = issue.status
        if s not in by_assignee[a]['statuses']:
            by_assignee[a]['statuses'][s] = 0
        by_assignee[a]['statuses'][s] += 1

    rows = []
    for assignee, data in by_assignee.items():
        status_str = ', '.join([f"{k}: {v}" for k, v in data['statuses'].items()])
        rows.append({
            'Исполнитель': assignee,
            'Задач': data['count'],
            'Оценка (ч)': f"{data['estimated']:.0f}",
            'Залогировано (ч)': f"{data['spent']:.1f}",
            'Остаток (ч)': f"{data['estimated'] - data['spent']:.1f}",
            'Статусы': status_str
        })

    df = pd.DataFrame(rows).sort_values('Задач', ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        'Исполнитель': st.column_config.TextColumn('Исполнитель', width='medium'),
        'Задач': st.column_config.NumberColumn('Задач', width='small'),
        'Оценка (ч)': st.column_config.TextColumn('Оценка', width='small'),
        'Залогировано (ч)': st.column_config.TextColumn('Залог.', width='small'),
        'Остаток (ч)': st.column_config.TextColumn('Остаток', width='small'),
        'Статусы': st.column_config.TextColumn('Статусы', width='large'),
    })


def render_all_issues_table(sprint_data: SprintData):
    st.markdown("### 📁 Все задачи")
    issues = sprint_data.issues

    fcol1, fcol2, fcol3 = st.columns(3)
    statuses = sorted(set(i.status for i in issues))
    assignees = sorted(set(i.assignee for i in issues))
    types = sorted(set(i.issue_type for i in issues))

    with fcol1:
        status_filter = st.multiselect("Статус", options=statuses, default=statuses)
    with fcol2:
        assignee_filter = st.multiselect("Исполнитель", options=assignees, default=assignees)
    with fcol3:
        type_filter = st.multiselect("Тип", options=types, default=types)

    filtered = [i for i in issues
                if i.status in status_filter and i.assignee in assignee_filter and i.issue_type in type_filter]

    rows = [{
        'Ключ': i.key, 'Тип': i.issue_type, 'Название': i.summary,
        'Статус': i.status, 'Исполнитель': i.assignee,
        'Оценка (ч)': i.estimated_hours or 0, 'Залогировано (ч)': i.spent_hours or 0,
        'Приоритет': i.priority
    } for i in filtered]

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        'Ключ': st.column_config.TextColumn('Ключ', width='small'),
        'Тип': st.column_config.TextColumn('Тип', width='small'),
        'Название': st.column_config.TextColumn('Название', width='large'),
        'Статус': st.column_config.TextColumn('Статус', width='medium'),
        'Исполнитель': st.column_config.TextColumn('Исполнитель', width='medium'),
        'Оценка (ч)': st.column_config.NumberColumn('Оценка', format="%.0f", width='small'),
        'Залогировано (ч)': st.column_config.NumberColumn('Залог.', format="%.1f", width='small'),
        'Приоритет': st.column_config.TextColumn('Приоритет', width='small'),
    })
    st.caption(f"Показано {len(filtered)} из {len(issues)} задач")


def render_summary_table(sprint_data: SprintData):
    st.markdown("### 📋 Сводная таблица")
    summary = {}
    for issue in sprint_data.issues:
        key = (issue.issue_type, issue.status)
        if key not in summary:
            summary[key] = {'count': 0, 'estimated': 0, 'spent': 0}
        summary[key]['count'] += 1
        summary[key]['estimated'] += issue.estimated_hours or 0
        summary[key]['spent'] += issue.spent_hours or 0

    rows = [{
        'Тип': k[0], 'Статус': k[1], 'Задач': v['count'],
        'Оценка (ч)': v['estimated'], 'Залогировано (ч)': v['spent'],
        'Остаток (ч)': v['estimated'] - v['spent']
    } for k, v in summary.items()]

    df = pd.DataFrame(rows).sort_values(['Тип', 'Статус'])
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        'Тип': st.column_config.TextColumn('Тип', width='small'),
        'Статус': st.column_config.TextColumn('Статус', width='medium'),
        'Задач': st.column_config.NumberColumn('Задач', width='small'),
        'Оценка (ч)': st.column_config.NumberColumn('Оценка', format="%.0f", width='small'),
        'Залогировано (ч)': st.column_config.NumberColumn('Залог.', format="%.1f", width='small'),
        'Остаток (ч)': st.column_config.NumberColumn('Остаток', format="%.1f", width='small'),
    })


# ─────────────────────────────────────────────
# Страница создания задач
# ─────────────────────────────────────────────
def render_task_creator():
    st.markdown("## ➕ Создание задач в Jira")

    if not st.session_state.connected or not st.session_state.jira_client:
        st.warning("👈 Сначала подключитесь к Jira через боковую панель")
        return

    st.markdown("Вставьте JSON с задачами и нажмите **Создать задачи**.")

    with st.expander("📖 Формат JSON"):
        st.code('''{
  "jira_config": {
    "project_key": "TEST"
  },
  "tasks": [
    {
      "summary": "Название задачи",
      "description": "Описание задачи",
      "issuetype": "Task",
      "priority": "Medium",
      "labels": ["label1"],
      "assignee": "username",
      "epic_link": "EPIC-1",
      "components": ["Backend"]
    }
  ]
}''', language='json')

    json_input = st.text_area(
        "JSON с задачами",
        height=300,
        placeholder='{"jira_config": {"project_key": "TEST"}, "tasks": [...]}',
        label_visibility="collapsed"
    )

    if st.button("🚀 Создать задачи", type="primary", use_container_width=False):
        if not json_input.strip():
            st.error("Введите JSON")
            return
        try:
            data = json.loads(json_input)
        except json.JSONDecodeError as e:
            st.error(f"Ошибка в JSON: {e}")
            return

        tasks = data.get('tasks', [])
        if not tasks:
            st.error('В JSON нет поля "tasks" или список пуст')
            return
        project_key = data.get('jira_config', {}).get('project_key', '')
        if not project_key:
            st.error('В JSON нет поля "jira_config.project_key"')
            return

        client: JiraClient = st.session_state.jira_client
        creator = JiraTaskCreator(client.base_url, client.api_token, client.email)

        with st.spinner(f"Создание {len(tasks)} задач в проекте {project_key}..."):
            results = creator.create_tasks_from_data(data)

        total = len(results['successful']) + len(results['failed'])
        st.markdown(f"### Результат: {len(results['successful'])}/{total} задач создано")

        if results['successful']:
            st.success(f"✅ Успешно создано: {len(results['successful'])}")
            rows = [{'Ключ': r['key'], 'Название': r['summary'], 'Ссылка': r['url']}
                    for r in results['successful']]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, column_config={
                'Ключ': st.column_config.TextColumn('Ключ', width='small'),
                'Название': st.column_config.TextColumn('Название', width='large'),
                'Ссылка': st.column_config.LinkColumn('Ссылка', width='medium'),
            })

        if results['failed']:
            st.error(f"❌ Ошибки: {len(results['failed'])}")
            for fail in results['failed']:
                st.markdown(f"- **{fail['summary']}**: `{fail['error']}`")


# ─────────────────────────────────────────────
# Страница анализа спринта
# ─────────────────────────────────────────────
def render_analysis_page():
    st.markdown("## 🏃 Анализ спринта")

    if not st.session_state.connected or not st.session_state.jira_client:
        st.info("👈 Подключитесь к Jira через боковую панель")
        with st.expander("📖 Как использовать"):
            st.markdown("""
            1. **Подключитесь к Jira** — убедитесь, что URL и API токен указаны в .env
            2. **Выберите спринт** из списка доступных или введите название
            3. **Нажмите "Загрузить"** для получения задач
            4. **Анализируйте** — используйте вкладки для разных представлений
            """)
        return

    # Выбор спринта — теперь здесь, на основной странице
    render_sprint_selector()

    # Отображаем данные, если загружены
    if st.session_state.sprint_data:
        sprint_data: SprintData = st.session_state.sprint_data

        st.markdown("---")
        render_sprint_header(sprint_data)

        st.markdown("---")
        render_metrics(sprint_data)

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 По статусам",
            "👥 По исполнителям",
            "📋 Сводная",
            "📁 Все задачи"
        ])

        with tab1:
            render_status_breakdown(sprint_data)
        with tab2:
            render_assignee_stats(sprint_data)
        with tab3:
            render_summary_table(sprint_data)
        with tab4:
            render_all_issues_table(sprint_data)
    else:
        st.info("☝️ Выберите спринт и нажмите «Загрузить»")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    init_session_state()
    render_sidebar()

    if st.session_state.page == "analysis":
        render_analysis_page()
    else:
        render_task_creator()


if __name__ == "__main__":
    main()